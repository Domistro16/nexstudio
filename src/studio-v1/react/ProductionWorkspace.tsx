"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ProductionDraft } from "@/domain/studio-production-draft";
import { createStudioProductionDraftClient } from "@/lib/studio-production-draft-client";
import { ProductionMemoryControls } from "@/studio-v1/react/ProductionMemoryControls";

type Plan = { status: "ready"; planPreviewId: string; thesis: string; recommendedDuration: number; beats: Array<{ start: number; end: number; purposeTitle: string; description: string }>; missingInput: string[]; complimentaryPassConsumed: true; replayed: boolean };
type Quote = { quoteId: string; approvedDurationSeconds: number; baseAmountMinor: number; finalAmountMinor: number; displayAmount: string; currency: "USD"; discount: null | { code: string; percent: number; amountMinor: number }; accountBalanceMinor: number; amountRequiredMinor: number; sufficientBalance: boolean; expiresAt: string };
type WorkflowProjection = { workflowRunId: string; status: string; phase: string; title: string; detail: string; needsUserAction: boolean; events: Array<{ type: string; at: string }> };
type VersionSummary = { currentVersionNumber: number | null; versions: Array<{ id:string; versionNumber:number; approvedAt:string|null; createdAt:string; isCurrent:boolean }> };

async function dataResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null) as { data?: T; detail?: string; code?: string } | null;
  if (!response.ok) throw new Error(body?.code || body?.detail || `REQUEST_FAILED_${response.status}`);
  return body?.data as T;
}

function DraftHeader({ draft }: { draft: ProductionDraft }) {
  return <div className="sv1-production-identity"><span>{draft.family.replaceAll("_", " ")}</span><strong>{draft.videoType.replaceAll("-", " ")}</strong></div>;
}

