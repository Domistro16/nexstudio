import type { StudioProductionFamily } from "@/generated/prisma/client";

export type StudioEngineAuthorityStatus =
  | "ENGINEERING_COMPLETE_CREATIVE_REVIEW_PENDING"
  | "TECHNICAL_PASS_CREATIVE_REVIEW_PENDING"
  | "MACHINE_CERTIFIED_NO_SHIP"
  | "INTERNAL_PERFORMANCE_MASTER";

export type StudioFamilyEngineAuthority = {
  family: StudioProductionFamily;
  authorityId: string;
  sourceLabel: string;
  sourceArchiveSha256: string;
  capabilityManifestSha256?: string;
  technicalStatus: StudioEngineAuthorityStatus;
  executionBody: string;
  truthBoundary: string;
  eligibleForInternalReviewEvidence: boolean;
  eligibleForPublicProduction: boolean;
  dispatchAdapterStatus: "ADAPTER_PENDING" | "READY";
};

/**
 * Current execution-body truth for Standalone Studio V1.
 *
 * Public production is deliberately false for every family until the missing
 * independent creative / deployment evidence is completed. This registry is
 * for server-side routing and release gating; it must never be interpreted as
 * a marketing registry.
 */
export const STUDIO_FAMILY_ENGINE_AUTHORITIES: Readonly<Record<StudioProductionFamily, StudioFamilyEngineAuthority>> = {
  EXPLAINER: {
    family: "EXPLAINER",
    authorityId: "EXPLAINER_EXECUTION_BODY_V2_P8_UNIFIED",
    sourceLabel: "NexStudio_Explainer_Execution_Body_V2.zip",
    sourceArchiveSha256: "b2782b1557515d43db78a2c1507aeebb1cae99458104c450ed63ef752a675f1b",
    capabilityManifestSha256: "dbfd89654e869ad9a33917e668acca367bed34be8057c5526b710c179ebaf404",
    technicalStatus: "ENGINEERING_COMPLETE_CREATIVE_REVIEW_PENDING",
    executionBody: "Full NexMind P8 creative authority -> production-scoped authored-art execution body -> self-hosted renderer -> StudioFamilyExecutionFidelityV1 -> post-render Final Producer + independent perceptual auditor",
    truthBoundary: "The active Explainer archive is execution-only: rejected family-level creative Directors are physically absent. Real 9.5 creative certification still requires blind rendered evidence; implementation QA alone cannot award it.",
    eligibleForInternalReviewEvidence: true,
    eligibleForPublicProduction: false,
    dispatchAdapterStatus: "READY",
  },
  WHITEBOARD: {
    family: "WHITEBOARD",
    authorityId: "WHITEBOARD_EXECUTION_BODY_V2_P8_UNIFIED",
    sourceLabel: "NexStudio_Whiteboard_Execution_Body_V2.zip",
    sourceArchiveSha256: "25f87cb57d4a8ca99d004b443c0bd8df85a13d667596ddb0780d2c8f3884002c",
    capabilityManifestSha256: "a97b9397523ec827ca80200dc753a3a171b4afa3c805a255eb67b908a1c66421",
    technicalStatus: "TECHNICAL_PASS_CREATIVE_REVIEW_PENDING",
    executionBody: "NexMind P8 committed final board -> renderer-only semantic binding -> Whiteboard performance/compiler -> encoded render",
    truthBoundary: "The active Whiteboard archive is execution-only and physically excludes historical creative-director branches. Execution is a semantic scene graph bound from committed P8 semantics; style-prefix/fixed-family creative dispatch and generic substitution are forbidden. Public production remains false until live perceptual evidence clears the commercial gate.",
    eligibleForInternalReviewEvidence: true,
    eligibleForPublicProduction: false,
    dispatchAdapterStatus: "READY",
  },
  STICKMAN: {
    family: "STICKMAN",
    authorityId: "NEXSTICK_MASTER_V2_PERFORMANCE_V5_1",
    sourceLabel: "NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_2026-08-13.zip",
    sourceArchiveSha256: "67b49cc7275cd741a70f5851bf1f98d0a8cc7dbd3b1a884f458ddac789a21178",
    technicalStatus: "INTERNAL_PERFORMANCE_MASTER",
    executionBody: "NexPerformanceUnifiedV5@5.1.0-skin-safe-angular-continuity",
    truthBoundary: "Current V5.1 performance/cast capability evidence is authoritative. Direct give/receive handoff is supported; heavy carry and other unadmitted verbs remain fail-closed. Public release still requires the Studio-wide final evidence gates.",
    eligibleForInternalReviewEvidence: true,
    eligibleForPublicProduction: false,
    dispatchAdapterStatus: "READY",
  },
  EDITORIAL_MOTION: {
    family: "EDITORIAL_MOTION",
    authorityId: "EDITORIAL_EXECUTION_BODY_V2_P8_UNIFIED",
    sourceLabel: "NexStudio_Editorial_Execution_Body_V2.zip",
    sourceArchiveSha256: "b123325962778da3e1eed66cdc48cba3c396a092b3455baf8d032ed0115e3660",
    capabilityManifestSha256: "63d726d9f2bd19fec1344f2b8d06f47f5ff445ddb269993d41c3db005bfbf8ef",
    technicalStatus: "MACHINE_CERTIFIED_NO_SHIP",
    executionBody: "NexMind P8 committed final board -> renderer-only Editorial binding -> Faceless Level 5 renderer -> directed audio -> encoded render",
    truthBoundary: "The active Editorial archive is execution-only and no longer imports the historical Faceless Level1-4 creative stack. It packages and renders only the committed P8 render program. Current certified binding remains typography/composition-led; broader mixed-editorial visual range and 9.5 blind creative evidence are still open, so public production remains false.",
    eligibleForInternalReviewEvidence: true,
    eligibleForPublicProduction: false,
    dispatchAdapterStatus: "READY",
  },
};

export function familyEngineAuthority(family: StudioProductionFamily) {
  return STUDIO_FAMILY_ENGINE_AUTHORITIES[family];
}

export function assertInternalReviewEvidenceEligible(family: StudioProductionFamily) {
  const authority = familyEngineAuthority(family);
  if (!authority.eligibleForInternalReviewEvidence) throw new Error(`FAMILY_INTERNAL_REVIEW_EVIDENCE_BLOCKED:${family}`);
  return authority;
}

export function assertPublicProductionEligible(family: StudioProductionFamily) {
  const authority = familyEngineAuthority(family);
  if (!authority.eligibleForPublicProduction || authority.dispatchAdapterStatus !== "READY") {
    throw new Error(`FAMILY_PUBLIC_PRODUCTION_NOT_CERTIFIED:${family}`);
  }
  return authority;
}
