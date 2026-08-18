# Deployment / release blockers

The UI implementation is complete for this branch, but these gates remain fail-closed:

- **Commercial media:** current certification recommends 0/24 subtypes public-enabled and supplies no certified showcase film/poster.
- **Provider/blind-film evidence:** four-family commercial certification still needs the live-provider blind film corpus and independent review required by its threshold.
- **Production build:** `package.json` requires Node >=24.0.0; this environment is Node 22.16.0 and has no installed dependency tree. A dependency-complete Next build, Prisma validation/generation, real PostgreSQL migration run, Lighthouse-style bundled-app performance test and staging integration run are therefore not claimed.

These are release-evidence blockers, not reasons to weaken the public gate.
