# Authority supersession guard

The later Architecture Core patch contains an older `production-engines/authority.ts` snapshot and must **not** overwrite the current creative-source authority file.

Current authorities retained by this branch:

- Explainer: `EXPLAINER_MOTION_P14_3_P8_UNIFIED_EXECUTION` — `2dceb9aac11940aaaabf2e02b4aa4d24a0cf606c894bc1b94cf4d9a49f0e9a24`
- Whiteboard: `WHITEBOARD_V1_PUBLIC_HARDENING_CHAIN` — `6f87a4ea054a766a4950f232a9ee1bc6c5b2901766671aabe174c3ad3ef0f570`
- Stickman: `NEXSTICK_MASTER_V2_PERFORMANCE_V5_1` — `67b49cc7275cd741a70f5851bf1f98d0a8cc7dbd3b1a884f458ddac789a21178`
- Editorial Motion: `FACELESS_PUBLIC_LEVEL7_EDITORIAL_RUNTIME` — `dcea330da2181656138b58692893ceb93b5aea794ae0dcf589e5047b82196671`

The Architecture Core snapshot would regress Explainer to P14.1 and uses stale Whiteboard/Editorial hashes. Apply Architecture Core durability work around the current authorities, never the reverse.
