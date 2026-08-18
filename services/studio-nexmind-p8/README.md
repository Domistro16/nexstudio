# Standalone Studio ↔ NexMind P8 bridge

This directory is an adapter around the frozen, verified P8 authority snapshot in `vendor/nexmind-god-mode-p8`.

It does **not** modify P8's governance code. It binds current Studio request data and current engine capability evidence into the P8 control path.

Key rules:

- the complimentary Studio plan is a non-authoritative hint only;
- P8 remains the creative authority after payment;
- the frozen P8 `STICKMAN_V2` schema label is treated as a compatibility alias only; runtime evidence is rebound to the current V5.1 performance master;
- unsupported current capabilities fail closed;
- live-provider credential failures return `PROVIDER_UNAVAILABLE`, never recorded fixtures;
- missing human calibration/review returns `HUMAN_REVIEW_REQUIRED`; it is not renamed `CREATIVE_LOCKED`;
- this process bridge is intended for local/staging. Production may use the HTTP sidecar contract instead.
