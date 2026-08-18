# NexStudio Public Homepage V3 — Final Public Homepage Handoff

Date: 2026-08-15
Scope: public homepage only. Authenticated Dashboard, Production Room, Screening Room, billing, production engines and registry contracts are not redesigned here.

## Product direction

The public homepage now behaves as a creation product rather than a marketing document:

1. premium Light Rays hero + prompt composer;
2. four visual production choices directly under the composer: Explainer, Whiteboard, Stickman, Editorial Motion;
3. certified-film gallery immediately after those choices when certified films exist;
4. visual output-format stage for 16:9, 9:16 and 1:1;
5. source/context stage for brief, links/references, images/video and Brand context;
6. persistent production journey from Brief -> Direction -> Production -> Screening -> Revision;
7. short final creation signal + minimal footer.

No long How-it-works module, continuity essay, testimonial fabrication, fake project, fake film or substitute showcase media is introduced.

## Mobile authority

Mobile is a separate first-class composition, not desktop scaled down:

- dedicated compact app bar and bottom-sheet navigation;
- safe-area aware top and bottom spacing;
- hero composition tuned independently for narrow screens;
- compact creation composer with 44px+ actions;
- horizontal touch/scroll-snap production-choice rail;
- certified-film rail when real media exists;
- swipeable output-format deck;
- swipeable source/context cards;
- swipeable persistent-production journey;
- fixed translucent creation dock after the first creation surface has scrolled away;
- reduced-motion behavior retained.

## Media truth

The production registry remains the only source for public showcase films. The film gallery renders only when public-certified production entries expose both a poster frame and preview video. No source path, old smoke test, external footage or fabricated poster is substituted when the registry is empty.

## Source changes from V2 homepage branch

Changed:
- `src/studio-v1/react/StudioPublicExperience.tsx`
- `app/studio-v1.css`
- `qa/homepage_visual_authority_qa.py`

Added:
- `reports/public-experience/HOMEPAGE_VISUAL_AUTHORITY_QA_V3.json`
- this handoff

No inherited production/auth/billing/dashboard/workspace file was removed.

## QA

- Homepage Visual Authority V3: 42/42 PASS
- Public Experience source QA: 28/28 PASS
- Accessibility QA: 9/9 PASS
- No-placeholder QA: PASS
- TS/TSX syntax transpilation: 132 files / 0 failures
- CSS structural balance: 904 opens / 904 closes
- Diff from V2 source before handoff docs: 3 changed production/QA files, 1 added QA report, 0 missing inherited files

## Runtime boundary

The repository still declares Node >=24 while this execution environment provides Node 22.16.0 and does not contain the dependency-complete production tree. This handoff therefore certifies source structure, visual authority contracts and static visual proof, not a dependency-complete Next/Prisma staging deployment.
