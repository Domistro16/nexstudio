export type StudioAssetKind = "logo" | "image" | "video" | "document" | "audio" | "data" | "other";
export type StudioAssetStatus = "processing" | "ready" | "failed";

export interface StudioAsset {
  id: string;
  name: string;
  kind: StudioAssetKind;
  mimeType: string | null;
  sizeBytes: number | null;
  reusable: boolean;
  rightsAttested: boolean | null;
  status: StudioAssetStatus;
  previewUrl: string | null;
  sourceProductionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StudioAssetPage {
  items: StudioAsset[];
  nextCursor: string | null;
}
