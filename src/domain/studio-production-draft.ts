export const studioProductionFamilies = [
  "EXPLAINER",
  "WHITEBOARD",
  "STICKMAN",
  "EDITORIAL_MOTION",
] as const;

export type StudioProductionFamily = (typeof studioProductionFamilies)[number];

export const studioProductionStates = [
  "DRAFT",
  "AUTH_REQUIRED",
  "PLANNING",
  "PLAN_READY",
  "PAYMENT_REQUIRED",
  "PAYMENT_PENDING",
  "PRODUCTION",
  "FINAL_REVIEW",
  "COMPLETE",
  "INSUFFICIENT_BALANCE",
  "PRODUCTION_FAILED",
  "TECHNICAL_RETRY",
  "REVISION_REQUESTED",
] as const;

export type StudioProductionState = (typeof studioProductionStates)[number];

export type ProductionDraftSource = {
  id?: string;
  kind: "URL" | "UPLOAD" | "LIBRARY" | "TEXT";
  label?: string | null;
  reference?: string | null;
  mimeType?: string | null;
};

export type ProductionDraft = {
  id: string;
  ownerId: string | null;
  anonymousSessionId: string | null;
  family: StudioProductionFamily;
  videoType: string;
  prompt: string;
  sources: ProductionDraftSource[];
  duration: number | null;
  aspectRatio: string | null;
  voicePreference: string | null;
  brandContext: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
  state: StudioProductionState;
};

export function kindForStudioProductionDraft(_family: StudioProductionFamily): "VIDEO" {
  return "VIDEO";
}
