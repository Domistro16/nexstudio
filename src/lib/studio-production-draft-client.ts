import type {
  ProductionDraft,
  ProductionDraftSource,
  StudioProductionFamily,
  StudioProductionState,
} from "../domain/studio-production-draft";

const ACTIVE_DRAFT_KEY = "studio.productionDraft.active.v1";
const DRAFT_KEY_PREFIX = "studio.productionDraft.v1:";

export type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export type LocalProductionDraftSnapshot = {
  id: string;
  family: StudioProductionFamily;
  videoType: string;
  prompt: string;
  sources: ProductionDraftSource[];
  duration: number | null;
  aspectRatio: string | null;
  voicePreference: string | null;
  brandContext: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
  state: StudioProductionState;
  dirty: boolean;
};

export type StudioProductionDraftClientEnvironment = {
  storage: StorageLike;
  fetch: typeof fetch;
  randomUUID: () => string;
  now: () => string;
};

export type BeginStudioProductionDraftInput = {
  family: StudioProductionFamily;
  videoType: string;
  prompt: string;
  sources?: ProductionDraftSource[];
  duration?: number | null;
  aspectRatio?: string | null;
  voicePreference?: string | null;
  brandContext?: Record<string, unknown> | null;
};

type ApiEnvelope = { data?: ProductionDraft };

function draftKey(id: string) {
  return `${DRAFT_KEY_PREFIX}${id}`;
}

function redactRecord(value: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!value) return null;
  const sensitive = /(authorization|password|passwd|secret|token|cookie|api[-_]?key|credential|private[-_]?key)/i;
  const walk = (input: unknown): unknown => {
    if (Array.isArray(input)) return input.map(walk);
    if (!input || typeof input !== "object") return input;
    return Object.fromEntries(Object.entries(input as Record<string, unknown>).flatMap(([key, item]) => sensitive.test(key) ? [] : [[key, walk(item)]]));
  };
  return walk(value) as Record<string, unknown>;
}

function safeUrlReference(reference: string | null | undefined) {
  if (!reference) return reference ?? null;
  try {
    const url = new URL(reference);
    url.username = "";
    url.password = "";
    for (const key of [...url.searchParams.keys()]) {
      if (/(authorization|password|secret|token|cookie|api[-_]?key|credential|signature|sig)/i.test(key)) url.searchParams.delete(key);
    }
    return url.toString();
  } catch {
    return reference.startsWith("blob:") || reference.startsWith("data:") ? null : reference;
  }
}

function safeSources(sources: ProductionDraftSource[]) {
  return sources.map((source) => ({
    id: source.id,
    kind: source.kind,
    label: source.label ?? null,
    reference: source.kind === "URL" ? safeUrlReference(source.reference) : source.kind === "UPLOAD" && source.reference?.startsWith("blob:") ? null : source.reference ?? null,
    mimeType: source.mimeType ?? null,
  }));
}

export function toLocalProductionDraftSnapshot(draft: ProductionDraft): LocalProductionDraftSnapshot {
  return {
    id: draft.id,
    family: draft.family,
    videoType: draft.videoType,
    prompt: draft.prompt,
    sources: safeSources(draft.sources),
    duration: draft.duration,
    aspectRatio: draft.aspectRatio,
    voicePreference: draft.voicePreference,
    brandContext: redactRecord(draft.brandContext),
    createdAt: draft.createdAt,
    updatedAt: draft.updatedAt,
    state: draft.state,
    dirty: false,
  };
}

function localAsDraft(local: LocalProductionDraftSnapshot): ProductionDraft {
  const { dirty: _dirty, ...draft } = local;
  return { ...draft, ownerId: null, anonymousSessionId: null };
}

function contentFromLocal(local: LocalProductionDraftSnapshot) {
  return {
    family: local.family,
    videoType: local.videoType,
    prompt: local.prompt,
    sources: local.sources,
    duration: local.duration,
    aspectRatio: local.aspectRatio,
    voicePreference: local.voicePreference,
    brandContext: local.brandContext,
  };
}

function writeLocal(storage: StorageLike, draft: ProductionDraft | LocalProductionDraftSnapshot) {
  const local = "ownerId" in draft ? toLocalProductionDraftSnapshot(draft) : draft;
  storage.setItem(draftKey(local.id), JSON.stringify(local));
  storage.setItem(ACTIVE_DRAFT_KEY, local.id);
  return local;
}

function readLocal(storage: StorageLike, id: string) {
  const raw = storage.getItem(draftKey(id));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LocalProductionDraftSnapshot;
  } catch {
    return null;
  }
}

async function readResponse(response: Response) {
  const body = await response.json().catch(() => ({})) as ApiEnvelope;
  return body.data ?? null;
}

function defaultEnvironment(): StudioProductionDraftClientEnvironment {
  if (typeof window === "undefined") throw new Error("Studio production draft client requires a browser environment or injected test environment.");
  return {
    storage: window.localStorage,
    fetch: window.fetch.bind(window),
    randomUUID: () => window.crypto.randomUUID(),
    now: () => new Date().toISOString(),
  };
}

