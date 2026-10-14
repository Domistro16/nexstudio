import path from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { requireSession } from "@/lib/route-auth";
import { json, problem } from "@/lib/http";
import { getPrisma } from "@/lib/db";
import { createEngineDraft, registerCastScope, runningEngineJobs } from "@/lib/engine-jobs";
import { renderInFlightLimit, submitRenderJob } from "@/lib/render-queue";
import { engineJobsDir } from "@/lib/engine-paths";
import { explainerStyles } from "@/lib/explainer-catalog";
import { normalizeNarration } from "@/lib/narration-text";

export const runtime = "nodejs";

const JOBS = engineJobsDir("explainer");
const VOICES = [
  { id: "heart",   name: "Heart",   gender: "female", accent: "American", engine: "Kokoro",           preview: "/voice-previews/heart.mp3" },
  { id: "sky",     name: "Sky",     gender: "female", accent: "American", engine: "Kokoro",           preview: "/voice-previews/sky.mp3" },
  { id: "sarah",   name: "Sarah",   gender: "female", accent: "American", engine: "Kokoro",           preview: "/voice-previews/sarah.mp3" },
  { id: "liam",    name: "Liam",    gender: "male",   accent: "American", engine: "Kokoro",           preview: "/voice-previews/liam.mp3" },
  { id: "adam",    name: "Adam",    gender: "male",   accent: "American", engine: "Kokoro",           preview: "/voice-previews/adam.mp3" },
  { id: "emma",    name: "Emma",    gender: "female", accent: "American", engine: "Microsoft neural", preview: "/voice-previews/emma.mp3" },
  { id: "emily",   name: "Emily",   gender: "female", accent: "Irish",    engine: "Microsoft neural", preview: "/voice-previews/emily.mp3" },
  { id: "andrew",  name: "Andrew",  gender: "male",   accent: "American", engine: "Microsoft neural", preview: "/voice-previews/andrew.mp3" },
  { id: "steffan", name: "Steffan", gender: "male",   accent: "American", engine: "Microsoft neural", preview: "/voice-previews/steffan.mp3" },
  { id: "ava",     name: "Ava",     gender: "female", accent: "American", engine: "Microsoft neural", preview: "/previews/voices/ava.mp3" },
  { id: "brian",   name: "Brian",   gender: "male",   accent: "American", engine: "Microsoft neural", preview: "/previews/voices/brian.mp3" },
  { id: "sonia",   name: "Sonia",   gender: "female", accent: "British",  engine: "Microsoft neural", preview: "/previews/voices/sonia.mp3" },
  { id: "natasha", name: "Natasha", gender: "female", accent: "Australian", engine: "Microsoft neural", preview: "/previews/voices/natasha.mp3" },
  { id: "david",   name: "David",   gender: "male",   accent: "British",  engine: "Chatterbox clone", preview: "/voice-previews/david.mp3" },
];
const VOICE_IDS = new Set(VOICES.map((v) => v.id));
const ASPECTS = new Set(["16x9", "1x1", "9x16"]);

function stylesList() {
  try { return explainerStyles(); }
  catch { return []; }
}

export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  return json({ styles: stylesList(), voices: VOICES, aspects: [...ASPECTS] }, auth.id);
}

export async function POST(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const id = auth.id;
  let form: FormData;
  try { form = await request.formData(); }
  catch { return problem(id, 400, "BAD_FORM", "Invalid form", "Send multipart/form-data."); }

  const style = String(form.get("style") ?? "photo_story");
  const validStyles = new Set(stylesList().flatMap((s) => [s.id, ...s.variants.map((v) => v.id)]));
  if (!validStyles.size)
    return problem(id, 503, "STYLE_CATALOG_UNAVAILABLE", "Styles unavailable", "The explainer style catalog could not be loaded. Try again shortly.");
  if (!validStyles.has(style))
    return problem(id, 422, "STYLE_UNKNOWN", "Unknown style", `Pick one of: ${[...validStyles].join(", ")}.`);

  const script = normalizeNarration(String(form.get("script") ?? ""));
  const voiceFile = form.get("voiceFile");
  if (!script && !(voiceFile instanceof File))
    return problem(id, 422, "VOICE_REQUIRED", "Voice required", "Send 'script' (for a Microsoft voice) or a 'voiceFile' upload.");

  const voice = String(form.get("voice") ?? "andrew");
  if (script && !VOICE_IDS.has(voice))
    return problem(id, 422, "VOICE_UNKNOWN", "Unknown voice", `Pick one of: ${[...VOICE_IDS].join(", ")}.`);

  const subject = String(form.get("subject") ?? "").trim() || null;
  const castMemberId = String(form.get("castMemberId") ?? "").trim() || null;

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

  const jobId = `xr-${randomUUID().slice(0, 8)}`;
  const dir = path.join(JOBS, jobId);
  const mediaDir = path.join(dir, "media");
  mkdirSync(mediaDir, { recursive: true });

  let voicePath: string | null = null;
  if (voiceFile instanceof File) {
    voicePath = path.join(dir, `voice_src${path.extname(voiceFile.name || ".mp3")}`);
    writeFileSync(voicePath, Buffer.from(await voiceFile.arrayBuffer()));
  }

  const mediaPaths: string[] = [];
  for (const m of form.getAll("media")) {
    if (!(m instanceof File)) continue;
    const safe = (m.name || `media-${mediaPaths.length}`).replace(/[^\w.-]/g, "_");
    const dest = path.join(mediaDir, safe);
    writeFileSync(dest, Buffer.from(await m.arrayBuffer()));
    mediaPaths.push(dest);
  }

  writeFileSync(path.join(dir, "request.json"), JSON.stringify({
    userId: auth.session!.userId, style, voice, aspects,
    script: script || null, media: mediaPaths.map((p) => path.basename(p)), createdAt: new Date().toISOString(),
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
      jobId, kind: "explainer", subtype: style,
      title: script.split("\n")[0]?.split(/\s+/).slice(0, 8).join(" ") || "Explainer",
    }).catch(() => null);
  })() : null;
  writeFileSync(path.join(dir, "engine_request.json"), JSON.stringify({
    schema: "StudioSiteEngineRequestV1", family: "explainer", subtype: style, jobId,
    params: {
      script: script || null, voice, voiceFile: voicePath,
      aspects, duration: durationRaw || null, speed: speedRaw || null, media: mediaPaths, subject,
      cast: castScope && {
        productionId: castScope.productionId, castMemberId,
        specHash: castScope.specHash, subtype: style, jobId,
      },
    },
  }, null, 1));

  await submitRenderJob({ jobId, dir, family: "explainer" });

  // Jobs are work items — surface them in Work alongside real productions.
  try {
    await createEngineDraft({
      ownerUserId: auth.session!.userId,
      kind: "explainer",
      jobId,
      videoType: style,
      script: script || "",
      duration: durationRaw || null,
      voice: script ? voice : null,
      castMemberId,
    });
  } catch { /* a missing draft never blocks the render */ }

  return json({ jobId, status: "running", statusUrl: `/api/v1/explainers/${jobId}` }, id, { status: 202 });
}
