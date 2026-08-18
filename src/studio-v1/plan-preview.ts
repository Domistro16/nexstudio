import { createHash } from "node:crypto";
import { z } from "zod";
import type { Prisma } from "@/generated/prisma/client";
import type { ProductionDraft, StudioProductionFamily } from "@/domain/studio-production-draft";
import { callNexMindDetailed, parseProviderJson } from "@/lib/nexmind";
import { nexMindRoleRouting } from "@/lib/nexmind-routing";
import { getPrisma } from "@/lib/db";

export const STUDIO_PLAN_PREVIEW_POLICY = Object.freeze({
  version: "studio-plan-preview-v1",
  provider: "capability-routed",
  maxOutputTokens: 700,
  maxApproxInputTokens: 6_000,
  maxProviderAttempts: 2,
  timeoutMs: 12_000,
  successfulComplimentaryPlansPerVerifiedAccount: 1,
  minBriefChars: 24,
  maxBriefChars: 5_000,
  minDurationSeconds: 15,
  maxDurationSeconds: 60,
  minBeats: 1,
  maxBeats: 12,
  accountRateLimit: { limit: 5, windowMs: 15 * 60_000 },
  ipRateLimit: { limit: 20, windowMs: 24 * 60 * 60_000 },
});

const beatSchema = z.object({
  start: z.number().int().min(0).max(60),
  end: z.number().int().min(1).max(60),
  purposeTitle: z.string().trim().min(1).max(90),
  description: z.string().trim().min(1).max(240),
}).strict();

const outputSchema = z.object({
  thesis: z.string().trim().min(1).max(220),
  recommendedDuration: z.number().int().min(15).max(60),
  beats: z.array(beatSchema).min(STUDIO_PLAN_PREVIEW_POLICY.minBeats).max(STUDIO_PLAN_PREVIEW_POLICY.maxBeats),
  missingInput: z.array(z.string().trim().min(1).max(140)).max(2),
}).strict();

export type StudioPlanPreview = z.infer<typeof outputSchema> & {
  status: "ready";
  planPreviewId: string;
  complimentaryPassConsumed: true;
  replayed: boolean;
};

const PLAN_PREVIEW_JSON_SCHEMA: Record<string, unknown> = {
  type: "object",
  additionalProperties: false,
  required: ["thesis", "recommendedDuration", "beats", "missingInput"],
  properties: {
    thesis: { type: "string", minLength: 1, maxLength: 220 },
    recommendedDuration: { type: "integer", minimum: 15, maximum: 60 },
    beats: {
      type: "array", minItems: 1, maxItems: 12,
      items: {
        type: "object", additionalProperties: false,
        required: ["start", "end", "purposeTitle", "description"],
        properties: {
          start: { type: "integer", minimum: 0, maximum: 60 },
          end: { type: "integer", minimum: 1, maximum: 60 },
          purposeTitle: { type: "string", minLength: 1, maxLength: 90 },
          description: { type: "string", minLength: 1, maxLength: 240 },
        },
      },
    },
    missingInput: { type: "array", maxItems: 2, items: { type: "string", minLength: 1, maxLength: 140 } },
  },
};

const restrictedPatterns = [
  /\b(system|developer|internal) prompt\b/i,
  /\basset[_ -]?id\b/i,
  /\b(renderer|render code|html|svg|gsap|ffmpeg|keyframes?)\b/i,
  /\bcamera (move|angle|lens|dolly|pan|zoom)\b/i,
  /\b(production|visual|story) director\b/i,
  /\bnegative prompt\b/i,
  /\bseed\s*[:=]/i,
];

