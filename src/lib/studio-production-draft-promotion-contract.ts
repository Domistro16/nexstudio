import type { ProductionDraft } from "../domain/studio-production-draft";

/**
 * Integration contract for the engine branch. Branch C does not choose a
 * production engine or legacy Production.mode. Once a draft is claimed, the
 * engine adapter must create/ensure its authenticated Production using this
 * same id as Production.id.
 */
export type ClaimedStudioDraftPromotion = {
  id: string;
  ownerUserId: string;
  family: ProductionDraft["family"];
  videoType: string;
  prompt: string;
  sources: ProductionDraft["sources"];
  duration: number | null;
  aspectRatio: string | null;
  voicePreference: string | null;
  brandContext: Record<string, unknown> | null;
};

export function claimedStudioDraftPromotion(draft: ProductionDraft): ClaimedStudioDraftPromotion {
  if (!draft.ownerId) throw new Error("STUDIO_DRAFT_MUST_BE_CLAIMED_BEFORE_PROMOTION");
  return {
    id: draft.id,
    ownerUserId: draft.ownerId,
    family: draft.family,
    videoType: draft.videoType,
    prompt: draft.prompt,
    sources: draft.sources,
    duration: draft.duration,
    aspectRatio: draft.aspectRatio,
    voicePreference: draft.voicePreference,
    brandContext: draft.brandContext,
  };
}
