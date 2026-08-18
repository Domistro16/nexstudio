import { humanStatusFor, type ProductionState } from "./production-state.js";

export type ProductionFamily = "EXPLAINER" | "WHITEBOARD" | "STICKMAN" | "EDITORIAL_MOTION";

export interface DashboardProject {
  id: string;
  title: string;
  family: ProductionFamily;
  videoType: string;
  state: ProductionState;
  durationSeconds: number | null;
  aspectRatio: string | null;
  coverUrl: string | null;
  previewUrl: string | null;
  updatedAt: string;
  createdAt: string;
  latestOutputUrl: string | null;
  brandId: string | null;
  seriesId: string | null;
  episodeOrdinal: number | null;
  needsAction: boolean;
  statusLabel: string;
  statusTone: "attention" | "active" | "ready" | "recovering" | "neutral";
}

export interface DashboardWorkSnapshot {
  projects: DashboardProject[];
  fetchedAt: string;
}

function timeValue(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortDashboardProjects(projects: readonly DashboardProject[]): DashboardProject[] {
  return [...projects].sort((a, b) => {
    const aHuman = humanStatusFor(a.state);
    const bHuman = humanStatusFor(b.state);
    if (aHuman.active !== bHuman.active) return aHuman.active ? -1 : 1;
    if (aHuman.needsAction !== bHuman.needsAction) return aHuman.needsAction ? -1 : 1;
    if (aHuman.priority !== bHuman.priority) return bHuman.priority - aHuman.priority;
    return timeValue(b.updatedAt) - timeValue(a.updatedAt);
  });
}

export function isProductionFamily(value: unknown): value is ProductionFamily {
  return ["EXPLAINER", "WHITEBOARD", "STICKMAN", "EDITORIAL_MOTION"].includes(String(value));
}
