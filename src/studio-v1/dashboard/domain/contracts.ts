import type { ProductionFamily } from "./dashboard.js";
import type { ProductionState } from "./production-state.js";

export interface ProductionDraftRecord {
  id: string;
  ownerId: string | null;
  anonymousSessionId: string | null;
  family: ProductionFamily;
  videoType: string;
  prompt: string;
  sources: unknown[];
  duration: number | null;
  aspectRatio: string | null;
  voicePreference: unknown | null;
  brandContext: unknown | null;
  createdAt: string;
  updatedAt: string;
  state: ProductionState;
  title?: string | null;
  coverUrl?: string | null;
  previewUrl?: string | null;
  latestOutputUrl?: string | null;
  brandId?: string | null;
  seriesId?: string | null;
  episodeOrdinal?: number | null;
}
