# P14.3 patch application

Apply this patch over the latest `STUDIO_V1_STANDALONE_COMPLETE` source tree, preserving relative paths.

Then, in the target production environment:

1. Use Node **24+**.
2. Run the normal package dependency install (`npm ci` when the lockfile is authoritative).
3. Configure `OPENAI_API_KEY`, `AGENTROUTER_API_KEY`, and `AGENTROUTER_BASE_URL` in the server environment. Do not expose them to the browser.
4. Run `python scripts/install-engines.py`.
5. Run `python scripts/standalone-qa.py`.
6. Run `python scripts/validate-p14-3-unified-integration.py`.
7. Re-run the blind 30-second `01 white movements(1).mp4` benchmark through the normal Studio production route. Do not invoke a fixture Director, manual scene plan, DirectorV3, or post-render rescue.

A render is not accepted merely because it encodes successfully. The strict rendered-frame critic must pass its 90-average / 85-minimum / zero-major-blocker gate, followed by human visual review.
