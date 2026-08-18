import { useCallback, useEffect, useState } from "react";
import type { StudioMemoryScope } from "../domain/creative-memory.js";
import { useStudioDashboardGateway } from "./context.js";

export interface AsyncState<T> { data: T | null; loading: boolean; error: string | null; refresh: () => void; }

function useAsyncResource<T>(loader: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(null);
    loader(controller.signal).then((value) => { if (!controller.signal.aborted) setData(value); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Unable to load Studio data."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [loader, version]);
  return { data, loading, error, refresh };
}

export function useStudioWork() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getWork(signal), [gateway])); }
export function useStudioBrands() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getBrands(signal), [gateway])); }
export function useStudioCast() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getCast(signal), [gateway])); }
export function useStudioSeries() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getSeries(signal), [gateway])); }
export function useStudioMemory(scope: StudioMemoryScope, scopeRefId: string | null) {
  const gateway = useStudioDashboardGateway();
  return useAsyncResource(useCallback((signal: AbortSignal) => scopeRefId ? gateway.getMemory(scope, scopeRefId, signal) : Promise.resolve({ memories: [], customerControl: { inspect: true, editByAppendOnlyVersion: true, deleteByTombstone: true } }), [gateway, scope, scopeRefId]));
}
export function useStudioAssets() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getAssets(null, signal), [gateway])); }
export function useStudioBalance() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getBalance(signal), [gateway])); }
export function useStudioBillingHistory() { const gateway = useStudioDashboardGateway(); return useAsyncResource(useCallback((signal: AbortSignal) => gateway.getBillingHistory(null, signal), [gateway])); }
