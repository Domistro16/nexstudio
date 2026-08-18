"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createStudioProductionDraftClient } from "@/lib/studio-production-draft-client";
import type { StudioProductionFamily } from "@/domain/studio-production-draft";
import { getVideoType, isPublicVideoType, PRODUCTION_REGISTRY } from "@/studio-v1/public/registry";

const FAMILY_MAP: Record<string, StudioProductionFamily> = { explainer: "EXPLAINER", whiteboard: "WHITEBOARD", stickman: "STICKMAN", "editorial-motion": "EDITORIAL_MOTION" };
const INTENT_KEY = "studio.initialIntent.v1";

export function NewProductionBrief() {
  const router = useRouter();
  const params = useSearchParams();
  const family = params.get("family") ?? "";
  const videoTypeId = params.get("videoType") ?? "";
  const item = useMemo(() => getVideoType(PRODUCTION_REGISTRY, videoTypeId), [videoTypeId]);
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState<number | null>(60);
  const [ratio, setRatio] = useState("16:9");
  const [error, setError] = useState("");
  useEffect(() => { setPrompt(window.localStorage.getItem(INTENT_KEY) ?? ""); }, []);
  if (!item || item.family !== family || !FAMILY_MAP[family] || !isPublicVideoType(item)) return <div className="sv1-root sv1-calm"><main className="sv1-room"><div className="sv1-gate-message"><strong>That production type is unavailable.</strong><button className="sv1-primary" onClick={() => router.push("/")}>Back to Studio</button></div></main></div>;
  async function start() {
    if (prompt.trim().length < 1) { setError("Tell us what you want to make."); return; }
    setError("");
    const client = createStudioProductionDraftClient();
    const result = await client.begin({ family: FAMILY_MAP[family], videoType: item!.id, prompt: prompt.trim(), duration, aspectRatio: ratio });
    window.localStorage.removeItem(INTENT_KEY);
    router.push(`/production/${result.draft.id}`);
  }
  return <div className="sv1-root sv1-calm" data-phase="brief"><main className="sv1-room"><button className="sv1-back" onClick={() => router.push("/")}>← Back</button><div className="sv1-room-head"><p className="sv1-kicker">{item.name}</p><h1>Tell us what to make.</h1><p>Describe the outcome. The Studio will work out the production.</p></div><div className="sv1-brief-grid"><section className="sv1-brief-main"><label htmlFor="new-production-prompt">Your brief</label><textarea id="new-production-prompt" value={prompt} onChange={(event) => { setPrompt(event.currentTarget.value); window.localStorage.setItem(INTENT_KEY, event.currentTarget.value); }} rows={9} placeholder="Describe the film in your own words." style={{ viewTransitionName: "production-prompt" }} /><p className="sv1-quiet">Websites, files and reference media connect at the source-material step.</p></section><aside className="sv1-brief-options"><label>Length</label><div className="sv1-chip-row"><button className={duration === null ? "active" : ""} onClick={() => setDuration(null)}>Auto</button>{[30,45,60].map((value) => <button key={value} className={duration === value ? "active" : ""} onClick={() => setDuration(value)}>{value}s</button>)}</div><label>Format</label><div className="sv1-chip-row">{["16:9","9:16","1:1"].map((value) => <button key={value} className={ratio === value ? "active" : ""} onClick={() => setRatio(value)}>{value}</button>)}</div></aside></div>{error ? <p className="sv1-error">{error}</p> : null}<div className="sv1-room-actions"><button className="sv1-primary" onClick={start}>Develop my video</button></div></main></div>;
}
