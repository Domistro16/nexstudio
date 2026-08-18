"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { PRODUCTION_REGISTRY } from "@/studio-v1/public/registry/production-family-registry";
import { getPublicVideoTypes } from "@/studio-v1/public/registry/selectors";
import type { FamilyId, ProductionVideoType } from "@/studio-v1/public/registry/types";
import { createStudioProductionDraftClient } from "@/lib/studio-production-draft-client";
import type { ProductionDraftSource, StudioProductionFamily } from "@/domain/studio-production-draft";
import { NexStudioLightRays } from "./NexStudioLightRays";

const INTENT_KEY = "studio.initialIntent.v1";
const SOURCES_KEY = "studio.initialSources.v1";
const FAMILY_TO_CANONICAL: Record<FamilyId, StudioProductionFamily> = {
  explainer: "EXPLAINER",
  whiteboard: "WHITEBOARD",
  stickman: "STICKMAN",
  "editorial-motion": "EDITORIAL_MOTION",
};

const WORK_FILTERS: Array<{ id: "all" | FamilyId; label: string }> = [
  { id: "all", label: "All" },
  { id: "explainer", label: "Explainer" },
  { id: "whiteboard", label: "Whiteboard" },
  { id: "stickman", label: "Stickman" },
  { id: "editorial-motion", label: "Editorial Motion" },
];

const DELIVERY_FORMATS = [
  { ratio: "16:9", label: "Landscape", className: "landscape" },
  { ratio: "9:16", label: "Vertical", className: "vertical" },
  { ratio: "1:1", label: "Square", className: "square" },
] as const;

const SOURCE_CARDS = [
  { key: "brief", eyebrow: "Start here", label: "Your brief", note: "Say what the film needs to achieve." },
  { key: "references", eyebrow: "Bring context", label: "Links + references", note: "Point Studio at the visual language that matters." },
  { key: "media", eyebrow: "Show, don’t explain", label: "Images + video", note: "Use source material and visual references where the production supports them." },
  { key: "brand", eyebrow: "Keep it yours", label: "Brand context", note: "Carry the right identity into the same production." },
] as const;

const PRODUCTION_JOURNEY = ["Brief", "Direction", "Production", "Screening", "Revision"] as const;

type Recommendation = { family: FamilyId; videoType: string; reason: string };
type StagedFile = { name: string; size: number; type: string };

function CertifiedPreview({ item, hero = false }: { item: ProductionVideoType; hero?: boolean }) {
  if (!item.previewVideo?.src || !item.posterFrame) return null;
  return <div className={hero ? "sv1-certified-media sv1-hero-certified-media" : "sv1-certified-media"}>
    <video muted loop playsInline autoPlay={hero} preload={hero ? "metadata" : "none"} poster={item.posterFrame} aria-label={`${item.name} certified Studio preview`}>
      <source src={item.previewVideo.src} type={item.previewVideo.type || "video/mp4"}/>
    </video>
  </div>;
}

function SignInDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const dialogRef = useRef<HTMLElement | null>(null);
  const emailRef = useRef<HTMLInputElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    requestAnimationFrame(() => emailRef.current?.focus());
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusables = [...dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')];
      if (!focusables.length) return;
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); returnFocusRef.current?.focus(); };
  }, [open, onClose]);

  async function requestSignIn() {
    if (!email.includes("@")) return;
    setMessage("");
    const response = await fetch("/api/v1/auth/email/request", {
      method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json", "Idempotency-Key": `studio-public-signin:${crypto.randomUUID()}` },
      body: JSON.stringify({ email, next: "/dashboard" }),
    });
    setMessage(response.ok ? "Check your email. Your Studio will still be here." : "The sign-in link could not be sent yet.");
  }

  if (!open) return null;
  return <div className="sv1-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
    <section ref={dialogRef} className="sv1-modal" role="dialog" aria-modal="true" aria-labelledby="studio-signin-title" aria-describedby="studio-signin-description">
      <button className="sv1-close" onClick={onClose} aria-label="Close sign in">×</button>
      <p className="sv1-kicker">Your work stays here</p>
      <h2 id="studio-signin-title">Sign in to your Studio.</h2>
      <p id="studio-signin-description">Use your email. If you already started a production, it will continue from the same saved production.</p>
      <label className="sv1-visually-hidden" htmlFor="studio-signin-email">Email address</label>
      <input ref={emailRef} id="studio-signin-email" value={email} onChange={(event) => setEmail(event.currentTarget.value)} autoComplete="email" type="email" inputMode="email" placeholder="Email address" />
      <button className="sv1-primary full" onClick={requestSignIn} disabled={!email.includes("@")} >Continue with email</button>
      {message ? <p className="sv1-auth-message" role="status">{message}</p> : null}
    </section>
  </div>;
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function FamilyVisual({ family }: { family: FamilyId }) {
  if (family === "explainer") return <div className="nxs-family-art" aria-hidden="true">
    <span className="nxs-explainer-panel"><i/><i/><i/></span><span className="nxs-explainer-orbit"/><span className="nxs-explainer-node a"/><span className="nxs-explainer-node b"/>
  </div>;
  if (family === "whiteboard") return <div className="nxs-family-art" aria-hidden="true">
    <span className="nxs-board-stroke a"/><span className="nxs-board-stroke b"/><span className="nxs-board-circle"/><span className="nxs-board-arrow">→</span>
  </div>;
  if (family === "stickman") return <div className="nxs-family-art" aria-hidden="true">
    <span className="nxs-stick-head"/><span className="nxs-stick-body"/><span className="nxs-stick-arm a"/><span className="nxs-stick-arm b"/><span className="nxs-stick-leg a"/><span className="nxs-stick-leg b"/><span className="nxs-stick-prop"/>
  </div>;
  return <div className="nxs-family-art" aria-hidden="true">
    <span className="nxs-editorial-type">MOVE</span><span className="nxs-editorial-rule a"/><span className="nxs-editorial-rule b"/><span className="nxs-editorial-block"/>
  </div>;
}

function ShowcaseFilm({ item, onSelect, reducedMotion }: { item: ProductionVideoType; onSelect: () => void; reducedMotion: boolean }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const node = videoRef.current;
    if (!node || reducedMotion) return;
    const observer = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry?.isIntersecting && entry.intersectionRatio >= 0.58) void node.play().catch(() => undefined);
      else node.pause();
    }, { threshold: [0, 0.58, 0.82] });
    observer.observe(node);
    return () => { observer.disconnect(); node.pause(); };
  }, [reducedMotion]);

  const familyName = PRODUCTION_REGISTRY.families.find((family) => family.id === item.family)?.name || item.family;
  return <motion.button className="nxs-film-card" type="button" onClick={onSelect}
    onPointerEnter={() => { if (!reducedMotion) void videoRef.current?.play().catch(() => undefined); }}
    onPointerLeave={() => { if (!reducedMotion) videoRef.current?.pause(); }}
    whileTap={reducedMotion ? undefined : { scale: .985 }}>
    <span className="nxs-film-frame">
      <video ref={videoRef} muted loop playsInline preload="metadata" poster={item.posterFrame} aria-label={`${item.name} NexStudio film preview`}>
        <source src={item.previewVideo?.src} type={item.previewVideo?.type || "video/mp4"}/>
      </video>
      <i className="nxs-film-play" aria-hidden="true">▶</i>
    </span>
    <span className="nxs-film-meta"><strong>{item.name}</strong><small>{familyName}</small></span>
  </motion.button>;
}

