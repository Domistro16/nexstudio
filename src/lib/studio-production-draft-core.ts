import type {
  ProductionDraft,
  ProductionDraftSource,
  StudioProductionFamily,
  StudioProductionState,
} from "../domain/studio-production-draft";


const transitionTable: Record<StudioProductionState, readonly StudioProductionState[]> = {
  DRAFT: ["AUTH_REQUIRED", "PLANNING"],
  AUTH_REQUIRED: ["DRAFT", "PLANNING", "PLAN_READY", "PAYMENT_REQUIRED", "PAYMENT_PENDING", "PRODUCTION", "FINAL_REVIEW", "INSUFFICIENT_BALANCE", "PRODUCTION_FAILED", "TECHNICAL_RETRY", "REVISION_REQUESTED"],
  PLANNING: ["AUTH_REQUIRED", "DRAFT", "PLAN_READY", "TECHNICAL_RETRY", "PRODUCTION_FAILED"],
  PLAN_READY: ["AUTH_REQUIRED", "PAYMENT_REQUIRED", "PRODUCTION"],
  PAYMENT_REQUIRED: ["AUTH_REQUIRED", "PAYMENT_PENDING", "INSUFFICIENT_BALANCE"],
  PAYMENT_PENDING: ["AUTH_REQUIRED", "PRODUCTION", "PAYMENT_REQUIRED", "INSUFFICIENT_BALANCE", "TECHNICAL_RETRY"],
  PRODUCTION: ["FINAL_REVIEW", "PRODUCTION_FAILED", "TECHNICAL_RETRY"],
  FINAL_REVIEW: ["COMPLETE", "REVISION_REQUESTED"],
  COMPLETE: [],
  INSUFFICIENT_BALANCE: ["AUTH_REQUIRED", "PAYMENT_REQUIRED", "PAYMENT_PENDING"],
  PRODUCTION_FAILED: ["TECHNICAL_RETRY", "PRODUCTION"],
  TECHNICAL_RETRY: ["PLANNING", "PAYMENT_PENDING", "PRODUCTION", "PRODUCTION_FAILED"],
  REVISION_REQUESTED: ["PRODUCTION", "FINAL_REVIEW"],
};

export function canTransitionStudioProductionState(from: StudioProductionState, to: StudioProductionState) {
  return from === to || transitionTable[from].includes(to);
}

export function assertStudioProductionTransition(from: StudioProductionState, to: StudioProductionState) {
  if (!canTransitionStudioProductionState(from, to)) {
    throw new Error(`INVALID_STUDIO_PRODUCTION_STATE_TRANSITION:${from}->${to}`);
  }
}

export type DraftActor =
  | { kind: "USER"; userId: string }
  | { kind: "ANONYMOUS"; anonymousSessionId: string; anonymousSessionSecretHash: string; expiresAt: Date };

export type StoredProductionDraft = {
  id: string;
  ownerUserId: string | null;
  family: StudioProductionFamily;
  videoType: string;
  prompt: string;
  sources: ProductionDraftSource[];
  duration: number | null;
  aspectRatio: string | null;
  voicePreference: string | null;
  brandContext: Record<string, unknown> | null;
  studioState: StudioProductionState;
  resumeState: StudioProductionState | null;
  anonymousSessionId: string | null;
  anonymousSessionSecretHash: string | null;
  anonymousExpiresAt: Date | null;
  claimedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
};

export type CreateProductionDraftInput = {
  id: string;
  family: StudioProductionFamily;
  videoType: string;
  prompt: string;
  sources?: ProductionDraftSource[];
  duration?: number | null;
  aspectRatio?: string | null;
  voicePreference?: string | null;
  brandContext?: Record<string, unknown> | null;
};

export type UpdateProductionDraftInput = Partial<Omit<CreateProductionDraftInput, "id">> & {
  state?: StudioProductionState;
};

export interface ProductionDraftRepository {
  findById(id: string): Promise<StoredProductionDraft | null>;
  findLatestForUser(userId: string): Promise<StoredProductionDraft | null>;
  findLatestForAnonymous(anonymousSessionId: string, anonymousSessionSecretHash: string, now: Date): Promise<StoredProductionDraft | null>;
  create(input: CreateProductionDraftInput, actor: DraftActor, now: Date): Promise<StoredProductionDraft>;
  updateContent(id: string, actor: DraftActor, patch: UpdateProductionDraftInput, now: Date): Promise<StoredProductionDraft | null>;
  updateState(
    id: string,
    actor: DraftActor,
    from: StudioProductionState,
    to: StudioProductionState,
    resumeState: StudioProductionState | null,
    now: Date,
  ): Promise<StoredProductionDraft | null>;
  claimAnonymous(
    id: string,
    userId: string,
    anonymousSessionId: string,
    anonymousSessionSecretHash: string,
    now: Date,
  ): Promise<StoredProductionDraft | null>;
}

export class ProductionDraftError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ProductionDraftError";
    this.code = code;
  }
}

function actorCanAccess(record: StoredProductionDraft, actor: DraftActor, now: Date) {
  if (actor.kind === "USER") return record.ownerUserId === actor.userId;
  if (record.ownerUserId) return false;
  if (!record.anonymousExpiresAt || record.anonymousExpiresAt <= now) return false;
  return record.anonymousSessionId === actor.anonymousSessionId
    && record.anonymousSessionSecretHash === actor.anonymousSessionSecretHash;
}

function assertUsablePrompt(prompt: string) {
  if (!prompt.trim()) throw new ProductionDraftError("PROMPT_REQUIRED", "The production prompt cannot be blank.");
}

