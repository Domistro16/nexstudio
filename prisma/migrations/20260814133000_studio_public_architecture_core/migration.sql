-- STUDIO PUBLIC 10/10 — Architecture Core
-- Incremental migration from the Prisma-7-fixed Standalone Studio V1 schema.
-- PostgreSQL only. Run MIGRATION_PRECHECK.sql before applying to a populated database.

ALTER TABLE "productions"
  ADD COLUMN "studioState" "StudioProductionState" NOT NULL DEFAULT 'DRAFT',
  ADD COLUMN "stateVersion" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "lastStateChangedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN "canonicalInputHash" TEXT;

-- Preserve the existing customer lifecycle when adopting Production as the canonical authority.
UPDATE "productions" AS p
SET "studioState" = d."studioState",
    "lastStateChangedAt" = COALESCE(d."updatedAt", p."updatedAt", CURRENT_TIMESTAMP)
FROM "drafts" AS d
WHERE p."id" = d."id";

CREATE INDEX "productions_ownerUserId_studioState_updatedAt_idx"
  ON "productions"("ownerUserId", "studioState", "updatedAt");

ALTER TABLE "production_versions"
  ADD COLUMN "workflowRunId" UUID,
  ADD COLUMN "entitlementId" UUID,
  ADD COLUMN "quoteId" UUID,
  ADD COLUMN "inputSnapshotId" UUID,
  ADD COLUMN "inputSnapshotHash" TEXT,
  ADD COLUMN "creativeLockArtifactId" UUID,
  ADD COLUMN "creativeLockHash" TEXT,
  ADD COLUMN "outputSha256" TEXT,
  ADD COLUMN "lineageHash" TEXT;

CREATE UNIQUE INDEX "production_versions_lineageHash_key" ON "production_versions"("lineageHash");
CREATE INDEX "production_versions_productionId_createdAt_idx" ON "production_versions"("productionId", "createdAt");
CREATE INDEX "production_versions_workflowRunId_idx" ON "production_versions"("workflowRunId");

ALTER TABLE "studio_production_entitlements" ADD COLUMN "workflowRunId" UUID;
CREATE UNIQUE INDEX "studio_production_entitlements_workflowRunId_key" ON "studio_production_entitlements"("workflowRunId");

CREATE TABLE "studio_production_inputs" (
  "id" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "sourceId" UUID,
  "ordinal" INTEGER NOT NULL,
  "kind" TEXT NOT NULL,
  "label" TEXT,
  "reference" TEXT,
  "mimeType" TEXT,
  "snapshot" JSONB NOT NULL,
  "snapshotHash" TEXT NOT NULL,
  "active" BOOLEAN NOT NULL DEFAULT true,
  "attachedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "studio_production_inputs_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_production_inputs_productionId_ordinal_key" ON "studio_production_inputs"("productionId", "ordinal");
CREATE INDEX "studio_production_inputs_productionId_active_idx" ON "studio_production_inputs"("productionId", "active");
CREATE INDEX "studio_production_inputs_sourceId_idx" ON "studio_production_inputs"("sourceId");
CREATE INDEX "studio_production_inputs_snapshotHash_idx" ON "studio_production_inputs"("snapshotHash");

CREATE TABLE "studio_lineage_snapshots" (
  "id" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "projectVersion" INTEGER NOT NULL,
  "snapshotType" TEXT NOT NULL,
  "content" JSONB NOT NULL,
  "contentHash" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_lineage_snapshots_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_lineage_snapshots_productionId_projectVersion_snapshotType_key"
  ON "studio_lineage_snapshots"("productionId", "projectVersion", "snapshotType");
CREATE INDEX "studio_lineage_snapshots_productionId_createdAt_idx" ON "studio_lineage_snapshots"("productionId", "createdAt");
CREATE INDEX "studio_lineage_snapshots_contentHash_idx" ON "studio_lineage_snapshots"("contentHash");

CREATE TABLE "studio_state_transitions" (
  "id" UUID NOT NULL,
  "productionId" UUID NOT NULL,
  "sequence" INTEGER NOT NULL,
  "fromState" "StudioProductionState" NOT NULL,
  "toState" "StudioProductionState" NOT NULL,
  "actorType" TEXT NOT NULL,
  "actorId" TEXT,
  "reason" TEXT NOT NULL,
  "requestId" TEXT,
  "metadata" JSONB NOT NULL DEFAULT '{}',
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "studio_state_transitions_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "studio_state_transitions_productionId_sequence_key" ON "studio_state_transitions"("productionId", "sequence");
CREATE INDEX "studio_state_transitions_productionId_createdAt_idx" ON "studio_state_transitions"("productionId", "createdAt");

-- Content-addressed artifact idempotency. Precheck blocks the migration if exact duplicates exist.
CREATE UNIQUE INDEX "studio_artifacts_productionId_projectVersion_artifactType_contentHash_key"
  ON "studio_artifacts"("productionId", "projectVersion", "artifactType", "contentHash");

ALTER TABLE "studio_workflow_events" ADD COLUMN "idempotencyKey" TEXT;
CREATE UNIQUE INDEX "studio_workflow_events_idempotencyKey_key" ON "studio_workflow_events"("idempotencyKey");

ALTER TABLE "studio_workflow_activities"
  ADD COLUMN "claimedBy" TEXT,
  ADD COLUMN "leaseExpiresAt" TIMESTAMP(3),
  ADD COLUMN "recoveryCount" INTEGER NOT NULL DEFAULT 0;
CREATE INDEX "studio_workflow_activities_status_leaseExpiresAt_idx" ON "studio_workflow_activities"("status", "leaseExpiresAt");

ALTER TABLE "studio_production_inputs"
  ADD CONSTRAINT "studio_production_inputs_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT "studio_production_inputs_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "sources"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "studio_lineage_snapshots"
  ADD CONSTRAINT "studio_lineage_snapshots_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "studio_state_transitions"
  ADD CONSTRAINT "studio_state_transitions_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "studio_production_entitlements"
  ADD CONSTRAINT "studio_production_entitlements_workflowRunId_fkey" FOREIGN KEY ("workflowRunId") REFERENCES "studio_workflow_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "production_versions"
  ADD CONSTRAINT "production_versions_workflowRunId_fkey" FOREIGN KEY ("workflowRunId") REFERENCES "studio_workflow_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT "production_versions_entitlementId_fkey" FOREIGN KEY ("entitlementId") REFERENCES "studio_production_entitlements"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT "production_versions_quoteId_fkey" FOREIGN KEY ("quoteId") REFERENCES "studio_purchase_quotes"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT "production_versions_inputSnapshotId_fkey" FOREIGN KEY ("inputSnapshotId") REFERENCES "studio_lineage_snapshots"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT "production_versions_creativeLockArtifactId_fkey" FOREIGN KEY ("creativeLockArtifactId") REFERENCES "studio_artifacts"("id") ON DELETE SET NULL ON UPDATE CASCADE;
