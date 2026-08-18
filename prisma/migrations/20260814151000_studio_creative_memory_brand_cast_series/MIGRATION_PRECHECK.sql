-- STUDIO PUBLIC 10/10 — Creative Memory, Brand, Cast & Series precheck.
-- Must run after the 20260814133000 Architecture Core migration.
DO $$
BEGIN
  IF to_regclass('public.productions') IS NULL OR to_regclass('public.production_versions') IS NULL OR to_regclass('public.studio_lineage_snapshots') IS NULL THEN
    RAISE EXCEPTION 'Architecture Core tables are required before Studio Memory migration';
  END IF;
  IF to_regclass('public.studio_memory_items') IS NOT NULL THEN
    RAISE EXCEPTION 'Studio Memory tables already exist; do not reapply migration';
  END IF;
END $$;
