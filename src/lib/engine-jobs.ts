import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { getPrisma } from "@/lib/db";
import { appendStudioMemoryVersion } from "@/studio-v1/memory/service";

import { engineJobsDir, type EngineKind } from "./engine-paths";
export { engineJobsDir, type EngineKind } from "./engine-paths";
export const ENGINE_KINDS: EngineKind[] = ["whiteboard", "explainer", "presenter"];

export function friendlyEngineError(dir: string): string | undefined {
  try {
    const statusRaw = existsSync(path.join(dir, "status.json"))
      ? JSON.parse(readFileSync(path.join(dir, "status.json"), "utf8"))
      : {};
    const direct = typeof statusRaw.error === "string" && statusRaw.error
      ? statusRaw.error
      : (typeof statusRaw.failureCode === "string" && statusRaw.failureCode ? statusRaw.failureCode : undefined);
    if (statusRaw.status === "failed" && (!direct || /^engine exited \d+ with no outputs$/.test(direct) || direct === "ENGINE_EXIT_NONZERO")) {
      const logPath = path.join(dir, "job.log");
      const log = existsSync(logPath) ? readFileSync(logPath, "utf8").split("--- P8 dispatch").at(-1) ?? "" : "";
      if (log.includes("WHITEBOARD_V3_EXECUTION_BODY_MISSING"))
        return "The whiteboard renderer isn't installed on this server. Your narration is saved; retry after the renderer is restored.";
      if (log.includes("WHITEBOARD_LANGUAGE_DATA_MISSING"))
        return "The whiteboard planner's language data isn't installed on this server. Your narration is saved; retry after it is restored.";
      if (log.includes("mkl_malloc: failed to allocate memory") || log.includes("The paging file is too small"))
        return "The render server ran out of memory. Try again after freeing some memory.";
      if (log.includes("NARRATION_PROVIDER_UNAVAILABLE") || (log.includes("edge_tts") && log.includes("WSServerHandshakeError: 403")))
        return "The narration service couldn't generate your selected voice. Try again shortly or choose another voice.";
      if (log.includes("NARRATION_ALIGNMENT_FAILED"))
        return "The narration audio couldn't be prepared for rendering. Try again shortly.";
    }
    if (direct) return /^(16x9|1x1|9x16):/.test(direct) ? gateFailureMessage(direct) : direct;
    if (statusRaw.status !== "failed") return undefined;
    const outDir = path.join(dir, "out");
    if (!existsSync(outDir)) return undefined;
    for (const entry of readdirSync(outDir)) {
      const reportPath = path.join(outDir, entry, "gate_report.json");
      if (!existsSync(reportPath)) continue;
      const report = JSON.parse(readFileSync(reportPath, "utf8")) as { failures?: string[] };
      const first = report.failures?.[0];
      if (first) return gateFailureMessage(first);
    }
  } catch { /* fall through */ }
  return undefined;
}

export function gateFailureMessage(failure: string): string {
  const code = failure.split(":").find((part) => /^[A-Z][A-Z0-9_]+$/.test(part)) ?? failure;
  if (/LEGIBLE_HOLD|SETTLED_HOLD|CASCADE_OVERRUNS/i.test(code))
    return "Some lines couldn't stay on screen long enough to read — try a shorter script or a longer duration.";
  if (/ILLUSTRATION_TOO_FEW_ENTITIES/i.test(code))
    return "This style couldn't find enough visual elements for the script — try more concrete subjects or a different style.";
  if (/ILLUSTRATION_COLLIDES_TEXT|TEXT_COLLISION|TEXT_OUTSIDE_SAFE|TYPE_FLOOR_BREACH|TYPE_WORD_TOO_WIDE|FIGURE_COLLIDES/i.test(code))
    return "Some on-screen text couldn't be laid out cleanly in every video size — try shorter sentences or a different style. Your script is saved.";
  return `The render didn't pass its quality gate — ${code}.`;
}

