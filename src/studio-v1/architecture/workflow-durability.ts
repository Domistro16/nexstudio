import type { Prisma, PrismaClient } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { canonicalHash } from "./hash";

const LEASE_MS = Number.parseInt(process.env.STUDIO_WORKER_LEASE_MS || "90000", 10);
const HEARTBEAT_MS = Math.max(5000, Math.min(30000, Math.floor(LEASE_MS / 3)));

type Tx = Prisma.TransactionClient;

export async function appendStudioWorkflowEvent(workflowRunId: string, eventType: string, payload: Record<string, unknown>) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  return prisma.$transaction((tx) => appendStudioWorkflowEventTx(tx, workflowRunId, eventType, payload), { isolationLevel: "Serializable" });
}

export async function appendStudioWorkflowEventTx(tx: Tx, workflowRunId: string, eventType: string, payload: Record<string, unknown>) {
  const idempotencyKey = canonicalHash({ schema: "StudioWorkflowEventV1", workflowRunId, eventType, payload });
  const existing = await tx.studioWorkflowEvent.findUnique({ where: { idempotencyKey } });
  if (existing) return existing;
  // Serialize sequence allocation on the workflow row. This avoids max(sequence)+1 races
  // even when multiple activities finish concurrently.
  await tx.$queryRawUnsafe(`SELECT id FROM studio_workflow_runs WHERE id = $1::uuid FOR UPDATE`, workflowRunId);
  const raced = await tx.studioWorkflowEvent.findUnique({ where: { idempotencyKey } });
  if (raced) return raced;
  const run = await tx.studioWorkflowRun.findUniqueOrThrow({ where: { id: workflowRunId }, select: { stage: true } });
  const max = await tx.studioWorkflowEvent.aggregate({ where: { workflowRunId }, _max: { sequence: true } });
  return tx.studioWorkflowEvent.create({
    data: {
      workflowRunId,
      sequence: (max._max.sequence ?? 0) + 1,
      idempotencyKey,
      eventType,
      fromStage: run.stage,
      toStage: run.stage,
      payload: payload as Prisma.InputJsonValue,
    },
  });
}

export async function ensureStudioWorkflowActivityTx(tx: Tx, data: Prisma.StudioWorkflowActivityUncheckedCreateInput) {
  await tx.$queryRawUnsafe(`SELECT id FROM studio_workflow_runs WHERE id = $1::uuid FOR UPDATE`, String(data.workflowRunId));
  const existing = await tx.studioWorkflowActivity.findUnique({ where: { idempotencyKey: String(data.idempotencyKey) } });
  if (existing) return { activity: existing, created: false as const };
  const activity = await tx.studioWorkflowActivity.create({ data });
  return { activity, created: true as const };
}

export async function ensureStudioWorkflowActivity(data: Prisma.StudioWorkflowActivityUncheckedCreateInput) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  return prisma.$transaction((tx) => ensureStudioWorkflowActivityTx(tx, data), { isolationLevel: "Serializable" });
}

export async function assertStudioActivityLeaseTx(tx: Tx, activityId: string, workerId: string) {
  const activity = await tx.studioWorkflowActivity.findUnique({ where: { id: activityId }, select: { status: true, claimedBy: true } });
  if (!activity || activity.status !== "RUNNING" || activity.claimedBy !== workerId) throw new Error("WORKER_ACTIVITY_LEASE_LOST");
  return true;
}

export async function assertStudioActivityLease(activityId: string, workerId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  const activity = await prisma.studioWorkflowActivity.findUnique({ where: { id: activityId }, select: { status: true, claimedBy: true } });
  if (!activity || activity.status !== "RUNNING" || activity.claimedBy !== workerId) throw new Error("WORKER_ACTIVITY_LEASE_LOST");
  return true;
}

export async function recoverExpiredStudioActivityLeases(prisma: PrismaClient, now = new Date()) {
  const stale = await prisma.studioWorkflowActivity.findMany({
    where: { status: "RUNNING", leaseExpiresAt: { lt: now } },
    orderBy: { leaseExpiresAt: "asc" },
    take: 100,
  });
  let requeued = 0;
  let exhausted = 0;
  for (const row of stale) {
    const localRetry = row.attempts < row.maxAttempts;
    // A lease/restart failure is an infrastructure recovery condition, not a
    // creative/product terminal state. maxAttempts bounds one local retry cycle;
    // exhausting that cycle widens the backoff and resets the local counter.
    const recoveryCycle = Math.max(0, row.recoveryCount ?? 0);
    const delayMs = localRetry ? 0 : Math.min(30 * 60_000, 30_000 * 2 ** Math.min(6, recoveryCycle));
    const changed = await prisma.studioWorkflowActivity.updateMany({
      where: { id: row.id, status: "RUNNING", leaseExpiresAt: { lt: now } },
      data: {
        status: "QUEUED",
        attempts: localRetry ? row.attempts : 0,
        availableAt: new Date(now.getTime() + delayMs),
        claimedBy: null,
        leaseExpiresAt: null,
        recoveryCount: { increment: 1 },
        lastError: row.lastError ?? (localRetry ? "WORKER_LEASE_EXPIRED" : "WORKER_LEASE_RECOVERY_CYCLE"),
      },
    });
    if (!changed.count) continue;
    requeued += 1;
    if (!localRetry) exhausted += 1; // telemetry: local cycle exhausted, production is still alive.
    await prisma.studioWorkflowRun.update({
      where: { id: row.workflowRunId },
      data: { status: "RUNNING", blockedReason: null },
    }).catch(() => undefined);
  }
  return { scanned: stale.length, requeued, exhausted };
}

export async function claimStudioActivity(prisma: PrismaClient, activityId: string, workerId: string, now = new Date()) {
  const leaseExpiresAt = new Date(now.getTime() + LEASE_MS);
  const claimed = await prisma.studioWorkflowActivity.updateMany({
    where: { id: activityId, status: "QUEUED", availableAt: { lte: now } },
    data: {
      status: "RUNNING",
      attempts: { increment: 1 },
      startedAt: now,
      heartbeatAt: now,
      claimedBy: workerId,
      leaseExpiresAt,
      lastError: null,
    },
  });
  return claimed.count === 1;
}

export async function withStudioActivityLease<T>(activityId: string, workerId: string, work: () => Promise<T>): Promise<T> {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  let stopped = false;
  const beat = async () => {
    if (stopped) return;
    const now = new Date();
    const updated = await prisma.studioWorkflowActivity.updateMany({
      where: { id: activityId, status: "RUNNING", claimedBy: workerId },
      data: { heartbeatAt: now, leaseExpiresAt: new Date(now.getTime() + LEASE_MS) },
    });
    if (!updated.count) throw new Error("WORKER_ACTIVITY_LEASE_LOST");
  };
  const interval = setInterval(() => { void beat().catch((error) => console.error("Studio worker heartbeat failed", error)); }, HEARTBEAT_MS);
  try {
    return await work();
  } finally {
    stopped = true;
    clearInterval(interval);
  }
}
