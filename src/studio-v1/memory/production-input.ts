import type { Prisma, PrismaClient } from "@/generated/prisma/client";
import { canonicalHash } from "@/studio-v1/architecture/hash";
import { resolveProductionMemoryPacket } from "./resolver";

type Tx = Prisma.TransactionClient;
function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function list(value: unknown): string[] { return Array.isArray(value) ? value.map(String) : []; }

export async function captureProductionMemoryInputSnapshot(prisma: PrismaClient, input: { productionId: string; projectVersion: number }) {
  const existing = await prisma.studioMemorySnapshot.findUnique({ where: { productionId_projectVersion_snapshotType_sequence: { productionId: input.productionId, projectVersion: input.projectVersion, snapshotType: "MEMORY_INPUT", sequence: 1 } } });
  if (existing) return existing;
  const packet = await resolveProductionMemoryPacket(prisma, input);
  const contentHash = canonicalHash(packet);
  try {
    return await prisma.studioMemorySnapshot.create({ data: { productionId: input.productionId, projectVersion: input.projectVersion, snapshotType: "MEMORY_INPUT", sequence: 1, content: packet as unknown as Prisma.InputJsonValue, contentHash } });
  } catch (error: any) {
    if (error?.code !== "P2002") throw error;
    const replay = await prisma.studioMemorySnapshot.findUnique({ where: { productionId_projectVersion_snapshotType_sequence: { productionId: input.productionId, projectVersion: input.projectVersion, snapshotType: "MEMORY_INPUT", sequence: 1 } } });
    if (!replay || replay.contentHash !== contentHash) throw new Error("MEMORY_INPUT_SNAPSHOT_CONFLICT");
    return replay;
  }
}

export async function captureFilmMemorySnapshotTx(tx: Tx, input: { productionId: string; projectVersion: number; finalBoard: unknown; family: string; authorityId: string; outputSha256: string }) {
  const board = record(input.finalBoard);
  const explicit = record(board.filmMemory);
  const signature = record(board.planSignature);
  const content = {
    schema: "StudioFilmMemoryV1",
    source: "FINAL_LOCKED_PRODUCTION",
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    family: input.family,
    executionAuthorityId: input.authorityId,
    outputSha256: input.outputSha256,
    whatHasBeenShown: explicit.whatHasBeenShown ?? board.whatHasBeenShown ?? [],
    audienceLearned: explicit.audienceLearned ?? board.audienceLearned ?? [],
    persistentObjects: explicit.persistentObjects ?? board.persistentObjects ?? [],
    unresolvedNarrativePromises: explicit.unresolvedNarrativePromises ?? board.unresolvedNarrativePromises ?? [],
    usedVisualMetaphors: explicit.usedVisualMetaphors ?? signature.visualMetaphors ?? [],
    previousCameraGrammar: explicit.previousCameraGrammar ?? signature.cameras ?? [],
    motifEvolution: explicit.motifEvolution ?? signature.motifs ?? [],
    intensityCurve: explicit.intensityCurve ?? board.intensityCurve ?? [],
    settledSceneState: explicit.currentSceneState ?? board.currentSceneState ?? null,
    planSignature: {
      environments: list(signature.environments), silhouettes: list(signature.silhouettes), transitions: list(signature.transitions), cameras: list(signature.cameras),
      actorPositions: list(signature.actorPositions), headlineStructures: list(signature.headlineStructures), cardGrid: signature.cardGrid === true,
      floatingObjects: signature.floatingObjects === true, visualMetaphors: list(signature.visualMetaphors), motifs: list(signature.motifs),
    },
    extractionStatus: Object.keys(explicit).length || Object.keys(signature).length ? "STRUCTURED" : "MINIMAL_FALLBACK",
  };
  const contentHash = canonicalHash(content);
  const existing = await tx.studioMemorySnapshot.findUnique({ where: { productionId_projectVersion_snapshotType_sequence: { productionId: input.productionId, projectVersion: input.projectVersion, snapshotType: "FILM_MEMORY", sequence: 1 } } });
  if (existing) {
    if (existing.contentHash !== contentHash) throw new Error("FILM_MEMORY_SNAPSHOT_CONFLICT");
    return existing;
  }
  return tx.studioMemorySnapshot.create({ data: { productionId: input.productionId, projectVersion: input.projectVersion, snapshotType: "FILM_MEMORY", sequence: 1, content: content as Prisma.InputJsonValue, contentHash } });
}
