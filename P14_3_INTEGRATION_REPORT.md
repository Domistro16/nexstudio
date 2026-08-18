# Studio V1 — P14.3 P8-Unified Explainer Integration

**Date:** 2026-08-14  
**Status:** `SOURCE_INTEGRATION_VERIFIED__LIVE_PRODUCTION_RUNTIME_REQUIRED`

## What was actually wrong

Two independently completed branches had diverged:

1. Standalone Studio owned the full NexMind P8 creative brain, but its Explainer engine was still P14.1 and its adapter flattened P8 decisions into older generic mechanism families.
2. P14.2 owned the repaired Explainer production spine and seven production-art systems, but it existed outside the Standalone Studio package.

The first blind `white movements` render therefore could legally reach an old execution path and produce another weak, presentation-like film. P14.2 later fixed the fallback behavior but was not yet the engine Standalone Studio shipped.

## Canonical architecture after P14.3

```text
User brief + source/reference media
        ↓
Reference-language analysis (before creative commitment)
        ↓
NexMind P8 — sole top-level creative authority
Story → Visual → Art → Cinematography → Editorial → Motion → Sound
        ↓
Committed P8 checkpoint + canonical final board
        ↓
P14.2 seven-system production-art execution body
Character Skin / Whiteboard Drawing / Environment / Object-Prop /
Scene Composer / Shared Style Grammar / Visual Critic
        ↓
Paper Motion compiler + self-hosted renderer
        ↓
5–8 actual rendered frames + reference frames
        ↓
Strict frame-level Explainer critic
average >= 90; minimum >= 85; zero major/blocker failures
        ↓
Only then: video/audio/contact-sheet evidence returned to P8 final review
```

There is no DirectorV3 fallback and no duplicate P14.2 Story/Visual/Motion authority in the Studio path.

## Repairs applied

- Replaced the stale P14.1 Explainer engine archive with the P14.2 execution source plus the P14.3 P8-unified runner.
- Replaced the old `canonical.explainer_plan` family-mapping adapter.
- Made P8 checkpoint + complete P8 department decisions mandatory for Explainer execution.
- Added reference-language analysis before P8 so the Directors see the reference constraints before committing Story/Visual/Art decisions.
- Materializes real reference video/image files for downstream execution; no filename-only proxy.
- Added strict rendered-frame visual criticism before evidence is released.
- Unmappable P8 visual verbs fail closed instead of falling back to generic Reveal/card language.
- Fixed the NexStick V5.1 capability-registry path consumed by P8.
- Added the missing AgentRouter environment contract required by P8 Sol review/showrunner roles.
- Updated Standalone authority manifests, engine hash, smoke logic, and source QA to P14.3.

## Verification

- P14.2 inherited production spine: **33/33 PASS**.
- P14.3 unified integration QA: **23/23 PASS**.
- Standalone source QA: **PASS**.
- Explainer archive integrity: **PASS**.
- Explainer archive: **40,318,568 bytes**, SHA-256 `2dceb9aac11940aaaabf2e02b4aa4d24a0cf606c894bc1b94cf4d9a49f0e9a24`.
- No active Standalone source declares P14.1 as Explainer authority.
- No active Explainer adapter imports DirectorV3 or `canonical.explainer_plan`.
- Actual no-provider test reaches P8 Story boundary and returns `LIVE_PROVIDER_BLOCKED_MISSING_CREDENTIAL:OPENAI_API_KEY` after validating the current NexStick V5.1 capability graph.
- Actual no-dependency family-engine test returns `EXPLAINER_P14_2_DEPENDENCIES_NOT_INSTALLED`; no fallback film is emitted.
- All three user reference clips are parsed before P8 as rich white-field references; `01 hand draw` is specifically classified `hand-drawn-whiteboard`.

## Truth boundary

This patch verifies the **source integration and fail-closed production path**. It does **not** claim that the 30-second visual benchmark has now passed.

The current sandbox cannot execute that final blind render because:

- Standalone requires Node >=24; this sandbox is Node 22.16.0.
- project `node_modules` are not installed here;
- live OpenAI / AgentRouter provider secrets are not available here.

Those are now deployment/runtime requirements, not another creative architecture rebuild. A real P14.3 benchmark must run in the deployed Studio environment with Node 24+, installed dependencies, and live P8 provider configuration. The 90/85 rendered-frame gate must pass before the result can be returned as acceptable evidence.