export function StudioPublicExperience({ authenticated }: { authenticated: boolean }) {
  const router = useRouter();
  const reducedMotion = useReducedMotion();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [prompt, setPrompt] = useState("");
  const [family, setFamily] = useState<FamilyId | null>(null);
  const [signIn, setSignIn] = useState(false);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recommendationMessage, setRecommendationMessage] = useState("");
  const [recommending, setRecommending] = useState(false);
  const [creating, setCreating] = useState(false);
  const [composerFocused, setComposerFocused] = useState(false);
  const [referenceOpen, setReferenceOpen] = useState(false);
  const [referenceValue, setReferenceValue] = useState("");
  const [sources, setSources] = useState<ProductionDraftSource[]>([]);
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [composerMessage, setComposerMessage] = useState("");
  const [headerScrolled, setHeaderScrolled] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobileDockVisible, setMobileDockVisible] = useState(false);
  const [workFilter, setWorkFilter] = useState<"all" | FamilyId>("all");

  useEffect(() => {
    const saved = window.localStorage.getItem(INTENT_KEY);
    if (saved) setPrompt(saved);
    const savedSources = window.localStorage.getItem(SOURCES_KEY);
    if (savedSources) {
      try {
        const parsed = JSON.parse(savedSources) as ProductionDraftSource[];
        setSources(parsed.filter((source) => source.kind === "URL" && typeof source.reference === "string"));
      } catch { /* ignore stale local data */ }
    }
    if (new URLSearchParams(window.location.search).get("signin") === "1") setSignIn(true);
  }, []);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(248, Math.max(86, node.scrollHeight))}px`;
  }, [prompt]);

  useEffect(() => {
    const updateHeader = () => {
      setHeaderScrolled(window.scrollY > 24);
      setMobileDockVisible(window.scrollY > Math.min(680, window.innerHeight * .72));
    };
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
    window.addEventListener("resize", updateHeader, { passive: true });
    return () => { window.removeEventListener("scroll", updateHeader); window.removeEventListener("resize", updateHeader); };
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileNavOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  const setIntent = (value: string) => {
    setPrompt(value);
    setRecommendation(null);
    setRecommendationMessage("");
    setComposerMessage("");
    window.localStorage.setItem(INTENT_KEY, value);
  };

  const persistSources = (next: ProductionDraftSource[]) => {
    setSources(next);
    window.localStorage.setItem(SOURCES_KEY, JSON.stringify(next.filter((source) => source.kind === "URL")));
  };

  const selected = family ? PRODUCTION_REGISTRY.families.find((item) => item.id === family) ?? null : null;
  const types = useMemo(() => family ? getPublicVideoTypes(PRODUCTION_REGISTRY, family) : [], [family]);
  const publicTypes = useMemo(() => PRODUCTION_REGISTRY.families.flatMap((item) => getPublicVideoTypes(PRODUCTION_REGISTRY, item.id)), []);
  const certifiedCount = publicTypes.length;
  const certifiedShowcase = useMemo(() => publicTypes.filter((item) => item.previewVideo?.src && item.posterFrame).slice(0, 3), [publicTypes]);
  const certifiedWork = useMemo(() => publicTypes.filter((item) => item.previewVideo?.src && item.posterFrame).slice(0, 6), [publicTypes]);
  const filteredCertifiedWork = useMemo(() => workFilter === "all" ? certifiedWork : certifiedWork.filter((item) => item.family === workFilter), [certifiedWork, workFilter]);

  function goCreate() {
    setMobileNavOpen(false);
    document.getElementById("studio-create")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" });
    window.setTimeout(() => textareaRef.current?.focus({ preventScroll: true }), reducedMotion ? 0 : 420);
  }

  async function chooseType(item: ProductionVideoType) {
    const initial = prompt.trim();
    if (!initial) { router.push(`/production/new?family=${encodeURIComponent(item.family)}&videoType=${encodeURIComponent(item.id)}`); return; }
    const client = createStudioProductionDraftClient();
    const result = await client.begin({ family: FAMILY_TO_CANONICAL[item.family], videoType: item.id, prompt: initial, sources, duration: 60, aspectRatio: "16:9" });
    window.localStorage.removeItem(INTENT_KEY);
    window.localStorage.removeItem(SOURCES_KEY);
    router.push(`/production/${result.draft.id}`);
  }

  async function fetchRecommendation() {
    const initial = prompt.trim();
    if (initial.length < 8) { setRecommendationMessage("Add a little more about what you want to make."); return null; }
    setRecommending(true); setRecommendation(null); setRecommendationMessage("");
    try {
      const response = await fetch("/api/v1/studio/recommendation", { method:"POST", credentials:"same-origin", headers:{"content-type":"application/json"}, body:JSON.stringify({prompt:initial}) });
      const body = await response.json().catch(() => null) as { data?: { status:string; recommendation?:Recommendation }; detail?:string } | null;
      if (!response.ok || !body?.data) throw new Error(body?.detail || "A recommendation is unavailable right now.");
      if (body.data.status !== "ready" || !body.data.recommendation) { setRecommendationMessage("NexStudio does not have an available production path for this request yet."); return null; }
      setRecommendation(body.data.recommendation);
      return PRODUCTION_REGISTRY.videoTypes.find((item) => item.id === body.data?.recommendation?.videoType && item.family === body.data.recommendation.family) ?? null;
    } catch (reason) {
      setRecommendationMessage(reason instanceof Error ? reason.message : "A recommendation is unavailable right now.");
      return null;
    } finally { setRecommending(false); }
  }

  async function recommend() { await fetchRecommendation(); }

  async function createFromPrompt() {
    if (creating) return;
    if (prompt.trim().length < 8) { setComposerMessage("Give Studio a little more to work with."); textareaRef.current?.focus(); return; }
    if (stagedFiles.length) {
      setComposerMessage("Your file selection is staged locally. Secure file ingestion remains behind Studio’s authenticated source-material gate; the hero will not bypass that security boundary.");
      return;
    }
    if (!certifiedCount) {
      setComposerMessage("NexStudio is not accepting new productions yet. Your idea stays here.");
      return;
    }
    setCreating(true);
    try {
      const item = await fetchRecommendation();
      if (item) await chooseType(item);
    } finally { setCreating(false); }
  }

  function addReference() {
    const value = referenceValue.trim();
    if (!value) return;
    try {
      const url = new URL(value);
      if (!/^https?:$/.test(url.protocol)) throw new Error("unsupported");
      const next: ProductionDraftSource[] = [...sources, { id: crypto.randomUUID(), kind: "URL", label: url.hostname.replace(/^www\./, ""), reference: url.toString(), mimeType: "text/uri-list" }];
      persistSources(next);
      setReferenceValue("");
      setReferenceOpen(false);
      setComposerMessage("");
    } catch {
      setComposerMessage("Add a full http:// or https:// reference link.");
    }
  }

  function removeSource(id?: string) {
    persistSources(sources.filter((source) => source.id !== id));
  }

  function stageFiles(files: FileList | null) {
    if (!files?.length) return;
    const next = [...files].slice(0, 8).map((file) => ({ name: file.name, size: file.size, type: file.type }));
    setStagedFiles((current) => [...current, ...next].slice(0, 8));
    setComposerMessage(authenticated
      ? "Files are staged in this browser session. Secure upload will remain behind the existing source-material security gate."
      : "Files are staged in this browser session. Sign in is required before Studio can securely ingest them.");
  }

  const recommendedItem = recommendation ? PRODUCTION_REGISTRY.videoTypes.find((item) => item.id === recommendation.videoType && item.family === recommendation.family) : null;
  const composerActive = composerFocused || Boolean(prompt.trim()) || Boolean(sources.length) || Boolean(stagedFiles.length) || referenceOpen;

  return <div className="sv1-root sv1-calm" data-environment="calm">
    <header className={`sv1-header sv1-header-premium${headerScrolled ? " is-scrolled" : ""}`}>
      <button className="sv1-wordmark" onClick={() => { setFamily(null); router.push("/"); }} aria-label="NexStudio home"><span className="sv1-wordmark-glyph" aria-hidden="true"><i/><i/></span><span>NexStudio</span></button>
      <nav className="nxs-desktop-nav" aria-label="NexStudio navigation">
        <button onClick={() => router.push("/work")}>Work</button>
        <button onClick={() => router.push("/pricing")}>Pricing</button>
        {authenticated ? <button onClick={() => router.push("/dashboard")}>Dashboard</button> : <button onClick={() => setSignIn(true)}>Sign in</button>}
        <button className="sv1-primary small sv1-nav-create" onClick={goCreate}>Create</button>
      </nav>
      <button className="nxs-mobile-menu" type="button" onClick={() => setMobileNavOpen(true)} aria-label="Open NexStudio menu" aria-expanded={mobileNavOpen}><i/><i/></button>
    </header>

    <AnimatePresence>
      {mobileNavOpen ? <motion.div className="nxs-mobile-menu-backdrop" role="presentation" initial={reducedMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.currentTarget === event.target) setMobileNavOpen(false); }}>
        <motion.section className="nxs-mobile-menu-sheet" role="dialog" aria-modal="true" aria-label="NexStudio navigation" initial={reducedMotion ? false : { y: 36, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 28, opacity: 0 }} transition={{ duration: reducedMotion ? 0 : .28 }}>
          <div className="nxs-mobile-menu-head"><span>Navigate</span><button type="button" onClick={() => setMobileNavOpen(false)} aria-label="Close menu">×</button></div>
          <button type="button" onClick={() => { setMobileNavOpen(false); router.push("/work"); }}><span>Work</span><i>↗</i></button>
          <button type="button" onClick={() => { setMobileNavOpen(false); router.push("/pricing"); }}><span>Pricing</span><i>↗</i></button>
          <button type="button" onClick={() => { setMobileNavOpen(false); authenticated ? router.push("/dashboard") : setSignIn(true); }}><span>{authenticated ? "Dashboard" : "Sign in"}</span><i>↗</i></button>
          <button type="button" className="is-create" onClick={goCreate}><span>Create something</span><i>→</i></button>
        </motion.section>
      </motion.div> : null}
    </AnimatePresence>

    {!selected ? <main className="sv1-public-main sv1-home-main">
      <section className="sv1-hero" aria-labelledby="studio-hero-title">
        <div className="sv1-hero-atmosphere" aria-hidden="true">
          <div className="sv1-hero-bloom sv1-hero-bloom-a" />
          <div className="sv1-hero-bloom sv1-hero-bloom-b" />
          <NexStudioLightRays className="sv1-hero-rays" raysOrigin="top-left" raysColor="#7468ff" secondaryColor="#e89cc4" raysSpeed={0.12} lightSpread={1.34} rayLength={1.92} fadeDistance={1.22} pointerInfluence={0.03} noiseAmount={0.018} distortion={0.028} intensity={0.66}/>
          <div className="sv1-hero-focus-wash" />
          <div className="sv1-hero-grain" />
        </div>

        {certifiedShowcase.length ? <div className="sv1-hero-showcase" aria-label="Certified NexStudio work">
          {certifiedShowcase.map((item, index) => <motion.div key={item.id} className={`sv1-hero-showcase-card sv1-hero-showcase-${index + 1}`} initial={reducedMotion ? false : { opacity: 0, y: 20, rotate: index === 1 ? 1 : -1 }} animate={{ opacity: 1, y: 0, rotate: index === 1 ? 2.2 : index === 2 ? -2.5 : -1.6 }} transition={{ duration: .7, delay: .14 + index * .08 }}><CertifiedPreview item={item} hero/><span>{item.name}</span></motion.div>)}
        </div> : null}

        <div className="sv1-hero-stage">
          <motion.div className="sv1-hero-copy" initial={reducedMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .62 }}>
            <p className="sv1-kicker">Your AI production studio</p>
            <h1 id="studio-hero-title">Make something worth watching.</h1>
            <p>Describe what you need. Add what you already have. NexStudio carries it through to a finished film.</p>
          </motion.div>

          <motion.div id="studio-create" className={`sv1-composer sv1-composer-premium${composerActive ? " is-active" : ""}`} layout transition={{ layout: { duration: reducedMotion ? 0 : .34 } }} style={{ viewTransitionName: "production-prompt" }}>
            <label className="sv1-visually-hidden" htmlFor="studio-intent">What do you want to make?</label>
            <textarea ref={textareaRef} id="studio-intent" rows={3} value={prompt} onFocus={() => setComposerFocused(true)} onBlur={() => setComposerFocused(false)} onChange={(event) => setIntent(event.currentTarget.value)} placeholder="What do you want to make?" />

            <AnimatePresence initial={false}>
              {sources.length || stagedFiles.length ? <motion.div className="sv1-attachment-rail" initial={reducedMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                {sources.map((source) => <span className="sv1-attachment-chip" key={source.id}><span className="sv1-attachment-icon" aria-hidden="true">↗</span><span><strong>{source.label || "Reference"}</strong><small>Link</small></span><button onClick={() => removeSource(source.id)} aria-label={`Remove ${source.label || "reference"}`}>×</button></span>)}
                {stagedFiles.map((file, index) => <span className="sv1-attachment-chip is-staged" key={`${file.name}-${index}`}><span className="sv1-attachment-icon" aria-hidden="true">＋</span><span><strong>{file.name}</strong><small>{formatBytes(file.size)} · staged</small></span><button onClick={() => setStagedFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Remove ${file.name}`}>×</button></span>)}
              </motion.div> : null}
            </AnimatePresence>

            <AnimatePresence initial={false}>
              {referenceOpen ? <motion.div className="sv1-reference-entry" initial={reducedMotion ? false : { opacity: 0, y: 8, height: 0 }} animate={{ opacity: 1, y: 0, height: "auto" }} exit={{ opacity: 0, y: 4, height: 0 }}>
                <label className="sv1-visually-hidden" htmlFor="studio-reference">Reference link</label>
                <input id="studio-reference" autoFocus value={referenceValue} onChange={(event) => setReferenceValue(event.currentTarget.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addReference(); } if (event.key === "Escape") setReferenceOpen(false); }} placeholder="Paste a website, video or reference link" inputMode="url" />
                <button className="sv1-reference-add" onClick={addReference} disabled={!referenceValue.trim()}>Add</button>
              </motion.div> : null}
            </AnimatePresence>

            <div className="sv1-composer-actions">
              <div className="sv1-source-actions">
                <input ref={fileInputRef} className="sv1-visually-hidden" type="file" multiple onChange={(event) => { stageFiles(event.currentTarget.files); event.currentTarget.value = ""; }} />
                <button className="sv1-composer-tool" onClick={() => fileInputRef.current?.click()}><span aria-hidden="true">＋</span> Add files</button>
                <button className={`sv1-composer-tool${referenceOpen ? " active" : ""}`} onClick={() => setReferenceOpen((value) => !value)}><span aria-hidden="true">↗</span> Add reference</button>
              </div>
              <button className="sv1-create-button" onClick={createFromPrompt} disabled={creating || recommending} aria-label="Create with NexStudio"><span>{creating || recommending ? "Starting" : "Create"}</span><i aria-hidden="true">→</i></button>
            </div>

            {composerMessage ? <p className="sv1-composer-message" role="status">{composerMessage}</p> : null}
            {recommendedItem ? <div className="sv1-recommendation" role="status"><div><span>Studio recommendation</span><strong>{recommendedItem.name}</strong><p>{recommendation?.reason}</p></div><button className="sv1-primary" onClick={() => chooseType(recommendedItem)}>Continue</button></div> : null}
            {recommendationMessage ? <p className="sv1-auth-message" role="status">{recommendationMessage}</p> : null}
          </motion.div>

          <div className="nxs-family-quick" aria-label="Choose what you want to make">
            {PRODUCTION_REGISTRY.families.map((item, index) => <motion.button key={item.id} type="button" data-family={item.id} className="nxs-family-choice" onClick={() => setFamily(item.id)} initial={reducedMotion ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .46, delay: .2 + index * .055 }} whileHover={reducedMotion ? undefined : { y: -4 }}>
              <FamilyVisual family={item.id}/>
              <span className="nxs-family-choice-copy"><strong>{item.name}</strong><small>{item.shortDescription}</small></span>
              <i className="nxs-family-choice-arrow" aria-hidden="true">↗</i>
            </motion.button>)}
          </div>
        </div>
      </section>

      {certifiedWork.length ? <section className="nxs-film-gallery" aria-labelledby="nxs-work-title">
        <div className="nxs-section-shell">
          <div className="nxs-film-gallery-head">
            <div><p className="sv1-kicker">Made with NexStudio</p><h2 id="nxs-work-title">Watch what Studio can make.</h2></div>
            <p>Finished films, shown as films — not feature descriptions.</p>
          </div>
          <div className="nxs-film-filters" role="tablist" aria-label="Filter NexStudio films">
            {WORK_FILTERS.map((filter) => <button key={filter.id} role="tab" aria-selected={workFilter === filter.id} className={workFilter === filter.id ? "active" : ""} onClick={() => setWorkFilter(filter.id)}>{filter.label}</button>)}
          </div>
          <motion.div className="nxs-film-grid" layout>
            <AnimatePresence mode="popLayout">
              {filteredCertifiedWork.map((item) => <ShowcaseFilm key={item.id} item={item} reducedMotion={Boolean(reducedMotion)} onSelect={() => chooseType(item)}/>)}
            </AnimatePresence>
          </motion.div>
        </div>
      </section> : null}

      <section className="nxs-format-stage" aria-labelledby="nxs-format-title">
        <div className="nxs-section-shell">
          <div className="nxs-format-head">
            <div><p className="sv1-kicker">Finish anywhere</p><h2 id="nxs-format-title">One production. Every screen.</h2></div>
            <p>16:9 · 9:16 · 1:1</p>
          </div>
          <div className="nxs-format-deck">
            {DELIVERY_FORMATS.map((format, index) => <motion.article key={format.ratio} className={`nxs-format-card is-${format.className}`} initial={reducedMotion ? false : { opacity: 0, y: 24, rotate: index === 0 ? -2.2 : index === 2 ? 2.4 : 0 }} whileInView={{ opacity: 1, y: 0, rotate: index === 0 ? -1.25 : index === 2 ? 1.3 : 0 }} viewport={{ once: true, amount: .35 }} transition={{ duration: reducedMotion ? 0 : .48, delay: index * .06 }}>
              <span className="nxs-format-canvas" aria-hidden="true"><i className="nxs-format-glow"/><i className="nxs-format-line a"/><i className="nxs-format-line b"/><i className="nxs-format-block"/><b>NX</b></span>
              <span className="nxs-format-meta"><strong>{format.ratio}</strong><small>{format.label}</small></span>
            </motion.article>)}
          </div>
        </div>
      </section>

      <section className="nxs-source-stage" aria-labelledby="nxs-source-title">
        <div className="nxs-source-ambient" aria-hidden="true"><i/><i/></div>
        <div className="nxs-section-shell nxs-source-shell">
          <div className="nxs-source-copy"><p className="sv1-kicker">Bring the context</p><h2 id="nxs-source-title">Give Studio what you already have.</h2><p>The idea can start rough. Add the context that should shape the production.</p></div>
          <div className="nxs-source-deck">
            {SOURCE_CARDS.map((card, index) => <motion.article key={card.key} data-source={card.key} initial={reducedMotion ? false : { opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .35 }} transition={{ duration: reducedMotion ? 0 : .4, delay: index * .055 }}>
              <span className="nxs-source-icon" aria-hidden="true"><i/><i/></span><small>{card.eyebrow}</small><strong>{card.label}</strong><p>{card.note}</p>
            </motion.article>)}
          </div>
        </div>
      </section>

      <section className="nxs-journey-stage" aria-labelledby="nxs-journey-title">
        <div className="nxs-section-shell nxs-journey-shell">
          <div className="nxs-journey-copy"><p className="sv1-kicker">One production</p><h2 id="nxs-journey-title">The work stays connected.</h2><p>Your brief does not disappear when production starts. The same job carries through screening and revision.</p></div>
          <div className="nxs-journey-visual" aria-label="Brief to revision production flow">
            <span className="nxs-journey-spine" aria-hidden="true"/>
            {PRODUCTION_JOURNEY.map((step, index) => <motion.div key={step} className={`nxs-journey-node node-${index + 1}`} initial={reducedMotion ? false : { opacity: 0, scale: .96 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: .45 }} transition={{ duration: reducedMotion ? 0 : .34, delay: index * .06 }}><small>0{index + 1}</small><strong>{step}</strong>{index === 3 ? <i aria-hidden="true">▶</i> : null}</motion.div>)}
          </div>
        </div>
      </section>

      <section className="nxs-final-signal" aria-labelledby="nxs-final-title">
        <div className="nxs-section-shell"><div><p className="sv1-kicker">Ready when you are</p><h2 id="nxs-final-title">Make something worth watching.</h2></div><button type="button" onClick={goCreate}><span>Start creating</span><i>→</i></button></div>
      </section>

      <footer className="nxs-home-footer nxs-home-footer-final">
        <div className="nxs-section-shell"><button className="sv1-wordmark" onClick={() => window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" })} aria-label="Back to top"><span className="sv1-wordmark-glyph" aria-hidden="true"><i/><i/></span><span>NexStudio</span></button><nav aria-label="Footer navigation"><button onClick={() => router.push("/work")}>Work</button><button onClick={() => router.push("/pricing")}>Pricing</button><button onClick={goCreate}>Create</button></nav><p>Creative production, carried from brief to film.</p></div>
      </footer>
    </main> : <main className="sv1-public-main sv1-family-page">
      <button className="sv1-back" onClick={() => setFamily(null)}>← All production families</button>
      <div className="sv1-section-head large"><p className="sv1-kicker">{selected.name}</p><h1>Choose a starting point.</h1><p>Only production types with finished Studio-made work appear here.</p></div>
      {types.length ? <div className="sv1-video-grid">{types.map((item) => <button key={item.id} className="sv1-video-tile" onClick={() => chooseType(item)}><CertifiedPreview item={item}/><span><strong>{item.name}</strong><small>{item.shortDescription}</small></span></button>)}</div> : <div className="sv1-release-state"><p className="sv1-kicker">Not yet open</p><h2>No public {selected.name.toLowerCase()} work is published yet.</h2><p>Studio opens a production type only when its finished-film standard is met. No borrowed footage or staged example is substituted.</p><button className="sv1-secondary" onClick={() => router.push("/work")}>View certified work</button></div>}
    </main>}

    <AnimatePresence>
      {mobileDockVisible && !mobileNavOpen && !selected ? <motion.div className="nxs-mobile-create-dock" initial={reducedMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 14 }} transition={{ duration: reducedMotion ? 0 : .24 }}>
        <button type="button" onClick={goCreate}><span><small>Create with NexStudio</small><strong>Make something</strong></span><i aria-hidden="true">→</i></button>
      </motion.div> : null}
    </AnimatePresence>

    <SignInDialog open={signIn} onClose={() => setSignIn(false)}/>
  </div>;
}
