import { createHash } from "node:crypto";
import { z } from "zod";
import { getPrisma } from "@/lib/db";
import { saveStudioArtifact } from "@/lib/studio-governance";

export const p8MultimodalKinds = ["CONTACT_SHEET", "KEYFRAME", "VIDEO", "AUDIO_MIX", "WAVEFORM", "TRANSCRIPT"] as const;
export type P8MultimodalKind = (typeof p8MultimodalKinds)[number];

const expectedArtifactTypes: Record<P8MultimodalKind, string> = {
  CONTACT_SHEET: "INTERNAL_REVIEW_CONTACT_SHEET",
  KEYFRAME: "INTERNAL_REVIEW_KEYFRAME",
  VIDEO: "INTERNAL_REVIEW_VIDEO",
  AUDIO_MIX: "INTERNAL_REVIEW_AUDIO_MIX",
  WAVEFORM: "INTERNAL_REVIEW_WAVEFORM",
  TRANSCRIPT: "INTERNAL_REVIEW_TRANSCRIPT",
};

export const p8MultimodalPackageInputSchema = z.object({
  artifacts: z.array(z.object({ artifactId: z.string().uuid(), kind: z.enum(p8MultimodalKinds) }).strict()).min(1).max(64),
  audioExpected: z.boolean().default(true),
}).strict();

