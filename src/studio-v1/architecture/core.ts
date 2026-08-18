import type { Prisma, StudioProductionState } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { assertStudioProductionTransition } from "@/lib/studio-production-draft-core";
import type { ProductionDraft } from "@/domain/studio-production-draft";
import { canonicalHash } from "./hash";

type Tx = Prisma.TransactionClient;

type StateActor = {
  type: "user" | "service" | "worker" | "system";
  id?: string | null;
  reason: string;
  requestId?: string | null;
  metadata?: Record<string, unknown>;
};

async function lockProduction(tx: Tx, productionId: string) {
  await tx.$queryRawUnsafe(`SELECT id FROM productions WHERE id = $1::uuid FOR UPDATE`, productionId);
}

function inputSnapshot(source: ProductionDraft["sources"][number], ordinal: number) {
  return {
    ordinal,
    id: source.id ?? null,
    kind: source.kind,
    label: source.label ?? null,
    reference: source.reference ?? null,
    mimeType: source.mimeType ?? null,
  };
}

export function canonicalDraftInput(draft: Pick<ProductionDraft, "id" | "family" | "videoType" | "prompt" | "sources" | "duration" | "aspectRatio" | "voicePreference" | "brandContext">) {
  return {
    productionId: draft.id,
    family: draft.family,
    videoType: draft.videoType,
    prompt: draft.prompt,
    sources: draft.sources.map(inputSnapshot),
    duration: draft.duration,
    aspectRatio: draft.aspectRatio,
    voicePreference: draft.voicePreference,
    brandContext: draft.brandContext,
  };
}

export async function syncClaimedDraftToCanonicalProduction(draft: ProductionDraft) {
  if (!draft.ownerId) throw new Error("STUDIO_DRAFT_MUST_BE_CLAIMED_BEFORE_PROMOTION");
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  const canonical = canonicalDraftInput(draft);
  const canonicalInputHash = canonicalHash(canonical);

  for (let attempt=0;attempt<5;attempt+=1) {
    try {
      return await prisma.$transaction(async (tx) => {
        const existing = await tx.production.findUnique({ where: { id: draft.id } });
        if (existing && existing.ownerUserId !== draft.ownerId) throw new Error("PRODUCTION_OWNER_CONFLICT");

        const production = existing
          ? await tx.production.update({
              where: { id: draft.id },
              data: {
                mode: `STANDALONE_${draft.family}`,
                title: draft.prompt.trim().slice(0, 120),
                brief: canonical as Prisma.InputJsonValue,
                canonicalInputHash,
              },
            })
          : await tx.production.create({
              data: {
                id: draft.id,
                ownerUserId: draft.ownerId,
                kind: "VIDEO",
                mode: `STANDALONE_${draft.family}`,
                title: draft.prompt.trim().slice(0, 120),
                status: "DRAFT",
                studioState: draft.state,
                stateVersion: 0,
                lastStateChangedAt: new Date(),
                brief: canonical as Prisma.InputJsonValue,
                canonicalInputHash,
                direction: { standaloneStudio: true, family: draft.family, videoType: draft.videoType } as Prisma.InputJsonValue,
              },
            });

        const sourceIds = draft.sources
          .map((source) => source.id)
          .filter((id): id is string => Boolean(id && /^[0-9a-f-]{36}$/i.test(id)));
        const ownedSources = sourceIds.length
          ? await tx.source.findMany({ where: { id: { in: sourceIds }, ownerUserId: draft.ownerId }, select: { id: true } })
          : [];
        const ownedSourceIds = new Set(ownedSources.map((source) => source.id));

        await tx.studioProductionInput.deleteMany({ where: { productionId: draft.id } });
        if (draft.sources.length) {
          await tx.studioProductionInput.createMany({
            data: draft.sources.map((source, ordinal) => {
              const snapshot = inputSnapshot(source, ordinal);
              return {
                productionId: draft.id,
                sourceId: source.id && ownedSourceIds.has(source.id) ? source.id : null,
                ordinal,
                kind: source.kind,
                label: source.label ?? null,
                reference: source.reference ?? null,
                mimeType: source.mimeType ?? null,
                snapshot: snapshot as Prisma.InputJsonValue,
                snapshotHash: canonicalHash(snapshot),
              };
            }),
          });
        }

        const transitionCount=await tx.studioStateTransition.count({where:{productionId:draft.id}});
        if(!transitionCount){
          await tx.studioStateTransition.create({data:{
            productionId:draft.id,
            sequence:1,
            fromState:production.studioState,
            toState:production.studioState,
            actorType:"system",
            actorId:"architecture-core",
            reason:existing?"CANONICAL_STATE_HISTORY_ADOPTED":"CANONICAL_PRODUCTION_CREATED",
            metadata:{canonicalInputHash} as Prisma.InputJsonValue,
          }});
        }
        return production;
      }, { isolationLevel: "Serializable" });
    } catch(error) {
      const code=(error as {code?:string}).code;
      if(!["P2002","P2034"].includes(String(code))||attempt===4)throw error;
    }
  }
  throw new Error("CANONICAL_PRODUCTION_SYNC_RETRY_EXHAUSTED");
}

