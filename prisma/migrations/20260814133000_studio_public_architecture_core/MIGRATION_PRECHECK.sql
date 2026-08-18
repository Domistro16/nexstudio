-- Must return zero rows before the Architecture Core migration is applied.

-- Stable-id ownership must not disagree across the Draft/Production handoff.
SELECT p."id", p."ownerUserId" AS production_owner, d."ownerUserId" AS draft_owner
FROM "productions" p
JOIN "drafts" d ON d."id" = p."id"
WHERE d."ownerUserId" IS NOT NULL AND p."ownerUserId" <> d."ownerUserId";

-- Exact artifact duplicates prevent the new content-addressed uniqueness constraint.
SELECT "productionId", "projectVersion", "artifactType", "contentHash", COUNT(*) AS duplicate_count
FROM "studio_artifacts"
GROUP BY "productionId", "projectVersion", "artifactType", "contentHash"
HAVING COUNT(*) > 1;

-- Entitlements must already be unique by production + approved plan (existing invariant).
SELECT "productionId", "approvedPlanVersion", COUNT(*) AS duplicate_count
FROM "studio_production_entitlements"
GROUP BY "productionId", "approvedPlanVersion"
HAVING COUNT(*) > 1;
