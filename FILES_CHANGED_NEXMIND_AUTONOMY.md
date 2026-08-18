# Files changed — NexMind Autonomous Creative Authority (final merged branch)

## NexMind/P8 authority and quality
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/story_director.py` — three narrative strategy candidates.
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/showrunner_reasoner.py` — Story selection by Showrunner.
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/council.py` — Story competition/review/diversity/commit.
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/showrunner_p8.py` — decision-slot boundaries and memory/Film state.
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/human_calibration.py` — Studio calibration/error/bias/false-accept gates.
- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/studio_quality.py` — non-aggregate quality gate and repair routing.
- `services/studio-nexmind-p8/orchestrator.py` — Story competition, multimodal finalization, conditional autonomous lock, repair/human-exception paths.

## Studio autonomy bridge
- `src/studio-v1/nexmind-p8/autonomy.ts` — calibration, immutable production-memory adapter, finalization and repair orchestration.
- `src/studio-v1/nexmind-p8/creative-state.ts` — authority + immutable MEMORY_INPUT creative-state contract.
- `src/studio-v1/nexmind-p8/contract.ts` — autonomy/repair/calibration/finalization contracts.
- `src/studio-v1/nexmind-p8/workflow.ts` — paid P8 bridge, Story/memory/Series gate, repair and finalization states.
- `src/studio-v1/production-engines/authority.ts` — P14.3/family execution authorities.
- `src/studio-v1/production-engines/workflow.ts` — real reference bytes, memory lineage, FILM_MEMORY, autonomous finalization queue.

## Current five-scope Creative Memory / Brand / Cast / Series authority
- `src/studio-v1/memory/contracts.ts`
- `src/studio-v1/memory/policies.ts`
- `src/studio-v1/memory/service.ts`
- `src/studio-v1/memory/resolver.ts`
- `src/studio-v1/memory/production-input.ts`
- `app/api/v1/studio/memory/route.ts`
- `app/api/v1/studio/memory/[id]/route.ts`
- `app/api/v1/studio/brands/route.ts`
- `app/api/v1/studio/cast/route.ts`
- `app/api/v1/studio/series/route.ts`
- `app/api/v1/productions/[id]/memory/route.ts`
- `prisma/schema.prisma`
- `prisma/migrations/20260814151000_studio_creative_memory_brand_cast_series/migration.sql`

## Current four-family certification evidence/gate recovered
- `src/studio-v1/public/certification/certification-gate.ts`
- `src/studio-v1/public/certification/four-family-capability-registry.json`
- `src/studio-v1/public/registry/production-family-registry.ts` — subtype publication derives from certification evidence rather than a gallery-owned boolean.
- `evaluations/four-family-commercial-certification-v1/corpus.json`
- `scripts/validate-four-family-commercial-certification.py`

## Tests / validators
- `vendor/nexmind-god-mode-p8/tests/test_p8_autonomous_authority.py`
- `services/studio-nexmind-p8/tests/test_autonomous_finalize.py`
- `scripts/run-nexmind-autonomy-blind-preflight.py`
- `scripts/validate-nexmind-autonomous-authority.py`
- `scripts/memory-architecture-qa.py`
- `scripts/memory-domain-tests.mjs`
- `scripts/typescript-syntax-memory.mjs`

## Policy / evidence
- `config/studio-v1/nexmind-autonomous-authority.json`
- `docs/studio-v1/NEXMIND_AUTONOMOUS_CREATIVE_AUTHORITY.md`
- `STUDIO_PUBLIC_10_10_NEXMIND_AUTONOMOUS_CREATIVE_AUTHORITY_HANDOFF.md`
- final reports under `reports/`.

## Explicit non-changes
- P0 authority kernel remains byte-identical to the frozen recovered base.
- `src/studio-v1/billing.ts` remains byte-identical.
- No Studio UI file is part of the autonomy changes.
