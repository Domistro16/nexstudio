import { z } from "zod";

export const nexMindP8Phases = [
  "CAPABILITY_GRAPH_VALIDATED",
  "SOURCE_INTELLIGENCE",
  "STORY",
  "VISUAL_CONCEPT",
  "ART_DIRECTION",
  "STORYBOARD",
  "CINEMATOGRAPHY",
  "EDITORIAL_RHYTHM",
  "MOTION_PERFORMANCE",
  "SOUND_DIRECTION",
  "DEPARTMENTS_COMPLETE",
  "FINAL_PRODUCER",
  "AUTONOMOUS_REPAIR",
  "HUMAN_REVIEW_REQUIRED",
  "CREATIVE_LOCKED",
] as const;
export type NexMindP8Phase = (typeof nexMindP8Phases)[number];

export const nexMindP8Statuses = [
  "DEPARTMENTS_COMPLETE",
  "HUMAN_REVIEW_REQUIRED",
  "CREATIVE_LOCKED",
  "REQUIRES_INPUT",
  "PROVIDER_UNAVAILABLE",
  "REVISE",
  "BLOCKED",
] as const;
export type NexMindP8Status = (typeof nexMindP8Statuses)[number];

const auditSchema = z.object({
  task: z.string().optional(),
  role: z.string().optional(),
  provider: z.string().optional(),
  model: z.string().optional(),
  resolved_model: z.string().optional(),
  input_tokens: z.number().int().nonnegative().optional(),
  cached_input_tokens: z.number().int().nonnegative().optional(),
  output_tokens: z.number().int().nonnegative().optional(),
  reasoning_tokens: z.number().int().nonnegative().optional(),
  request_id: z.string().optional(),
  request_hash: z.string().optional(),
}).passthrough();

export const nexMindP8ResultSchema = z.object({
  schema: z.literal("StudioNexMindP8ResultV1"),
  status: z.enum(nexMindP8Statuses),
  code: z.string(),
  productionId: z.string().optional(),
  revision: z.number().int().nonnegative().optional(),
  stateHash: z.string().optional(),
  decisionSlots: z.array(z.string()).optional(),
  capabilityGraphHash: z.string().optional(),
  dossier: z.unknown().optional(),
  finalBoard: z.unknown().optional(),
  checkpoint: z.unknown().optional(),
  providerAudits: z.array(auditSchema).optional(),
  detail: z.string().optional(),
}).passthrough();
export type NexMindP8Result = z.infer<typeof nexMindP8ResultSchema>;

export type StudioNexMindP8Request = {
  schema: "StudioNexMindP8RequestV1";
  productionId: string;
  workflowRunId: string;
  projectVersion: number;
  family: "EXPLAINER" | "WHITEBOARD" | "STICKMAN" | "EDITORIAL_MOTION";
  videoType: string;
  prompt: string;
  planPreview: null | {
    id: string;
    thesis: string;
    recommendedDuration: number;
    beats: Array<{ start: number; end: number; purposeTitle: string; description: string }>;
    authority: "NON_AUTHORITATIVE_COMMERCIAL_PREVIEW";
  };
  sourceSummaries: Array<{ id: string; kind: string; label?: string | null; summary?: string | null }>;
  evidence: Array<{ claim_id: string; claim: string; source: string; status: string }>;
  sourceIntelligence?: {
    schema: "StudioP8SourceIntelligencePacketV1";
    extractedSourceCount: number;
    contextChars: number;
    warnings: string[];
    visualReferences: Array<{ sourceId: string; sourceLabel: string; page: number | null; locator: string; role: string; visuallyComplex: boolean; visualOnly: boolean; objectKey: string; mimeType: string; sha256: string }>;
    provenanceLaw: string;
  };
  sourceVisualEvidence?: Array<{ sourceId: string; sourceLabel: string; page: number | null; locator: string; role: string; sha256: string; mimeType: string; dataUrl: string }>;
  sourceVisualEvidenceOmissions?: Array<{ sourceId?: string; locator?: string; sha256?: string; reason: string }>;
  durationSeconds: number;
  aspectRatio: string | null;
  voicePreference: string | null;
  brandContext: Record<string, unknown> | null;
  referenceLanguageProfile?: Record<string, unknown> | null;
  referenceStyleHint?: string | null;
  capabilityGraph?: Record<string, unknown>;
  creativeMemory?: Array<Record<string, unknown>>;
  autonomousRepairContext?: Record<string, unknown> | null;
  revisionContext?: null | {
    instruction: string;
    timestampSeconds: number | null;
    priorCreativeLockArtifactId: string;
    priorCreativeLockArtifactHash: string;
    priorFinalBoard: unknown;
    preservationLaw: "PRESERVE_UNAFFECTED_LOCKED_DECISIONS";
  };
  policy: {
    fullNexMindRequired: true;
    planPreviewIsNotCreativeLock: true;
  };
};

export type NexMindProgress = { phase: NexMindP8Phase; payload: Record<string, unknown> };

export type StudioNexMindP8FinalizeRequest = {
  schema: "StudioNexMindP8FinalizeRequestV1";
  operation: "FINALIZE_WITH_MULTIMODAL_EVIDENCE";
  productionId: string;
  workflowRunId: string;
  checkpoint: unknown;
  finalBoard: unknown;
  multimodalArtifacts: Array<{ artifact_id: string; kind: "CONTACT_SHEET" | "KEYFRAME" | "VIDEO" | "AUDIO_MIX" | "WAVEFORM" | "TRANSCRIPT"; sha256: string; media_sha256?: string; object_key?: string; source: string }>;
  mediaSetSha256: string;
  p8BuildHash: string;
  perceptualMedia: { videoArtifactId: string; videoMediaSha256: string; temporalFrames: Array<{ timestampSeconds:number; sha256:string; dataUrl:string }>; audio: null | { sha256:string; mimeType:string; sampleRate:number; channels:number; dataUrl:string }; referenceVisuals?: Array<{ sha256:string; dataUrl:string; sourceId?:string; locator?:string }>; referenceVisualOmissions?: Array<{ sourceId?:string; locator?:string; sha256?:string; reason:string }> };
  audioExpected: boolean;
  studioTasteCalibration?: {
    schema: "StudioTasteCalibrationSnapshotV1";
    records: Array<{
      productionId: string;
      family: "EXPLAINER" | "WHITEBOARD" | "STICKMAN" | "EDITORIAL_MOTION";
      evidenceHash: string;
      p8BuildHash: string;
      judgeEnsembleHash: string;
      machineReview: Record<string, unknown>;
      humanReview: Record<string, unknown>;
      synthetic: false;
    }>;
  };
  autonomyPolicy?: { repairRound: number };
  humanReview?: null | {
    reviewer_id: string;
    reviewer_provenance: string;
    blind: true;
    independent: true;
    scores: Record<string, number>;
    hard_rejects: string[];
    notes: string;
  };
};

export type StudioNexMindP8BridgeRequest = StudioNexMindP8Request | StudioNexMindP8FinalizeRequest;

