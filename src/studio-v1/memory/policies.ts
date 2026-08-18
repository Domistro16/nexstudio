import type { EffectiveStudioMemory, SeriesPlanSignature } from "./contracts";
import { NEXSTICK_V5_1_PERFORMANCE_AUTHORITY } from "./contracts";

const dimensions = [
  "environments", "silhouettes", "transitions", "cameras", "actorPositions",
  "headlineStructures", "visualMetaphors", "motifs",
] as const;

type Dimension = (typeof dimensions)[number];

function normalized(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return [...new Set(values.map(String).map((v) => v.trim().toLowerCase()).filter(Boolean))].sort();
}

export function evaluateSeriesAntiRepetition(input: {
  candidate: SeriesPlanSignature;
  history: SeriesPlanSignature[];
  historyWindow?: number;
  continuityReasons?: Partial<Record<Dimension | "cardGrid" | "floatingObjects", string>>;
}) {
  const window = Math.max(1, Math.min(12, input.historyWindow ?? 2));
  const recent = input.history.slice(-window);
  const collisions: Array<{ dimension: string; repeated: string[]; continuityReason: string | null; blocked: boolean }> = [];

  for (const dimension of dimensions) {
    const candidateValues = normalized(input.candidate[dimension]);
    if (!candidateValues.length) continue;
    const historical = new Set(recent.flatMap((signature) => normalized(signature[dimension])));
    const repeated = candidateValues.filter((value) => historical.has(value));
    if (!repeated.length) continue;
    const continuityReason = input.continuityReasons?.[dimension]?.trim() || null;
    collisions.push({ dimension, repeated, continuityReason, blocked: !continuityReason });
  }
  for (const dimension of ["cardGrid", "floatingObjects"] as const) {
    if (input.candidate[dimension] !== true) continue;
    if (!recent.some((signature) => signature[dimension] === true)) continue;
    const continuityReason = input.continuityReasons?.[dimension]?.trim() || null;
    collisions.push({ dimension, repeated: ["true"], continuityReason, blocked: !continuityReason });
  }

  return {
    historyWindow: window,
    historyCount: recent.length,
    collisions,
    blockedDimensions: collisions.filter((collision) => collision.blocked).map((collision) => collision.dimension),
    passes: collisions.every((collision) => !collision.blocked),
    law: "REPETITION_REQUIRES_CONTINUITY_REASON_OR_RANKED_ALTERNATIVE",
  } as const;
}

const forbiddenPerformanceKeys = new Set([
  "jointAngles", "trajectory", "pose", "poses", "keyframes", "motionClip", "motionPath",
  "handTargets", "footTargets", "rootMotion", "animationFrames",
]);

function stripPerformanceState(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripPerformanceState);
  if (!value || typeof value !== "object") return value;
  const out: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (forbiddenPerformanceKeys.has(key)) continue;
    out[key] = stripPerformanceState(child);
  }
  return out;
}

export function compileStableCastIdentity(input: {
  castMemberId: string;
  identityKey: string;
  name: string;
  memories: EffectiveStudioMemory[];
}) {
  const identity: Record<string, unknown> = {};
  for (const memory of input.memories) identity[memory.key] = stripPerformanceState(memory.content);
  return {
    castMemberId: input.castMemberId,
    identityKey: input.identityKey,
    name: input.name,
    identity,
    performanceAuthority: NEXSTICK_V5_1_PERFORMANCE_AUTHORITY,
    performanceDirection: "RESOLVE_FRESH_FROM_CURRENT_SCENE_INTENT",
  } as const;
}

export function castIdentityFingerprint(identity: ReturnType<typeof compileStableCastIdentity>) {
  return JSON.stringify({ castMemberId: identity.castMemberId, identityKey: identity.identityKey, identity: identity.identity });
}
