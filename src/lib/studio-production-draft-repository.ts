import { Prisma, type Draft as PrismaDraft } from "@/generated/prisma/client";
import { type StudioProductionState, kindForStudioProductionDraft } from "@/domain/studio-production-draft";
import { getPrisma } from "./db";
import type {
  CreateProductionDraftInput,
  DraftActor,
  ProductionDraftRepository,
  StoredProductionDraft,
  UpdateProductionDraftInput,
} from "./studio-production-draft-core";

function jsonObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function jsonArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function mapRow(row: PrismaDraft): StoredProductionDraft {
  if (!row.family || !row.videoType || !row.prompt) throw new Error(`LEGACY_DRAFT_NOT_STUDIO_COMPATIBLE:${row.id}`);
  return {
    id: row.id,
    ownerUserId: row.ownerUserId,
    family: row.family,
    videoType: row.videoType,
    prompt: row.prompt,
    sources: jsonArray(row.sources),
    duration: row.duration,
    aspectRatio: row.aspectRatio,
    voicePreference: row.voicePreference,
    brandContext: jsonObject(row.brandContext),
    studioState: row.studioState,
    resumeState: row.resumeState,
    anonymousSessionId: row.anonymousSessionId,
    anonymousSessionSecretHash: row.anonymousSessionSecretHash,
    anonymousExpiresAt: row.anonymousExpiresAt,
    claimedAt: row.claimedAt,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
  };
}

function actorWhere(actor: DraftActor, now: Date) {
  if (actor.kind === "USER") return { ownerUserId: actor.userId };
  return {
    ownerUserId: null,
    anonymousSessionId: actor.anonymousSessionId,
    anonymousSessionSecretHash: actor.anonymousSessionSecretHash,
    anonymousExpiresAt: { gt: now },
  };
}

export class PrismaProductionDraftRepository implements ProductionDraftRepository {
  private prisma() {
    const prisma = getPrisma();
    if (!prisma) throw new Error("Persistent database is required for Studio drafts.");
    return prisma;
  }

  async findById(id: string) {
    const row = await this.prisma().draft.findUnique({ where: { id } });
    if (!row || !row.family || !row.videoType || !row.prompt) return null;
    return mapRow(row);
  }

  async findLatestForUser(userId: string) {
    const row = await this.prisma().draft.findFirst({
      where: { ownerUserId: userId, family: { not: null }, prompt: { not: null } },
      orderBy: { updatedAt: "desc" },
    });
    return row ? mapRow(row) : null;
  }

  async findLatestForAnonymous(anonymousSessionId: string, anonymousSessionSecretHash: string, now: Date) {
    const row = await this.prisma().draft.findFirst({
      where: {
        ownerUserId: null,
        family: { not: null },
        prompt: { not: null },
        anonymousSessionId,
        anonymousSessionSecretHash,
        anonymousExpiresAt: { gt: now },
      },
      orderBy: { updatedAt: "desc" },
    });
    return row ? mapRow(row) : null;
  }

  async create(input: CreateProductionDraftInput, actor: DraftActor, now: Date) {
    const anonymous = actor.kind === "ANONYMOUS" ? actor : null;
    const row = await this.prisma().draft.create({
      data: {
        id: input.id,
        ownerUserId: actor.kind === "USER" ? actor.userId : null,
        kind: kindForStudioProductionDraft(input.family),
        title: input.prompt.trim().slice(0, 120),
        payload: {},
        family: input.family,
        videoType: input.videoType,
        prompt: input.prompt,
        sources: (input.sources ?? []) as Prisma.InputJsonValue,
        duration: input.duration ?? null,
        aspectRatio: input.aspectRatio ?? null,
        voicePreference: input.voicePreference ?? null,
        brandContext: input.brandContext == null ? Prisma.DbNull : input.brandContext as Prisma.InputJsonValue,
        studioState: "DRAFT",
        anonymousSessionId: anonymous?.anonymousSessionId ?? null,
        anonymousSessionSecretHash: anonymous?.anonymousSessionSecretHash ?? null,
        anonymousExpiresAt: anonymous?.expiresAt ?? null,
        createdAt: now,
        updatedAt: now,
      },
    });
    return mapRow(row);
  }

  async updateContent(id: string, actor: DraftActor, patch: UpdateProductionDraftInput, now: Date) {
    const data: Prisma.DraftUpdateManyMutationInput = { updatedAt: now };
    if (patch.family !== undefined) {
      data.family = patch.family;
      data.kind = kindForStudioProductionDraft(patch.family);
    }
    if (patch.videoType !== undefined) data.videoType = patch.videoType;
    if (patch.prompt !== undefined) {
      data.prompt = patch.prompt;
      data.title = patch.prompt.trim().slice(0, 120);
    }
    if (patch.sources !== undefined) data.sources = patch.sources as Prisma.InputJsonValue;
    if (patch.duration !== undefined) data.duration = patch.duration;
    if (patch.aspectRatio !== undefined) data.aspectRatio = patch.aspectRatio;
    if (patch.voicePreference !== undefined) data.voicePreference = patch.voicePreference;
    if (patch.brandContext !== undefined) {
      data.brandContext = patch.brandContext === null ? Prisma.DbNull : patch.brandContext as Prisma.InputJsonValue;
    }
    const result = await this.prisma().draft.updateMany({ where: { id, ...actorWhere(actor, now) }, data });
    if (!result.count) return null;
    return this.findById(id);
  }

  async updateState(id: string, actor: DraftActor, from: StudioProductionState, to: StudioProductionState, resumeState: StudioProductionState | null, now: Date) {
    const result = await this.prisma().draft.updateMany({
      where: { id, studioState: from, ...actorWhere(actor, now) },
      data: { studioState: to, resumeState, updatedAt: now },
    });
    if (!result.count) return null;
    return this.findById(id);
  }

  async claimAnonymous(id: string, userId: string, anonymousSessionId: string, anonymousSessionSecretHash: string, now: Date) {
    const row = await this.prisma().draft.findUnique({ where: { id } });
    if (!row || row.ownerUserId || !row.family || !row.videoType || !row.prompt) return null;
    if (row.anonymousSessionId !== anonymousSessionId || row.anonymousSessionSecretHash !== anonymousSessionSecretHash) return null;
    if (!row.anonymousExpiresAt || row.anonymousExpiresAt <= now) return null;
    const resumeState = row.studioState === "AUTH_REQUIRED" ? (row.resumeState ?? "DRAFT") : row.studioState;
    const result = await this.prisma().draft.updateMany({
      where: {
        id,
        ownerUserId: null,
        anonymousSessionId,
        anonymousSessionSecretHash,
        anonymousExpiresAt: { gt: now },
      },
      data: {
        ownerUserId: userId,
        studioState: resumeState,
        resumeState: null,
        claimedAt: now,
        anonymousSessionId: null,
        anonymousSessionSecretHash: null,
        anonymousExpiresAt: null,
        updatedAt: now,
      },
    });
    if (!result.count) return null;
    return this.findById(id);
  }
}
