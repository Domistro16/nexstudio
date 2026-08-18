export type StudioMemoryScope = "ACCOUNT" | "BRAND" | "CAST" | "SERIES" | "PRODUCTION";
export type StudioMemoryEffectiveState = "ACTIVE" | "INACTIVE" | "DELETED";

export interface StudioMemoryVersionRecord {
  id: string;
  versionNumber: number;
  effectiveState: StudioMemoryEffectiveState;
  effectiveFrom: string;
  effectiveUntil: string | null;
  effectiveFromEpisodeOrdinal: number | null;
  effectiveUntilEpisodeOrdinal: number | null;
  content: Record<string, unknown>;
  contentHash: string;
  provenance: Record<string, unknown>;
  sourceProductionId: string | null;
  sourceProductionVersionId: string | null;
  createdByType: string;
  createdById: string | null;
  reason: string | null;
  createdAt: string;
}

export interface StudioMemoryItemRecord {
  id: string;
  ownerUserId: string;
  scope: StudioMemoryScope;
  scopeRefId: string;
  key: string;
  category: string;
  label: string | null;
  currentVersion: number;
  createdAt: string;
  updatedAt: string;
  versions: StudioMemoryVersionRecord[];
}

export interface StudioBrandRoot {
  id: string;
  ownerUserId: string;
  name: string;
  slug: string | null;
  description: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StudioCastRoot {
  id: string;
  ownerUserId: string;
  brandId: string | null;
  name: string;
  assetNamespace: "CAST" | string;
  identityKey: string;
  createdAt: string;
  updatedAt: string;
}

export interface StudioSeriesEpisodeRoot {
  id: string;
  seriesId: string;
  productionId: string;
  episodeOrdinal: number;
  title: string | null;
  createdAt: string;
}

export interface StudioSeriesRoot {
  id: string;
  ownerUserId: string;
  brandId: string | null;
  name: string;
  description: string | null;
  createdAt: string;
  updatedAt: string;
  episodes: StudioSeriesEpisodeRoot[];
}

export interface StudioBrandCollection { brands: StudioBrandRoot[]; }
export interface StudioCastCollection { cast: StudioCastRoot[]; performanceAuthority: Record<string, unknown>; }
export interface StudioSeriesCollection { series: StudioSeriesRoot[]; productionFamily: false; }
export interface StudioMemoryCollection { memories: StudioMemoryItemRecord[]; customerControl: { inspect: boolean; editByAppendOnlyVersion: boolean; deleteByTombstone: boolean; }; }
