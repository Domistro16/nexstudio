import path from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { requireSession } from "@/lib/route-auth";
import { json, problem } from "@/lib/http";
import { getPrisma } from "@/lib/db";
import { createEngineDraft, registerCastScope, runningEngineJobs } from "@/lib/engine-jobs";
import { renderInFlightLimit, submitRenderJob } from "@/lib/render-queue";
import { engineJobsDir } from "@/lib/engine-paths";
import { normalizeNarration } from "@/lib/narration-text";
import { chooseVideoTitle } from "@/lib/video-title";

export const runtime = "nodejs";

const JOBS = engineJobsDir("whiteboard");

const TYPES = {
  "kinetic-text": { id: "kinetic-text", name: "Text-Driven Whiteboard", pipeline: "kinetic" },
  "hand-drawn-board": { id: "hand-drawn-board", name: "Hand-Drawn Whiteboard", pipeline: "board" },
  "board-scenes": { id: "board-scenes", name: "Board Scenes", pipeline: "board-scenes" },
} as const;
const VOICES = ["emma", "ava", "andrew", "brian", "sonia", "natasha"];
const THEMES = new Set(["light", "dark"]);
const ASPECTS = new Set(["16x9", "1x1", "9x16"]);

export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  return json({
    types: Object.values(TYPES).map(({ id, name }) => ({ id, name })),
    themes: [...THEMES], voices: VOICES, aspects: [...ASPECTS],
  }, auth.id);
}

export async function POST(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const id = auth.id;
  let form: FormData;
  try { form = await request.formData(); }
  catch { return problem(id, 400, "BAD_FORM", "Invalid form", "Send multipart/form-data."); }

  const type = String(form.get("type") ?? "kinetic-text");
  const spec = TYPES[type as keyof typeof TYPES];
  if (!spec)
    return problem(id, 422, "TYPE_UNKNOWN", "Unknown whiteboard type",
      `Pick one of: ${Object.keys(TYPES).join(", ")}.`);

  const script = normalizeNarration(String(form.get("script") ?? ""), { keepHeadings: true });
  const voiceFile = form.get("voiceFile");
  if (!script && !(voiceFile instanceof File))
    return problem(id, 422, "VOICE_REQUIRED", "Voice required", "Send 'script' (for a Microsoft voice) or a 'voiceFile' upload.");

  const voice = String(form.get("voice") ?? "emma");
  if (script && !VOICES.includes(voice))
    return problem(id, 422, "VOICE_UNKNOWN", "Unknown voice", `Pick one of: ${VOICES.join(", ")}.`);

  const theme = String(form.get("theme") ?? "light");
  if (!THEMES.has(theme))
    return problem(id, 422, "THEME_UNKNOWN", "Unknown theme", `Pick one of: ${[...THEMES].join(", ")}.`);

  const accent = String(form.get("accent") ?? "").trim();
  const castMemberId = String(form.get("castMemberId") ?? "").trim() || null;
  if (accent && !/^#[0-9a-fA-F]{3,8}$/.test(accent))
    return problem(id, 422, "ACCENT_INVALID", "Invalid accent color", "Send a hex color like #2f6fb3.");

  const aspects = String(form.get("aspects") ?? "16x9,1x1,9x16")
    .split(",").map((a) => a.trim()).filter((a) => ASPECTS.has(a));
  if (!aspects.length)
    return problem(id, 422, "ASPECT_UNKNOWN", "No valid aspect", `Pick from: ${[...ASPECTS].join(", ")}.`);

  const durationRaw = Number(form.get("duration") ?? 0);
  if (durationRaw && (!Number.isFinite(durationRaw) || durationRaw < 5 || durationRaw > 600))
    return problem(id, 422, "DURATION_RANGE", "Invalid length", "Target length must be 5 to 600 seconds.");

  const speedRaw = Number(form.get("speed") ?? 0);
  if (speedRaw && (!Number.isFinite(speedRaw) || speedRaw < 0.7 || speedRaw > 1.5))
    return problem(id, 422, "SPEED_RANGE", "Invalid speed", "Narration speed must be 0.7 to 1.5×.");

  if (runningEngineJobs() >= renderInFlightLimit())
    return problem(id, 429, "RENDER_AT_CAPACITY", "The render floor is full right now", "A few renders are already running. Try again in a minute. Your brief and direction are saved.");

  const title = await chooseVideoTitle(script, form.get("title"));
  const jobId = `wb-${randomUUID().slice(0, 8)}`;
  const dir = path.join(JOBS, jobId);
  mkdirSync(dir, { recursive: true });

  const scriptPath = path.join(dir, "script.txt");
  let voicePath: string | null = null;
  if (script) {
    writeFileSync(scriptPath, script.endsWith("\n") ? script : `${script}\n`);
  }
  if (voiceFile instanceof File) {
    voicePath = path.join(dir, `voice_src${path.extname(voiceFile.name || ".mp3")}`);
    writeFileSync(voicePath, Buffer.from(await voiceFile.arrayBuffer()));
  }

  writeFileSync(path.join(dir, "request.json"), JSON.stringify({
    userId: auth.session!.userId, type, voice, theme, accent: accent || null, aspects,
    title: title || null, script: script || null, createdAt: new Date().toISOString(),
  }, null, 1));
  writeFileSync(path.join(dir, "status.json"), JSON.stringify({ status: "running", startedAt: new Date().toISOString() }));
  // All renders dispatch through P8's family-engine surface: the runner resolves
  // the subtype in site-dispatch.json (fail-closed), builds the engine call and
  // writes status.json + the P8 result envelope itself.
  const castScope = castMemberId ? await (async () => {
    const prisma = getPrisma();
    const member = prisma && await prisma.studioCastMember.findFirst({
      where: { id: castMemberId, ownerUserId: auth.session!.userId },
    });
    return member && registerCastScope({
      ownerUserId: auth.session!.userId,
      member: { id: member.id, name: member.name, identityKey: member.identityKey, spec: member.spec },
      jobId, kind: "whiteboard", subtype: type,
      title: title || script.split("\n")[0]?.split(/\s+/).slice(0, 8).join(" ") || "Whiteboard",
    }).catch(() => null);
  })() : null;
  writeFileSync(path.join(dir, "engine_request.json"), JSON.stringify({
    schema: "StudioSiteEngineRequestV1", family: "whiteboard", subtype: type, jobId,
    params: {
      theme, voice, accent: accent || null, aspects, title: title || null,
      duration: durationRaw || null, speed: speedRaw || null,
      scriptPath: script ? scriptPath : null, voiceFile: voicePath,
      cast: castScope && {
        productionId: castScope.productionId, castMemberId,
        specHash: castScope.specHash, subtype: type, jobId,
      },
    },
  }, null, 1));

  await submitRenderJob({ jobId, dir, family: "whiteboard" });

  // Jobs are work items — surface them in Work alongside real productions.
  try {
    await createEngineDraft({
      ownerUserId: auth.session!.userId,
      kind: "whiteboard",
      jobId,
      videoType: type,
      script: script || "",
      title,
      duration: durationRaw || null,
      voice: script ? voice : null,
      castMemberId,
    });
  } catch { /* a missing draft never blocks the render */ }

  return json({ jobId, status: "running", statusUrl: `/api/v1/whiteboards/${jobId}` }, id, { status: 202 });
}
