import path from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { requireSession } from "@/lib/route-auth";
import { json, problem } from "@/lib/http";
import { getPrisma } from "@/lib/db";
import { createEngineDraft, engineJobsDir, registerCastScope, runningEngineJobs } from "@/lib/engine-jobs";
import { renderInFlightLimit, submitRenderJob } from "@/lib/render-queue";
import { castRenderConfig } from "@/studio-v2/cast/render-config";
import { normalizeCastSpec, type CastSpec } from "@/studio-v2/cast/spec";
import { ENVIRONMENTS } from "@/studio-v2/cast/environments";
import { castPreset } from "@/lib/cast-presets";
import { normalizeNarration } from "@/lib/narration-text";
import type { Prisma } from "@/generated/prisma/client";

export const runtime = "nodejs";

const VOICES = ["emma", "ava", "andrew", "brian", "sonia", "natasha"];
const ASPECTS: Record<string, string> = { "16x9": "16:9", "1x1": "1:1", "9x16": "9:16" };
const PROMOS = new Set(["off", "lower-third", "squeeze"]);
const IMAGE_TYPES: Record<string, string> = { "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp" };
const MAX_IMAGE = 5 * 1024 * 1024;
const MAX_SCRIPT = 4000;

export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  return json({
    available: process.env.STUDIO_PRESENTER_ENABLED !== "false",
    voices: VOICES, aspects: Object.keys(ASPECTS), promos: [...PROMOS],
    direction: { cinematic: true, infographic: false },
    backgrounds: ENVIRONMENTS.map((e) => ({ id: e.key, name: e.label })),
  }, auth.id);
}