export function ProductionWorkspace({ draftId, authenticated, continueAfterAuth = false }: { draftId: string; authenticated: boolean; continueAfterAuth?: boolean }) {
  const router = useRouter();
  const client = useMemo(() => typeof window === "undefined" ? null : createStudioProductionDraftClient(), []);
  const [draft, setDraft] = useState<ProductionDraft | null>(null);
  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState<"loading"|"saving"|"planning"|"quote"|"purchase"|null>("loading");
  const [error, setError] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const authDialogRef = useRef<HTMLElement | null>(null);
  const authEmailRef = useRef<HTMLInputElement | null>(null);
  const authReturnFocusRef = useRef<HTMLElement | null>(null);
  const [fundingMessage, setFundingMessage] = useState("");
  const [workflow, setWorkflow] = useState<WorkflowProjection | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [revisionNote, setRevisionNote] = useState("");
  const [revisionTime, setRevisionTime] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");
  const [versionSummary, setVersionSummary] = useState<VersionSummary | null>(null);
  const [viewVersion, setViewVersion] = useState<number | null>(null);
  const fundingReturnHandled = useRef(false);

  const loadPlan = useCallback(async () => {
    if (!authenticated) return null;
    const response = await fetch(`/api/v1/studio/plan-preview?productionId=${encodeURIComponent(draftId)}`, { credentials: "same-origin" });
    const value = await dataResponse<Plan | null>(response);
    if (value) setPlan(value);
    return value;
  }, [authenticated, draftId]);

  const loadWorkflow = useCallback(async () => {
    if (!authenticated) return null;
    try {
      const value = await dataResponse<WorkflowProjection>(await fetch(`/api/v1/studio/productions/${encodeURIComponent(draftId)}/workflow`, { credentials: "same-origin", cache: "no-store" }));
      setWorkflow(value);
      return value;
    } catch { return null; }
  }, [authenticated, draftId]);

  const loadVersions = useCallback(async () => {
    if (!authenticated) return null;
    try {
      const value = await dataResponse<VersionSummary>(await fetch(`/api/v1/studio/productions/${encodeURIComponent(draftId)}/versions`, { credentials: "same-origin", cache: "no-store" }));
      setVersionSummary(value);
      setViewVersion((current) => current ?? value.currentVersionNumber);
      return value;
    } catch { return null; }
  }, [authenticated, draftId]);

  const runPlan = useCallback(async (current: ProductionDraft) => {
    if (!authenticated) return;
    setBusy("planning"); setError("");
    try {
      const response = await fetch("/api/v1/studio/plan-preview", {
        method: "POST", credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-plan:${current.id}:${current.updatedAt}` },
        body: JSON.stringify({ productionId: current.id }),
      });
      const value = await dataResponse<Plan | { status: "needs_input"; missingInput: string[] }>(response);
      if (value.status === "needs_input") { setError(value.missingInput.join(" ")); return; }
      setPlan(value as Plan);
      const resumed = await client?.resume(current.id); if (resumed) { setDraft(resumed.draft); setPrompt(resumed.draft.prompt); }
    } catch (reason) { setError(reason instanceof Error && reason.message === "COMPLIMENTARY_PLAN_ALREADY_USED" ? "This account's complimentary planning pass has already been used." : "The Studio could not shape this plan yet. Your brief remains saved."); }
    finally { setBusy(null); }
  }, [authenticated, client]);

  useEffect(() => {
    if (!client) return;
    let cancelled = false;
    (async () => {
      setBusy("loading");
      try {
        let resumed;
        if (authenticated && continueAfterAuth) resumed = await client.claimAfterAuth(draftId);
        else resumed = await client.resume(draftId);
        if (!resumed || cancelled) return;
        setDraft(resumed.draft); setPrompt(resumed.draft.prompt);
        if (authenticated && new Set(["PLAN_READY","PAYMENT_REQUIRED","INSUFFICIENT_BALANCE","PAYMENT_PENDING","PRODUCTION","FINAL_REVIEW","COMPLETE","REVISION_REQUESTED"]).has(resumed.draft.state)) await loadPlan().catch(() => null);
        if (authenticated && continueAfterAuth && resumed.draft.state === "DRAFT") await runPlan(resumed.draft);
      } catch { if (!cancelled) setError("This production could not be resumed. If it was a guest draft, use the same browser where it was started."); }
      finally { if (!cancelled) setBusy(null); }
    })();
    return () => { cancelled = true; };
  }, [authenticated, client, continueAfterAuth, draftId, loadPlan, runPlan]);

  useEffect(() => {
    if (!authOpen) return;
    authReturnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    requestAnimationFrame(() => authEmailRef.current?.focus());
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setAuthOpen(false); return; }
      if (event.key !== "Tab" || !authDialogRef.current) return;
      const focusables = [...authDialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')];
      if (!focusables.length) return;
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); authReturnFocusRef.current?.focus(); };
  }, [authOpen]);

  useEffect(() => {
    if (!authenticated || !client || !draft || fundingReturnHandled.current || typeof window === "undefined") return;
    const currentUrl = new URL(window.location.href);
    const sessionId = currentUrl.searchParams.get("session_id");
    const fundingState = currentUrl.searchParams.get("funding");
    if (!sessionId || fundingState !== "success") return;
    fundingReturnHandled.current = true;
    (async () => {
      setFundingMessage("Confirming your payment.");
      await fetch("/api/v1/studio/funding-intents/reconcile", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ sessionId }) }).catch(() => null);
      const resumed = await client.resume(draftId).catch(() => null);
      if (resumed) setDraft(resumed.draft);
      const clean = new URL(window.location.href);
      clean.searchParams.delete("session_id");
      clean.searchParams.delete("funding");
      window.history.replaceState(null, "", clean.pathname + clean.search);
      setFundingMessage("");
    })();
  }, [authenticated, client, draft, draftId]);

  useEffect(() => {
    if (!authenticated || !draft || quote || !new Set(["PAYMENT_REQUIRED","INSUFFICIENT_BALANCE"]).has(draft.state)) return;
    let cancelled = false;
    (async () => {
      try {
        const value = await dataResponse<Quote>(await fetch(`/api/v1/studio/productions/${draft.id}/quote`, { method: "POST", credentials: "same-origin" }));
        if (!cancelled) setQuote(value);
      } catch { /* The saved production stays recoverable; manual quote retry remains available. */ }
    })();
    return () => { cancelled = true; };
  }, [authenticated, draft?.id, draft?.state, quote]);

  useEffect(() => {
    if (!authenticated || !client || !draft || draft.state !== "PAYMENT_PENDING") return;
    let cancelled = false;
    const tick = async () => {
      const resumed = await client.resume(draftId).catch(() => null);
      if (resumed && !cancelled && resumed.draft.state !== "PAYMENT_PENDING") setDraft(resumed.draft);
    };
    void tick();
    const timer = window.setInterval(() => { void tick(); }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [authenticated, client, draft?.state, draftId]);

  useEffect(() => {
    if (!authenticated || !draft || !new Set(["FINAL_REVIEW","COMPLETE"]).has(draft.state)) return;
    void loadVersions();
  }, [authenticated, draft?.state, loadVersions]);

  useEffect(() => {
    if (!authenticated || !client || !draft || !new Set(["PRODUCTION","TECHNICAL_RETRY","PRODUCTION_FAILED"]).has(draft.state)) return;
    let cancelled = false;
    const tick = async () => {
      const value = await loadWorkflow();
      if (cancelled || !value) return;
      const resumed = await client.resume(draftId).catch(() => null);
      if (resumed && !cancelled) setDraft(resumed.draft);
    };
    void tick();
    const timer = window.setInterval(() => { void tick(); }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [authenticated, client, draft?.state, draftId, loadWorkflow]);

  async function saveBrief() {
    if (!client || !draft) return;
    if (!prompt.trim()) { setError("Tell us what you want to make."); return; }
    setBusy("saving"); setError("");
    const result = await client.update(draft.id, { prompt: prompt.trim() });
    setDraft(result.draft); setPrompt(result.draft.prompt); setBusy(null);
  }

  async function develop() {
    if (!client || !draft) return;
    let current = draft;
    if (prompt.trim() !== draft.prompt) {
      const saved = await client.update(draft.id, { prompt: prompt.trim() }); current = saved.draft; setDraft(current);
    }
    if (!authenticated) {
      await client.beginAuthHandoff(draft.id); setAuthOpen(true); return;
    }
    await runPlan(current);
  }

  async function requestEmailSignIn() {
    if (!draft || !email.includes("@")) return;
    setAuthMessage("");
    const next = `/production/${draft.id}?claim=1&continue=1`;
    const response = await fetch("/api/v1/auth/email/request", {
      method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json", "Idempotency-Key": `studio-auth:${draft.id}:${crypto.randomUUID()}` },
      body: JSON.stringify({ email, next }),
    });
    setAuthMessage(response.ok ? "Check your email. This exact production is saved and will reopen from the same point." : "The sign-in link could not be sent. Your production is still saved.");
  }

  async function approvePlan() {
    if (!draft) return;
    setBusy("quote"); setError("");
    try {
      const value = await dataResponse<Quote>(await fetch(`/api/v1/studio/productions/${draft.id}/quote`, { method: "POST", credentials: "same-origin" }));
      setQuote(value);
      const resumed = await client?.resume(draft.id); if (resumed) setDraft(resumed.draft);
    } catch { setError("The price could not be prepared. The plan remains saved."); }
    finally { setBusy(null); }
  }

  async function purchase() {
    if (!draft || !quote) return;
    setBusy("purchase"); setError("");
    try {
      const response = await fetch(`/api/v1/studio/productions/${draft.id}/purchase`, {
        method: "POST", credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-purchase:${draft.id}:${quote.quoteId}` },
        body: JSON.stringify({ quoteId: quote.quoteId }),
      });
      const body = await response.json().catch(() => null) as { data?: { ok: boolean; code?: string; amountRequiredMinor?: number }; code?: string; detail?: string } | null;
      if (response.status === 409 && body?.data?.code === "INSUFFICIENT_BALANCE") {
        setError(`Add $${((body.data.amountRequiredMinor ?? 0) / 100).toFixed(2)} to continue. Your plan remains saved.`);
        const resumed = await client?.resume(draft.id); if (resumed) setDraft(resumed.draft);
        return;
      }
      if (!response.ok) throw new Error(body?.code || body?.detail || `REQUEST_FAILED_${response.status}`);
      const result = body?.data;
      if (!result?.ok) { setError("Your production is saved. Add the required balance and continue from this same point."); return; }
      const resumed = await client?.resume(draft.id); if (resumed) setDraft(resumed.draft);
    } catch (reason) { setError(reason instanceof Error && reason.message === "INSUFFICIENT_BALANCE" ? "Add balance to continue. Your plan remains saved." : "The purchase could not be confirmed. Do not retry with a different payment until this request resolves."); }
    finally { setBusy(null); }
  }

  function revisionTimestampSeconds() {
    const raw = revisionTime.trim();
    if (!raw) return null;
    if (/^\d+(?:\.\d+)?$/.test(raw)) return Number(raw);
    const match = raw.match(/^(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.(\d+))?$/);
    if (!match) return null;
    const hours = Number(match[1] || 0), minutes = Number(match[2] || 0), seconds = Number(match[3] || 0), fraction = Number(`0.${match[4] || 0}`);
    return hours * 3600 + minutes * 60 + seconds + fraction;
  }

  async function submitReview(action: "approve" | "revision") {
    if (!draft || reviewBusy) return;
    if (action === "revision" && revisionNote.trim().length < 2) { setReviewMessage("Tell the Studio what should change."); return; }
    if (action === "revision" && revisionTime.trim() && revisionTimestampSeconds() === null) { setReviewMessage("Use a timestamp like 00:18, or leave it blank for a whole-film change."); return; }
    setReviewBusy(true); setReviewMessage(""); setError("");
    try {
      const payload = action === "approve" ? { action } : { action, note: revisionNote.trim(), timestampSeconds: revisionTimestampSeconds() };
      const response = await fetch(`/api/v1/productions/${draft.id}/review`, {
        method: "POST", credentials: "same-origin",
        headers: { "content-type": "application/json", "Idempotency-Key": `studio-review:${draft.id}:${action}:${crypto.randomUUID()}` },
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => null) as { data?: { action?: string }; detail?: string; code?: string } | null;
      if (!response.ok) throw new Error(body?.detail || body?.code || "REVIEW_SAVE_FAILED");
      const resumed = await client?.resume(draft.id).catch(() => null);
      if (resumed) { setDraft(resumed.draft); setPrompt(resumed.draft.prompt); }
      if (action === "revision") { setReviewOpen(false); setReviewMessage("Your changes are attached to this same paid production."); }
    } catch (reason) {
      setReviewMessage(reason instanceof Error ? reason.message : "The review could not be saved. The finished version remains available.");
      const resumed = await client?.resume(draft.id).catch(() => null); if (resumed) setDraft(resumed.draft);
    } finally { setReviewBusy(false); }
  }

  async function requestFunding() {
    setFundingMessage("");
    const response = await fetch("/api/v1/studio/funding-intents", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json", "Idempotency-Key": `studio-funding:${draftId}:${quote?.quoteId || "balance"}` }, body: JSON.stringify({ productionId: draftId, quoteId: quote?.quoteId, purpose: "EXACT_PRODUCTION" }) });
    const body = await response.json().catch(() => null) as { data?: { checkoutUrl?: string | null }; detail?: string } | null;
    if (response.ok && body?.data?.checkoutUrl) { window.location.assign(body.data.checkoutUrl); return; }
    setFundingMessage(response.ok ? "Funding is pending confirmation." : body?.detail || "Online funding is unavailable. Your production remains saved.");
  }

  if (busy === "loading" && !draft) return <div className="sv1-root sv1-calm"><main className="sv1-room sv1-center" aria-busy="true"><div className="sv1-static-status"><p className="sv1-kicker">Production</p><strong>Opening your saved production.</strong><span>No progress is simulated while the production is loading.</span></div></main></div>;
  if (!draft) return <div className="sv1-root sv1-calm"><main className="sv1-room"><div className="sv1-gate-message"><strong>Production unavailable.</strong><p>{error || "This draft could not be opened."}</p><button className="sv1-primary" onClick={() => router.push("/")}>Back to Studio</button></div></main></div>;

  const state = draft.state;
  const productionEnvironment = new Set(["PRODUCTION","FINAL_REVIEW","REVISION_REQUESTED","TECHNICAL_RETRY","PRODUCTION_FAILED"]).has(state);
  return <div className={`sv1-root ${productionEnvironment ? "sv1-production" : "sv1-calm"}`} data-environment={productionEnvironment ? "production" : "calm"} data-phase={state.toLowerCase()}>
    <header className="sv1-header"><button className="sv1-wordmark" onClick={() => router.push("/")}><i>·</i><span>Studio</span></button><nav><button onClick={() => router.push("/dashboard")}>{authenticated ? "Dashboard" : "Home"}</button></nav></header>
    <main className="sv1-room">
      <DraftHeader draft={draft}/>
      {state === "DRAFT" || state === "AUTH_REQUIRED" || state === "PLANNING" ? <>
        {busy === "planning" || state === "PLANNING" ? <section className="sv1-thinking" aria-busy="true"><div><p className="sv1-kicker">Complimentary plan</p><h1>Your brief is being developed.</h1><p>The brief is saved. This surface changes only when the real plan is ready or the Studio needs more information.</p></div></section> : <><div className="sv1-room-head"><p className="sv1-kicker">Your brief</p><h1>Tell us what to make.</h1><p>Your first idea stays attached to this production from here forward.</p></div><div className="sv1-brief-grid"><section className="sv1-brief-main"><textarea rows={10} value={prompt} onChange={(event) => setPrompt(event.currentTarget.value)} style={{ viewTransitionName: "production-prompt" }}/><div className="sv1-saved-line"><span>Saved brief</span><span className="sv1-info" tabIndex={0}>i<span>Videos are billed by finished duration. The current rate is $2 per minute. The exact total appears only after you approve the plan.</span></span></div></section><aside className="sv1-brief-options"><label>Length</label><strong>{draft.duration ? `${draft.duration}s` : "Auto"}</strong><label>Format</label><strong>{draft.aspectRatio || "Auto"}</strong><label>Voice</label><strong>{draft.voicePreference || "Studio decides"}</strong></aside></div><div className="sv1-room-actions"><button className="sv1-secondary" onClick={saveBrief} disabled={busy === "saving"}>Save</button><button className="sv1-primary" onClick={develop}>Develop my video</button></div></>}
      </> : null}

      {state === "PLAN_READY" && plan ? <section className="sv1-plan"><div className="sv1-room-head"><p className="sv1-kicker">Production plan</p><h1>Here’s how the story will move.</h1><p>{plan.thesis}</p></div><div className="sv1-plan-beats">{plan.beats.map((beat) => <article key={`${beat.start}-${beat.end}`}><time>{beat.start}–{beat.end} sec</time><div><strong>{beat.purposeTitle}</strong><p>{beat.description}</p></div></article>)}</div><div className="sv1-room-actions"><button className="sv1-secondary" onClick={() => { setPrompt(draft.prompt); setError("To change the creative intent, edit the brief. A new free plan is not automatically granted."); }}>Adjust brief</button><button className="sv1-primary" onClick={approvePlan} disabled={busy === "quote"}>Approve plan</button></div></section> : null}

      {authenticated ? <ProductionMemoryControls productionId={draft.id} state={draft.state}/> : null}

      {(state === "PAYMENT_REQUIRED" || state === "INSUFFICIENT_BALANCE" || state === "PAYMENT_PENDING") ? <section className="sv1-payment"><div className="sv1-room-head"><p className="sv1-kicker">Ready to produce</p><h1>Start the production.</h1><p>The plan is approved. Payment is the boundary between planning and the full Studio production system.</p></div>{quote ? <div className="sv1-payment-card"><div><span>Production</span><strong>{quote.displayAmount}</strong>{quote.discount ? <small>First production · {quote.discount.percent}% welcome rate applied automatically</small> : null}</div><dl><div><dt>Finished duration</dt><dd>{quote.approvedDurationSeconds}s</dd></div><div><dt>Your balance</dt><dd>${(quote.accountBalanceMinor/100).toFixed(2)}</dd></div>{quote.amountRequiredMinor ? <div><dt>Amount needed</dt><dd>${(quote.amountRequiredMinor/100).toFixed(2)}</dd></div> : null}</dl><div className="sv1-room-actions">{quote.sufficientBalance ? <button className="sv1-primary" onClick={purchase} disabled={busy === "purchase"}>Approve & produce</button> : <button className="sv1-primary" onClick={requestFunding}>Add balance & continue</button>}</div>{fundingMessage ? <p className="sv1-quiet">{fundingMessage}</p> : null}</div> : <div className="sv1-room-actions"><button className="sv1-primary" onClick={approvePlan}>Prepare price</button></div>}</section> : null}

      {(state === "PRODUCTION" || state === "TECHNICAL_RETRY") ? <section className="sv1-production-room" style={{ viewTransitionName: "production-film" }} aria-live="polite"><div className="sv1-room-head"><p className="sv1-kicker">Production</p><h1>{workflow?.title || "Production is underway."}</h1><p>{workflow?.detail || "The approved plan and paid production are secure. Status shown here comes from the production workflow."}</p></div><div className="sv1-stage-line" aria-label="Production stages"><span className="done">Paid</span><span className={new Set(["PREPARING","SHAPING_STORY","VISUAL_DIRECTION","DIRECTING_FILM"]).has(workflow?.phase || "PREPARING") ? "active" : workflow ? "done" : "active"}>Direction</span><span className={workflow?.phase === "DIRECTING_PERFORMANCE" ? "active" : new Set(["DESIGNING_SOUND","INTERNAL_REVIEW","CREATIVE_LOCKED"]).has(workflow?.phase || "") ? "done" : ""}>Performance</span><span className={workflow?.phase === "DESIGNING_SOUND" ? "active" : new Set(["INTERNAL_REVIEW","CREATIVE_LOCKED"]).has(workflow?.phase || "") ? "done" : ""}>Sound</span><span className={workflow?.phase === "INTERNAL_REVIEW" ? "active" : workflow?.phase === "CREATIVE_LOCKED" ? "done" : ""}>Review</span><span className={new Set(["CREATIVE_LOCKED","FINAL_PRODUCTION"]).has(workflow?.phase || "") ? "active" : ""}>Final film</span></div><div className="sv1-production-evidence"><strong>{workflow?.status === "PROVIDER_UNAVAILABLE" ? "Paused safely" : workflow?.phase === "CREATIVE_LOCKED" ? "Quality gate passed" : "In production"}</strong><span>{workflow?.status === "PROVIDER_UNAVAILABLE" ? "Your paid production remains intact." : "No percentage or finish time is invented."}</span></div></section> : null}
      {state === "FINAL_REVIEW" ? <section className="sv1-review-room"><div className="sv1-review-heading"><div className="sv1-room-head"><p className="sv1-kicker">Screening room</p><h1>Watch the finished film.</h1><p>Approve the current version, download it, or request a precise change. Earlier versions remain available for comparison.</p></div>{versionSummary?.versions.length ? <div className="sv1-version-control"><label htmlFor="sv1-version-select">Version</label><select id="sv1-version-select" value={viewVersion ?? versionSummary.currentVersionNumber ?? ""} onChange={(event)=>setViewVersion(Number(event.currentTarget.value))}>{versionSummary.versions.map((version)=><option key={version.id} value={version.versionNumber}>v{version.versionNumber}{version.isCurrent?" · current":""}</option>)}</select></div> : null}</div><div className="sv1-screening"><video key={viewVersion ?? "current"} controls playsInline preload="metadata" src={`/api/v1/productions/${draft.id}/output?disposition=inline${viewVersion ? `&version=${viewVersion}` : ""}`}/></div>{versionSummary?.currentVersionNumber && viewVersion && viewVersion !== versionSummary.currentVersionNumber ? <div className="sv1-version-note" role="status"><span>Viewing v{viewVersion}</span><p>Approval and revisions stay attached to the current version.</p><button className="sv1-secondary" onClick={()=>setViewVersion(versionSummary.currentVersionNumber)}>Return to v{versionSummary.currentVersionNumber}</button></div> : <div className="sv1-room-actions sv1-review-actions"><a className="sv1-secondary sv1-action-link" href={`/api/v1/productions/${draft.id}/output${viewVersion ? `?version=${viewVersion}` : ""}`} download>Download {viewVersion ?? versionSummary?.currentVersionNumber ? `v${viewVersion ?? versionSummary?.currentVersionNumber}` : "film"}</a><button className="sv1-secondary" onClick={() => setReviewOpen((value) => !value)} disabled={reviewBusy}>Request changes</button><button className="sv1-primary" onClick={() => submitReview("approve")} disabled={reviewBusy}>Approve current version</button></div>}{reviewOpen && (!versionSummary?.currentVersionNumber || !viewVersion || viewVersion === versionSummary.currentVersionNumber) ? <div className="sv1-revision-panel"><div><label htmlFor="sv1-revision-time">Timestamp <span>optional</span></label><input id="sv1-revision-time" value={revisionTime} onChange={(event) => setRevisionTime(event.currentTarget.value)} placeholder="00:18" inputMode="decimal"/></div><div className="wide"><label htmlFor="sv1-revision-note">What should change?</label><textarea id="sv1-revision-note" value={revisionNote} onChange={(event) => setRevisionNote(event.currentTarget.value)} rows={3} placeholder="Describe the change and what should stay untouched."/></div><button className="sv1-primary" onClick={() => submitReview("revision")} disabled={reviewBusy || revisionNote.trim().length < 2}>Send changes</button><p className="sv1-quiet wide">This remains the same paid production. The next finished film becomes a new version; earlier versions stay in its history.</p></div> : null}{reviewMessage ? <p className="sv1-auth-message" role="status">{reviewMessage}</p> : null}</section> : null}
      {state === "COMPLETE" ? <section><div className="sv1-room-head"><p className="sv1-kicker">Complete</p><h1>Ready.</h1><p>This production now lives in your Dashboard.</p></div><button className="sv1-primary" onClick={() => router.push("/dashboard")}>Open Dashboard</button></section> : null}
      {state === "PRODUCTION_FAILED" ? <section><div className="sv1-room-head"><p className="sv1-kicker">Recovery</p><h1>Production recovery is in progress.</h1><p>Your paid production, approved plan and original brief are preserved. Studio is continuing the same work without creating a second charge.</p></div></section> : null}
      {state === "REVISION_REQUESTED" ? <section><div className="sv1-room-head"><p className="sv1-kicker">Revision</p><h1>Your changes are attached to this production.</h1></div></section> : null}
      {error ? <p className="sv1-error">{error}</p> : null}
    </main>

    {authOpen ? <div className="sv1-modal-backdrop" role="presentation" onMouseDown={(event)=>{if(event.currentTarget===event.target)setAuthOpen(false)}}><section ref={authDialogRef} className="sv1-modal" role="dialog" aria-modal="true" aria-labelledby="studio-auth-title"><button className="sv1-close" onClick={() => setAuthOpen(false)} aria-label="Close sign in">×</button><p className="sv1-kicker">Your draft is already saved</p><h2 id="studio-auth-title">Keep this production.</h2><p>Sign in or create an account to continue. Nothing you entered will be lost.</p><div className="sv1-saved-preview"><span>Saved brief</span><p>{prompt}</p><span className="sv1-info" tabIndex={0}>i<span>Videos are billed by finished duration at $2 per minute. You’ll see the exact total after the complimentary plan, before paid production begins.</span></span></div><label className="sv1-visually-hidden" htmlFor="studio-auth-email">Email address</label><input ref={authEmailRef} id="studio-auth-email" value={email} onChange={(event) => setEmail(event.currentTarget.value)} type="email" inputMode="email" autoComplete="email" placeholder="Email address"/><button className="sv1-primary full" onClick={requestEmailSignIn} disabled={!email.includes("@")}>Continue with email</button>{authMessage ? <p className="sv1-auth-message">{authMessage}</p> : null}</section></div> : null}
  </div>;
}
