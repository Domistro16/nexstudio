import certification from "./four-family-capability-registry.json";
import type { FamilyId, PreviewAssetRef } from "../registry/types";

type Verification = {
  status: "unverified" | "verified" | "failed";
  verifiedAt?: string;
  verifier?: string;
  evidence?: readonly string[];
};

type Gate = {
  publicEnabled: boolean;
  verification: Verification;
  previewVideo: PreviewAssetRef | null;
  posterFrame: string | null;
};

export function getSubtypeCertificationGate(family: FamilyId, videoTypeId: string): Gate {
  const familyRecord = certification.families[family];
  const subtype = familyRecord.subtypes.find((item) => item.id === videoTypeId);
  if (!subtype) throw new Error(`Missing four-family certification record: ${family}/${videoTypeId}`);
  const verification = subtype.verification as Verification;
  const previewVideo = subtype.publicAssets.previewVideo as PreviewAssetRef | null;
  const posterFrame = subtype.publicAssets.posterFrame as string | null;
  const publicEnabled = Boolean(subtype.publicEnabledRecommendation);
  if (publicEnabled) {
    if (verification.status !== "verified" || !verification.verifiedAt || !verification.verifier || !verification.evidence?.length) {
      throw new Error(`Certification record cannot enable ${family}/${videoTypeId} without verified evidence.`);
    }
    if (!previewVideo?.src || !posterFrame) {
      throw new Error(`Certification record cannot enable ${family}/${videoTypeId} without certified homepage media.`);
    }
  }
  return { publicEnabled, verification, previewVideo, posterFrame };
}
