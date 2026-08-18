import { createHash } from "node:crypto";
import { z } from "zod";
import { getPrisma } from "@/lib/db";
import { saveStudioArtifact } from "@/lib/studio-governance";

export const P8_HUMAN_REVIEW_DIMENSIONS = [
  "story_clarity",
  "visual_communication",
  "illustration_art_quality",
  "character_subject_storytelling",
  "visual_hierarchy",
  "originality_appropriateness",
  "continuity_transformation",
  "motion_intentionality",
  "cinematography",
  "editorial_rhythm",
  "sound_design",
  "beauty_composition_taste",
  "charm_appeal",
  "emotional_appropriateness",
  "final_payoff",
  "commercial_believability",
  "engagement_memorability",
  "authorship_specificity",
  "reference_independence",
  "aesthetic_coherence",
  "emotional_resonance",
] as const;

export const P8_CRITICAL_HUMAN_DIMENSIONS = new Set([
  "story_clarity",
  "visual_communication",
  "illustration_art_quality",
  "continuity_transformation",
  "final_payoff",
  "commercial_believability",
  "engagement_memorability",
  "authorship_specificity",
  "reference_independence",
  "aesthetic_coherence",
  "emotional_resonance",
] as const);

const scoresShape = Object.fromEntries(P8_HUMAN_REVIEW_DIMENSIONS.map((dimension) => [dimension, z.number().min(0).max(10)])) as Record<(typeof P8_HUMAN_REVIEW_DIMENSIONS)[number], z.ZodNumber>;

export const p8HumanReviewInputSchema = z.object({
  reviewedArtifactId: z.string().uuid(),
  reviewedArtifactSha256: z.string().regex(/^[a-f0-9]{64}$/i),
  scores: z.object(scoresShape).strict(),
  hardRejects: z.array(z.string().trim().min(1).max(300)).max(30).default([]),
  notes: z.string().trim().max(4_000).default(""),
  blindReviewAcknowledged: z.literal(true),
  independentReviewAcknowledged: z.literal(true),
}).strict();

export type P8HumanReviewInput = z.infer<typeof p8HumanReviewInputSchema>;

function hash(value: unknown) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function reviewGate(scores: Record<string, number>, hardRejects: string[]) {
  const values = P8_HUMAN_REVIEW_DIMENSIONS.map((dimension) => Number(scores[dimension]));
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const below9 = Object.fromEntries(P8_HUMAN_REVIEW_DIMENSIONS.filter((dimension) => Number(scores[dimension]) < 9).map((dimension) => [dimension, Number(scores[dimension])]));
  const criticalBelow95 = Object.fromEntries(P8_HUMAN_REVIEW_DIMENSIONS.filter((dimension) => P8_CRITICAL_HUMAN_DIMENSIONS.has(dimension as never) && Number(scores[dimension]) < 9.5).map((dimension) => [dimension, Number(scores[dimension])]));
  return {
    status: mean >= 9.5 && Object.keys(below9).length === 0 && Object.keys(criticalBelow95).length === 0 && hardRejects.length === 0 ? "PASS" : "FAIL",
    mean: Number(mean.toFixed(4)),
    below9,
    criticalBelow95,
    hardRejects,
  } as const;
}

export async function recordP8BlindHumanReview(input: {
  operatorUserId: string;
  productionId: string;
  requestId: string;
  idempotencyKey: string;
  body: P8HumanReviewInput;
}) {
  const prisma = getPrisma()!;
  const production = await prisma.production.findUnique({ where: { id: input.productionId }, select: { id: true, ownerUserId: true } });
  if (!production) throw new Error("PRODUCTION_NOT_FOUND");
  if (production.ownerUserId === input.operatorUserId) throw new Error("REVIEWER_NOT_INDEPENDENT");

  const reviewedArtifact = await prisma.studioArtifact.findFirst({
    where: { id: input.body.reviewedArtifactId, productionId: input.productionId },
  });
  if (!reviewedArtifact) throw new Error("REVIEW_ARTIFACT_NOT_FOUND");
  if (reviewedArtifact.contentHash.toLowerCase() !== input.body.reviewedArtifactSha256.toLowerCase()) throw new Error("REVIEW_ARTIFACT_HASH_MISMATCH");
  if (reviewedArtifact.artifactType !== "NEXMIND_P8_MULTIMODAL_REVIEW_PACKAGE") throw new Error("REVIEW_ARTIFACT_TYPE_INVALID");

  const gate = reviewGate(input.body.scores, input.body.hardRejects);
  const reviewerProvenance = `production-operator:${input.operatorUserId}`;
  const reviewPayload = {
    schema: "NexMindP8BlindHumanReviewRecordV1",
    authoritySnapshot: "P8_FINAL_PRODUCER_2026_08_12",
    reviewedArtifactId: reviewedArtifact.id,
    reviewedArtifactSha256: reviewedArtifact.contentHash,
    reviewerId: input.operatorUserId,
    reviewerProvenance,
    blind: true,
    independent: true,
    scores: input.body.scores,
    hardRejects: input.body.hardRejects,
    notes: input.body.notes,
    gate,
    status: "RECORDED_PENDING_FINAL_PRODUCER_MULTIMODAL_BINDING",
    creativeLockGranted: false,
    reason: "A blind review is evidence only. Creative Lock requires the Final Producer to be rerun against the same complete hashed multimodal evidence before the P8 lock gate is evaluated.",
    idempotencyKeyHash: hash(input.idempotencyKey),
  };
  const contentHash = hash(reviewPayload);
  const existing = await prisma.studioArtifact.findFirst({
    where: { productionId: input.productionId, artifactType: "NEXMIND_P8_BLIND_HUMAN_REVIEW", contentHash },
    orderBy: { createdAt: "desc" },
  });
  if (existing) return { artifact: existing, gate, status: reviewPayload.status, creativeLockGranted: false };

  const artifact = await saveStudioArtifact({
    productionId: input.productionId,
    projectVersion: reviewedArtifact.projectVersion,
    artifactType: "NEXMIND_P8_BLIND_HUMAN_REVIEW",
    status: "candidate",
    content: reviewPayload,
    inputs: [{ artifactId: reviewedArtifact.id, sha256: reviewedArtifact.contentHash }],
    createdBy: { type: "operator", role: "independent_blind_creative_reviewer", runId: input.requestId, userId: input.operatorUserId },
  });
  await prisma.auditEvent.create({
    data: {
      actorUserId: input.operatorUserId,
      action: "STUDIO_NEXMIND_P8_BLIND_REVIEW_RECORDED",
      entityType: "StudioArtifact",
      entityId: artifact.id,
      before: {},
      after: { productionId: input.productionId, reviewedArtifactId: reviewedArtifact.id, reviewedArtifactSha256: reviewedArtifact.contentHash, gate, creativeLockGranted: false } as never,
      requestId: input.requestId,
    },
  });
  return { artifact, gate, status: reviewPayload.status, creativeLockGranted: false };
}