export function publicProductionDraft(record: StoredProductionDraft): ProductionDraft {
  return {
    id: record.id,
    ownerId: record.ownerUserId,
    anonymousSessionId: record.ownerUserId ? null : record.anonymousSessionId,
    family: record.family,
    videoType: record.videoType,
    prompt: record.prompt,
    sources: record.sources,
    duration: record.duration,
    aspectRatio: record.aspectRatio,
    voicePreference: record.voicePreference,
    brandContext: record.brandContext,
    createdAt: record.createdAt.toISOString(),
    updatedAt: record.updatedAt.toISOString(),
    state: record.studioState,
  };
}

export class ProductionDraftService {
  private readonly repository: ProductionDraftRepository;
  private readonly now: () => Date;

  constructor(repository: ProductionDraftRepository, now: () => Date = () => new Date()) {
    this.repository = repository;
    this.now = now;
  }

  async ensure(input: CreateProductionDraftInput, actor: DraftActor) {
    assertUsablePrompt(input.prompt);
    const now = this.now();
    const existing = await this.repository.findById(input.id);
    if (existing) {
      if (!actorCanAccess(existing, actor, now)) {
        throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
      }
      return publicProductionDraft(existing);
    }
    try {
      return publicProductionDraft(await this.repository.create(input, actor, now));
    } catch (error) {
      // Concurrent/retried create: the primary key is the idempotency boundary.
      const raced = await this.repository.findById(input.id);
      if (raced && actorCanAccess(raced, actor, now)) return publicProductionDraft(raced);
      throw error;
    }
  }

  async get(id: string, actor: DraftActor) {
    const record = await this.repository.findById(id);
    if (!record || !actorCanAccess(record, actor, this.now())) {
      throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
    }
    return publicProductionDraft(record);
  }

  async resume(actor: DraftActor, id?: string | null) {
    const now = this.now();
    let record: StoredProductionDraft | null;
    if (id) record = await this.repository.findById(id);
    else if (actor.kind === "USER") record = await this.repository.findLatestForUser(actor.userId);
    else record = await this.repository.findLatestForAnonymous(actor.anonymousSessionId, actor.anonymousSessionSecretHash, now);
    if (!record || !actorCanAccess(record, actor, now)) {
      throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
    }
    return publicProductionDraft(record);
  }

  async update(id: string, actor: DraftActor, patch: UpdateProductionDraftInput) {
    const now = this.now();
    const current = await this.repository.findById(id);
    if (!current || !actorCanAccess(current, actor, now)) {
      throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
    }
    if (patch.prompt !== undefined) assertUsablePrompt(patch.prompt);

    let updated = current;
    const contentPatch = { ...patch };
    delete contentPatch.state;
    if (Object.keys(contentPatch).length) {
      const content = await this.repository.updateContent(id, actor, contentPatch, now);
      if (!content) throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
      updated = content;
    }

    if (patch.state && patch.state !== updated.studioState) {
      assertStudioProductionTransition(updated.studioState, patch.state);
      const resumeState = patch.state === "AUTH_REQUIRED"
        ? (updated.studioState === "AUTH_REQUIRED" ? updated.resumeState : updated.studioState)
        : updated.resumeState;
      const state = await this.repository.updateState(id, actor, updated.studioState, patch.state, resumeState, now);
      if (!state) throw new ProductionDraftError("STALE_DRAFT_STATE", "The draft changed in another request. Resume and retry.");
      updated = state;
    }
    return publicProductionDraft(updated);
  }

  async beginAuthHandoff(id: string, actor: DraftActor) {
    return this.update(id, actor, { state: "AUTH_REQUIRED" });
  }

  async cancelAuthHandoff(id: string, actor: DraftActor) {
    const now = this.now();
    const current = await this.repository.findById(id);
    if (!current || !actorCanAccess(current, actor, now)) {
      throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
    }
    if (current.studioState !== "AUTH_REQUIRED") return publicProductionDraft(current);
    const target = current.resumeState ?? "DRAFT";
    assertStudioProductionTransition("AUTH_REQUIRED", target);
    const restored = await this.repository.updateState(id, actor, "AUTH_REQUIRED", target, null, now);
    if (!restored) throw new ProductionDraftError("STALE_DRAFT_STATE", "The draft changed in another request. Resume and retry.");
    return publicProductionDraft(restored);
  }

  async claim(
    id: string,
    userId: string,
    anonymousActor: Extract<DraftActor, { kind: "ANONYMOUS" }> | null,
  ) {
    const now = this.now();
    const before = await this.repository.findById(id);
    if (!before) throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");

    // Idempotent retry after a successful claim by this same account. This is
    // deliberately checked before requiring the guest cookie, so a lost first
    // claim response cannot force a duplicate or strand the authenticated user.
    if (before.ownerUserId === userId) return publicProductionDraft(before);

    if (!anonymousActor || !actorCanAccess(before, anonymousActor, now)) {
      throw new ProductionDraftError("DRAFT_NOT_FOUND", "The draft is unavailable.");
    }

    const claimed = await this.repository.claimAnonymous(
      id,
      userId,
      anonymousActor.anonymousSessionId,
      anonymousActor.anonymousSessionSecretHash,
      now,
    );
    if (claimed) return publicProductionDraft(claimed);

    // A concurrent identical claim may have won between read and update.
    const raced = await this.repository.findById(id);
    if (raced?.ownerUserId === userId) return publicProductionDraft(raced);
    throw new ProductionDraftError("DRAFT_CLAIM_CONFLICT", "The draft could not be attached to this account.");
  }
}
