# AgentRouter configurable model IDs update

Date: 2026-08-14

P8 now exposes two global model settings:

- `NEXMIND_LUNA_MODEL`
- `NEXMIND_SOL_MODEL`

This supports provider-specific catalog names such as Virtuals/AgentRouter's `openai-gpt-56-luna` without editing each Director role. Per-role model overrides remain higher priority.

AgentRouter-only default routing remains supported when `OPENAI_API_KEY` is absent and AgentRouter credentials are configured.

Verification:

- live-provider unit/transport tests: 16/16 PASS
- AgentRouter-only Story transport test confirms `/chat/completions` carries configured Luna catalog ID
- local benchmark runner model-config preflight confirmed `openai-gpt-56-luna` and `openai-gpt-56-sol`
