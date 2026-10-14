"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { formatUSD, MindSpark, route, useStudio, type ContextChip } from "../App";
import { studioApi, type EngineKind } from "../api";
import { ensureNxPresence } from "../nx-presence";
import AvatarStage from "../cast/AvatarStage";
import { PICKER_ENVIRONMENTS, environmentImage } from "../cast/environments";
import { normalizeCastSpec, type CastMember } from "../cast/spec";

export type FlowStage = "mind" | "direction" | "closed" | "production" | "review" | "publish" | "revision";

export interface FlowState {
  stage: FlowStage;
  productionId?: string;
  prompt?: string;
  contexts?: ContextChip[];
  family?: string | null;
  videoType?: string | null;
  duration?: number;
  aspectRatio?: string;
  thesis?: string;
  beats?: Array<{ start: number; end: number; purposeTitle: string; description: string }>;
  quoteId?: string;
  amountMinor?: number;
  jobKind?: EngineKind;
  jobId?: string;
  jobOutputs?: Record<string, string>;
  engine?: { wbType?: string; wbTheme?: string; wbAccent?: string; style?: string; voice?: string; speed?: string };
  script?: string;
  generatedScript?: string;
  generatedTitle?: string;
  error?: string;
}

export interface FlowApi {
  openFlow: (f: FlowState) => void;
  closeFlow: () => void;
  patchFlow: (p: Partial<FlowState>) => void;
  notify: (m: string) => void;
  openSeries?: (id: string | null) => void;
}

const FAMILY_LABEL: Record<string, string> = {
  explainer: "Explainer", EXPLAINER: "Explainer",
  whiteboard: "Whiteboard", WHITEBOARD: "Whiteboard",
  presenter: "Presenter", PRESENTER: "Presenter",
};

function engineKindOf(family?: string | null): EngineKind | null {
  const f = (family ?? "explainer").toLowerCase();
  if (f === "whiteboard") return "whiteboard";
  if (f === "explainer") return "explainer";
  if (f === "presenter") return "presenter";
  return null;
}

const MS_VOICES = [
  { id: "emma", label: "Emma", tag: "US" }, { id: "ava", label: "Ava", tag: "US" },
  { id: "andrew", label: "Andrew", tag: "US" }, { id: "brian", label: "Brian", tag: "US" },
  { id: "sonia", label: "Sonia", tag: "UK" }, { id: "natasha", label: "Natasha", tag: "AU" },
];

function PreviewChip({ video, label, desc, selected, onSelect }: { video: string; label: string; desc?: string; selected: boolean; onSelect: () => void }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const play = () => { const v = ref.current; if (v) { v.currentTime = 0; void v.play().catch(() => {}); } };
  const stop = () => { const v = ref.current; if (v) { v.pause(); v.currentTime = 0; } };
  return (
    <button type="button" className={`opt-chip preview ${selected ? "on" : ""}`}
      onMouseEnter={play} onMouseLeave={stop}
      onClick={() => { onSelect(); play(); }}>
      <span className="preview-frame"><video ref={ref} muted loop playsInline preload="metadata" src={video} /></span>
      <span className="preview-copy"><b>{label}</b>{desc ? <span>{desc}</span> : null}</span>
    </button>
  );
}

const MIND_STEPS = [
  { key: "understand", title: "Understanding the brief", copy: "Bringing your intent, context and production direction together." },
  { key: "shape", title: "Shaping the production direction", copy: "Choosing the family, format and structure before anything is made." },
  { key: "write", title: "Writing your narration", copy: "NexMind is turning your intent into a spoken script for the boards." },
  { key: "ready", title: "Direction is ready", copy: "Review every part of it. Nothing has been made yet." },
];

const DEFAULT_VIDEO_TYPE: Record<string, string> = {
  explainer: "photo_story",
  whiteboard: "kinetic-text",
  presenter: "presenter",
};

