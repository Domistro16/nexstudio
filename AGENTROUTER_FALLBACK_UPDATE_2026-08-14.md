# AgentRouter-only fallback update

Date: 2026-08-14

## Change

P8 live-provider routing now supports this behavior:

- If both `OPENAI_API_KEY` and `AGENTROUTER_*` credentials are configured, the default split remains:
  - Directors -> OpenAI / Luna
  - Producers / Showrunners / Final Producer -> AgentRouter / Sol
- If `OPENAI_API_KEY` is not configured, but `AGENTROUTER_API_KEY` is configured, default OpenAI-routed P8 roles are automatically routed through AgentRouter instead of failing immediately on a missing OpenAI key.
- Explicit per-role `*_PROVIDER` overrides still win.

## Files changed

- `vendor/nexmind-god-mode-p8/src/nexmind_god_mode/live_provider.py`
- `vendor/nexmind-god-mode-p8/tests/test_live_provider.py`
- `.env.example`

## Verification

- `python -m unittest tests.test_live_provider -v` -> PASS (13/13)
- `python scripts/validate-canonical-creative-authority-v2.py` -> PASS (10/10)

## Truth boundary

This update changes P8 live-provider routing only. It does not claim the full encoded-film runtime has been executed in this sandbox.