// Renders in flight across both engine families. A job counts as running when
// it has no status.json yet (or status "running") and was created within the
// last hour — older orphans from crashed workers don't hold the gate forever.
export function runningEngineJobs(): number {
  const cutoff = Date.now() - 60 * 60 * 1000;
  let running = 0;
  for (const kind of ENGINE_KINDS) {
    const jobsDir = engineJobsDir(kind);
    if (!existsSync(jobsDir)) continue;
    for (const entry of readdirSync(jobsDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      try {
        const dir = path.join(jobsDir, entry.name);
        const req = JSON.parse(readFileSync(path.join(dir, "request.json"), "utf8"));
        if (!req.createdAt || new Date(req.createdAt).getTime() < cutoff) continue;
        const statusPath = path.join(dir, "status.json");
        const status = existsSync(statusPath) ? JSON.parse(readFileSync(statusPath, "utf8")).status : "running";
        if (status === "running") running++;
      } catch { /* unreadable job dir — skip */ }
    }
  }
  return running;
}

export function renderCapacity(): number {
  const cap = parseInt(process.env.STUDIO_MAX_CONCURRENT_RENDERS ?? "4", 10);
  return Number.isFinite(cap) && cap > 0 ? cap : 4;
}

export interface EngineJobRead {
  status: "running" | "done" | "failed" | "unknown";
  phase?: string;
  outputs?: Record<string, string>;
  failureCode?: string;
  script?: string;
  title?: string;
}

export function readEngineJob(kind: EngineKind, jobId: string): EngineJobRead {
  try {
    const dir = path.join(engineJobsDir(kind), jobId);
    const statusRaw = existsSync(path.join(dir, "status.json"))
      ? JSON.parse(readFileSync(path.join(dir, "status.json"), "utf8")) : {};
    const progressRaw = existsSync(path.join(dir, "progress.json"))
      ? JSON.parse(readFileSync(path.join(dir, "progress.json"), "utf8")) : {};
    const requestRaw = existsSync(path.join(dir, "request.json"))
      ? JSON.parse(readFileSync(path.join(dir, "request.json"), "utf8")) : {};
    const status = typeof statusRaw.status === "string" ? statusRaw.status : "unknown";
    return {
      status: status === "done" || status === "failed" || status === "running" ? status : "unknown",
      phase: typeof progressRaw.phase === "string" ? progressRaw.phase : (typeof progressRaw.step === "string" ? progressRaw.step : undefined),
      outputs: statusRaw.outputs && typeof statusRaw.outputs === "object" ? statusRaw.outputs as Record<string, string> : undefined,
      failureCode: friendlyEngineError(dir),
      script: typeof requestRaw.script === "string" ? requestRaw.script : undefined,
      title: typeof requestRaw.title === "string" ? requestRaw.title : undefined,
    };
  } catch {
    return { status: "unknown" };
  }
}

// --- P8 cast scope -------------------------------------------------------
// Engine jobs that use a saved character must be visible to P8's memory:
// a Production row + StudioProductionCastMember link makes the render a
// first-class P8 production, and CAST-scope memory items record the
// character's performer signature and render history.

const CAST_SYSTEM_DIR = path.join(process.cwd(), "engine_sources", "makehuman-lineart", "character_system");

export function castSpecHash(spec: unknown): string {
  return createHash("sha256").update(JSON.stringify(spec ?? {})).digest("hex");
}

function admittedPerformerVerbs(): string[] {
  try {
    const meanings = JSON.parse(readFileSync(path.join(CAST_SYSTEM_DIR, "gesture-meanings.json"), "utf8"));
    const clips = JSON.parse(readFileSync(path.join(CAST_SYSTEM_DIR, "gesture-clips.json"), "utf8"));
    const verbs = new Set<string>((meanings.intents ?? []).map((i: [string, string]) => i[0]));
    for (const k of Object.keys(clips.groups ?? {})) verbs.add(`group:${k}`);
    return [...verbs].sort();
  } catch { return []; }
}

export async function registerCastScope(input: {
  ownerUserId: string;
  member: { id: string; name: string; identityKey: string; spec: unknown };
  jobId: string;
  kind: EngineKind;
  subtype: string;
  title: string;
}): Promise<{ productionId: string; specHash: string } | null> {
  const prisma = getPrisma();
  if (!prisma) return null;
  const specHash = castSpecHash(input.member.spec);
  const production = await prisma.production.create({
    data: {
      id: randomUUID(),
      ownerUserId: input.ownerUserId,
      kind: "VIDEO",
      title: input.title,
      status: "RENDERING",
      studioState: "PRODUCTION",
      direction: { engine: { kind: input.kind, jobId: input.jobId, subtype: input.subtype } },
    },
  });
  await prisma.studioProductionCastMember.create({
    data: { productionId: production.id, castMemberId: input.member.id, ordinal: 0 },
  });
  // Performer signature: the boundary evidence for this character — rewritten
  // only when the spec actually changes, so the memory is signal not noise.
  const latest = await prisma.studioMemoryItem.findUnique({
    where: {
      ownerUserId_scope_scopeRefId_key: {
        ownerUserId: input.ownerUserId, scope: "CAST", scopeRefId: input.member.id, key: "performer-signature",
      },
    },
    include: { versions: { orderBy: { versionNumber: "desc" }, take: 1 } },
  });
  const currentHash = (latest?.versions[0]?.content as { specHash?: string } | undefined)?.specHash;
  if (currentHash !== specHash) {
    await appendStudioMemoryVersion({
      prisma,
      ownerUserId: input.ownerUserId,
      scope: "CAST",
      scopeRefId: input.member.id,
      key: "performer-signature",
      category: "cast-boundary",
      content: {
        identityKey: input.member.identityKey,
        name: input.member.name,
        specHash,
        admittedVerbs: admittedPerformerVerbs(),
      },
      provenance: {
        source: "SYSTEM_INFERENCE",
        recordedAt: new Date().toISOString(),
        note: "Registered when the character was dispatched to render",
      },
      sourceProductionId: production.id,
      createdByType: "SYSTEM",
    });
  }
  return { productionId: production.id, specHash };
}

// Called lazily from the job-status route when a job reaches a terminal state.
// Closes the Production row and appends the render to the character's CAST
// memory under UPDATE_CHARACTER_GOING_FORWARD semantics.
export async function finalizeCastScope(dir: string, status: string): Promise<void> {
  const prisma = getPrisma();
  if (!prisma) return;
  try {
    const reqPath = path.join(dir, "engine_request.json");
    if (!existsSync(reqPath)) return;
    const engineReq = JSON.parse(readFileSync(reqPath, "utf8"));
    const cast = engineReq?.params?.cast as
      | { productionId?: string; castMemberId?: string; identityKey?: string; specHash?: string; subtype?: string; jobId?: string }
      | undefined;
    if (!cast?.productionId || !cast.castMemberId) return;
    const production = await prisma.production.findUnique({ where: { id: cast.productionId } });
    if (!production || production.status === "VERSION_READY") return;
    const outputs = status === "done"
      ? (JSON.parse(readFileSync(path.join(dir, "status.json"), "utf8")).outputs ?? null)
      : null;
    await prisma.production.update({
      where: { id: cast.productionId },
      data: { status: status === "done" ? "VERSION_READY" : "DRAFT" },
    });
    if (status !== "done") return;
    const req = JSON.parse(readFileSync(path.join(dir, "request.json"), "utf8"));
    await appendStudioMemoryVersion({
      prisma,
      ownerUserId: req.userId,
      scope: "CAST",
      scopeRefId: cast.castMemberId,
      key: "render-history",
      category: "cast-render",
      content: {
        jobId: cast.jobId ?? path.basename(dir),
        subtype: cast.subtype ?? engineReq.subtype,
        status, outputs, specHash: cast.specHash ?? null,
      },
      provenance: {
        source: "PRODUCTION",
        sourceProductionId: cast.productionId,
        recordedAt: new Date().toISOString(),
      },
      sourceProductionId: cast.productionId,
      createdByType: "SYSTEM",
      reason: "UPDATE_CHARACTER_GOING_FORWARD",
    });
  } catch { /* a missing finalization never breaks the status read */ }
}

export async function createEngineDraft(input: {
  ownerUserId: string;
  kind: EngineKind;
  jobId: string;
  videoType: string;
  script: string;
  title?: string | null;
  duration?: number | null;
  voice?: string | null;
  castMemberId?: string | null;
}): Promise<void> {
  const prisma = getPrisma();
  if (!prisma) return;
  // the cast member must belong to the caller - foreign keys make an owned lookup airtight
  if (input.castMemberId && !(await prisma.studioCastMember.findFirst({ where: { id: input.castMemberId, ownerUserId: input.ownerUserId }, select: { id: true } }))) {
    input.castMemberId = null;
  }
  const firstLine = input.script.split("\n").map((l) => l.trim()).filter(Boolean)[0] ?? "";
  const title = (input.title ?? "").trim() || (firstLine ? firstLine.split(/\s+/).slice(0, 8).join(" ") : "Untitled production");
  await prisma.draft.create({
    data: {
      ownerUserId: input.ownerUserId,
      kind: "VIDEO",
      family: input.kind === "whiteboard" ? "WHITEBOARD" : input.kind === "presenter" ? "PRESENTER" : "EXPLAINER",
      videoType: input.videoType,
      title,
      prompt: input.script || "[uploaded voiceover]",
      duration: input.duration ?? null,
      voicePreference: input.voice ?? null,
      payload: { engine: { kind: input.kind, jobId: input.jobId }, castMemberId: input.castMemberId ?? null },
      studioState: "PRODUCTION",
    },
  });
}