export function createStudioProductionDraftClient(environment?: StudioProductionDraftClientEnvironment) {
  const env = environment ?? defaultEnvironment();

  async function begin(input: BeginStudioProductionDraftInput) {
    const id = env.randomUUID();
    const now = env.now();
    const local: LocalProductionDraftSnapshot = {
      id,
      family: input.family,
      videoType: input.videoType,
      prompt: input.prompt,
      sources: safeSources(input.sources ?? []),
      duration: input.duration ?? null,
      aspectRatio: input.aspectRatio ?? null,
      voicePreference: input.voicePreference ?? null,
      brandContext: redactRecord(input.brandContext ?? null),
      createdAt: now,
      updatedAt: now,
      state: "DRAFT",
      dirty: true,
    };

    // Product invariant: local persistence happens BEFORE the first network hop.
    writeLocal(env.storage, local);

    try {
      const response = await env.fetch("/api/v1/studio/production-drafts", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-create:${id}` },
        body: JSON.stringify({ ...input, id }),
      });
      const server = response.ok ? await readResponse(response) : null;
      if (server) {
        writeLocal(env.storage, server);
        return { draft: server, sync: "SERVER" as const };
      }
    } catch {
      // Local-first resilience is the intended fallback, not an error reset.
    }
    return { draft: localAsDraft(local), sync: "LOCAL_ONLY" as const };
  }

  async function update(id: string, patch: Partial<BeginStudioProductionDraftInput>) {
    const current = readLocal(env.storage, id);
    if (!current) throw new Error(`LOCAL_STUDIO_DRAFT_NOT_FOUND:${id}`);
    const next: LocalProductionDraftSnapshot = {
      ...current,
      ...patch,
      sources: patch.sources ? safeSources(patch.sources) : current.sources,
      brandContext: patch.brandContext !== undefined ? redactRecord(patch.brandContext) : current.brandContext,
      updatedAt: env.now(),
      dirty: true,
    };

    // Save changes before network sync so refresh/back/navigation cannot erase intent.
    writeLocal(env.storage, next);
    try {
      const response = await env.fetch(`/api/v1/studio/production-drafts/${id}`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-update:${id}:${next.updatedAt}` },
        body: JSON.stringify(patch),
      });
      const server = response.ok ? await readResponse(response) : null;
      if (server) {
        writeLocal(env.storage, server);
        return { draft: server, sync: "SERVER" as const };
      }
    } catch {
      // Keep the local copy and retry/resume later.
    }
    return { draft: localAsDraft(next), sync: "LOCAL_ONLY" as const };
  }

  async function beginAuthHandoff(id: string) {
    const current = readLocal(env.storage, id);
    if (!current) throw new Error(`LOCAL_STUDIO_DRAFT_NOT_FOUND:${id}`);
    const local: LocalProductionDraftSnapshot = { ...current, state: "AUTH_REQUIRED", updatedAt: env.now(), dirty: true };
    writeLocal(env.storage, local);
    try {
      const response = await env.fetch(`/api/v1/studio/production-drafts/${id}/auth-handoff`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-auth-handoff:${id}` },
        body: "{}",
      });
      const server = response.ok ? await readResponse(response) : null;
      if (server) {
        writeLocal(env.storage, server);
        return { draft: server, sync: "SERVER" as const, draftId: id };
      }
    } catch {
      // Local AUTH_REQUIRED marker preserves the overlay handoff through navigation.
    }
    return { draft: localAsDraft(local), sync: "LOCAL_ONLY" as const, draftId: id };
  }

  async function cancelAuthHandoff(id: string) {
    const response = await env.fetch(`/api/v1/studio/production-drafts/${id}/auth-handoff`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "Idempotency-Key": `studio-draft-auth-handoff-cancel:${id}` },
    });
    if (!response.ok) throw new Error(`STUDIO_DRAFT_AUTH_CANCEL_FAILED:${response.status}`);
    const server = await readResponse(response);
    if (!server) throw new Error("STUDIO_DRAFT_AUTH_CANCEL_EMPTY");
    writeLocal(env.storage, server);
    return server;
  }

  async function claimAfterAuth(id: string) {
    const local = readLocal(env.storage, id);
    let response = await env.fetch(`/api/v1/studio/production-drafts/${id}/claim`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-claim:${id}` },
      body: "{}",
    });

    // If the guest's initial server create never completed, authentication can
    // create the missing server envelope using the exact same client UUID.
    if (response.status === 404 && local) {
      response = await env.fetch("/api/v1/studio/production-drafts", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-auth-create:${id}` },
        body: JSON.stringify({ id, ...contentFromLocal(local) }),
      });
    }

    if (!response.ok) throw new Error(`STUDIO_DRAFT_CLAIM_FAILED:${response.status}`);
    let server = await readResponse(response);
    if (!server || server.id !== id) throw new Error("STUDIO_DRAFT_CLAIM_ID_CHANGED");

    // Never let a successful auth response overwrite newer local intent. If an
    // update was unsynced before auth, attach first, then replay only content
    // fields onto the now-authenticated SAME draft. State remains server-owned.
    if (local?.dirty) {
      try {
        const sync = await env.fetch(`/api/v1/studio/production-drafts/${id}`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-auth-resync:${id}:${local.updatedAt}` },
          body: JSON.stringify(contentFromLocal(local)),
        });
        const synced = sync.ok ? await readResponse(sync) : null;
        if (synced) server = synced;
        else {
          const merged: ProductionDraft = { ...server, ...contentFromLocal(local) };
          writeLocal(env.storage, { ...toLocalProductionDraftSnapshot(merged), dirty: true });
          return { draft: merged, sync: "LOCAL_ONLY" as const };
        }
      } catch {
        const merged: ProductionDraft = { ...server, ...contentFromLocal(local) };
        writeLocal(env.storage, { ...toLocalProductionDraftSnapshot(merged), dirty: true });
        return { draft: merged, sync: "LOCAL_ONLY" as const };
      }
    }

    writeLocal(env.storage, server);
    return { draft: server, sync: "SERVER" as const };
  }

  async function resume(id?: string | null) {
    const draftId = id ?? env.storage.getItem(ACTIVE_DRAFT_KEY);
    if (!draftId) return null;
    const local = readLocal(env.storage, draftId);
    try {
      const response = await env.fetch(`/api/v1/studio/production-drafts/resume?draftId=${encodeURIComponent(draftId)}`, {
        credentials: "same-origin",
      });
      let server = response.ok ? await readResponse(response) : null;
      if (server) {
        if (local?.dirty) {
          try {
            const sync = await env.fetch(`/api/v1/studio/production-drafts/${draftId}`, {
              method: "PATCH",
              credentials: "same-origin",
              headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-resume-resync:${draftId}:${local.updatedAt}` },
              body: JSON.stringify(contentFromLocal(local)),
            });
            const synced = sync.ok ? await readResponse(sync) : null;
            if (synced) server = synced;
            else {
              const merged: ProductionDraft = { ...server, ...contentFromLocal(local) };
              writeLocal(env.storage, { ...toLocalProductionDraftSnapshot(merged), dirty: true });
              return { draft: merged, sync: "LOCAL_ONLY" as const };
            }
          } catch {
            const merged: ProductionDraft = { ...server, ...contentFromLocal(local) };
            writeLocal(env.storage, { ...toLocalProductionDraftSnapshot(merged), dirty: true });
            return { draft: merged, sync: "LOCAL_ONLY" as const };
          }
        }
        writeLocal(env.storage, server);
        return { draft: server, sync: "SERVER" as const };
      }
    } catch {
      // Reopen/refresh may be offline; local state remains usable.
    }
    return local ? { draft: localAsDraft(local), sync: "LOCAL_ONLY" as const } : null;
  }


  async function recoverExpiredLocalAsNewDraft(expiredId: string) {
    const local = readLocal(env.storage, expiredId);
    if (!local) throw new Error(`LOCAL_STUDIO_DRAFT_NOT_FOUND:${expiredId}`);
    const newId = env.randomUUID();
    if (newId === expiredId) throw new Error("STUDIO_DRAFT_RECOVERY_REQUIRES_NEW_ID");
    const now = env.now();
    const replacement: LocalProductionDraftSnapshot = {
      ...local,
      id: newId,
      state: "DRAFT",
      createdAt: now,
      updatedAt: now,
      dirty: true,
    };
    writeLocal(env.storage, replacement);
    try {
      const response = await env.fetch("/api/v1/studio/production-drafts", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-draft-recover:${newId}` },
        body: JSON.stringify({ id: newId, ...contentFromLocal(replacement) }),
      });
      const server = response.ok ? await readResponse(response) : null;
      if (server) {
        writeLocal(env.storage, server);
        return { previousId: expiredId, draft: server, sync: "SERVER" as const };
      }
    } catch {
      // Preserve the replacement locally; the user can retry when connectivity returns.
    }
    return { previousId: expiredId, draft: localAsDraft(replacement), sync: "LOCAL_ONLY" as const };
  }

  function getActiveDraftId() {
    return env.storage.getItem(ACTIVE_DRAFT_KEY);
  }

  function clearLocalDraft(id: string) {
    env.storage.removeItem(draftKey(id));
    if (env.storage.getItem(ACTIVE_DRAFT_KEY) === id) env.storage.removeItem(ACTIVE_DRAFT_KEY);
  }

  return { begin, update, beginAuthHandoff, cancelAuthHandoff, claimAfterAuth, resume, recoverExpiredLocalAsNewDraft, getActiveDraftId, clearLocalDraft };
}
