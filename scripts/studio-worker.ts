import "dotenv/config";
import { randomUUID } from "node:crypto";
import { getPrisma } from "../src/lib/db";
import { runStandaloneNexMindP8Activity, runFinalizeStandaloneNexMindP8Activity } from "../src/studio-v1/nexmind-p8/workflow";
import { runStandaloneFamilyReviewEvidenceActivity, runReviewedFinalOutputPromotionActivity } from "../src/studio-v1/production-engines/workflow";
import { claimStudioActivity, recoverExpiredStudioActivityLeases, withStudioActivityLease } from "../src/studio-v1/architecture/workflow-durability";
import { transitionCanonicalStudioState } from "../src/studio-v1/architecture/core";

const watch = process.argv.includes("--watch");
const workerId = `studio-worker-${process.pid}-${randomUUID()}`;
const handlers: Record<string, (a: { id: string; workflowRunId: string; workerId: string }) => Promise<unknown>> = {
  RUN_STANDALONE_NEXMIND_P8: runStandaloneNexMindP8Activity,
  FINALIZE_STANDALONE_NEXMIND_P8: runFinalizeStandaloneNexMindP8Activity,
  BUILD_STANDALONE_FAMILY_REVIEW_EVIDENCE: runStandaloneFamilyReviewEvidenceActivity,
  PROMOTE_REVIEWED_FINAL_OUTPUT: runReviewedFinalOutputPromotionActivity,
};

function retryDelayMs(attempts: number) {
  return Math.min(5 * 60_000, 5_000 * 2 ** Math.max(0, attempts - 1));
}

async function once() {
  const prisma = getPrisma();
  if (!prisma) throw new Error("DATABASE_URL is required.");
  const now = new Date();
  await recoverExpiredStudioActivityLeases(prisma, now);
  const candidates = await prisma.studioWorkflowActivity.findMany({
    where: { status: "QUEUED", availableAt: { lte: now }, activityType: { in: Object.keys(handlers) } },
    orderBy: { createdAt: "asc" },
    take: 8,
  });

  for (const row of candidates) {
    if (!(await claimStudioActivity(prisma, row.id, workerId, new Date()))) continue;
    const handler = handlers[row.activityType];
    try {
      await withStudioActivityLease(row.id, workerId, () => handler({ id: row.id, workflowRunId: row.workflowRunId, workerId }));
    } catch (error) {
      const current = await prisma.studioWorkflowActivity.findUnique({ where: { id: row.id } });
      if (current?.status === "COMPLETED") continue;
      const message = error instanceof Error ? error.message : String(error);
      const localRetry = (current?.attempts ?? 1) < (current?.maxAttempts ?? 1);
      const recoveryCycle = Math.max(0, current?.recoveryCount ?? 0);
      const delay = localRetry ? retryDelayMs(current?.attempts ?? 1) : Math.min(30 * 60_000, 30_000 * 2 ** Math.min(6, recoveryCycle));
      // Local maxAttempts is not permission to kill a paid production. It bounds
      // one technical retry cycle; after that we back off, reset the local
      // counter, preserve the same production, and keep recovery durable.
      await prisma.studioWorkflowActivity.update({
        where: { id: row.id },
        data: {
          status: "QUEUED",
          attempts: localRetry ? current?.attempts : 0,
          recoveryCount: { increment: localRetry ? 0 : 1 },
          lastError: message.slice(0, 2000),
          availableAt: new Date(Date.now() + delay),
          completedAt: null,
          claimedBy: null,
          leaseExpiresAt: null,
        },
      });
      await prisma.studioWorkflowRun.update({
        where: { id: row.workflowRunId },
        data: { status: "RUNNING", blockedReason: null },
      }).catch(() => undefined);
      const run = await prisma.studioWorkflowRun.findUnique({ where: { id: row.workflowRunId }, include: { production: true } }).catch(() => null);
      if (run?.production) {
        await transitionCanonicalStudioState({ productionId: run.productionId, ownerUserId: run.production.ownerUserId, to: "TECHNICAL_RETRY", actor: { type: "worker", id: workerId, reason: localRetry ? "WORKER_TECHNICAL_RETRY" : "WORKER_TECHNICAL_RECOVERY_CYCLE", metadata: { activityId: row.id, activityType: row.activityType, recoveryCycle } } }).catch(() => undefined);
      }
      console.error(JSON.stringify({ activityId: row.id, type: row.activityType, retry: true, localRetry, recoveryCycle, error: message }));
    }
  }
}

do {
  await once();
  if (watch) await new Promise((resolve) => setTimeout(resolve, 3000));
} while (watch);
