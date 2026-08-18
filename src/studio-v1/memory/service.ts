import type { Prisma, PrismaClient } from "@/generated/prisma/client";
import { canonicalHash } from "@/studio-v1/architecture/hash";
import type { StudioMemoryProvenance, StudioMemoryScopeName } from "./contracts";

type Tx = Prisma.TransactionClient;
type Db = PrismaClient | Tx;

async function assertScopeOwnership(db: Db, ownerUserId: string, scope: StudioMemoryScopeName, scopeRefId: string) {
  if (scope === "ACCOUNT") {
    if (scopeRefId !== ownerUserId) throw new Error("MEMORY_ACCOUNT_SCOPE_MISMATCH");
    return;
  }
  const record = scope === "BRAND"
    ? await db.studioBrand.findFirst({ where: { id: scopeRefId, ownerUserId }, select: { id: true } })
    : scope === "CAST"
      ? await db.studioCastMember.findFirst({ where: { id: scopeRefId, ownerUserId }, select: { id: true } })
      : scope === "SERIES"
        ? await db.studioSeries.findFirst({ where: { id: scopeRefId, ownerUserId }, select: { id: true } })
        : await db.production.findFirst({ where: { id: scopeRefId, ownerUserId }, select: { id: true } });
  if (!record) throw new Error(`MEMORY_SCOPE_NOT_OWNED:${scope}`);
}

export async function appendStudioMemoryVersion(input: {
  prisma: PrismaClient;
  ownerUserId: string;
  scope: StudioMemoryScopeName;
  scopeRefId: string;
  key: string;
  category: string;
  label?: string | null;
  effectiveState?: "ACTIVE" | "INACTIVE" | "DELETED";
  effectiveFrom?: Date;
  effectiveUntil?: Date | null;
  effectiveFromEpisodeOrdinal?: number | null;
  effectiveUntilEpisodeOrdinal?: number | null;
  content: Record<string, unknown>;
  provenance: StudioMemoryProvenance | Record<string, unknown>;
  sourceProductionId?: string | null;
  sourceProductionVersionId?: string | null;
  createdByType: string;
  createdById?: string | null;
  reason?: string | null;
}) {
  const key = input.key.trim();
  if (!key) throw new Error("MEMORY_KEY_REQUIRED");
  const contentHash = canonicalHash(input.content);
  return input.prisma.$transaction(async (tx) => {
    await assertScopeOwnership(tx, input.ownerUserId, input.scope, input.scopeRefId);
    const item = await tx.studioMemoryItem.upsert({
      where: { ownerUserId_scope_scopeRefId_key: { ownerUserId: input.ownerUserId, scope: input.scope, scopeRefId: input.scopeRefId, key } },
      create: { ownerUserId: input.ownerUserId, scope: input.scope, scopeRefId: input.scopeRefId, key, category: input.category, label: input.label ?? null },
      update: { category: input.category, label: input.label ?? undefined },
    });
    await tx.$queryRaw`SELECT id FROM studio_memory_items WHERE id = ${item.id}::uuid FOR UPDATE`;
    const locked = await tx.studioMemoryItem.findUniqueOrThrow({ where: { id: item.id } });
    const versionNumber = locked.currentVersion + 1;
    const version = await tx.studioMemoryVersion.create({ data: {
      memoryItemId: item.id,
      versionNumber,
      effectiveState: input.effectiveState ?? "ACTIVE",
      effectiveFrom: input.effectiveFrom ?? new Date(),
      effectiveUntil: input.effectiveUntil ?? null,
      effectiveFromEpisodeOrdinal: input.effectiveFromEpisodeOrdinal ?? null,
      effectiveUntilEpisodeOrdinal: input.effectiveUntilEpisodeOrdinal ?? null,
      content: input.content as Prisma.InputJsonValue,
      contentHash,
      provenance: input.provenance as Prisma.InputJsonValue,
      sourceProductionId: input.sourceProductionId ?? null,
      sourceProductionVersionId: input.sourceProductionVersionId ?? null,
      createdByType: input.createdByType,
      createdById: input.createdById ?? null,
      reason: input.reason ?? null,
    }});
    await tx.studioMemoryItem.update({ where: { id: item.id }, data: { currentVersion: versionNumber } });
    return { item, version };
  }, { isolationLevel: "Serializable" });
}

export async function tombstoneStudioMemory(input: { prisma: PrismaClient; ownerUserId: string; memoryItemId: string; createdById?: string | null; reason?: string | null }) {
  const item = await input.prisma.studioMemoryItem.findFirst({ where: { id: input.memoryItemId, ownerUserId: input.ownerUserId } });
  if (!item) throw new Error("MEMORY_NOT_FOUND");
  return appendStudioMemoryVersion({
    prisma: input.prisma, ownerUserId: input.ownerUserId, scope: item.scope, scopeRefId: item.scopeRefId,
    key: item.key, category: item.category, label: item.label, effectiveState: "DELETED", content: {},
    provenance: { source: "CUSTOMER", recordedAt: new Date().toISOString(), customerConfirmed: true, note: "Customer deleted remembered information for future use." },
    createdByType: "customer", createdById: input.createdById ?? input.ownerUserId, reason: input.reason ?? "CUSTOMER_DELETE",
  });
}

export async function inspectStudioMemory(prisma: PrismaClient, ownerUserId: string, scope?: StudioMemoryScopeName, scopeRefId?: string) {
  return prisma.studioMemoryItem.findMany({
    where: { ownerUserId, ...(scope ? { scope } : {}), ...(scopeRefId ? { scopeRefId } : {}) },
    include: { versions: { orderBy: { versionNumber: "desc" } } }, orderBy: [{ scope: "asc" }, { updatedAt: "desc" }],
  });
}
