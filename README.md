# Studio V1 — Standalone Complete Source

This is the standalone Studio application source. Studio is the root product in this repository; it is not mounted inside another public product and it contains no marketplace/Pass application shell.

## Product scope

The launch production families are exactly:

1. Explainer
2. Whiteboard
3. Stickman
4. Editorial Motion

The customer experience is:

`Home → visual family/type selection → preserved brief → email auth → complimentary text production plan → server quote/payment → full NexMind P8 production → private internal evidence/review → Creative Lock → finished-film review → approval or same-paid-production revision → Dashboard`

Projects live inside Dashboard, not public navigation. Public pricing is intentionally quiet; the server-authoritative base rate is $2 per finished minute and the first-production discount is configurable (10% default).

## What is included

- Standalone Next.js application at `/`, `/production/...`, `/dashboard`.
- Guest ProductionDraft persistence and same-ID account claim.
- Studio-only email session auth (`studio_session`).
- One bounded complimentary planning pass using the cheap plan-preview route.
- USD quote/balance/ledger/entitlement system with idempotent purchase logic.
- NexMind P8 Final Executive Producer bridge and frozen authority snapshot.
- Four current family execution adapters.
- Authoritative engine source archives for all four families plus Sound Library V2.
- Hashed creative-state → multimodal evidence → independent review → Final Producer → Creative Lock lineage.
- Real production-room workflow projection.
- Finished film review, download, approval and timestamped revision without a second charge.
- Authenticated Dashboard with Work, Brand, Assets, Billing and API/Agents surfaces.

## Important release boundary

The source is implementation-complete, but the four public video types intentionally remain disabled until independent human creative certification, launch preview films and real deployment evidence are attached. The code fails closed rather than taking payment for an uncertified public production path.

## Requirements

- Node.js 24+
- PostgreSQL
- Python 3.11+
- FFmpeg / ffprobe
- Chromium for Editorial Motion browser rendering
- Python packages in `requirements.txt`

## Setup

```bash
cp .env.example .env
npm install
python -m pip install -r requirements.txt
python scripts/install-engines.py
npm run db:generate
npm run db:migrate
npm run dev
```

Run the production worker separately:

```bash
npm run worker
```

## Engine roots

`python scripts/install-engines.py` expands the included authoritative archives into `engines/`. The default paths are already shown in `.env.example`.

## Production authority

The complimentary plan is not Creative Lock. After payment, P8 is the creative authority. Family adapters may translate P8 decisions into deterministic engine inputs but may not re-author the story, cast, visual concept, cinematography, rhythm or sound direction.

## Verification

Run:

```bash
npm run qa
```

The package also includes `docs/STANDALONE_SOURCE_MANIFEST.json` and a SHA-256 file next to the downloadable archive.
