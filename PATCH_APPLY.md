# Apply — Public Experience & Production Workspace final overlay

Base source for this overlay:
`STUDIO_PUBLIC_10_10_PUBLIC_EXPERIENCE_INTEGRATED_SOURCE_2026-08-14.zip`

The overlay reconciles later customer-facing Authenticated Production Desk and Trust/Commerce contracts while preserving the Public Experience workspace as visible authority.

1. Verify the exact base archive SHA-256 recorded in `PATCH_MANIFEST.json`.
2. Extract the base Studio source.
3. Delete every path listed in `DELETION_MANIFEST.txt`.
4. Overlay the patch ZIP, preserving relative paths.
5. Do not apply older full integrated Studio archives afterward; they can roll back this UI layer.
6. Independently owned NexMind/creative-authority patches must be merged and revalidated by their owning branch; this visible overlay does not rewrite NexMind.
7. Run the included standalone, Architecture Core, memory, authenticated-desk, Trust/security, Public Experience, browser, accessibility and no-placeholder gates.
8. Public release still requires certified showcase media and a dependency-complete Node >=24 / Prisma 7 / PostgreSQL staging build.
