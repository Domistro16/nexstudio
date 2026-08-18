type NexMindCapabilityRoute = {
  provider: string;
  model: string;
  capabilities: string[];
  priority: number;
  reasoning?: string;
  baseUrl?: string; apiKeyEnv?: string; apiMode?: string;
};

type NexMindResolvedRoute = {
  provider: string;
  model: string;
  reasoning: string;
  capability: string;
  source: "role-override" | "capability-registry";
  baseUrl: string; apiKeyEnv: string; apiMode: "responses"|"chat_completions"|"chat_completions_prompt_json";
};

const ROLE_CAPABILITY: Record<string, string> = {
  studio_plan_preview: "creative_reasoning",
};

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function parseCapabilityRegistry(): NexMindCapabilityRoute[] {
  const raw = text(process.env.NEXMIND_MODEL_REGISTRY_JSON);
  if (!raw) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("NEXMIND_MODEL_REGISTRY_JSON_INVALID");
  }
  const candidates = Array.isArray(parsed)
    ? parsed
    : parsed && typeof parsed === "object" && Array.isArray((parsed as { routes?: unknown }).routes)
      ? (parsed as { routes: unknown[] }).routes
      : [];
  return candidates.flatMap((candidate): NexMindCapabilityRoute[] => {
    if (!candidate || typeof candidate !== "object") return [];
    const route = candidate as Record<string, unknown>;
    if (route.enabled === false) return [];
    const provider = text(route.provider);
    const model = text(route.model);
    const capabilities = Array.isArray(route.capabilities)
      ? route.capabilities.map(text).filter(Boolean)
      : [];
    if (!provider || !model || capabilities.length === 0) return [];
    const priority = Number.isFinite(Number(route.priority)) ? Number(route.priority) : 0;
    const reasoning = text(route.reasoning);
    return [{ provider, model, capabilities, priority, ...(reasoning ? { reasoning } : {}), baseUrl:text(route.base_url)||text(process.env[text(route.base_url_env)]), apiKeyEnv:text(route.api_key_env)||"NEXMIND_API_KEY", apiMode:text(route.api_mode)||"chat_completions" }];
  }).sort((a, b) => b.priority - a.priority);
}

export function nexMindRoleRouting(role: string): NexMindResolvedRoute {
  const capability = ROLE_CAPABILITY[role];
  if (!capability) throw new Error(`Unsupported standalone NexMind role: ${role}`);

  // Exact operator overrides are allowed, but the architecture never supplies
  // a provider or model identity. Both must be explicitly configured together.
  const roleKey = role.toUpperCase().replace(/[^A-Z0-9]+/g, "_");
  const overrideModel = text(process.env[`NEXMIND_${roleKey}_MODEL`]) || (role === "studio_plan_preview" ? text(process.env.NEXMIND_PLAN_PREVIEW_MODEL) : "");
  const overrideProvider = text(process.env[`NEXMIND_${roleKey}_PROVIDER`]) || (role === "studio_plan_preview" ? text(process.env.NEXMIND_PLAN_PREVIEW_PROVIDER) : "");
  if (overrideModel || overrideProvider) {
    if (!overrideModel || !overrideProvider) throw new Error(`NEXMIND_ROLE_OVERRIDE_INCOMPLETE:${role}:${capability}`);
    return {
      provider: overrideProvider,
      model: overrideModel,
      reasoning: text(process.env[`NEXMIND_${roleKey}_REASONING`]) || text(process.env.NEXMIND_PLAN_PREVIEW_REASONING) || "none",
      capability,
      source: "role-override",
      baseUrl: text(process.env[`NEXMIND_${roleKey}_BASE_URL`]) || text(process.env.NEXMIND_PLAN_PREVIEW_BASE_URL),
      apiKeyEnv: text(process.env[`NEXMIND_${roleKey}_API_KEY_ENV`]) || text(process.env.NEXMIND_PLAN_PREVIEW_API_KEY_ENV) || "NEXMIND_API_KEY",
      apiMode: (text(process.env[`NEXMIND_${roleKey}_API_MODE`]) || text(process.env.NEXMIND_PLAN_PREVIEW_API_MODE) || "chat_completions") as NexMindResolvedRoute["apiMode"],
    };
  }

  const route = parseCapabilityRegistry().find((candidate) => candidate.capabilities.includes(capability) || candidate.capabilities.includes(role) || candidate.capabilities.includes("*"));
  if (!route) throw new Error(`NEXMIND_NO_COMPATIBLE_MODEL_CONFIG:${capability}:${role}`);
  return {
    provider: route.provider,
    model: route.model,
    reasoning: route.reasoning || "none",
    capability,
    source: "capability-registry",
    baseUrl: route.baseUrl || "", apiKeyEnv: route.apiKeyEnv || "NEXMIND_API_KEY", apiMode: (route.apiMode || "chat_completions") as NexMindResolvedRoute["apiMode"],
  };
}
