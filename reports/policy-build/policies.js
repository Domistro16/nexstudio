"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.evaluateSeriesAntiRepetition = evaluateSeriesAntiRepetition;
exports.compileStableCastIdentity = compileStableCastIdentity;
exports.castIdentityFingerprint = castIdentityFingerprint;
const contracts_1 = require("./contracts");
const dimensions = [
    "environments", "silhouettes", "transitions", "cameras", "actorPositions",
    "headlineStructures", "visualMetaphors", "motifs",
];
function normalized(values) {
    if (!Array.isArray(values))
        return [];
    return [...new Set(values.map(String).map((v) => v.trim().toLowerCase()).filter(Boolean))].sort();
}
function evaluateSeriesAntiRepetition(input) {
    const window = Math.max(1, Math.min(12, input.historyWindow ?? 2));
    const recent = input.history.slice(-window);
    const collisions = [];
    for (const dimension of dimensions) {
        const candidateValues = normalized(input.candidate[dimension]);
        if (!candidateValues.length)
            continue;
        const historical = new Set(recent.flatMap((signature) => normalized(signature[dimension])));
        const repeated = candidateValues.filter((value) => historical.has(value));
        if (!repeated.length)
            continue;
        const continuityReason = input.continuityReasons?.[dimension]?.trim() || null;
        collisions.push({ dimension, repeated, continuityReason, blocked: !continuityReason });
    }
    for (const dimension of ["cardGrid", "floatingObjects"]) {
        if (input.candidate[dimension] !== true)
            continue;
        if (!recent.some((signature) => signature[dimension] === true))
            continue;
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
    };
}
const forbiddenPerformanceKeys = new Set([
    "jointAngles", "trajectory", "pose", "poses", "keyframes", "motionClip", "motionPath",
    "handTargets", "footTargets", "rootMotion", "animationFrames",
]);
function stripPerformanceState(value) {
    if (Array.isArray(value))
        return value.map(stripPerformanceState);
    if (!value || typeof value !== "object")
        return value;
    const out = {};
    for (const [key, child] of Object.entries(value)) {
        if (forbiddenPerformanceKeys.has(key))
            continue;
        out[key] = stripPerformanceState(child);
    }
    return out;
}
function compileStableCastIdentity(input) {
    const identity = {};
    for (const memory of input.memories)
        identity[memory.key] = stripPerformanceState(memory.content);
    return {
        castMemberId: input.castMemberId,
        identityKey: input.identityKey,
        name: input.name,
        identity,
        performanceAuthority: contracts_1.NEXSTICK_V5_1_PERFORMANCE_AUTHORITY,
        performanceDirection: "RESOLVE_FRESH_FROM_CURRENT_SCENE_INTENT",
    };
}
function castIdentityFingerprint(identity) {
    return JSON.stringify({ castMemberId: identity.castMemberId, identityKey: identity.identityKey, identity: identity.identity });
}
