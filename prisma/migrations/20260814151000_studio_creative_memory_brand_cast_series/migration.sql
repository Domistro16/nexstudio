-- STUDIO PUBLIC 10/10 — Creative Memory, Brand, Cast & Series
-- Additive persistence overlay on the 2026-08-14 Architecture Core.

CREATE TYPE "StudioMemoryScope" AS ENUM ('ACCOUNT','BRAND','CAST','SERIES','PRODUCTION');
CREATE TYPE "StudioMemoryEffectiveState" AS ENUM ('ACTIVE','INACTIVE','DELETED');
CREATE TYPE "StudioMemoryWriteMode" AS ENUM ('THIS_PRODUCTION_ONLY','REMEMBER_FOR_BRAND','REMEMBER_FOR_SERIES','UPDATE_CHARACTER_GOING_FORWARD','UPDATE_FROM_FUTURE_EPISODE');

CREATE TABLE "studio_brands" (
  "id" UUID NOT NULL,
  "ownerUserId" UUID NOT NULL,
  "name" TEXT NOT NULL,
  "slug" TEXT,
  "description" TEXT,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "studio_brands_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_brands_ownerUserId_slug_key" ON "studio_brands"("ownerUserId","slug");
CREATE INDEX "studio_brands_ownerUserId_updatedAt_idx" ON "studio_brands"("ownerUserId","updatedAt");

CREATE TABLE "studio_cast_members" (
  "id" UUID NOT NULL,
  "ownerUserId" UUID NOT NULL,
  "brandId" UUID,
  "name" TEXT NOT NULL,
  "assetNamespace" TEXT NOT NULL DEFAULT 'CAST',
  "identityKey" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "studio_cast_members_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_cast_members_ownerUserId_identityKey_key" ON "studio_cast_members"("ownerUserId","identityKey");
CREATE INDEX "studio_cast_members_ownerUserId_brandId_updatedAt_idx" ON "studio_cast_members"("ownerUserId","brandId","updatedAt");

CREATE TABLE "studio_series" (
  "id" UUID NOT NULL,
  "ownerUserId" UUID NOT NULL,
  "brandId" UUID,
  "name" TEXT NOT NULL,
  "description" TEXT,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "studio_series_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "studio_series_ownerUserId_brandId_updatedAt_idx" ON "studio_series"("ownerUserId","brandId","updatedAt");

CREATE TABLE "studio_series_episodes" (
  "id" UUID NOT NULL,
  "seriesId" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "episodeOrdinal" INTEGER NOT NULL,
  "title" TEXT,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_series_episodes_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_series_episodes_productionId_key" ON "studio_series_episodes"("productionId");
CREATE UNIQUE INDEX "studio_series_episodes_seriesId_episodeOrdinal_key" ON "studio_series_episodes"("seriesId","episodeOrdinal");
CREATE INDEX "studio_series_episodes_seriesId_createdAt_idx" ON "studio_series_episodes"("seriesId","createdAt");

CREATE TABLE "studio_production_cast_members" (
  "id" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "castMemberId" UUID NOT NULL,
  "ordinal" INTEGER NOT NULL,
  "roleLabel" TEXT,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_production_cast_members_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_production_cast_members_productionId_castMemberId_key" ON "studio_production_cast_members"("productionId","castMemberId");
CREATE UNIQUE INDEX "studio_production_cast_members_productionId_ordinal_key" ON "studio_production_cast_members"("productionId","ordinal");
CREATE INDEX "studio_production_cast_members_castMemberId_createdAt_idx" ON "studio_production_cast_members"("castMemberId","createdAt");

CREATE TABLE "studio_memory_items" (
  "id" UUID NOT NULL,
  "ownerUserId" UUID NOT NULL,
  "scope" "StudioMemoryScope" NOT NULL,
  "scopeRefId" UUID NOT NULL,
  "key" TEXT NOT NULL,
  "category" TEXT NOT NULL,
  "label" TEXT,
  "currentVersion" INTEGER NOT NULL DEFAULT 0,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "studio_memory_items_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_memory_items_ownerUserId_scope_scopeRefId_key_key" ON "studio_memory_items"("ownerUserId","scope","scopeRefId","key");
CREATE INDEX "studio_memory_items_ownerUserId_scope_scopeRefId_updatedAt_idx" ON "studio_memory_items"("ownerUserId","scope","scopeRefId","updatedAt");

CREATE TABLE "studio_memory_versions" (
  "id" UUID NOT NULL,
  "memoryItemId" UUID NOT NULL,
  "versionNumber" INTEGER NOT NULL,
  "effectiveState" "StudioMemoryEffectiveState" NOT NULL DEFAULT 'ACTIVE',
  "effectiveFrom" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "effectiveUntil" TIMESTAMP(3),
  "effectiveFromEpisodeOrdinal" INTEGER,
  "effectiveUntilEpisodeOrdinal" INTEGER,
  "content" JSONB NOT NULL,
  "contentHash" TEXT NOT NULL,
  "provenance" JSONB NOT NULL,
  "sourceProductionId" UUID,
  "sourceProductionVersionId" UUID,
  "createdByType" TEXT NOT NULL,
  "createdById" TEXT,
  "reason" TEXT,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_memory_versions_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_memory_versions_memoryItemId_versionNumber_key" ON "studio_memory_versions"("memoryItemId","versionNumber");
CREATE INDEX "studio_memory_versions_memoryItemId_effectiveState_effectiveFrom_idx" ON "studio_memory_versions"("memoryItemId","effectiveState","effectiveFrom");
CREATE INDEX "studio_memory_versions_sourceProductionId_createdAt_idx" ON "studio_memory_versions"("sourceProductionId","createdAt");
CREATE INDEX "studio_memory_versions_contentHash_idx" ON "studio_memory_versions"("contentHash");

CREATE TABLE "studio_memory_snapshots" (
  "id" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "projectVersion" INTEGER NOT NULL,
  "snapshotType" TEXT NOT NULL,
  "sequence" INTEGER NOT NULL DEFAULT 1,
  "content" JSONB NOT NULL,
  "contentHash" TEXT NOT NULL,
  "frozenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_memory_snapshots_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_memory_snapshots_productionId_projectVersion_snapshotType_sequence_key" ON "studio_memory_snapshots"("productionId","projectVersion","snapshotType","sequence");
CREATE INDEX "studio_memory_snapshots_productionId_projectVersion_createdAt_idx" ON "studio_memory_snapshots"("productionId","projectVersion","createdAt" DESC);
CREATE INDEX "studio_memory_snapshots_contentHash_idx" ON "studio_memory_snapshots"("contentHash");

ALTER TABLE "productions" ADD COLUMN "brandId" UUID, ADD COLUMN "seriesId" UUID;
CREATE INDEX "productions_ownerUserId_brandId_updatedAt_idx" ON "productions"("ownerUserId","brandId","updatedAt");
CREATE INDEX "productions_ownerUserId_seriesId_updatedAt_idx" ON "productions"("ownerUserId","seriesId","updatedAt");

ALTER TABLE "production_versions" ADD COLUMN "memoryInputSnapshotId" UUID, ADD COLUMN "memoryInputSnapshotHash" TEXT;

ALTER TABLE "studio_brands" ADD CONSTRAINT "studio_brands_ownerUserId_fkey" FOREIGN KEY ("ownerUserId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_cast_members" ADD CONSTRAINT "studio_cast_members_ownerUserId_fkey" FOREIGN KEY ("ownerUserId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_cast_members" ADD CONSTRAINT "studio_cast_members_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "studio_brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "studio_series" ADD CONSTRAINT "studio_series_ownerUserId_fkey" FOREIGN KEY ("ownerUserId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_series" ADD CONSTRAINT "studio_series_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "studio_brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "studio_series_episodes" ADD CONSTRAINT "studio_series_episodes_seriesId_fkey" FOREIGN KEY ("seriesId") REFERENCES "studio_series"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_series_episodes" ADD CONSTRAINT "studio_series_episodes_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_production_cast_members" ADD CONSTRAINT "studio_production_cast_members_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_production_cast_members" ADD CONSTRAINT "studio_production_cast_members_castMemberId_fkey" FOREIGN KEY ("castMemberId") REFERENCES "studio_cast_members"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "studio_memory_items" ADD CONSTRAINT "studio_memory_items_ownerUserId_fkey" FOREIGN KEY ("ownerUserId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_memory_versions" ADD CONSTRAINT "studio_memory_versions_memoryItemId_fkey" FOREIGN KEY ("memoryItemId") REFERENCES "studio_memory_items"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "studio_memory_versions" ADD CONSTRAINT "studio_memory_versions_sourceProductionId_fkey" FOREIGN KEY ("sourceProductionId") REFERENCES "productions"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "studio_memory_versions" ADD CONSTRAINT "studio_memory_versions_sourceProductionVersionId_fkey" FOREIGN KEY ("sourceProductionVersionId") REFERENCES "production_versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "studio_memory_snapshots" ADD CONSTRAINT "studio_memory_snapshots_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "productions" ADD CONSTRAINT "productions_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "studio_brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "productions" ADD CONSTRAINT "productions_seriesId_fkey" FOREIGN KEY ("seriesId") REFERENCES "studio_series"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "production_versions" ADD CONSTRAINT "production_versions_memoryInputSnapshotId_fkey" FOREIGN KEY ("memoryInputSnapshotId") REFERENCES "studio_memory_snapshots"("id") ON DELETE SET NULL ON UPDATE CASCADE;