export async function POST(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const id = auth.id;
  if (process.env.STUDIO_PRESENTER_ENABLED === "false") {
    return problem(id, 503, "PRESENTER_RENDERING_DISABLED", "Presenter rendering unavailable",
      "This server currently supports whiteboard and explainer videos. Choose one of those production types.");
  }
  let form: FormData;
  try { form = await request.formData(); }
  catch { return problem(id, 400, "BAD_FORM", "Invalid form", "Send multipart/form-data."); }

  const castMemberId = String(form.get("castMemberId") ?? "").trim();
  const castPresetId = String(form.get("castPresetId") ?? "").trim();
  const prisma = getPrisma()!;
  let member = castMemberId
    ? await prisma.studioCastMember.findFirst({ where: { id: castMemberId, ownerUserId: auth.session!.userId } })
    : null;
  if (!member && castPresetId) {
    // Studio cast preset: adopt it into this user's cast on first use — a real
    // StudioCastMember under the shared preset-* identityKey so P8 sees the
    // same performer whoever renders with it.
    const preset = castPreset(castPresetId);
    if (preset) {
      member = (await prisma.studioCastMember.findFirst({
        where: { ownerUserId: auth.session!.userId, identityKey: preset.identityKey },
      })) ?? (await prisma.studioCastMember.create({
        data: {
          ownerUserId: auth.session!.userId, name: preset.name,
          identityKey: preset.identityKey,
          spec: normalizeCastSpec(preset.spec) as unknown as Prisma.InputJsonValue,
        },
      }));
    }
  }
  if (!member || !member.spec)
    return problem(id, 422, "CAST_REQUIRED", "Pick a character", "Choose a studio character or one of your saved characters to present this video.");

  const script = normalizeNarration(String(form.get("script") ?? ""));
  const voiceFile = form.get("voiceFile");
  if (!script && !(voiceFile instanceof File))
    return problem(id, 422, "VOICE_REQUIRED", "Script required", "Send 'script' (for a Microsoft voice) or a 'voiceFile' upload.");
  if (script.length > MAX_SCRIPT)
    return problem(id, 422, "SCRIPT_TOO_LONG", "Script is too long", `Keep the script under ${MAX_SCRIPT} characters.`);

  const voice = String(form.get("voice") ?? "andrew");
  if (!VOICES.includes(voice))
    return problem(id, 422, "VOICE_UNKNOWN", "Unknown voice", `Pick one of: ${VOICES.join(", ")}.`);

  const speedRaw = Number(form.get("speed") ?? 1);
  if (!Number.isFinite(speedRaw) || speedRaw < 0.7 || speedRaw > 1.5)
    return problem(id, 422, "SPEED_RANGE", "Invalid speed", "Narration speed must be 0.7 to 1.5×.");

  const background = String(form.get("background") ?? "neutral_studio");
  if (!ENVIRONMENTS.some((e) => e.key === background))
    return problem(id, 422, "BACKGROUND_UNKNOWN", "Unknown background", "Pick one of the studio backgrounds.");

  const accent = String(form.get("accent") ?? "").trim();
  if (accent && !/^#[0-9a-fA-F]{6}$/.test(accent))
    return problem(id, 422, "ACCENT_INVALID", "Invalid accent color", "Send a hex color like #2f6fb3.");

  const aspects = String(form.get("aspects") ?? "16x9,1x1,9x16")
    .split(",").map((a) => a.trim()).filter((a) => a in ASPECTS);
  if (!aspects.length)
    return problem(id, 422, "ASPECT_UNKNOWN", "No valid aspect", `Pick from: ${Object.keys(ASPECTS).join(", ")}.`);

  // Direction layer — cinematic is opt-out, infographics opt-in. Both flow
  // into request.json (composer flags) and the P8 engine_request envelope.
  const cinematic = String(form.get("cinematic") ?? "true") !== "false";
  const infographic = String(form.get("infographic") ?? "false") === "true";
  const promoMode = String(form.get("promo") ?? "off");
  if (!PROMOS.has(promoMode))
    return problem(id, 422, "PROMO_UNKNOWN", "Unknown promotion style", "Pick off, lower-third or squeeze.");
  const promoName = String(form.get("promoName") ?? "").trim();
  const promoLabel = String(form.get("promoLabel") ?? "").trim();
  const promoImage = form.get("promoImage");
  if (promoMode !== "off") {
    if (!promoName || promoName.length > 60)
      return problem(id, 422, "PROMO_NAME", "Add a promotion name", "Give the promotion a name of up to 60 characters.");
    if (promoLabel.length > 40)
      return problem(id, 422, "PROMO_LABEL", "Promotion label is too long", "Keep the small label under 40 characters.");
    if (promoImage instanceof File && (!IMAGE_TYPES[promoImage.type] || promoImage.size > MAX_IMAGE))
      return problem(id, 422, "PROMO_IMAGE", "Promotion image not supported", "Upload a PNG, JPEG or WebP image up to 5 MB.");
  }

  if (runningEngineJobs() >= renderInFlightLimit())
    return problem(id, 429, "RENDER_AT_CAPACITY", "The render floor is full right now", "A few renders are already running. Try again in a minute. Your script and choices are saved.");

  const jobId = `pr-${randomUUID().slice(0, 8)}`;
  const dir = path.join(engineJobsDir("presenter"), jobId);
  mkdirSync(dir, { recursive: true });

  let voiceName: string | null = null;
  if (voiceFile instanceof File) {
    voiceName = `voice_src${path.extname(voiceFile.name || ".mp3").replace(/[^.\w]/g, "") || ".mp3"}`;
    writeFileSync(path.join(dir, voiceName), Buffer.from(await voiceFile.arrayBuffer()));
  }
  let imageName: string | null = null;
  if (promoMode !== "off" && promoImage instanceof File && promoImage.size) {
    imageName = `promo${IMAGE_TYPES[promoImage.type]}`;
    writeFileSync(path.join(dir, imageName), Buffer.from(await promoImage.arrayBuffer()));
  }

  const spec = normalizeCastSpec(member.spec as unknown as CastSpec);
  writeFileSync(path.join(dir, "request.json"), JSON.stringify({
    userId: auth.session!.userId, castMemberId: member.id, config: castRenderConfig(spec),
    script: script || null, voice, speed: speedRaw, voiceFile: voiceName,
    aspects: aspects.map((a) => ASPECTS[a]), background, accent: accent || null,
    cinematic, infographic,
    promo: promoMode === "off" ? null : { mode: promoMode, name: promoName, label: promoLabel || null, image: imageName },
    createdAt: new Date().toISOString(),
  }, null, 1));
  writeFileSync(path.join(dir, "status.json"), JSON.stringify({ status: "running", startedAt: new Date().toISOString() }));
  // All renders dispatch through P8's family-engine surface; presenter-job.py
  // keeps owning the heavy pipeline, the runner records the P8 result envelope.
  const subtype = background === "lesson_board" ? "lesson-board"
    : background === "kids_book" ? "kids-lesson" : "presenter";
  // Register the render under P8's cast scope: a Production row + cast link so
  // P8 memory can resolve this character's authority for the job.
  const castScope = await registerCastScope({
    ownerUserId: auth.session!.userId,
    member: { id: member.id, name: member.name, identityKey: member.identityKey, spec: member.spec },
    jobId, kind: "presenter", subtype,
    title: script.split("\n")[0]?.split(/\s+/).slice(0, 8).join(" ") || member.name,
  }).catch(() => null);
  writeFileSync(path.join(dir, "engine_request.json"), JSON.stringify({
    schema: "StudioSiteEngineRequestV1", family: "presenter", subtype, jobId,
    params: { director: { cinematic, infographic }, cast: castScope && {
      productionId: castScope.productionId, castMemberId: member.id,
      identityKey: member.identityKey, specHash: castScope.specHash, subtype, jobId,
    } },
  }, null, 1));

  await submitRenderJob({ jobId, dir, family: "presenter" });

  try {
    await createEngineDraft({
      ownerUserId: auth.session!.userId, kind: "presenter", jobId, videoType: "presenter",
      script: script || "", voice: script ? voice : null, castMemberId: member.id,
    });
  } catch { /* a missing draft never blocks the render */ }

  return json({ jobId, status: "running", statusUrl: `/api/v1/presenters/${jobId}` }, id, { status: 202 });
}