export async function transitionCanonicalStudioStateTx(
  tx: Tx,
  input: { productionId: string; to: StudioProductionState; actor: StateActor; ownerUserId?: string | null; allowSame?: boolean },
) {
  await lockProduction(tx, input.productionId);
  const production = await tx.production.findUnique({ where: { id: input.productionId } });
  if (!production) throw new Error("PRODUCTION_NOT_FOUND");
  if (input.ownerUserId && production.ownerUserId !== input.ownerUserId) throw new Error("PRODUCTION_NOT_FOUND");

  const from = production.studioState;
  if (from === input.to) {
    if (input.allowSame !== false) return production;
    throw new Error(`INVALID_STUDIO_PRODUCTION_STATE_TRANSITION:${from}->${input.to}`);
  }
  assertStudioProductionTransition(from, input.to);

  const updated = await tx.production.update({
    where: { id: input.productionId },
    data: {
      studioState: input.to,
      stateVersion: { increment: 1 },
      lastStateChangedAt: new Date(),
    },
  });
  await tx.draft.updateMany({
    where: { id: input.productionId, ownerUserId: production.ownerUserId },
    data: { studioState: input.to },
  });
  const last = await tx.studioStateTransition.aggregate({
    where: { productionId: input.productionId },
    _max: { sequence: true },
  });
  await tx.studioStateTransition.create({
    data: {
      productionId: input.productionId,
      sequence: (last._max.sequence ?? 0) + 1,
      fromState: from,
      toState: input.to,
      actorType: input.actor.type,
      actorId: input.actor.id ?? null,
      reason: input.actor.reason,
      requestId: input.actor.requestId ?? null,
      metadata: (input.actor.metadata ?? {}) as Prisma.InputJsonValue,
    },
  });
  return updated;
}

export async function transitionCanonicalStudioState(input: { productionId: string; to: StudioProductionState; actor: StateActor; ownerUserId?: string | null; allowSame?: boolean }) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  return prisma.$transaction((tx) => transitionCanonicalStudioStateTx(tx, input), { isolationLevel: "Serializable" });
}

export async function allocateProjectVersionTx(tx: Tx, productionId: string) {
  await lockProduction(tx, productionId);
  const aggregate = await tx.studioWorkflowRun.aggregate({ where: { productionId }, _max: { projectVersion: true } });
  return (aggregate._max.projectVersion ?? 0) + 1;
}

export async function allocateProductionVersionNumberTx(tx: Tx, productionId: string) {
  await lockProduction(tx, productionId);
  const aggregate = await tx.productionVersion.aggregate({ where: { productionId }, _max: { versionNumber: true } });
  return (aggregate._max.versionNumber ?? 0) + 1;
}