export function FlowOverlay({ flow, api }: { flow: FlowState; api: FlowApi }) {
  const { refresh } = useStudio();
  const [mindStep, setMindStep] = useState(0);
  // Mind → real pipeline: recommend → create draft → plan preview → direction
  useEffect(() => {
    if (flow.stage !== "mind" || !flow.prompt) return;
    const brief = flow.prompt;
    let alive = true;
    (async () => {
      setMindStep(0);
      try {
        let family = flow.family;
        let videoType = flow.videoType;
        if (!family || !videoType) {
          try {
            const rec = await studioApi.recommend(brief);
            if (rec.status === "ready") { family = rec.recommendation?.family; videoType = rec.recommendation?.videoType; }
          } catch { /* fall through to defaults */ }
        }
        family = family ?? "explainer";
        videoType = DEFAULT_VIDEO_TYPE[family.toLowerCase()] ?? videoType ?? "photo_story";
        if (!alive) return;
        setMindStep(1);
        const engineKind = engineKindOf(family);
        let productionId: string | undefined;
        if (!engineKind) {
          const sources = (flow.contexts ?? []).filter((c) => c.kind === "file" || c.kind === "reference").map((c) => ({
            kind: c.kind === "file" ? "UPLOAD" as const : "URL" as const,
            label: c.label,
            reference: c.refId,
          }));
          const brandCtx = flow.contexts?.find((c) => c.kind === "brand");
          const draft = await studioApi.createDraft({
            id: crypto.randomUUID(),
            family: family.toUpperCase().replace(/-/g, "_"),
            videoType,
            prompt: brief,
            sources,
            brandContext: brandCtx ? { brandId: brandCtx.refId, name: brandCtx.label } : undefined,
          });
          productionId = (draft as { id?: string; productionId?: string }).productionId ?? (draft as { id?: string }).id;
          if (!alive) return;
          if (!productionId) { api.patchFlow({ stage: "closed", error: "The draft could not be created." }); return; }
        }
        api.patchFlow({ productionId, family, videoType });
        // Brief → NexMind narration (script mode stays verbatim). Part of the mind
        // pipeline so direction lands with the finished script, not a pending card.
        let generatedScript: string | undefined;
        if (engineKind && !flow.script) {
          setMindStep(2);
          try {
            const s = await studioApi.script({
              brief,
              family,
              videoType,
              duration: flow.duration ?? 45,
            });
            if (s.status === "ready" && s.script) generatedScript = s.script;
          } catch { /* Direction shows the unavailable narration state. */ }
          if (!alive) return;
          if (generatedScript) api.patchFlow({ generatedScript });
        }
        // plan preview → direction bridge (skip for engine families — the draft is bookkeeping only)
        if (productionId) {
          try {
            const preview = await studioApi.planPreview(productionId);
            if (!alive) return;
            const p = preview as { status?: string; thesis?: string; recommendedDuration?: number; beats?: FlowState["beats"]; missingInput?: string[] };
            if (p?.status === "ready" || p?.beats) {
              api.patchFlow({ stage: "direction", thesis: p.thesis, beats: p.beats, duration: p.recommendedDuration ?? flow.duration });
            } else {
              api.patchFlow({ stage: "direction" });
            }
          } catch {
            api.patchFlow({ stage: "direction" });
          }
        } else {
          api.patchFlow({ stage: "direction" });
        }
        setMindStep(3);
      } catch (e) {
        if (!alive) return;
        const msg = e instanceof Error ? e.message : "Production could not start.";
        api.patchFlow({ stage: "closed", error: msg });
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow.stage === "mind"]);

  if (flow.stage === "mind") return <MindStage step={mindStep} />;
  if (flow.stage === "closed") return <ClosedStage flow={flow} onClose={api.closeFlow}
    changeVoice={flow.jobKind === "explainer" && !!flow.error?.includes("selected voice")}
    onRetry={flow.jobKind && (flow.script || flow.generatedScript)
      ? () => api.patchFlow({ stage: "direction", error: undefined, jobId: undefined, jobKind: undefined, jobOutputs: undefined }) : undefined} />;
  if (flow.stage === "direction") return <DirectionStage flow={flow} api={api} />;
  if (flow.stage === "production") return <ProductionStage flow={flow} api={api} />;
  if (flow.stage === "review") return <ReviewStage flow={flow} api={api} refresh={refresh} />;
  if (flow.stage === "publish") return <PublishStage flow={flow} api={api} />;
  if (flow.stage === "revision") return <RevisionStage flow={flow} api={api} />;
  return null;
}

function MindStage({ step }: { step: number }) {
  useEffect(() => { ensureNxPresence(); }, []);
  const s = MIND_STEPS[Math.min(step, MIND_STEPS.length - 1)];
  return (
    <div className="mind-stage open" data-step={s.key} id="mindStage">
      <div className="mind-fragments" />
      <div aria-hidden="true" className="nx-mind-field">
        <div className="nx-field-rail top" /><div className="nx-field-rail right" /><div className="nx-field-rail bottom" /><div className="nx-field-rail left" />
        <div className="nx-field-axis x" /><div className="nx-field-axis y" />
        <div aria-hidden="true" className="nx-field-core nx-presence nx-presence--core" data-mode="matrix" data-nx-presence="" data-state="thinking"><canvas /></div>
        <div className="nx-field-word w1">CONTEXT</div><div className="nx-field-word w2">DIRECTION</div>
      </div>
      <div className="mind-wrap"><div className="micro">NexMind</div><h2>{s.title}</h2><p>{s.copy}</p><div className="mind-progress">{MIND_STEPS.map((m, i) => <i key={m.key} className={i <= step ? "active" : ""} />)}</div></div>
    </div>
  );
}

function ClosedStage({ flow, onClose, onRetry, changeVoice }: { flow: FlowState; onClose: () => void; onRetry?: () => void; changeVoice: boolean }) {
  return (
    <div className="mind-stage closed-stage open" data-step="understand" id="closedStage">
      <div className="mind-wrap" role="alert">
        <div className="micro">NexStudio</div>
        <h2>{flow.error ? "Your production couldn't complete." : "Not open for new productions yet."}</h2>
        <p>{flow.error || "This production type is being certified before it opens. Your brief is saved as a draft and nothing was charged."}</p>
        {onRetry && <p>{changeVoice ? "Your narration is saved. Choose a local voice to retry without the online voice service." : "Your narration and settings are saved. Review them and retry."}</p>}
        <div className="mind-actions">
          {onRetry && <button className="v2-primary" onClick={onRetry}>{changeVoice ? "Change voice and retry" : "Review direction and retry"}</button>}
          <button className="v2-primary" onClick={onClose}>Back to Create</button>
        </div>
      </div>
    </div>
  );
}

function DirectionStage({ flow, api }: { flow: FlowState; api: FlowApi }) {
  const { balance, refresh } = useStudio();
  const [adjust, setAdjust] = useState("");
  const [busy, setBusy] = useState(false);
  const beats = flow.beats?.length ? flow.beats : DEFAULT_BEATS;
  const costLabel = flow.amountMinor != null ? formatUSD(flow.amountMinor) : "…";

  const kind = engineKindOf(flow.family);
  const narration = flow.script?.trim() || flow.generatedScript?.trim() || "";
  const [engine, setEngine] = useState(() => ({
    wbType: "kinetic-text", wbTheme: "light", wbAccent: "#2f6fb3",
    style: "photo_story", voice: "emma", speed: "1.0",
    ...(flow.engine ?? {}),
  }));
  // Studio defaults: saved voice/length fill anything the flow didn't already set.
  useEffect(() => {
    let alive = true;
    studioApi.accountPreferences().then((r) => {
      if (!alive) return;
      const p = r.preferences;
      if (p.defaultVoice && !flow.engine?.voice) setEngine((e) => ({ ...e, voice: p.defaultVoice as string }));
      if (p.defaultDuration != null && flow.duration == null) api.patchFlow({ duration: p.defaultDuration });
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [explainerVoices, setExplainerVoices] = useState<Array<{ id: string; label: string; tag: string; preview: string }>>([]);
  const voiceOptions = kind === "explainer" ? explainerVoices : MS_VOICES;
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const playVoice = (id: string) => {
    const a = audioRef.current ?? (audioRef.current = new Audio());
    if (playingVoice === id) { a.pause(); setPlayingVoice(null); return; }
    a.src = explainerVoices.find((v) => v.id === id)?.preview ?? `/previews/voices/${id}.mp3`;
    a.onended = () => setPlayingVoice(null);
    void a.play().then(() => setPlayingVoice(id)).catch(() => setPlayingVoice(null));
  };
  const [styles, setStyles] = useState<Array<{ id: string; name: string; tagline?: string }>>([]);
  const [stylesLoading, setStylesLoading] = useState(true);
  useEffect(() => {
    if (kind !== "explainer") return;
    let alive = true;
    studioApi.explainerCatalog()
      .then((c) => {
        if (!alive) return;
        const voices = c.voices.filter((v) => v.engine === "Kokoro" || v.engine === "Microsoft neural").map((v) => ({
          id: v.id, label: v.name, tag: `${v.accent} · ${v.engine === "Kokoro" ? "local" : "online"}`, preview: v.preview,
        }));
        setExplainerVoices(voices);
        if (voices.length) setEngine((e) => voices.some((v) => v.id === e.voice) ? e : { ...e, voice: voices.find((v) => v.id === "emma")?.id ?? voices[0].id });
        if (!c.styles?.length) return;
        setStyles(c.styles);
        setEngine((e) => c.styles.some((s) => s.id === e.style) ? e : { ...e, style: c.styles[0].id });
      })
      .catch(() => {})
      .finally(() => { if (alive) setStylesLoading(false); });
    return () => { alive = false; };
  }, [kind]);

  // Brief mode: NexMind writes the narration script. Script mode stays verbatim.
  const [scriptState, setScriptState] = useState<"pending" | "ready" | "unavailable">(() => (flow.generatedScript || flow.script ? "ready" : "pending"));
  useEffect(() => {
    if (!kind || flow.script || flow.generatedScript || !flow.prompt) return;
    let alive = true;
    studioApi.script({
      brief: flow.prompt,
      family: flow.family ?? kind,
      videoType: flow.videoType ?? (kind === "whiteboard" ? "hand-drawn-board" : kind === "presenter" ? "presenter" : "photo_story"),
      duration: flow.duration ?? 45,
      beats: flow.beats?.map((b) => ({ purposeTitle: b.purposeTitle, description: b.description })),
    }).then((r) => {
      if (!alive) return;
      if (r.status === "ready" && r.script) {
        api.patchFlow({ generatedScript: r.script, generatedTitle: r.title ?? undefined });
        setScriptState("ready");
      } else setScriptState("unavailable");
    }).catch(() => { if (alive) setScriptState("unavailable"); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);
  const setOpt = (k: keyof typeof engine, v: string) => setEngine((e) => ({ ...e, [k]: v }));
  const [cast, setCast] = useState<CastMember[] | null>(null);
  const [presets, setPresets] = useState<Array<{ presetId: string; name: string; gender: string; tagline: string; spec: NonNullable<CastMember["spec"]> }>>([]);
  const [presenter, setPresenter] = useState<{ castMemberId: string; castPresetId: string; background: string; promo: "off" | "lower-third" | "squeeze"; promoName: string; promoLabel: string; cinematic: boolean; infographic: boolean }>({
    castMemberId: "", castPresetId: "", background: "neutral_studio", promo: "off", promoName: "", promoLabel: "", cinematic: true, infographic: false,
  });
  const [promoImage, setPromoImage] = useState<File | null>(null);
  useEffect(() => {
    if (kind !== "presenter") return;
    let alive = true;
    studioApi.cast().then((r) => {
      if (!alive) return;
      const saved = r.cast.filter((m) => m.spec);
      setCast(saved);
      setPresets(r.presets ?? []);
      const first = saved[0];
      if (!first && (r.presets ?? []).length) {
        setPresenter((p) => ({ ...p, castPresetId: p.castPresetId || r.presets![0].presetId }));
      }
      if (first) {
        setPresenter((p) => ({ ...p, castMemberId: p.castMemberId || first.id, background: first.spec?.environment ?? p.background }));
        const v = first.spec?.voiceId;
        if (v && MS_VOICES.some((x) => x.id === v) && !flow.engine?.voice) setOpt("voice", v);
      }
    }).catch(() => { if (alive) setCast([]); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  async function createVideo() {
    setBusy(true);
    try {
      if (kind && !narration) {
        api.notify("Narration is unavailable. Paste your narration in Script mode or try again after NexMind is available.");
        return;
      }
      if (kind === "explainer" && !styles.some((s) => s.id === engine.style)) {
        api.notify("The explainer styles are unavailable. Reopen Create to try again.");
        return;
      }
      if (kind) {
        const fd = new FormData();
        fd.set("script", narration);
        if (!flow.script?.trim() && flow.generatedTitle) fd.set("title", flow.generatedTitle);
        fd.set("voice", engine.voice);
        fd.set("aspects", "16x9,1x1,9x16");
        fd.set("duration", String(flow.duration ?? 45));
        fd.set("speed", engine.speed);
        if (kind === "presenter") {
          if (!presenter.castMemberId && !presenter.castPresetId) { api.notify("Pick a character first."); return; }
          if (presenter.promo !== "off" && !presenter.promoName.trim()) { api.notify("Give the promotion a name, or switch it off."); return; }
          if (presenter.castMemberId) fd.set("castMemberId", presenter.castMemberId);
          if (presenter.castPresetId) fd.set("castPresetId", presenter.castPresetId);
          fd.set("background", presenter.background);
          fd.set("promo", presenter.promo);
          fd.set("cinematic", String(presenter.cinematic));
          fd.set("infographic", String(presenter.infographic));
          if (presenter.promo !== "off") {
            fd.set("promoName", presenter.promoName.trim());
            if (presenter.promoLabel.trim()) fd.set("promoLabel", presenter.promoLabel.trim());
            if (promoImage) fd.set("promoImage", promoImage);
          }
        } else if (kind === "whiteboard") {
          fd.set("type", engine.wbType);
          fd.set("theme", engine.wbTheme);
          if (engine.wbType === "kinetic-text" && engine.wbAccent) fd.set("accent", engine.wbAccent);
        } else {
          fd.set("style", engine.style);
        }
        const job = await studioApi.createEngineJob(kind, fd);
        api.patchFlow({ stage: "production", jobKind: kind, jobId: job.jobId, engine });
        return;
      }
      if (!flow.productionId) return;
      const q = await studioApi.quote(flow.productionId) as { quoteId?: string; amountMinor?: number; finalAmountMinor?: number };
      const amount = q.finalAmountMinor ?? q.amountMinor ?? 0;
      api.patchFlow({ quoteId: q.quoteId, amountMinor: amount });
      const bal = balance?.availableMinor ?? 0;
      if (amount > bal) {
        // top-up via funding intent → Stripe checkout
        const need = amount - bal;
        const intent = await studioApi.fundingIntent(Math.max(need, 100)) as { checkoutUrl?: string };
        if (intent.checkoutUrl) { window.location.href = intent.checkoutUrl; return; }
        api.notify("Add funds from the Credits sheet, then try again.");
        return;
      }
      const res = await studioApi.purchase(flow.productionId, q.quoteId!) as { ok?: boolean; code?: string; amountRequiredMinor?: number };
      if (res.ok === false) {
        if (res.code === "INSUFFICIENT_BALANCE") { api.notify("Balance is short. Add credits first."); return; }
        api.notify("Production couldn't start. Try again.");
        return;
      }
      await refresh(["balance", "work", "ledger"]);
      api.patchFlow({ stage: "production" });
    } catch (e) {
      api.notify(e instanceof Error ? e.message : "Production could not start.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div aria-hidden="true" className="direction-stage open reveal" id="directionStage">
      <div className="direction-shell">
        <header className="direction-top">
          <button className="direction-back" onClick={api.closeFlow}>← <span className="direction-back-full">Back to brief</span><span className="direction-back-short">Brief</span></button>
          <div className="direction-id"><span className="direction-id-full">NexMind · Creative direction</span><span className="direction-id-short">NexMind</span></div>
          <div className="direction-status"><i /><span>Ready to adjust</span></div>
        </header>
        <main className="direction-content">
          <section className="direction-hero reveal" style={{ ["--d" as string]: ".04s" }}>
            <div className="direction-kicker"><span>Direction ready</span><span>Nothing has been produced yet</span></div>
            <h1>{flow.thesis || "A clear story with a strong visual pulse."}</h1>
            <p>NexMind has shaped a production direction from your brief. You can change any part naturally before credits are used.</p>
            <div className="direction-context">
              {(flow.contexts ?? []).map((c) => <span key={`${c.kind}:${c.refId}`} className="ctx-pill">{c.label}</span>)}
            </div>
          </section>
          <section className="direction-briefline reveal" style={{ ["--d" as string]: ".1s" }}><div><label>{flow.script ? "Your script" : "Your brief"}</label><b>{flow.prompt}</b></div><button onClick={api.closeFlow}>Edit brief</button></section>
          {kind && !flow.script && (
            <section className="direction-script reveal" style={{ ["--d" as string]: ".13s" }}>
              <div className="direction-script-head">
                <label>Narration, written by NexMind</label>
                <span>{scriptState === "ready" ? "Read exactly as written" : scriptState === "pending" ? "Writing…" : "Unavailable"}</span>
              </div>
              {scriptState === "ready" && flow.generatedScript ? (
                <ol className="direction-script-lines">
                  {flow.generatedScript.split("\n").filter(Boolean).map((l, i) => <li key={i}>{l}</li>)}
                </ol>
              ) : scriptState === "unavailable" ? (
                <p>NexMind couldn't write your narration. Go back and paste narration in Script mode, or try again when NexMind is available.</p>
              ) : (
                <div className="direction-script-lines pending"><i /><i /><i /></div>
              )}
            </section>
          )}
          <section className="decision-row two reveal" style={{ ["--d" as string]: ".16s" }}>
            <div className="decision"><label>Production</label><strong>{FAMILY_LABEL[flow.family ?? ""] ?? flow.family ?? "Explainer"}</strong><span>{flow.family ? "Your selection" : "NexMind selected"}</span></div>
            <div className="decision"><label>Format</label><strong>All screens</strong><span>16:9 · 9:16 · 1:1</span></div>
          </section>
          {kind && (
            <section className="options-duo reveal" style={{ ["--d" as string]: ".2s" }}>
              {kind === "whiteboard" && (
                <section className="options-band style-box">
                  <div className="opt-group">
                    <label>Whiteboard <span className="opt-hint">hover to preview · tap to select</span></label>
                    <div className="opt-row previews">
                      <PreviewChip video="/previews/wb-kinetic.mp4" label="Text-driven" desc="Type animates with the narration" selected={engine.wbType === "kinetic-text"} onSelect={() => setOpt("wbType", "kinetic-text")} />
                      <PreviewChip video="/previews/wb-hand.mp4" label="Hand-drawn" desc="The hand draws the board" selected={engine.wbType === "hand-drawn-board"} onSelect={() => setOpt("wbType", "hand-drawn-board")} />
                      <PreviewChip video="/previews/wb-scenes.mp4" label="Board scenes" desc="Rich pastel scenes the hand writes and draws" selected={engine.wbType === "board-scenes"} onSelect={() => setOpt("wbType", "board-scenes")} />
                    </div>
                  </div>
                  <div className="opt-row sub">
                    <div className="opt-group">
                      <label>Board</label>
                      <div className="opt-row">
                        {[["light", "White"], ["dark", "Black"]].map(([v, l]) => (
                          <button key={v} type="button" className={`opt-chip small ${engine.wbTheme === v ? "on" : ""}`} onClick={() => setOpt("wbTheme", v)}><b>{l}</b></button>
                        ))}
                      </div>
                    </div>
                    {engine.wbType === "kinetic-text" && (
                      <div className="opt-group">
                        <label>Highlight</label>
                        <div className="opt-row">
                          <input aria-label="Highlight color" className="opt-color" type="color" value={engine.wbAccent} onChange={(e) => setOpt("wbAccent", e.target.value)} />
                          <span className="opt-value">{engine.wbAccent}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}
              {kind === "presenter" && (
                <section className="options-band style-box presenter-box">
                  <div className="opt-group">
                    <label>Presenter <span className="opt-hint">studio cast or your saved characters</span></label>
                    {cast === null ? <p className="opt-note">Loading characters…</p> : (
                      <>
                      <div className="opt-row presenter-cast">
                        {presets.map((p) => (
                          <button key={p.presetId} type="button" className={`opt-chip presenter-pick ${presenter.castPresetId === p.presetId ? "on" : ""}`} onClick={() => setPresenter((s) => ({ ...s, castPresetId: p.presetId, castMemberId: "" }))}>
                            <span className="presenter-pick-stage"><AvatarStage spec={normalizeCastSpec(p.spec, p.spec.character)} /></span>
                            <b>{p.name}</b>
                          </button>
                        ))}
                        {cast.map((m) => (
                          <button key={m.id} type="button" className={`opt-chip presenter-pick ${presenter.castMemberId === m.id ? "on" : ""}`} onClick={() => setPresenter((s) => ({ ...s, castMemberId: m.id, castPresetId: "" }))}>
                            <span className="presenter-pick-stage"><AvatarStage spec={normalizeCastSpec(m.spec!, m.spec!.character)} /></span>
                            <b>{m.name}</b>
                          </button>
                        ))}
                      </div>
                      {cast.length === 0 && <p className="opt-note">The studio cast is ready to present. <button type="button" className="opt-link" onClick={() => { api.closeFlow(); route("cast"); }}>Or build your own in Cast →</button></p>}
                      </>
                    )}
                  </div>
                  <div className="opt-group">
                    <label>Background</label>
                    <div className="opt-row presenter-backgrounds">
                      {PICKER_ENVIRONMENTS.map((e) => (
                        <button key={e.key} type="button" aria-label={e.label} title={e.label} className={`opt-chip presenter-bg ${presenter.background === e.key ? "on" : ""}`} onClick={() => setPresenter((p) => ({ ...p, background: e.key }))}>
                          <img src={environmentImage(e.key, "landscape")} alt="" loading="lazy" />
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="opt-group">
                    <label>Direction <span className="opt-hint">the cinematic layer · optional</span></label>
                    <div className="opt-row">
                      {([["cinematic", "Director cuts", "Punch-in cuts, the hero word behind the character, sound bed"], ["infographic", "Infographics", "Drawn-on icons on emphasis beats"]] as const).map(([k, l, d]) => (
                        <button key={k} type="button" className={`opt-chip ${presenter[k] ? "on" : ""}`} onClick={() => setPresenter((p) => ({ ...p, [k]: !p[k] }))}><b>{l}</b><span>{d}</span></button>
                      ))}
                    </div>
                  </div>
                  <div className="opt-group">
                    <label>Promotion <span className="opt-hint">optional · shows for a few seconds</span></label>
                    <div className="opt-row">
                      {([["off", "Off", "No promotion"], ["lower-third", "Lower third", "A name card slides in low on screen"], ["squeeze", "Squeeze-back", "The video steps aside for a short spot"]] as const).map(([v, l, d]) => (
                        <button key={v} type="button" className={`opt-chip ${presenter.promo === v ? "on" : ""}`} onClick={() => setPresenter((p) => ({ ...p, promo: v }))}><b>{l}</b><span>{d}</span></button>
                      ))}
                    </div>
                    {presenter.promo !== "off" && (
                      <div className="opt-row presenter-promo">
                        <input className="opt-text" aria-label="Promotion name" maxLength={60} placeholder="What are you promoting?" value={presenter.promoName} onChange={(e) => setPresenter((p) => ({ ...p, promoName: e.target.value }))} />
                        <input className="opt-text" aria-label="Small label" maxLength={40} placeholder="Label, e.g. Brought to you by" value={presenter.promoLabel} onChange={(e) => setPresenter((p) => ({ ...p, promoLabel: e.target.value }))} />
                        <label className="opt-file">
                          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setPromoImage(e.target.files?.[0] ?? null)} />
                          <span>{promoImage ? promoImage.name : "Add image or icon"}</span>
                        </label>
                      </div>
                    )}
                  </div>
                </section>
              )}
              {kind === "explainer" && (
                <section className="options-band style-box">
                  <div className="opt-group">
                    <label>Style <span className="opt-hint">hover to preview · tap to select</span></label>
                    <div className="opt-row previews">
                      {styles.map((s) => (
                        <PreviewChip key={s.id} video={`/previews/xr-${s.id}.mp4`} label={s.name} desc={s.tagline} selected={engine.style === s.id} onSelect={() => setOpt("style", s.id)} />
                      ))}
                      {!styles.length && <span>{stylesLoading ? "Loading explainer styles…" : "Explainer styles are unavailable. Reopen Create to try again."}</span>}
                    </div>
                  </div>
                </section>
              )}
              <section className="options-band pacing open">
                <div className="band-head">
                  <span className="band-head-copy"><label>Voice & pacing</label><b>{voiceOptions.find((v) => v.id === engine.voice)?.label ?? engine.voice} · {flow.duration ?? 45}s · {engine.speed}×</b></span>
                </div>
                <div className="band-body">
                    <div className="opt-group">
                      <label>Voice <span className="opt-hint">{kind === "explainer" ? "Local voices work without an online service" : "Microsoft neural"} · ▶ plays a sample</span></label>
                      <div className="opt-row">
                        {voiceOptions.map((v) => (
                          <div key={v.id} className={`voice-chip ${engine.voice === v.id ? "on" : ""}`}>
                            <button type="button" className="voice-name" onClick={() => setOpt("voice", v.id)}><b>{v.label}</b><span>{v.tag}</span></button>
                            <button type="button" aria-label={`Hear ${v.label}`} className="voice-play" onClick={() => playVoice(v.id)}>{playingVoice === v.id ? "■" : "▶"}</button>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="opt-group">
                      <label>Length <span className="opt-hint">target seconds</span></label>
                      <div className="opt-row">
                        {[15, 30, 45, 60].map((s) => (
                          <button key={s} type="button" className={`opt-chip small ${flow.duration === s ? "on" : ""}`} onClick={() => api.patchFlow({ duration: s })}><b>{s}s</b></button>
                        ))}
                        <div className="opt-stepper">
                          <button type="button" aria-label="Shorter" onClick={() => api.patchFlow({ duration: Math.max(5, (flow.duration ?? 45) - 5) })}>−</button>
                          <input aria-label="Custom length in seconds" inputMode="numeric" type="number" min={5} max={600} step={5} value={flow.duration ?? 45} onChange={(e) => { const v = Math.round(Number(e.target.value)); if (Number.isFinite(v)) api.patchFlow({ duration: Math.min(600, Math.max(5, v)) }); }} />
                          <button type="button" aria-label="Longer" onClick={() => api.patchFlow({ duration: Math.min(600, (flow.duration ?? 45) + 5) })}>+</button>
                          <span>sec</span>
                        </div>
                      </div>
                    </div>
                    <div className="opt-group">
                      <label>Narration speed <span className="opt-hint">multiplies the pacing</span></label>
                      <div className="opt-row">
                        {["0.9", "1.0", "1.1", "1.25"].map((s) => (
                          <button key={s} type="button" className={`opt-chip small ${engine.speed === s ? "on" : ""}`} onClick={() => setOpt("speed", s)}><b>{s}×</b></button>
                        ))}
                      </div>
                    </div>
                  </div>
              </section>
            </section>
          )}
          <section className="direction-grid reveal" style={{ ["--d" as string]: ".26s" }}>
            <div className="story-main">
              <div className="story-label"><h2>How the story moves</h2><span>{beats.length} intentional beats</span></div>
              <div className="story-path">
                {beats.map((b, i) => (
                  <article key={i} className="story-beat"><span className="beat-num">{String(i + 1).padStart(2, "0")}</span><div className="beat-copy"><b>{b.purposeTitle}</b><p>{b.description}</p></div><div className={`beat-visual v${(i % 4) + 1}`} /></article>
                ))}
              </div>
            </div>
            <aside className="creative-side">
              <h2>Creative treatment</h2>
              <div className="creative-sticky">
                <div className="direction-preview"><div className="preview-grid" /><div className="preview-orbit" /><div className="preview-type"><small>NexMind treatment</small><b>Clarity with motion.</b></div></div>
                <div className="creative-list">
                  <div className="creative-item"><label>Look</label><b>Editorial, restrained and spatially clean</b></div>
                  <div className="creative-item"><label>Rhythm</label><b>Confident pacing with room for ideas to land</b></div>
                  <div className="creative-item"><label>Sound</label><b>Purposeful voice, subtle texture, no filler</b></div>
                </div>
              </div>
            </aside>
          </section>

        </main>
      </div>
      <div className="direction-dock">
        <div className="quick-adjusts">
          {["Shorter", "More cinematic", "More energetic", "More restrained"].map((label) => (
            <button key={label} onClick={() => setAdjust(`Make it ${label.toLowerCase()}`)}>{label}</button>
          ))}
        </div>
        <div className="direction-dock-inner">
          <div className="adjuster"><span className="spark">✦</span><input value={adjust} onChange={(e) => setAdjust(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setAdjust(""); }} placeholder="Tell NexMind what to change…" /><button aria-label="Apply direction change" className="adjust-go" onClick={() => setAdjust("")}>↑</button></div>
          <button aria-label="Create video" className="credit-next" disabled={busy || (!!kind && !narration) || (kind === "explainer" && !styles.some((s) => s.id === engine.style))} onClick={() => void createVideo()}><span className="full">{busy ? "Starting…" : <>Create video {!kind && <span className="cost-label">· <b>{costLabel}</b></span>}</>}</span><span>→</span></button>
        </div>
      </div>
    </div>
  );
}

const DEFAULT_BEATS = [
  { start: 0, end: 10, purposeTitle: "Earn attention immediately", description: "Open on the clearest tension in the brief, not an introduction." },
  { start: 10, end: 20, purposeTitle: "Frame what matters", description: "Give the viewer the minimum context needed to understand the idea." },
  { start: 20, end: 35, purposeTitle: "Make the idea tangible", description: "Use the strongest visual mechanism of the chosen production family." },
  { start: 35, end: 45, purposeTitle: "Land one memorable takeaway", description: "Finish with clarity rather than another layer of explanation." },
];

const PHASE_ORDER = ["PREPARING", "SHAPING_STORY", "VISUAL_DIRECTION", "DIRECTING_FILM", "INTERNAL_REVIEW", "FINAL_PRODUCTION"];

function ProductionStage({ flow, api }: { flow: FlowState; api: FlowApi }) {
  const [proj, setProj] = useState<{ title?: string; detail?: string; phase?: string; status?: string } | null>(null);
  const [jobProgress, setJobProgress] = useState<{ phase?: string; aspect?: string; aspectsDone?: number; aspectsTotal?: number; percent?: number } | null>(null);
  useEffect(() => { ensureNxPresence(); }, []);
  // Engine job path: poll the job until outputs land
  useEffect(() => {
    if (!flow.jobId || !flow.jobKind) return;
    let alive = true;
    const poll = async () => {
      try {
        const s = await studioApi.engineJobStatus(flow.jobKind!, flow.jobId!);
        if (!alive) return;
        if (s.progress) setJobProgress(s.progress);
        if (s.status === "done") {
          const outputs = s.outputs ?? {};
          if (Object.keys(outputs).length) {
            api.patchFlow({ stage: "review", jobOutputs: outputs });
          } else {
            api.patchFlow({ stage: "closed", error: "The render finished but made no files. Try again." });
          }
        } else if (s.status === "failed") {
          api.patchFlow({ stage: "closed", error: s.error || "The render failed. Try again." });
        }
      } catch { /* keep polling */ }
    };
    void poll();
    const t = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [flow.jobId, flow.jobKind]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!flow.productionId || flow.jobId) return;
    let alive = true;
    const poll = async () => {
      try {
        const w = await studioApi.workflow(flow.productionId!);
        if (!alive) return;
        if (w) setProj(w as typeof proj);
        const status = String((w as { status?: string } | null)?.status ?? "");
        const phase = String((w as { phase?: string } | null)?.phase ?? "");
        if (status === "COMPLETE" || phase === "FINAL_REVIEW") api.patchFlow({ stage: "review" });
      } catch { /* keep polling */ }
    };
    void poll();
    const t = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [flow.productionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const JOB_STEP: Record<string, number> = { voice: 0, direction: 1, render: 2, packaging: 3, finishing: 3 };
  const idx = flow.jobKind
    ? (jobProgress ? (JOB_STEP[jobProgress.phase ?? ""] ?? 1) : 0)
    : Math.max(0, PHASE_ORDER.indexOf(proj?.phase ?? "PREPARING"));
  const PRESENTER_PHASE: Record<string, [string, string]> = {
    voice: ["story", "Recording the voiceover."], lipsync: ["direction", "Matching the mouth to every sound."],
    gestures: ["direction", "Planning the gestures."], character: ["scenes", "Setting up your presenter."],
    motion: ["life", "Animating your presenter."], frames: ["sound", "Filming every frame."], compose: ["finish", "Adding captions and finishing the files."],
  };
  const presenterPhase = flow.jobKind === "presenter" ? PRESENTER_PHASE[jobProgress?.phase ?? "voice"] ?? PRESENTER_PHASE.voice : null;
  const jobCopy = flow.jobKind === "presenter"
    ? { title: "Your presenter is on set.", detail: "Voice, lip sync, gestures and captions are being made. A one minute video takes about 15 to 25 minutes." }
    : flow.jobKind === "whiteboard"
    ? { title: "The hand is moving.", detail: "Voice, plan and board are rendering. One pass per screen, so all three sizes land together." }
    : flow.jobKind === "explainer"
      ? { title: "The film is being cut.", detail: "Script, voice and style are rendering. One pass per screen, so all three sizes land together." }
      : null;
  const JOB_PHASE: Record<string, string> = { voice: "Recording the voiceover.", direction: "Setting the direction.", render: "Rendering the screens.", packaging: "Finishing the files.", finishing: "Finishing the files." };
  const jobDetail = presenterPhase
    ? (jobProgress?.phase ? presenterPhase[1] : jobCopy?.detail)
    : flow.jobKind && jobProgress?.phase
    ? jobProgress.phase === "render" && jobProgress.aspectsTotal
      ? `Rendering the screens. ${jobProgress.aspectsDone ?? 0} of ${jobProgress.aspectsTotal} done${jobProgress.aspect ? `, now on ${ASPECT_LABEL[jobProgress.aspect] ?? jobProgress.aspect}` : ""}.`
      : JOB_PHASE[jobProgress.phase] ?? jobCopy?.detail
    : jobCopy?.detail;
  const V2_PHASES: Array<{ key: string; label: string }> = [
    { key: "story", label: "Building the story" },
    { key: "direction", label: "Directing the scenes" },
    { key: "scenes", label: "Composing the visuals" },
    { key: "life", label: "Bringing it to life" },
    { key: "sound", label: "Finishing sound" },
    { key: "finish", label: "Preparing final video" },
  ];
  const v2phase = presenterPhase
    ? presenterPhase[0]
    : flow.jobKind
    ? (jobProgress?.phase === "render"
      ? ((jobProgress.aspectsDone ?? 0) / Math.max(1, jobProgress.aspectsTotal ?? 3) >= 0.66 ? "sound"
        : (jobProgress.aspectsDone ?? 0) / Math.max(1, jobProgress.aspectsTotal ?? 3) >= 0.33 ? "life" : "scenes")
      : ({ voice: "story", direction: "direction", packaging: "finish", finishing: "finish" } as Record<string, string>)[jobProgress?.phase ?? ""] ?? "story")
    : V2_PHASES[Math.min(Math.max(idx, 0), 5)].key;
  const v2idx = V2_PHASES.findIndex((p) => p.key === v2phase);
  const frac = presenterPhase
    ? (jobProgress?.percent ?? 0) / 100
    : flow.jobKind
    ? (jobProgress?.phase === "render" && jobProgress.aspectsTotal
      ? (2 + 3 * ((jobProgress.aspectsDone ?? 0) / jobProgress.aspectsTotal)) / 6
      : (v2idx + 0.5) / 6)
    : (idx + 1) / PHASE_ORDER.length;
  const progressX = Math.round(8 + 304 * Math.min(0.97, Math.max(0.08, frac)));
  const prodBeats = flow.beats?.length
    ? flow.beats.slice(0, 4).map((b) => b.purposeTitle)
    : ["Open on the tension", "Frame what matters", "Make it tangible", "Land the takeaway"];
  while (prodBeats.length < 4) prodBeats.push(prodBeats[prodBeats.length - 1] ?? "Land the takeaway");
  return (
    <div aria-hidden="true" className="production-stage open" data-phase={v2phase} id="productionStage">
      <header className="production-top">
        <button aria-label="Leave production and return to Work" className="production-exit" onClick={api.closeFlow}>← <span>Work</span></button>
        <div className="production-brand">
          <span aria-hidden="true" className="nx-presence nx-presence--mini" data-mode="matrix" data-nx-presence="" data-state="thinking"><canvas /></span>
          <span className="production-brand-full">NexStudio · Production</span>
          <span className="production-brand-short">Production</span>
        </div>
        <div className="production-credit"><i /><span>Credits secured</span></div>
      </header>
      <div className="production-wrap">
        <section className="production-canvas">
          <div className="production-frame" id="productionFrame">
            <div className="nx-prod-world nx-prod-world-v2">
              <div aria-hidden="true" className="nx-story-assembly">
                {prodBeats.map((b, i) => (
                  <div key={i} className="nx-story-beat"><span>{String(i + 1).padStart(2, "0")}</span><i /><b>{b}</b><em><u /><u /></em></div>
                ))}
              </div>
              <div aria-hidden="true" className="nx-scene-assembly">
                {["s1", "s2", "s3", "s4"].map((s, i) => (
                  <div key={s} className={`nx-scene ${s}`}><span>{String(i + 1).padStart(2, "0")}</span><div className="nx-scene-layout"><b /><em /><u /></div></div>
                ))}
              </div>
              <div aria-hidden="true" className="nx-composition">
                <div className="nx-comp-kicker">NexMind direction</div>
                <div className="nx-comp-title">One idea.<br />Fully resolved.</div>
                <div className="nx-comp-rule" />
                <div className="nx-comp-object"><i /><i /><i /></div>
                <div className="nx-comp-caption"><span>CONTEXT</span><b>→</b><span>DIRECTION</span></div>
                <div aria-hidden="true" className="nx-layer-stack"><i /><i /><i /></div>
                <div aria-hidden="true" className="nx-motion-echo"><i /><i /><i /></div>
                <div aria-hidden="true" className="nx-cut-timeline"><i /><i /><i /><i /><i /><b /></div>
                <div className="nx-motion-path"><i /><b /></div>
              </div>
              <div aria-hidden="true" className="nx-sound-bed"><span>SYNC</span>
                {[18, 38, 62, 31, 76, 52, 88, 44, 68, 29, 81, 56, 92, 43, 72, 34, 66, 48, 84, 37, 58, 26, 74, 42].map((h, i) => (
                  <i key={i} style={{ "--h": `${h}%`, "--d": `${(i * 0.035).toFixed(2)}s` } as CSSProperties} />
                ))}
                <b className="nx-sync-head" />
              </div>
              <div aria-hidden="true" className="nx-final-lock"><span>FINAL CUT</span><div className="nx-final-mark">✓</div><i /></div>
            </div>
          </div>
        </section>
        <aside className="production-side">
          <div className="production-mind-status">
            <span aria-hidden="true" className="nx-presence nx-presence--status" data-mode="matrix" data-nx-presence="" data-state="thinking"><canvas /></span>
            <div className="micro">NexMind is making your video</div>
          </div>
          <h1 id="productionTitle">{jobCopy?.title ?? proj?.title ?? "Preparing the production."}</h1>
          <p id="productionCopy">{jobDetail ?? proj?.detail ?? "The Studio is checking the approved brief and what the production system can safely make."}</p>
          <svg aria-hidden="true" className="nx-production-progress" viewBox="0 0 320 18" preserveAspectRatio="none">
            <path className="nx-progress-track" d="M8 9 H312" />
            <path className="nx-progress-live" d={`M8 9 H${progressX}`} />
          </svg>
          <div className="phase-list" id="phaseList">
            {V2_PHASES.map((p, i) => (
              <div key={p.key} className={`phase ${i < v2idx ? "done" : i === v2idx ? "active" : ""}`} data-p={p.key}><i />{p.label}</div>
            ))}
          </div>
          <div className="production-note">You can leave this screen. Your production keeps running. Come back when the screens are ready.</div>
        </aside>
      </div>
    </div>
  );
}

const ASPECT_LABEL: Record<string, string> = { "16x9": "16:9", "9x16": "9:16", "1x1": "1:1" };

function ReviewStage({ flow, api, refresh }: { flow: FlowState; api: FlowApi; refresh: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const outputs = flow.jobOutputs ?? null;
  const outputKeys = useMemo(() => Object.keys(outputs ?? {}), [outputs]);
  const [aspect, setAspect] = useState("16x9");
  const [videoFailed, setVideoFailed] = useState(false);
  const activeAspect = outputs?.[aspect] ? aspect : (outputKeys[0] ?? "16x9");
  async function act(action: "approve" | "revision", note?: string) {
    if (outputs) {
      if (action === "approve") api.patchFlow({ stage: "publish" });
      return;
    }
    if (!flow.productionId) return;
    setBusy(true);
    try {
      await studioApi.review(flow.productionId, action === "approve" ? { action: "approve" } : { action: "revision", note: note || "Please revise" });
      await refresh();
      api.notify(action === "approve" ? "Approved. Moved to publish." : "Revision queued with NexMind.");
      api.patchFlow({ stage: action === "approve" ? "publish" : "revision" });
    } catch (e) {
      api.notify(e instanceof Error ? e.message : "That action is not available yet.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div aria-hidden="true" className="finished-stage open" id="finishedStage">
      <header className="review-top">
        <button aria-label="Back to Work" className="review-back" onClick={api.closeFlow}>← <span>Work</span></button>
        <div className="review-brand"><span className="mind-spark">✦</span><span className="review-brand-full">NexStudio · Review</span><span className="review-brand-short">Review</span></div>
        <div className="review-state"><i /><span className="review-state-full">Ready for your call</span><span className="review-state-short">Ready</span></div>
      </header>
      <div className="review-wrap">
        <section className="review-canvas">
          <div className={`review-video-shell ${outputs ? (activeAspect === "9x16" ? "vertical" : activeAspect === "1x1" ? "square" : "") : ""}`}>
            {videoFailed ? (
              <div className="review-video review-video-empty">
                <span className="review-unavailable">Video unavailable</span>
                <span className="review-unavailable-sub">This render file is no longer on disk. Try a new render.</span>
              </div>
            ) : outputs ? (
              <video key={activeAspect} className="review-video" controls playsInline src={outputs[activeAspect]} onError={() => setVideoFailed(true)} />
            ) : flow.productionId ? (
              <video className="review-video" controls playsInline src={`/api/v1/productions/${flow.productionId}/output`} poster={`/api/v1/productions/${flow.productionId}/poster`} onError={() => setVideoFailed(true)} />
            ) : <div className="review-video" />}
            {!videoFailed && <span className="review-version-tag">Ready to review</span>}
          </div>
          {outputs && outputKeys.length > 1 && (
            <div className="aspect-switch">
              {outputKeys.map((k) => (
                <button key={k} type="button" className={`aspect-chip ${activeAspect === k ? "on" : ""}`} onClick={() => setAspect(k)}>{ASPECT_LABEL[k] ?? k}</button>
              ))}
            </div>
          )}
        </section>
        <aside className="review-side">
          <div className="micro">{videoFailed ? "Your video isn't here" : "Your video is ready"}</div>
          <h1>{videoFailed ? "This render is no longer available." : "Review the finished video."}</h1>
          <p>{videoFailed ? "The render file for this production was removed from the server. Your brief and direction are safe. Start a new render for a fresh file." : "Watch the version NexStudio made from your approved direction. Download it, publish it, or ask NexMind for a revision."}</p>
          <div className="review-meta">
            <span><b>{ASPECT_LABEL[activeAspect] ?? "16:9"}</b> shown</span>
            <span><b>{outputs ? outputKeys.length : 1}</b> screens</span>
            <span>{flow.duration ? `${flow.duration} sec` : "Version 1"}</span>
          </div>
          <div className="review-actions">
            {!videoFailed && <a className="review-primary light" href={outputs ? outputs[activeAspect] : `/api/v1/productions/${flow.productionId}/output`} download>↓ Download</a>}
            {!videoFailed && <button className="review-primary" disabled={busy} onClick={() => void act("approve")}>↗ Publish</button>}
            {videoFailed && <button className="review-primary" onClick={api.closeFlow}>Back to Create</button>}
          </div>
          {outputs
            ? <button className="review-revise" disabled={busy} onClick={() => api.patchFlow({ stage: "direction", jobId: undefined, jobOutputs: undefined })}><span className="spark">✦</span> Revise brief</button>
            : <button className="review-revise" disabled={busy} onClick={() => api.patchFlow({ stage: "revision" })}><span className="spark">✦</span> Revise with NexMind</button>}
          {(() => { const seriesChip = (flow.contexts ?? []).find((c) => c.kind === "series"); return (
          <div className="review-next">
            <span>What's next</span>
            <div className="review-next-row">
              {seriesChip && api.openSeries && <button className="review-next-btn" onClick={() => api.openSeries!(seriesChip.refId)}>Make the next episode →</button>}
              <button className="review-next-btn" onClick={() => { api.closeFlow(); route("create"); }}>Make another one →</button>
              <button className="review-next-btn" onClick={() => { api.closeFlow(); route("work"); }}>View in Work →</button>
            </div>
          </div>
          ); })()}
          <div className="review-privacy">No social accounts to connect. NexStudio prepares the file and hands it to you.</div>
        </aside>
      </div>
    </div>
  );
}

const DESTINATIONS = ["YouTube", "TikTok", "Instagram", "X", "Threads", "Facebook"];

function PublishStage({ flow, api }: { flow: FlowState; api: FlowApi }) {
  const primaryOutput = flow.jobOutputs?.["16x9"] ?? Object.values(flow.jobOutputs ?? {})[0];
  const outputUrl = primaryOutput ?? `/api/v1/productions/${flow.productionId}/output`;
  return (
    <div aria-hidden="true" className="publish-overlay open" id="publishOverlay" onClick={(e) => { if (e.target === e.currentTarget) api.closeFlow(); }}>
      <section className="publish-shell" role="dialog" aria-modal="true">
        <div className="sheet-head"><div><div className="micro">Publish · Privacy first</div><h2>Take it everywhere.</h2><p>NexStudio prepares the file and caption for each destination. You keep your own accounts, and nothing is ever posted without you.</p></div><button aria-label="Close publish" className="sheet-close" onClick={api.closeFlow}>×</button></div>
        <div className="platform-grid">
          {DESTINATIONS.map((d) => (
            <a key={d} className="platform" href={outputUrl} download>
              <span className="platform-ico">{d.slice(0, 2).toUpperCase()}</span>
              <span><b>{d}</b><span>{d === "YouTube" ? "MP4 + title + description" : "MP4 + caption"}</span></span>
            </a>
          ))}
        </div>
        <div className="publish-detail open">
          <div className="publish-specs">
            <div className="publish-spec"><label>Version</label><b>Prepared</b></div>
            <div className="publish-spec"><label>Format</label><b>{flow.aspectRatio ?? "16:9"}</b></div>
            <div className="publish-spec"><label>Cover</label><b>Ready</b></div>
          </div>
        </div>
      </section>
    </div>
  );
}

function RevisionStage({ flow, api }: { flow: FlowState; api: FlowApi }) {
  const [note, setNote] = useState("");
  const [ts, setTs] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!flow.productionId || !note.trim()) return;
    setBusy(true);
    try {
      await studioApi.review(flow.productionId, { action: "revision", note: note.trim(), timestampSeconds: ts ? Number(ts) : undefined });
      api.notify("Revision queued. NexMind will take another pass.");
      api.patchFlow({ stage: "production" });
    } catch (e) {
      api.notify(e instanceof Error ? e.message : "Revision could not be queued.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div aria-hidden="true" className="revision-overlay open" id="revisionOverlay" onClick={(e) => { if (e.target === e.currentTarget) api.closeFlow(); }}>
      <section className="revision-shell" role="dialog" aria-modal="true">
        <div className="sheet-head"><div><div className="revision-nexmind-label"><MindSpark /><div className="micro">NexMind · Revision</div></div><h2>What should change?</h2><p>Describe the result you want. NexMind keeps the approved production context and changes only what is necessary.</p></div><button aria-label="Close revision" className="sheet-close" onClick={api.closeFlow}>×</button></div>
        <div className="revision-composer">
          <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Make the opening faster and remove the long middle section." />
          <div className="revision-composer-foot"><span>The current version stays available.</span><input inputMode="numeric" value={ts} onChange={(e) => setTs(e.target.value)} placeholder="Timestamp (sec, optional)" /><button className="revision-review-btn" disabled={busy || !note.trim()} onClick={() => void submit()}>{busy ? "Sending…" : "Review change →"}</button></div>
        </div>
      </section>
    </div>
  );
}
