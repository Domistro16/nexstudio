# STUDIO PUBLIC 10/10 — Performance evidence

**UI harness: PASS. Production deployment performance: OPEN.**

The dependency-free Chromium harness uses the exact final production CSS and reports **0 external resource requests** at desktop, tablet and mobile. The current home DOM evidence is 75 nodes and 50839 serialized HTML bytes in the test harness.

A real production build was attempted from the merged source. It stopped at `prisma generate` because the runner has **Node v22.16.0**, the repository requires **Node >=24.0.0**, and the dependency tree/Prisma CLI is not installed. Exit code: **127**.

Therefore no fake Lighthouse/Core Web Vitals or dependency-complete Next.js performance score is reported. Final staging must rerun build, bundle and browser performance under the required Node/Prisma/PostgreSQL environment.
