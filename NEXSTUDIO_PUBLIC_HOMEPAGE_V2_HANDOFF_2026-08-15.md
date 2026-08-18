# NEXSTUDIO PUBLIC HOMEPAGE V2 — CREATION → CATEGORIES → FILMS

**Date:** 2026-08-15  
**Scope:** Public homepage only.  
**Base:** Approved NexStudio hero + 2026-08-15 complete homepage branch.  

## Product correction

The previous homepage extension became too explanatory after the hero. This correction applies the product principle visible in strong AI-creation products without copying their page design:

**creation first → immediate visual choices → proof through output**

The new homepage order is now:

1. Approved NexStudio hero + creation composer.
2. Four visual production-category boxes directly under the composer:
   - Explainer
   - Whiteboard
   - Stickman
   - Editorial Motion
3. Certified NexStudio film rail immediately after those categories when release-grade films exist.
4. Minimal footer.

Removed from the homepage:

- long three-step explainer section;
- separate oversized production-family section;
- continuity / quality essay section;
- duplicate bottom creation composer;
- verbose empty showcase explanation.

## Category-box treatment

The four boxes are custom NexStudio UI, not borrowed component-library cards and not fake film thumbnails.

- Explainer: system / information relationship motif.
- Whiteboard: authored stroke / diagram motif.
- Stickman: minimal character-performance motif.
- Editorial Motion: typography / rhythm / composition motif.

Desktop and tablet show the four together. Mobile uses a horizontal snap rail so the creation choices stay visual and touch-friendly without shrinking into unreadable cards.

## Video truth boundary

The film rail is implemented directly after the four categories and renders from `certifiedWork` only. It is conditional and stays absent while the commercial registry has no certified showcase film + poster pairs. No old engine smoke, borrowed footage, fake project art or synthetic film placeholder was introduced.

## QA

- Repository TS/TSX syntax transpilation: **132/132 PASS**.
- Public Experience source QA: **28/28 PASS**.
- Homepage Visual Authority V2 QA: **28/28 PASS**.
- Accessibility QA: **9/9 PASS**.
- No-placeholder QA: **PASS**.
- CSS structural balance: **685/685 braces**.
- Static production-CSS proof overflow:
  - desktop 1440: **0 horizontal overflow**;
  - tablet 1024: **0 horizontal overflow**;
  - mobile 390: **0 horizontal overflow**.

## Regression boundary

Compared with the immediately preceding integrated homepage package, only these implementation/evidence files changed:

- `src/studio-v1/react/StudioPublicExperience.tsx`
- `app/studio-v1.css`
- `qa/homepage_visual_authority_qa.py`
- `reports/public-experience/HOMEPAGE_VISUAL_AUTHORITY_QA.json`
- `reports/public-experience/NO_PLACEHOLDER_QA.json`

No authenticated Dashboard, Auth, Billing, Production Room, Screening Room, Trust, Memory, Brand, Cast, Series or production-engine file was changed.

## Proof note

The supplied screenshots are static Chromium renders using the exact production homepage CSS and matching DOM composition. They are layout/art-direction proof, not a dependency-complete Next.js staging claim. The recovered repository still requires Node >=24 and the runnable dependency tree is not present in this environment.
