import { createHash } from "node:crypto";
import type { Prisma } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { allocateProjectVersionTx, transitionCanonicalStudioStateTx } from "@/studio-v1/architecture/core";
import { saveLineageSnapshotTx } from "@/studio-v1/architecture/lineage";
import { saveStudioArtifactTx } from "@/lib/studio-governance";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function sha(value: unknown) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

export async function queueStandaloneCustomerRevision(input: {
  userId: string;
  productionId: string;
  versionId: string;
  instruction: string;
  timestampSeconds?: number | null;
}) {
  const instruction = input.instruction.trim();
  if (!instruction) throw new Error("REVISION_INSTRUCTION_REQUIRED");
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");

  const revisionKey = sha({
    productionId: input.productionId,
    versionId: input.versionId,
    instruction,
    timestampSeconds: input.timestampSeconds ?? null,
  });
  const workflowId = `${input.productionId}:standalone:revision:${revisionKey}`;
  const existing = await prisma.studioWorkflowRun.findUnique({ where: { workflowId } });
  if (existing) {
    const artifact = await prisma.studioArtifact.findFirst({
      where: { productionId: input.productionId, projectVersion: existing.projectVersion, artifactType: "STANDALONE_REVISION_REQUEST" },
      orderBy: { createdAt: "desc" },
    });
    return { workflowRunId: existing.id, projectVersion: existing.projectVersion, revisionArtifactId: artifact?.id ?? null, secondCharge: false as const, reused: true as const };
  }

  return prisma.$transaction(async (tx) => {
    const raced = await tx.studioWorkflowRun.findUnique({ where: { workflowId } });
    if (raced) {
      const artifact = await tx.studioArtifact.findFirst({
        where: { productionId: input.productionId, projectVersion: raced.projectVersion, artifactType: "STANDALONE_REVISION_REQUEST" },
        orderBy: { createdAt: "desc" },
      });
      return { workflowRunId: raced.id, projectVersion: raced.projectVersion, revisionArtifactId: artifact?.id ?? null, secondCharge: false as const, reused: true as const };
    }

    const [production, draft, version] = await Promise.all([
      tx.production.findFirst({ where: { id: input.productionId, ownerUserId: input.userId } }),
      tx.draft.findFirst({ where: { id: input.productionId, ownerUserId: input.userId } }),
      tx.productionVersion.findFirst({ where: { id: input.versionId, productionId: input.productionId } }),
    ]);
    if (!production) throw new Error("PRODUCTION_NOT_FOUND");
    if (!draft?.family) throw new Error("STANDALONE_DRAFT_NOT_FOUND");
    if (!version) throw new Error("REVISION_VERSION_NOT_FOUND");
    if (production.studioState !== "FINAL_REVIEW") throw new Error("REVISION_STATE_INVALID");

    const entitlement = await tx.studioProductionEntitlement.findFirst({
      where: { productionId: input.productionId, userId: input.userId, source: "PAID" },
      orderBy: [{ approvedPlanVersion: "desc" }, { createdAt: "desc" }],
    });
    if (!entitlement) throw new Error("PAID_ENTITLEMENT_REQUIRED_FOR_REVISION");
    const priorLock = await tx.studioArtifact.findFirst({
      where: { productionId: input.productionId, artifactType: "NEXMIND_P8_CREATIVE_LOCK", status: "approved" },
      orderBy: [{ projectVersion: "desc" }, { createdAt: "desc" }],
    });
    if (!priorLock) throw new Error("PRIOR_CREATIVE_LOCK_REQUIRED_FOR_REVISION");

    const projectVersion = await allocateProjectVersionTx(tx, input.productionId);
    const now = new Date();
    const revisionContent = {
      schema: "StandaloneStudioCustomerRevisionV2",
      productionId: input.productionId,
      priorVersionId: input.versionId,
      instruction,
      timestampSeconds: input.timestampSeconds ?? null,
      priorCreativeLockArtifactId: priorLock.id,
      priorCreativeLockArtifactHash: priorLock.contentHash,
      requestedByUserId: input.userId,
      requestedAt: now.toISOString(),
      commercialRule: "SAME_PAID_PRODUCTION_NO_SECOND_CHARGE",
      entitlementId: entitlement.id,
      priorOutputSha256: version.outputSha256 ?? null,
      priorLineageHash: version.lineageHash ?? null,
    };
    const revisionHash = sha(revisionContent);

    await transitionCanonicalStudioStateTx(tx, {
      productionId: input.productionId,
      ownerUserId: input.userId,
      to: "REVISION_REQUESTED",
      actor: { type: "user", id: input.userId, reason: "CUSTOMER_REVISION_REQUESTED", metadata: { priorVersionId: input.versionId, revisionHash } },
    });

    const workflow = await tx.studioWorkflowRun.create({
      data: {
        productionId: input.productionId,
        workflowId,
        workflowType: "STANDALONE_STUDIO_CREATE_VIDEO",
        status: "RUNNING",
        stage: "PROJECT_CREATED",
        projectVersion,
        approvalMode: "fully_managed",
        policy: { fullNexMindRequired: true, planPreviewIsNotCreativeLock: true, revisionIsIncludedInPaidProduction: true } as Prisma.InputJsonValue,
        context: {} as Prisma.InputJsonValue,
        events: { create: { sequence: 1, eventType: "CUSTOMER_REVISION_WORKFLOW_CREATED", toStage: "PROJECT_CREATED", payload: { priorVersionId: input.versionId, priorCreativeLockArtifactId: priorLock.id, paidEntitlementId: entitlement.id, secondCharge: false } as Prisma.InputJsonValue } },
      },
    });

    const artifact = await saveStudioArtifactTx(tx,{
      productionId:input.productionId,
      versionId:input.versionId,
      projectVersion,
      artifactType:"STANDALONE_REVISION_REQUEST",
      status:"approved",
      content:revisionContent,
      inputs:[{artifactId:priorLock.id,sha256:priorLock.contentHash}],
      createdBy:{type:"user",role:"customer_revision_request",runId:workflow.id,userId:input.userId},
    });

    const lineage = await saveLineageSnapshotTx(tx, {
      productionId: input.productionId,
      projectVersion,
      snapshotType: "REVISION_INPUT",
      content: {
        schema: "StudioRevisionInputLineageV1",
        productionId: input.productionId,
        projectVersion,
        entitlementId: entitlement.id,
        quoteId: entitlement.quoteId,
        priorVersion: { id: version.id, versionNumber: version.versionNumber, outputSha256: version.outputSha256, lineageHash: version.lineageHash },
        priorCreativeLock: { id: priorLock.id, hash: priorLock.contentHash },
        revision: { artifactId: artifact.id, hash: artifact.contentHash, instruction, timestampSeconds: input.timestampSeconds ?? null },
      },
    });

    const activity = await tx.studioWorkflowActivity.create({
      data: {
        workflowRunId: workflow.id,
        activityType: "RUN_STANDALONE_NEXMIND_P8",
        workerClass: "CREATIVE",
        idempotencyKey: `${input.productionId}:standalone:v${projectVersion}:nexmind-p8:revision:${revisionHash}`,
        status: "QUEUED",
        attempts: 0,
        maxAttempts: 3,
        input: { productionId: input.productionId, projectVersion, revisionArtifactId: artifact.id, revisionArtifactHash: artifact.contentHash, inputLineageSnapshotId: lineage.id, inputLineageSnapshotHash: lineage.contentHash } as Prisma.InputJsonValue,
      },
    });

    await tx.studioWorkflowRun.update({
      where: { id: workflow.id },
      data: {
        context: {
          paidEntitlementId: entitlement.id,
          planPreviewId: entitlement.planPreviewId,
          family: draft.family,
          videoType: draft.videoType,
          inputLineageSnapshotId: lineage.id,
          inputLineageSnapshotHash: lineage.contentHash,
          revision: {
            status: "QUEUED",
            revisionArtifactId: artifact.id,
            revisionArtifactHash: revisionHash,
            priorCreativeLockArtifactId: priorLock.id,
            priorCreativeLockArtifactHash: priorLock.contentHash,
            priorVersionId: input.versionId,
          },
          nexmind: { status: "QUEUED", phase: "CAPABILITY_GRAPH_VALIDATED", customerPhase: "PREPARING" },
        } as Prisma.InputJsonValue,
      },
    });

    await transitionCanonicalStudioStateTx(tx, {
      productionId: input.productionId,
      ownerUserId: input.userId,
      to: "PRODUCTION",
      actor: { type: "service", id: "studio-revision", reason: "REVISION_WORKFLOW_QUEUED", metadata: { workflowRunId: workflow.id, activityId: activity.id } },
    });
    await tx.production.update({ where: { id: input.productionId }, data: { status: "QUEUED", approverUserId: null } });

    return { workflowRunId: workflow.id, projectVersion, revisionArtifactId: artifact.id, secondCharge: false as const, reused: false as const };
  }, { isolationLevel: "Serializable" });
}
