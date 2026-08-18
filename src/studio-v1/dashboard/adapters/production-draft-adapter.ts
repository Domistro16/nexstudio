import type { DashboardProject } from "../domain/dashboard.js";
import { humanStatusFor } from "../domain/production-state.js";
import type { ProductionDraftRecord } from "../domain/contracts.js";

function fallbackTitle(record: ProductionDraftRecord): string {
  const prompt = record.prompt.trim().replace(/\s+/g, " ");
  if (prompt.length >= 3) return prompt.length > 68 ? `${prompt.slice(0, 65)}…` : prompt;
  return record.videoType || "Untitled production";
}

export function projectFromProductionDraft(record: ProductionDraftRecord): DashboardProject {
  const human = humanStatusFor(record.state);
  return {
    id: record.id,
    title: record.title?.trim() || fallbackTitle(record),
    family: record.family,
    videoType: record.videoType,
    state: record.state,
    durationSeconds: record.duration,
    aspectRatio: record.aspectRatio,
    coverUrl: record.coverUrl ?? null,
    previewUrl: record.previewUrl ?? null,
    updatedAt: record.updatedAt,
    createdAt: record.createdAt,
    latestOutputUrl: record.latestOutputUrl ?? null,
    brandId: record.brandId ?? null,
    seriesId: record.seriesId ?? null,
    episodeOrdinal: record.episodeOrdinal ?? null,
    needsAction: human.needsAction,
    statusLabel: human.label,
    statusTone: human.tone,
  };
}
