import type { Prisma, StudioProductionFamily } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { saveStudioArtifact } from "@/lib/studio-governance";
import { appendStudioWorkflowEventTx, ensureStudioWorkflowActivityTx } from "@/studio-v1/architecture/workflow-durability";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? value : []; }

export const STUDIO_AUTONOMY_POLICY = Object.freeze({
  schema: "StudioNexMindAutonomyPolicyV3",
  creativeRecoveryLaw: "LOCAL_IDEA_MAY_FAIL__PRODUCTION_CONTINUES_WITH_BROADER_REPLAN",
  calibrationScope: "EXACT_FAMILY__EXACT_P8_BUILD__EXACT_TWO_JUDGE_ENSEMBLE",
  calibrationEligibilityReviews: 12,
  autonomousCalibrationReviews: 36,
  autonomousCalibrationDistinctProductions: 12,
  autonomousCalibrationDistinctReviewers: 5,
  reviewerConcentrationCeiling: 0.35,
  heldoutPercent: 20,
  rankCorrelation: "SPEARMAN",
  meanCorrelationFloor: 0.80,
  dimensionCorrelationFloor: 0.60,
  meanAbsoluteErrorCeiling: 0.70,
  dimensionAbsoluteErrorCeiling: 1.00,
  machineOptimismBiasCeiling: 0.35,
  machineFalseAcceptCeiling: 0,
  craftMeanFloor: 9.5,
  tasteMeanFloor: 9.5,
  dimensionFloor: 9.0,
  criticalDimensionFloor: 9.5,
  qualityGateLaw: "NEVER_LOWER_QUALITY_FOR_AUTONOMY",
} as const);

export type StudioTasteCalibrationRecord = {
  productionId: string;
  family: StudioProductionFamily;
  evidenceHash: string;
  p8BuildHash: string;
  judgeEnsembleHash: string;
  machineReview: Record<string, unknown>;
  humanReview: Record<string, unknown>;
  synthetic: false;
};

