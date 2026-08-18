ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "privacyStatus" TEXT NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "deletionRequestedAt" TIMESTAMP(3);
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMP(3);
ALTER TABLE "sources" ADD COLUMN IF NOT EXISTS "securityStatus" TEXT NOT NULL DEFAULT 'PENDING';
ALTER TABLE "sources" ADD COLUMN IF NOT EXISTS "detectedMimeType" TEXT;
ALTER TABLE "sources" ADD COLUMN IF NOT EXISTS "quarantineObjectKey" TEXT;

CREATE TABLE IF NOT EXISTS "auth_identities" (
  "id" UUID PRIMARY KEY,
  "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
  "provider" TEXT NOT NULL,
  "subject" TEXT NOT NULL,
  "email" TEXT,
  "emailVerified" BOOLEAN NOT NULL DEFAULT FALSE,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS "auth_identities_provider_subject_key" ON "auth_identities"("provider","subject");
CREATE INDEX IF NOT EXISTS "auth_identities_userId_provider_idx" ON "auth_identities"("userId","provider");

CREATE TABLE IF NOT EXISTS "upload_scan_jobs" (
  "id" UUID PRIMARY KEY,
  "sourceId" UUID NOT NULL UNIQUE REFERENCES "sources"("id") ON DELETE CASCADE,
  "status" TEXT NOT NULL DEFAULT 'QUEUED', "scanner" TEXT NOT NULL DEFAULT 'CLAMAV', "attempts" INTEGER NOT NULL DEFAULT 0,
  "verdict" TEXT, "detail" TEXT, "claimedAt" TIMESTAMP(3), "completedAt" TIMESTAMP(3),
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP, "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "upload_scan_jobs_status_createdAt_idx" ON "upload_scan_jobs"("status","createdAt");

CREATE TABLE IF NOT EXISTS "studio_notifications" (
  "id" UUID PRIMARY KEY, "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
  "type" TEXT NOT NULL, "title" TEXT NOT NULL, "body" TEXT NOT NULL, "href" TEXT, "dedupeKey" TEXT NOT NULL,
  "readAt" TIMESTAMP(3), "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS "studio_notifications_userId_dedupeKey_key" ON "studio_notifications"("userId","dedupeKey");
CREATE INDEX IF NOT EXISTS "studio_notifications_userId_createdAt_idx" ON "studio_notifications"("userId","createdAt");

CREATE TABLE IF NOT EXISTS "asset_delivery_tickets" (
  "id" UUID PRIMARY KEY, "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
  "productionId" UUID, "sourceId" UUID REFERENCES "sources"("id") ON DELETE CASCADE, "objectKey" TEXT NOT NULL,
  "purpose" TEXT NOT NULL, "tokenHash" TEXT NOT NULL UNIQUE, "maxUses" INTEGER NOT NULL DEFAULT 1, "useCount" INTEGER NOT NULL DEFAULT 0,
  "expiresAt" TIMESTAMP(3) NOT NULL, "lastUsedAt" TIMESTAMP(3), "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "asset_delivery_tickets_userId_expiresAt_idx" ON "asset_delivery_tickets"("userId","expiresAt");
CREATE INDEX IF NOT EXISTS "asset_delivery_tickets_productionId_expiresAt_idx" ON "asset_delivery_tickets"("productionId","expiresAt");
DO $$ BEGIN
  ALTER TABLE "asset_delivery_tickets" ADD CONSTRAINT "asset_delivery_tickets_productionId_fkey" FOREIGN KEY ("productionId") REFERENCES "productions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS "account_data_requests" (
  "id" UUID PRIMARY KEY, "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
  "type" TEXT NOT NULL, "idempotencyKey" TEXT NOT NULL, "status" TEXT NOT NULL DEFAULT 'QUEUED', "objectKey" TEXT, "failureReason" TEXT,
  "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP, "completedAt" TIMESTAMP(3), "expiresAt" TIMESTAMP(3)
);
CREATE INDEX IF NOT EXISTS "account_data_requests_userId_requestedAt_idx" ON "account_data_requests"("userId","requestedAt");
CREATE INDEX IF NOT EXISTS "account_data_requests_status_requestedAt_idx" ON "account_data_requests"("status","requestedAt");

ALTER TABLE "studio_funding_intents" ADD COLUMN IF NOT EXISTS "providerCheckoutUrl" TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS "studio_funding_intents_provider_providerReference_key" ON "studio_funding_intents"("provider", "providerReference");

CREATE UNIQUE INDEX IF NOT EXISTS "account_data_requests_userId_idempotencyKey_key" ON "account_data_requests"("userId", "idempotencyKey");

CREATE INDEX IF NOT EXISTS "audit_events_actorUserId_createdAt_idx" ON "audit_events"("actorUserId", "createdAt");
CREATE OR REPLACE FUNCTION studio_audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit_events are immutable'; END; $$;
DROP TRIGGER IF EXISTS audit_events_no_update ON "audit_events";
CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON "audit_events" FOR EACH ROW EXECUTE FUNCTION studio_audit_events_immutable();

ALTER TABLE "studio_purchase_quotes" ADD COLUMN IF NOT EXISTS "standaloneLockKey" TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS "studio_purchase_quotes_standaloneLockKey_key" ON "studio_purchase_quotes"("standaloneLockKey");
