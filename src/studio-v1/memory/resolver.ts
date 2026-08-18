import type { PrismaClient } from "@/generated/prisma/client";
import type { EffectiveStudioMemory, SeriesPlanSignature, StudioProductionMemoryPacket } from "./contracts";
import { NEXSTICK_V5_1_PERFORMANCE_AUTHORITY } from "./contracts";

function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }

function applicable(version: any, episodeOrdinal: number | null, now: Date) {
  if (new Date(version.effectiveFrom) > now) return false;
  if (version.effectiveUntil && new Date(version.effectiveUntil) <= now) return false;
  if (version.effectiveFromEpisodeOrdinal != null && (episodeOrdinal == null || episodeOrdinal < version.effectiveFromEpisodeOrdinal)) return false;
  if (version.effectiveUntilEpisodeOrdinal != null && episodeOrdinal != null && episodeOrdinal > version.effectiveUntilEpisodeOrdinal) return false;
  return true;
}

function selectEffective(item: any, episodeOrdinal: number | null, now: Date): EffectiveStudioMemory | null {
  const latest = item.versions.find((version: any) => applicable(version, episodeOrdinal, now));
  if (!latest || latest.effectiveState !== "ACTIVE") return null;
  return {
    itemId: item.id, scope: item.scope, scopeRefId: item.scopeRefId, key: item.key, category: item.category,
    versionId: latest.id, versionNumber: latest.versionNumber, effectiveState: latest.effectiveState,
    content: record(latest.content), contentHash: latest.contentHash, provenance: record(latest.provenance),
    effectiveFrom: latest.effectiveFrom.toISOString(), effectiveUntil: latest.effectiveUntil?.toISOString() ?? null,
    effectiveFromEpisodeOrdinal: latest.effectiveFromEpisodeOrdinal, effectiveUntilEpisodeOrdinal: latest.effectiveUntilEpisodeOrdinal,
  };
}

export async function resolveProductionMemoryPacket(prisma: PrismaClient, input: { productionId: string; ownerUserId?: string; projectVersion: number; now?: Date }): Promise<StudioProductionMemoryPacket> {
  const production = await prisma.production.findFirst({
    where: { id: input.productionId, ...(input.ownerUserId ? { ownerUserId: input.ownerUserId } : {}) },
    include: { seriesEpisode: true, studioCastLinks: { include: { castMember: true }, orderBy: { ordinal: "asc" } } },
  });
  if (!production) throw new Error("MEMORY_PRODUCTION_NOT_FOUND");
  const episodeOrdinal = production.seriesEpisode?.episodeOrdinal ?? null;
  const scopePairs = [
    { scope: "ACCOUNT" as const, scopeRefId: production.ownerUserId },
    ...(production.brandId ? [{ scope: "BRAND" as const, scopeRefId: production.brandId }] : []),
    ...(production.seriesId ? [{ scope: "SERIES" as const, scopeRefId: production.seriesId }] : []),
    ...production.studioCastLinks.map((link) => ({ scope: "CAST" as const, scopeRefId: link.castMemberId })),
    { scope: "PRODUCTION" as const, scopeRefId: production.id },
  ];
  const items = await prisma.studioMemoryItem.findMany({
    where: { ownerUserId: production.ownerUserId, OR: scopePairs },
    include: { versions: { orderBy: { versionNumber: "desc" } } },
  });
  const now = input.now ?? new Date();
  const effective = items.map((item) => selectEffective(item, episodeOrdinal, now)).filter(Boolean) as EffectiveStudioMemory[];
  const byScope = (scope: EffectiveStudioMemory["scope"], ref?: string | null) => effective.filter((memory) => memory.scope === scope && (!ref || memory.scopeRefId === ref));

  const previousEpisodeSignatures: SeriesPlanSignature[] = [];
  if (production.seriesId && episodeOrdinal != null) {
    const episodes = await prisma.studioSeriesEpisode.findMany({
      where: { seriesId: production.seriesId, episodeOrdinal: { lt: episodeOrdinal }, production: { studioState: "COMPLETE" } },
      orderBy: { episodeOrdinal: "desc" }, take: 12,
    });
    for (const episode of episodes.reverse()) {
      const snapshot = await prisma.studioMemorySnapshot.findFirst({ where: { productionId: episode.productionId, snapshotType: "FILM_MEMORY" }, orderBy: [{ projectVersion: "desc" }, { sequence: "desc" }] });
      const content = record(snapshot?.content);
      const signature = record(content.planSignature) as SeriesPlanSignature;
      if (Object.keys(signature).length) previousEpisodeSignatures.push({ ...signature, productionId: episode.productionId, episodeOrdinal: episode.episodeOrdinal });
    }
  }

  return {
    schema: "StudioProductionMemoryPacketV1", productionId: production.id, projectVersion: input.projectVersion,
    ownerUserId: production.ownerUserId, episodeOrdinal,
    selected: { brandId: production.brandId, seriesId: production.seriesId, castMemberIds: production.studioCastLinks.map((link) => link.castMemberId) },
    accountMemory: byScope("ACCOUNT", production.ownerUserId),
    brandAuthority: { brandId: production.brandId, memories: byScope("BRAND", production.brandId), enforcement: "BINDING_UNLESS_EXPLICIT_PRODUCTION_EXCEPTION" },
    castAuthority: production.studioCastLinks.map((link) => ({
      castMemberId: link.castMemberId, identityKey: link.castMember.identityKey, name: link.castMember.name,
      memories: byScope("CAST", link.castMemberId), performance: NEXSTICK_V5_1_PERFORMANCE_AUTHORITY,
    })),
    seriesMemory: { seriesId: production.seriesId, memories: byScope("SERIES", production.seriesId), previousEpisodeSignatures, antiRepetitionWindow: 2 },
    productionMemory: byScope("PRODUCTION", production.id),
    precedence: ["ACCOUNT", "BRAND", "SERIES", "CAST", "PRODUCTION"],
    laws: { completedProductionsNeverRetroactivelyChange: true, memorySnapshotIsImmutableProductionInput: true, seriesIsNotProductionFamily: true, castLivesUnderAssetsAndCreativeMemory: true },
  };
}
