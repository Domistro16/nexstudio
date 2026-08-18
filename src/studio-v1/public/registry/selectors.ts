import { FAMILY_IDS, type FamilyId, type ProductionRegistry, type ProductionVideoType } from "./types";

export function hasVerifiedCapabilityContract(videoType: ProductionVideoType): boolean {
  const verification = videoType.capabilityContract.verification;
  return (
    verification.status === "verified" &&
    Boolean(verification.verifiedAt) &&
    Boolean(verification.verifier) &&
    Boolean(verification.evidence?.length)
  );
}

export function hasPublicPreviewAssets(videoType: ProductionVideoType): boolean {
  return Boolean(videoType.previewVideo?.src && videoType.posterFrame);
}

/**
 * Strong public gate: the publishing switch, verified production support and real preview assets
 * must all be present. This intentionally fails closed.
 */
export function isPublicVideoType(videoType: ProductionVideoType): boolean {
  return videoType.publicEnabled && hasVerifiedCapabilityContract(videoType) && hasPublicPreviewAssets(videoType);
}

export function getPublicVideoTypes(registry: ProductionRegistry, family: FamilyId): readonly ProductionVideoType[] {
  return registry.videoTypes.filter((item) => item.family === family && isPublicVideoType(item));
}

export function getFamilyVideoTypes(registry: ProductionRegistry, family: FamilyId): readonly ProductionVideoType[] {
  return registry.videoTypes.filter((item) => item.family === family);
}

export function getVideoType(registry: ProductionRegistry, videoTypeId: string): ProductionVideoType | undefined {
  return registry.videoTypes.find((item) => item.id === videoTypeId);
}

export function assertRegistryIntegrity(registry: ProductionRegistry): void {
  const familySet = new Set(registry.families.map((family) => family.id));
  const expectedFamilies = new Set(FAMILY_IDS);

  if (familySet.size !== expectedFamilies.size || FAMILY_IDS.some((family) => !familySet.has(family))) {
    throw new Error(`Registry must contain exactly these launch families: ${FAMILY_IDS.join(", ")}.`);
  }

  const ids = new Set<string>();
  for (const item of registry.videoTypes) {
    if (!familySet.has(item.family)) throw new Error(`Unknown family on video type: ${item.id}`);
    if (ids.has(item.id)) throw new Error(`Duplicate video type id: ${item.id}`);
    ids.add(item.id);

    if (item.publicEnabled && !hasVerifiedCapabilityContract(item)) {
      throw new Error(`Public video type ${item.id} is missing verified production evidence.`);
    }
    if (item.publicEnabled && !hasPublicPreviewAssets(item)) {
      throw new Error(`Public video type ${item.id} is missing a real preview video or poster frame.`);
    }
  }
}
