import { formatMinor } from "../../domain/billing.js";
import { useStudioBalance, useStudioBillingHistory } from "../hooks.js";
import { ErrorState, LoadState } from "./shared.js";

export function BillingRoute() {
  const balance = useStudioBalance();
  const history = useStudioBillingHistory();
  if (balance.loading || history.loading) return <LoadState label="Loading billing" />;
  if (balance.error) return <ErrorState message={balance.error} onRetry={balance.refresh} />;
  if (history.error) return <ErrorState message={history.error} onRetry={history.refresh} />;
  const current = balance.data;
  const entries = history.data?.entries ?? [];
  return <section className="sf-route"><header className="sf-route-head"><div><span>Billing</span><h1>Balance and history.</h1><p>USD balance and production charges, without financial-dashboard clutter.</p></div></header>
    {current ? <article className="sf-balance"><span>Available balance</span><b>{formatMinor(current.availableMinor, current.currency)}</b>{current.pendingMinor ? <p>{formatMinor(current.pendingMinor, current.currency)} pending</p> : null}</article> : null}
    <div className="sf-ledger">{entries.length ? entries.map((entry) => <article key={entry.id}><div><b>{entry.description || entry.type.replaceAll("_", " ")}</b><small>{entry.productionId ? `Production ${entry.productionId}` : "Account"}</small></div><time dateTime={entry.createdAt}>{new Date(entry.createdAt).toLocaleDateString()}</time><strong>{entry.amountMinor > 0 ? "+" : ""}{formatMinor(entry.amountMinor, entry.currency)}</strong></article>) : <p className="sf-muted">No billing history returned.</p>}</div>
  </section>;
}
