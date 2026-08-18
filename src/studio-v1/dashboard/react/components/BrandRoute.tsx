import { useEffect, useState } from "react";
import { useStudioBrands } from "../hooks.js";
import { studioMutation } from "../api.js";
import { ErrorState, LoadState } from "./shared.js";
import { MemoryPanel } from "./MemoryPanel.js";

function lines(value: string) { return value.split(/\n|,/).map((part) => part.trim()).filter(Boolean); }
export function BrandRoute() {
  const brands = useStudioBrands();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", description: "", palette: "", heading: "", body: "", voice: "", instructions: "", must: "", mustNot: "" });
  useEffect(() => { if (!selectedId && brands.data?.brands[0]) setSelectedId(brands.data.brands[0].id); }, [brands.data, selectedId]);
  if (brands.loading) return <LoadState label="Loading Brand" />;
  if (brands.error) return <ErrorState message={brands.error} onRetry={brands.refresh} />;
  const list = brands.data?.brands ?? [];
  const selected = list.find((item) => item.id === selectedId) ?? null;
  async function createBrand() {
    if (!form.name.trim()) return; setBusy(true); setError("");
    try {
      const result = await studioMutation<{ brandId: string }>("/api/v1/studio/brands", "POST", { name: form.name.trim(), description: form.description.trim() || null, authority: { logos: [], palette: { colours: lines(form.palette) }, typography: { headingFamily: form.heading.trim() || null, bodyFamily: form.body.trim() || null }, voice: { notes: form.voice.trim() || null }, must: lines(form.must), mustNot: lines(form.mustNot), assetRefs: [], creativeInstructions: form.instructions.trim() } });
      setSelectedId(result.brandId); setCreating(false); setForm({ name: "", description: "", palette: "", heading: "", body: "", voice: "", instructions: "", must: "", mustNot: "" }); brands.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Brand could not be created."); } finally { setBusy(false); }
  }
  return <section className="sf-route"><header className="sf-route-head"><div><span>Brand</span><h1>Brand authority.</h1><p>Keep the identity and production rules Studio should carry into future work.</p></div><button className="sf-primary" onClick={() => setCreating(true)}>New Brand</button></header>
    {!list.length ? <div className="sf-empty"><h2>No Brand yet.</h2><p>Create one when you want Studio to carry consistent identity, voice and production rules across work.</p><button className="sf-primary" onClick={() => setCreating(true)}>Create Brand</button></div> : <div className="sf-desk-layout"><aside className="sf-record-list" aria-label="Brands">{list.map((brand) => <button key={brand.id} className={selectedId === brand.id ? "active" : ""} onClick={() => setSelectedId(brand.id)}><strong>{brand.name}</strong><small>{brand.description || "Brand authority"}</small></button>)}</aside>{selected ? <div className="sf-record-detail"><div className="sf-profile-head"><span>Brand</span><h2>{selected.name}</h2><p>{selected.description || "No description saved."}</p><small>Updated {new Date(selected.updatedAt).toLocaleDateString()}</small></div><MemoryPanel scope="BRAND" scopeRefId={selected.id} title="Brand memory" description="Binding Brand rules apply to future productions unless you make an explicit production-only exception."/></div> : null}</div>}
    {creating ? <div className="sf-dialog-backdrop"><section className="sf-dialog sf-dialog-wide" role="dialog" aria-modal="true" aria-label="Create Brand"><button className="sf-dialog-close" onClick={() => setCreating(false)}>×</button><span>Brand</span><h2>Create Brand</h2><div className="sf-form-grid"><label>Name<input value={form.name} onChange={(e) => setForm({...form,name:e.currentTarget.value})}/></label><label>Description<input value={form.description} onChange={(e) => setForm({...form,description:e.currentTarget.value})}/></label><label>Colours<input value={form.palette} onChange={(e) => setForm({...form,palette:e.currentTarget.value})} placeholder="#111111, #F4EBDD"/></label><label>Heading type<input value={form.heading} onChange={(e) => setForm({...form,heading:e.currentTarget.value})}/></label><label>Body type<input value={form.body} onChange={(e) => setForm({...form,body:e.currentTarget.value})}/></label><label>Voice notes<input value={form.voice} onChange={(e) => setForm({...form,voice:e.currentTarget.value})}/></label><label className="wide">Creative instructions<textarea rows={3} value={form.instructions} onChange={(e) => setForm({...form,instructions:e.currentTarget.value})}/></label><label>Always do<textarea rows={3} value={form.must} onChange={(e) => setForm({...form,must:e.currentTarget.value})}/></label><label>Never do<textarea rows={3} value={form.mustNot} onChange={(e) => setForm({...form,mustNot:e.currentTarget.value})}/></label></div>{error ? <p className="sf-inline-error">{error}</p> : null}<div className="sf-dialog-actions"><button className="sf-secondary" onClick={() => setCreating(false)}>Cancel</button><button className="sf-primary" disabled={busy || !form.name.trim()} onClick={createBrand}>Create Brand</button></div></section></div> : null}
  </section>;
}
