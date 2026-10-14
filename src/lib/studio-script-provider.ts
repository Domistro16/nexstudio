import { nexMindRoleRouting } from "@/lib/nexmind-routing";

export function scriptProviderKey(): string | undefined {
  return process.env.STUDIO_SCRIPT_OPENAI_API_KEY?.trim()
    || process.env.STUDIO_PLAN_PREVIEW_OPENAI_API_KEY?.trim()
    || process.env.OPENAI_API_KEY?.trim();
}

export function scriptProvider() {
  // Prefer the provider-neutral routing registry; when nothing is configured
  // fall back to an explicit env model or a small default (local servers ignore it).
  let model = process.env.STUDIO_SCRIPT_MODEL?.trim() || "gpt-4o-mini";
  try {
    model = nexMindRoleRouting("studio_script").model || model;
  } catch { /* no registry configured — use the env/default model */ }
  const configured = Number(process.env.STUDIO_SCRIPT_TIMEOUT_MS);
  return {
    model,
    apiUrl: process.env.STUDIO_SCRIPT_OPENAI_API_URL?.trim() || process.env.STUDIO_PLAN_PREVIEW_OPENAI_API_URL?.trim() || "https://api.openai.com/v1",
    apiKey: scriptProviderKey(),
    timeoutMs: Number.isInteger(configured) && configured >= 1000 && configured <= 300000 ? configured : 60_000,
  };
}
