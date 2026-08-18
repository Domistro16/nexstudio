export const FAMILY_IDS = ["explainer", "whiteboard", "stickman", "editorial-motion"] as const;
export type FamilyId = (typeof FAMILY_IDS)[number];

export const ASPECT_RATIOS = ["16:9", "9:16", "1:1"] as const;
export type AspectRatio = (typeof ASPECT_RATIOS)[number];

export type CapabilityVerificationStatus = "unverified" | "verified" | "failed";

export interface PreviewAssetRef {
  /** Public or CDN URL. Branch B ships no preview media files. */
  src: string;
  /** Optional media type. Prefer video/mp4 or video/webm. */
  type?: string;
}

export interface InputRequirement {
  id: string;
  label: string;
  kind: "text" | "url" | "file" | "number" | "choice";
  description?: string;
}

export interface CapabilityContract {
  /** Stable key consumed by the production-capability verifier. */
  contractId: string;
  requiredCapabilities: readonly string[];
  verification: {
    status: CapabilityVerificationStatus;
    verifiedAt?: string;
    verifier?: string;
    evidence?: readonly string[];
  };
}

export interface ProductionVideoType {
  id: string;
  family: FamilyId;
  name: string;
  shortDescription: string;
  previewVideo: PreviewAssetRef | null;
  posterFrame: string | null;
  supportedDurations: readonly number[];
  supportedAspectRatios: readonly AspectRatio[];
  requiredInputs: readonly InputRequirement[];
  optionalInputs: readonly InputRequirement[];
  capabilityContract: CapabilityContract;
  /** Explicit publishing switch. Verification is still required. */
  publicEnabled: boolean;
}

export interface ProductionFamily {
  id: FamilyId;
  name: string;
  shortDescription: string;
  publicEnabled: boolean;
  previewVideo: PreviewAssetRef | null;
  posterFrame: string | null;
}

export interface ProductionRegistry {
  families: readonly ProductionFamily[];
  videoTypes: readonly ProductionVideoType[];
}
