import type { StudioDashboardGateway } from "./gateway.js";
import type { ProductionDraftRecord } from "../domain/contracts.js";
import { projectFromProductionDraft } from "./production-draft-adapter.js";
import { sortDashboardProjects } from "../domain/dashboard.js";
import type { StudioAssetPage } from "../domain/assets.js";
import type { StudioBalance, StudioBillingHistory } from "../domain/billing.js";
import type { StudioBrandCollection, StudioCastCollection, StudioMemoryCollection, StudioMemoryScope, StudioSeriesCollection } from "../domain/creative-memory.js";

export interface StudioDashboardEndpointConfig {
  work: string;
  brands: string;
  cast: string;
  series: string;
  memory: string;
  assets: string;
  balance: string;
  billingHistory: string;
}

const DEFAULT_ENDPOINTS: StudioDashboardEndpointConfig = {
  work: "/api/v1/studio/productions",
  brands: "/api/v1/studio/brands",
  cast: "/api/v1/studio/cast",
  series: "/api/v1/studio/series",
  memory: "/api/v1/studio/memory",
  assets: "/api/v1/studio/assets",
  balance: "/api/v1/studio/balance",
  billingHistory: "/api/v1/studio/billing/history",
};

async function readJson<T>(fetcher: typeof fetch, url: string, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = { method: "GET", credentials: "include", headers: { Accept: "application/json" }, cache: "no-store" };
  if (signal) init.signal = signal;
  const response = await fetcher(url, init);
  if (!response.ok) throw new Error(`Studio dashboard request failed (${response.status}) for ${url}`);
  const payload = await response.json() as { data?: T } | T;
  if (payload && typeof payload === "object" && "data" in payload) return (payload as { data: T }).data;
  return payload as T;
}

function withCursor(url: string, cursor?: string | null): string {
  if (!cursor) return url;
  const join = url.includes("?") ? "&" : "?";
  return `${url}${join}cursor=${encodeURIComponent(cursor)}`;
}

export class HttpStudioDashboardGateway implements StudioDashboardGateway {
  constructor(
    private readonly fetcher: typeof fetch = fetch,
    private readonly endpoints: StudioDashboardEndpointConfig = DEFAULT_ENDPOINTS,
  ) {}

  async getWork(signal?: AbortSignal) {
    const payload = await readJson<{ productions: ProductionDraftRecord[]; fetchedAt?: string }>(this.fetcher, this.endpoints.work, signal);
    const projects = sortDashboardProjects(payload.productions.map(projectFromProductionDraft));
    return { projects, fetchedAt: payload.fetchedAt ?? new Date().toISOString() };
  }

  getBrands(signal?: AbortSignal) { return readJson<StudioBrandCollection>(this.fetcher, this.endpoints.brands, signal); }
  getCast(signal?: AbortSignal) { return readJson<StudioCastCollection>(this.fetcher, this.endpoints.cast, signal); }
  getSeries(signal?: AbortSignal) { return readJson<StudioSeriesCollection>(this.fetcher, this.endpoints.series, signal); }
  getMemory(scope: StudioMemoryScope, scopeRefId: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ scope, scopeRefId });
    return readJson<StudioMemoryCollection>(this.fetcher, `${this.endpoints.memory}?${params}`, signal);
  }
  getAssets(cursor?: string | null, signal?: AbortSignal) { return readJson<StudioAssetPage>(this.fetcher, withCursor(this.endpoints.assets, cursor), signal); }
  getBalance(signal?: AbortSignal) { return readJson<StudioBalance>(this.fetcher, this.endpoints.balance, signal); }
  getBillingHistory(cursor?: string | null, signal?: AbortSignal) { return readJson<StudioBillingHistory>(this.fetcher, withCursor(this.endpoints.billingHistory, cursor), signal); }
}