function createMediaSetSha256(items: Array<{artifact_id:string;kind:string;media_sha256:string;object_key:string}>) {
  const canonical = JSON.stringify(items);
  return createHash("sha256").update(canonical).digest("hex");
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export async function assembleP8MultimodalReviewPackage(input: {
  productionId: string;
  operatorUserId: string;
  requestId: string;
  body: z.infer<typeof p8MultimodalPackageInputSchema>;
  creator?: { type: "operator" | "service"; role: string; userId?: string; runId?: string };
}) {
  const prisma = getPrisma()!;
  const production = await prisma.production.findUnique({ where: { id: input.productionId }, select: { id: true } });
  if (!production) throw new Error("PRODUCTION_NOT_FOUND");
  const run = await prisma.studioWorkflowRun.findFirst({ where: { productionId: input.productionId, workflowType: "STANDALONE_STUDIO_CREATE_VIDEO" }, orderBy: { createdAt: "desc" } });
  if (!run) throw new Error("STUDIO_WORKFLOW_NOT_FOUND");
  const nexmind = record(record(run.context).nexmind);
  if (!["DEPARTMENTS_COMPLETE", "HUMAN_REVIEW_REQUIRED"].includes(String(nexmind.status || ""))) throw new Error("NEXMIND_REVIEW_PACKAGE_NOT_READY");
  const creativeStateArtifactId = typeof nexmind.creativeStateArtifactId === "string" ? nexmind.creativeStateArtifactId : null;
  const creativeStateArtifactHash = typeof nexmind.creativeStateArtifactHash === "string" ? nexmind.creativeStateArtifactHash : null;
  if (!creativeStateArtifactId || !creativeStateArtifactHash) throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISSING");
  const creativeState = await prisma.studioArtifact.findFirst({ where: { id: creativeStateArtifactId, productionId: input.productionId, artifactType: "NEXMIND_P8_CREATIVE_STATE" } });
  if (!creativeState || creativeState.contentHash !== creativeStateArtifactHash) throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISMATCH");

  const ids = [...new Set(input.body.artifacts.map((artifact) => artifact.artifactId))];
  const rows = await prisma.studioArtifact.findMany({ where: { id: { in: ids }, productionId: input.productionId } });
  if (rows.length !== ids.length) throw new Error("MULTIMODAL_ARTIFACT_NOT_FOUND");
  const rowMap = new Map(rows.map((row) => [row.id, row]));
  const p8Artifacts = input.body.artifacts.map((item) => {
    const artifact = rowMap.get(item.artifactId)!;
    if (artifact.artifactType !== expectedArtifactTypes[item.kind]) throw new Error(`MULTIMODAL_ARTIFACT_TYPE_MISMATCH:${item.kind}`);
    const dependencies = Array.isArray(artifact.inputs) ? artifact.inputs.map((entry) => record(entry)) : [];
    const bound = dependencies.some((entry) => entry.artifactId === creativeState.id && entry.sha256 === creativeState.contentHash);
    if (!bound) throw new Error(`MULTIMODAL_ARTIFACT_NOT_BOUND_TO_CREATIVE_STATE:${artifact.id}`);
    const payload = record(artifact.content);
    const mediaSha256 = typeof payload.mediaSha256 === "string" ? payload.mediaSha256 : "";
    const objectKey = typeof payload.objectKey === "string" ? payload.objectKey : "";
    if (!["TRANSCRIPT"].includes(item.kind) && (!/^[a-f0-9]{64}$/i.test(mediaSha256) || !objectKey)) throw new Error(`MULTIMODAL_MEDIA_BYTE_IDENTITY_MISSING:${artifact.id}`);
    return { artifact_id: artifact.id, kind: item.kind, sha256: artifact.contentHash, media_sha256: mediaSha256 || artifact.contentHash, object_key: objectKey, source: artifact.artifactType };
  });
  const visualPresent = p8Artifacts.some((artifact) => ["CONTACT_SHEET", "KEYFRAME", "VIDEO"].includes(artifact.kind));
  const audioPresent = p8Artifacts.some((artifact) => ["AUDIO_MIX", "WAVEFORM"].includes(artifact.kind));
  const issues = [
    ...(visualPresent ? [] : ["NO_VISUAL_RENDER_EVIDENCE"]),
    ...(input.body.audioExpected && !audioPresent ? ["NO_AUDIO_RENDER_EVIDENCE"] : []),
  ];
  if (issues.length) throw new Error(`MULTIMODAL_EVIDENCE_INCOMPLETE:${issues.join(",")}`);

  const mediaIdentity = p8Artifacts.map((artifact) => ({ artifact_id: artifact.artifact_id, kind: artifact.kind, media_sha256: artifact.media_sha256, object_key: artifact.object_key })).sort((a,b)=>a.artifact_id.localeCompare(b.artifact_id));
  const mediaSetSha256 = createMediaSetSha256(mediaIdentity);
  const content = {
    schema: "StudioNexMindP8MultimodalReviewPackageV1",
    status: "COMPLETE",
    productionId: input.productionId,
    workflowRunId: run.id,
    projectVersion: run.projectVersion,
    creativeStateArtifactId: creativeState.id,
    creativeStateArtifactSha256: creativeState.contentHash,
    stateHash: nexmind.stateHash ?? null,
    finalBoardHash: nexmind.finalBoardHash ?? null,
    artifacts: p8Artifacts,
    issues: [],
    visualPresent,
    audioPresent,
    audioExpected: input.body.audioExpected,
    mediaSetSha256,
  };
  const existing = await prisma.studioArtifact.findMany({ where: { productionId: input.productionId, projectVersion: run.projectVersion, artifactType: "NEXMIND_P8_MULTIMODAL_REVIEW_PACKAGE" }, orderBy: { createdAt: "desc" }, take: 20 });
  const identical = existing.find((artifact) => JSON.stringify(artifact.content) === JSON.stringify(content));
  if (identical) return identical;
  return saveStudioArtifact({
    productionId: input.productionId,
    projectVersion: run.projectVersion,
    artifactType: "NEXMIND_P8_MULTIMODAL_REVIEW_PACKAGE",
    status: "candidate",
    content,
    inputs: [{ artifactId: creativeState.id, sha256: creativeState.contentHash }, ...p8Artifacts.map((artifact) => ({ artifactId: artifact.artifact_id, sha256: artifact.sha256 }))],
    createdBy: input.creator ?? { type: "operator", role: "internal_multimodal_review_packager", runId: input.requestId, userId: input.operatorUserId },
  });
}