export async function loadStudioTasteCalibration(): Promise<{ schema: "StudioTasteCalibrationSnapshotV1"; records: StudioTasteCalibrationRecord[] }> {
  const prisma = getPrisma()!;
  const artifacts = await prisma.studioArtifact.findMany({
    where: { artifactType: "NEXMIND_P8_TASTE_CALIBRATION_SAMPLE", status: "approved" },
    orderBy: { createdAt: "desc" },
  });
  const records: StudioTasteCalibrationRecord[] = [];
  const seen = new Set<string>();
  for (const artifact of artifacts) {
    const content = record(artifact.content);
    if (content.schema !== "StudioNexMindTasteCalibrationSampleV1" || content.synthetic === true) continue;
    const family = String(content.family || "") as StudioProductionFamily;
    if (!["EXPLAINER", "WHITEBOARD", "STICKMAN", "EDITORIAL_MOTION"].includes(family)) continue;
    const evidenceHash = String(content.evidenceHash || "");
    const p8BuildHash = String(content.p8BuildHash || "");
    const judgeEnsembleHash = String(content.judgeEnsembleHash || "");
    const machineReview = record(content.machineReview);
    const humanReview = record(content.humanReview);
    const productionId = String(content.productionId || artifact.productionId);
    if (!evidenceHash || !p8BuildHash || !judgeEnsembleHash || !Object.keys(machineReview).length || !Object.keys(humanReview).length) continue;
    // One exact machine/human/evidence pairing counts once even if a retry wrote a duplicate artifact.
    const key = `${productionId}:${evidenceHash}:${String(humanReview.reviewer_id || "")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    records.push({ productionId, family, evidenceHash, p8BuildHash, judgeEnsembleHash, machineReview, humanReview, synthetic: false });
  }
  return { schema: "StudioTasteCalibrationSnapshotV1", records };
}

export function productionMemoryPacketToCreativeRefs(packetValue: unknown, snapshotHash: string) {
  const packet = record(packetValue);
  const refs: Record<string, unknown>[] = [];
  const pushMemories = (items: unknown, scopeOverride?: string, ownerRef?: string) => {
    for (const raw of array(items)) {
      const item = record(raw);
      if (String(item.effectiveState || "ACTIVE") !== "ACTIVE") continue;
      const provenance = record(item.provenance);
      refs.push({
        memory_id: String(item.itemId || item.versionId || `${scopeOverride || item.scope || "MEMORY"}:${item.key || refs.length + 1}`),
        status: "PROMOTED",
        scope: String(scopeOverride || item.scope || "ACCOUNT"),
        scope_ref_id: String(ownerRef || item.scopeRefId || ""),
        kind: String(item.category || "MEMORY"),
        lesson: JSON.stringify(record(item.content)),
        evidence: [String(item.contentHash || "")].filter(Boolean),
        provenance: JSON.stringify({ ...provenance, immutableMemoryInputSnapshotHash: snapshotHash }),
        version: String(item.versionNumber || 1),
        valid_from: item.effectiveFrom ?? null,
        valid_until: item.effectiveUntil ?? null,
        effective_from_episode_ordinal: item.effectiveFromEpisodeOrdinal ?? null,
        source_authority: "STUDIO_PRODUCTION_MEMORY_PACKET_V1",
      });
    }
  };
  pushMemories(packet.accountMemory, "ACCOUNT", String(packet.ownerUserId || ""));
  const brand = record(packet.brandAuthority); pushMemories(brand.memories, "BRAND", String(brand.brandId || ""));
  const series = record(packet.seriesMemory); pushMemories(series.memories, "SERIES", String(series.seriesId || ""));
  for (const rawCast of array(packet.castAuthority)) {
    const cast = record(rawCast); pushMemories(cast.memories, "CAST", String(cast.castMemberId || ""));
  }
  pushMemories(packet.productionMemory, "PRODUCTION", String(packet.productionId || ""));
  return refs;
}

// Canonical live Creative Memory comes only from the immutable five-scope
// StudioProductionMemoryPacketV1 captured at production start. Production-time
// observations below are offline evidence and never a second live memory store.

export async function saveStudioTasteCalibrationSample(input: {
  productionId: string;
  projectVersion: number;
  family: StudioProductionFamily;
  workflowRunId: string;
  multimodalPackageArtifact: { id: string; contentHash: string };
  humanReviewArtifact: { id: string; contentHash: string; content: unknown };
  machineReview: Record<string, unknown>;
  p8BuildHash: string;
  judgeEnsembleHash: string;
}) {
  const hr = record(input.humanReviewArtifact.content);
  const humanReview = {
    reviewer_id: String(hr.reviewerId || ""),
    reviewer_provenance: String(hr.reviewerProvenance || ""),
    blind: true,
    independent: true,
    scores: Object.fromEntries(Object.entries(record(hr.scores)).map(([key, value]) => [key, Number(value)])),
    hard_rejects: array(hr.hardRejects).map(String),
    notes: String(hr.notes || ""),
  };
  const content = {
    schema: "StudioNexMindTasteCalibrationSampleV1",
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    family: input.family,
    evidenceHash: input.multimodalPackageArtifact.contentHash,
    p8BuildHash: input.p8BuildHash,
    judgeEnsembleHash: input.judgeEnsembleHash,
    multimodalPackageArtifactId: input.multimodalPackageArtifact.id,
    humanReviewArtifactId: input.humanReviewArtifact.id,
    machineReview: input.machineReview,
    humanReview,
    synthetic: false,
    provenance: "EXACT_FINAL_PRODUCER_REVIEW_PAIRED_WITH_BLIND_INDEPENDENT_HUMAN_REVIEW",
  };
  return saveStudioArtifact({
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    artifactType: "NEXMIND_P8_TASTE_CALIBRATION_SAMPLE",
    status: "approved",
    content,
    inputs: [
      { artifactId: input.multimodalPackageArtifact.id, sha256: input.multimodalPackageArtifact.contentHash },
      { artifactId: input.humanReviewArtifact.id, sha256: input.humanReviewArtifact.contentHash },
    ],
    createdBy: { type: "service", role: "nexmind_p8_taste_calibration", runId: input.workflowRunId },
  });
}

export async function saveCreativeMemoryObservation(input: {
  productionId: string;
  projectVersion: number;
  workflowRunId: string;
  family: StudioProductionFamily;
  resultCode: string;
  finalReview: unknown;
  qualityEvidence: unknown;
  repairRequest: unknown;
}) {
  // Observations are deliberately NOT promoted into live Creative Memory. They
  // are evidence for the offline calibration/evolution process only.
  return saveStudioArtifact({
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    artifactType: "NEXMIND_P8_CREATIVE_MEMORY_OBSERVATION",
    status: "observed",
    content: {
      schema: "StudioNexMindCreativeMemoryObservationV1",
      family: input.family,
      resultCode: input.resultCode,
      finalReview: input.finalReview,
      qualityEvidence: input.qualityEvidence,
      repairRequest: input.repairRequest,
      livePromotionAllowed: false,
    },
    inputs: [],
    createdBy: { type: "service", role: "nexmind_p8_offline_learning_observer", runId: input.workflowRunId },
  });
}

export function nextRepairContext(current: unknown, repairRequest: unknown, priorStateHash: string | null, priorBoardHash: string | null) {
  const existing = record(current);
  const request = record(repairRequest);
  return {
    schema: "StudioAutonomousCreativeRepairContextV1",
    repairRound: Number(request.round || existing.repairRound || 1),
    escalationScope: String(request.escalation_scope || existing.escalationScope || "RESPONSIBLE_DEPARTMENT"),
    priorStateHash,
    priorBoardHash,
    invalidateSlots: array(request.invalidate_slots).map(String),
    issues: array(request.issues).map(String),
    revisionPlan: array(request.revision_plan).map(String),
    qualityReasons: array(request.quality_reasons).map(String),
    law: "REPAIR_ONLY_RESPONSIBLE_CREATIVE_CAUSES__NEVER_LOWER_QUALITY_GATE",
  };
}


export async function queueAutonomousP8Finalization(productionId: string) {
  const prisma = getPrisma()!;
  const run = await prisma.studioWorkflowRun.findFirst({
    where: { productionId, workflowType: "STANDALONE_STUDIO_CREATE_VIDEO" },
    orderBy: { createdAt: "desc" },
  });
  if (!run) throw new Error("STUDIO_WORKFLOW_NOT_FOUND");
  const context = record(run.context);
  const nx = record(context.nexmind);
  const creativeStateId = typeof nx.creativeStateArtifactId === "string" ? nx.creativeStateArtifactId : null;
  const creativeStateHash = typeof nx.creativeStateArtifactHash === "string" ? nx.creativeStateArtifactHash : null;
  if (!creativeStateId || !creativeStateHash) throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISSING");
  const creativeState = await prisma.studioArtifact.findFirst({ where: { id: creativeStateId, productionId, artifactType: "NEXMIND_P8_CREATIVE_STATE", contentHash: creativeStateHash } });
  if (!creativeState) throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISMATCH");
  const packages = await prisma.studioArtifact.findMany({ where: { productionId, projectVersion: run.projectVersion, artifactType: "NEXMIND_P8_MULTIMODAL_REVIEW_PACKAGE" }, orderBy: { createdAt: "desc" }, take: 20 });
  const reviewPackage = packages.find((artifact) => {
    const content = record(artifact.content);
    return content.status === "COMPLETE" && content.creativeStateArtifactId === creativeState.id && content.creativeStateArtifactSha256 === creativeState.contentHash;
  });
  if (!reviewPackage) throw new Error("NEXMIND_MULTIMODAL_REVIEW_PACKAGE_MISSING");
  const reviews = await prisma.studioArtifact.findMany({ where: { productionId, projectVersion: run.projectVersion, artifactType: "NEXMIND_P8_BLIND_HUMAN_REVIEW" }, orderBy: { createdAt: "desc" }, take: 30 });
  const humanReview = reviews.find((artifact) => {
    const content = record(artifact.content);
    return content.reviewedArtifactId === reviewPackage.id && content.reviewedArtifactSha256 === reviewPackage.contentHash && record(content.gate).status === "PASS";
  }) ?? null;
  const repair = record(nx.autonomousRepair);
  const repairRound = Math.max(0, Number(repair.repairRound || 0));
  const key = `${productionId}:standalone:v${run.projectVersion}:nexmind-p8-finalize:${reviewPackage.contentHash}:${humanReview?.contentHash || `autonomous-r${repairRound}`}`;
  return prisma.$transaction(async (tx) => {
    const ensured = await ensureStudioWorkflowActivityTx(tx, {
      workflowRunId: run.id,
      activityType: "FINALIZE_STANDALONE_NEXMIND_P8",
      workerClass: "CREATIVE",
      idempotencyKey: key,
      status: "QUEUED",
      maxAttempts: 3,
      input: {
        creativeStateArtifactId: creativeState.id,
        creativeStateArtifactHash: creativeState.contentHash,
        multimodalPackageArtifactId: reviewPackage.id,
        multimodalPackageArtifactHash: reviewPackage.contentHash,
        humanReviewArtifactId: humanReview?.id ?? null,
        humanReviewArtifactHash: humanReview?.contentHash ?? null,
        repairRound,
      } as Prisma.InputJsonValue,
    });
    if (ensured.created) {
      await tx.studioWorkflowRun.update({
        where: { id: run.id },
        data: {
          status: "RUNNING",
          blockedReason: null,
          context: { ...context, nexmind: { ...nx, status: "RUNNING", phase: "FINAL_PRODUCER", customerPhase: "INTERNAL_REVIEW", finalizationEvidence: { creativeStateArtifactId: creativeState.id, multimodalPackageArtifactId: reviewPackage.id, humanReviewArtifactId: humanReview?.id ?? null, repairRound } } } as Prisma.InputJsonValue,
        },
      });
      await appendStudioWorkflowEventTx(tx, run.id, humanReview ? "NEXMIND_P8_HUMAN_ASSISTED_FINALIZATION_QUEUED" : "NEXMIND_P8_AUTONOMOUS_FINALIZATION_QUEUED", { creativeStateArtifactId: creativeState.id, multimodalPackageArtifactId: reviewPackage.id, humanReviewArtifactId: humanReview?.id ?? null, repairRound, activityId: ensured.activity.id });
    }
    return ensured.activity;
  }, { isolationLevel: "Serializable" });
}


export async function queueAutonomousP8Repair(input: {
  workflowRunId: string;
  productionId: string;
  projectVersion: number;
  repairContext: Record<string, unknown>;
}) {
  const prisma = getPrisma()!;
  const round = Number(input.repairContext.repairRound || 0);
  if (!Number.isInteger(round) || round < 1) throw new Error("NEXMIND_AUTONOMOUS_REPAIR_CONTEXT_INVALID");
  const priorStateHash = String(input.repairContext.priorStateHash || "none");
  const key = `${input.productionId}:standalone:v${input.projectVersion}:nexmind-p8-autonomous-repair:r${round}:${priorStateHash.slice(0, 24)}`;
  return prisma.$transaction(async (tx) => {
    const run = await tx.studioWorkflowRun.findUniqueOrThrow({ where: { id: input.workflowRunId } });
    const context = record(run.context);
    const nx = record(context.nexmind);
    const ensured = await ensureStudioWorkflowActivityTx(tx, {
      workflowRunId: run.id,
      activityType: "RUN_STANDALONE_NEXMIND_P8",
      workerClass: "CREATIVE",
      idempotencyKey: key,
      status: "QUEUED",
      maxAttempts: 3,
      input: { autonomousRepair: input.repairContext } as Prisma.InputJsonValue,
    });
    if (ensured.created) {
      await tx.studioWorkflowRun.update({
        where: { id: run.id },
        data: { status: "RUNNING", blockedReason: null, context: { ...context, nexmind: { ...nx, status: "RUNNING", phase: "AUTONOMOUS_REPAIR", customerPhase: "INTERNAL_REVIEW", autonomousRepair: input.repairContext, updatedAt: new Date().toISOString() } } as Prisma.InputJsonValue },
      });
      await appendStudioWorkflowEventTx(tx, run.id, "NEXMIND_P8_AUTONOMOUS_REPAIR_QUEUED", { round, activityId: ensured.activity.id, reasons: input.repairContext.qualityReasons ?? input.repairContext.issues ?? [] });
    }
    return ensured.activity;
  }, { isolationLevel: "Serializable" });
}