function sha256(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function normalizedFamily(family: StudioProductionFamily) {
  return family === "EDITORIAL_MOTION" ? "editorial_motion" : family.toLowerCase();
}

function safeBrandTone(draft: ProductionDraft) {
  const brand = draft.brandContext;
  if (!brand) return "";
  const compact = JSON.stringify(brand);
  return compact.length > 1_200 ? compact.slice(0, 1_200) : compact;
}

function modelRequest(draft: ProductionDraft) {
  return {
    family: normalizedFamily(draft.family),
    videoType: draft.videoType,
    brief: draft.prompt.slice(0, STUDIO_PLAN_PREVIEW_POLICY.maxBriefChars),
    sourceSummaries: (() => {
      const all=draft.sources.map((source) => ({ sourceKind: source.kind.toLowerCase(), summary: [source.label, source.reference].filter(Boolean).join(": ") })).filter((item) => item.summary);
      const budget=18_000; let used=0; const selected=[] as typeof all; const omitted=[] as Array<{sourceKind:string;reason:string}>;
      for(const item of all){const text=item.summary.slice(0,4_000); if(used+text.length>budget){omitted.push({sourceKind:item.sourceKind,reason:"PREVIEW_CONTEXT_CHARACTER_BUDGET"});continue;} selected.push({...item,summary:text});used+=text.length;}
      return [...selected, ...(omitted.length ? [{sourceKind:"coverage",summary:`${omitted.length} additional source summaries are indexed but omitted from this lightweight preview by explicit context budget; full P8 production must retrieve them.`}] : [])];
    })(),
    requestedDuration: draft.duration ?? "auto",
    aspectRatio: draft.aspectRatio,
    brandTone: safeBrandTone(draft),
  };
}

function canonicalRequest(value: ReturnType<typeof modelRequest>) {
  return JSON.stringify(value);
}

function validateOutput(value: unknown) {
  const parsed = outputSchema.parse(value);
  let previousEnd = 0;
  for (let index = 0; index < parsed.beats.length; index += 1) {
    const beat = parsed.beats[index];
    if (index === 0 && beat.start !== 0) throw new Error("PLAN_PREVIEW_FIRST_BEAT_MUST_START_AT_ZERO");
    if (index > 0 && beat.start !== previousEnd) throw new Error("PLAN_PREVIEW_BEATS_MUST_BE_CONTIGUOUS");
    if (beat.end <= beat.start) throw new Error("PLAN_PREVIEW_BEAT_TIMING_INVALID");
    if (restrictedPatterns.some((pattern) => pattern.test(`${beat.purposeTitle} ${beat.description}`))) throw new Error("PLAN_PREVIEW_PRODUCTION_DETAIL_LEAK");
    previousEnd = beat.end;
  }
  if (previousEnd !== parsed.recommendedDuration) throw new Error("PLAN_PREVIEW_DURATION_MISMATCH");
  if (restrictedPatterns.some((pattern) => pattern.test(parsed.thesis))) throw new Error("PLAN_PREVIEW_PRODUCTION_DETAIL_LEAK");
  return parsed;
}

function systemInstruction(correction: boolean) {
  return [
    "Create only a lightweight customer-facing pre-payment production plan.",
    "Return one concise thesis and as many contiguous timed beats as the approved brief actually needs within the 60-second preview window; do not target a house beat count.",
    "Describe what each beat must communicate, not how to render or execute it.",
    "Do not provide a full script, scene-generation prompts, shot lists, camera instructions, motion specifications, asset IDs or routing, renderer/code details, Director reasoning, seeds, or negative prompts.",
    "Use ordinary customer language. Keep each description short and useful.",
    "If requestedDuration is numeric, use it unless impossible; otherwise recommend an appropriate duration from 15-60 seconds.",
    correction ? "The previous candidate failed the safety/shape validator. Make this attempt more abstract and less production-specific." : "",
  ].filter(Boolean).join("\n");
}

export function previewNeedsInput(draft: ProductionDraft) {
  if (draft.prompt.trim().length < STUDIO_PLAN_PREVIEW_POLICY.minBriefChars) {
    return ["Add a little more about what the film needs to communicate."];
  }
  return [] as string[];
}

export async function latestSuccessfulStudioPlanPreview(userId: string, productionId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio planning.");
  const row = await prisma.studioPlanPreviewRequest.findFirst({
    where: { userId, productionId, state: "SUCCEEDED" },
    orderBy: { completedAt: "desc" },
  });
  if (!row?.responseJson) return null;
  return { id: row.id, ...validateOutput(row.responseJson) };
}

export async function createComplimentaryStudioPlanPreview(input: {
  userId: string;
  productionId: string;
  draft: ProductionDraft;
  idempotencyKey: string;
}) : Promise<StudioPlanPreview | { status: "needs_input"; missingInput: string[]; complimentaryPassConsumed: false }> {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio planning.");
  const missingInput = previewNeedsInput(input.draft);
  if (missingInput.length) return { status: "needs_input", missingInput, complimentaryPassConsumed: false };

  const request = modelRequest(input.draft);
  const canonical = canonicalRequest(request);
  if (Math.ceil(canonical.length / 3) > STUDIO_PLAN_PREVIEW_POLICY.maxApproxInputTokens) throw new Error("PLAN_PREVIEW_CONTEXT_TOO_LARGE");
  const keyHash = sha256(`${input.userId}\n${input.idempotencyKey}`);
  const bodyHash = sha256(canonical);
  const fingerprint = sha256(`${input.userId}\n${canonical.toLowerCase()}`);

  const existing = await prisma.studioPlanPreviewRequest.findUnique({
    where: { userId_idempotencyKeyHash: { userId: input.userId, idempotencyKeyHash: keyHash } },
  });
  if (existing) {
    if (existing.bodyHash !== bodyHash) throw new Error("PLAN_PREVIEW_IDEMPOTENCY_CONFLICT");
    if (existing.state === "SUCCEEDED" && existing.responseJson) return {
      status: "ready", ...validateOutput(existing.responseJson), planPreviewId: existing.id, complimentaryPassConsumed: true, replayed: true,
    };
    if (existing.state === "PROCESSING") throw new Error("PLAN_PREVIEW_IN_PROGRESS");
  }

  const duplicate = await prisma.studioPlanPreviewRequest.findFirst({
    where: { userId: input.userId, requestFingerprint: fingerprint, state: "SUCCEEDED" },
    orderBy: { completedAt: "desc" },
  });
  if (duplicate?.responseJson) return {
    status: "ready", ...validateOutput(duplicate.responseJson), planPreviewId: duplicate.id, complimentaryPassConsumed: true, replayed: true,
  };

  const routing = nexMindRoleRouting("studio_plan_preview");
  const row = await prisma.$transaction(async (tx) => {
    const entitlement = await tx.studioPlanPreviewEntitlement.upsert({
      where: { userId: input.userId },
      create: { userId: input.userId, maxSuccessfulPlans: STUDIO_PLAN_PREVIEW_POLICY.successfulComplimentaryPlansPerVerifiedAccount, successfulPlans: 0 },
      update: {},
    });
    if (entitlement.successfulPlans >= entitlement.maxSuccessfulPlans) throw new Error("COMPLIMENTARY_PLAN_ALREADY_USED");
    try {
      return await tx.studioPlanPreviewRequest.create({
        data: {
          userId: input.userId,
          productionId: input.productionId,
          idempotencyKeyHash: keyHash,
          bodyHash,
          requestFingerprint: fingerprint,
          state: "PROCESSING",
          policyVersion: STUDIO_PLAN_PREVIEW_POLICY.version,
          provider: STUDIO_PLAN_PREVIEW_POLICY.provider,
          model: routing.model,
          reasoningEffort: routing.reasoning,
          activeSlot: input.userId,
        },
      });
    } catch (error) {
      if ((error as { code?: string }).code === "P2002") throw new Error("PLAN_PREVIEW_IN_PROGRESS");
      throw error;
    }
  });

  let lastError: unknown = null;
  for (let attempt = 1; attempt <= STUDIO_PLAN_PREVIEW_POLICY.maxProviderAttempts; attempt += 1) {
    try {
      await prisma.studioPlanPreviewRequest.update({ where: { id: row.id }, data: { attempts: attempt } });
      const result = await callNexMindDetailed([
        { role: "system", content: systemInstruction(attempt > 1) },
        { role: "user", content: JSON.stringify(request) },
      ], {
        responsesApi: routing.apiMode === "responses",
        forceResponsesTransport: routing.apiMode === "responses",
        modelIdPassthrough: true,
        model: routing.model,
        apiUrl: routing.baseUrl,
        apiKey: process.env[routing.apiKeyEnv]?.trim(),
        apiMode: routing.apiMode,
        maxTokens: STUDIO_PLAN_PREVIEW_POLICY.maxOutputTokens,
        timeoutMs: STUDIO_PLAN_PREVIEW_POLICY.timeoutMs,
        retries: 0,
        textVerbosity: "low",
        jsonSchema: { name: "studio_plan_preview", schema: PLAN_PREVIEW_JSON_SCHEMA },
        requestIdempotencyKey: `${input.idempotencyKey}:${attempt}`,
      });
      const checked = validateOutput(parseProviderJson(result.content));
      await prisma.$transaction(async (tx) => {
        const currentEntitlement = await tx.studioPlanPreviewEntitlement.findUniqueOrThrow({ where: { userId: input.userId } });
        if (currentEntitlement.successfulPlans >= currentEntitlement.maxSuccessfulPlans) throw new Error("COMPLIMENTARY_PLAN_ALREADY_USED");
        await tx.studioPlanPreviewRequest.update({
          where: { id: row.id },
          data: {
            state: "SUCCEEDED",
            responseJson: checked as unknown as Prisma.InputJsonValue,
            providerRequestId: result.providerRequestId ?? null,
            usageJson: result.usage ? result.usage as unknown as Prisma.InputJsonValue : undefined,
            activeSlot: null,
            completedAt: new Date(),
          },
        });
        await tx.studioPlanPreviewEntitlement.update({ where: { userId: input.userId }, data: { successfulPlans: { increment: 1 } } });
      });
      return { status: "ready", ...checked, planPreviewId: row.id, complimentaryPassConsumed: true, replayed: false };
    } catch (error) {
      lastError = error;
      const retryableShape = error instanceof z.ZodError || (error instanceof Error && error.message.startsWith("PLAN_PREVIEW_"));
      if (attempt < STUDIO_PLAN_PREVIEW_POLICY.maxProviderAttempts && retryableShape) continue;
      break;
    }
  }

  await prisma.studioPlanPreviewRequest.update({
    where: { id: row.id },
    data: { state: "FAILED", activeSlot: null, failureClass: lastError instanceof Error ? lastError.name.slice(0, 80) : "Error", failedAt: new Date() },
  }).catch(() => undefined);
  throw lastError instanceof Error ? lastError : new Error("PLAN_PREVIEW_UNAVAILABLE");
}
