# STUDIO PUBLIC 10/10 — Trust, Commerce & Account Infrastructure Handoff

**Date:** 2026-08-14  
**Branch:** Trust, Commerce & Account Infrastructure  
**Input source:** `STUDIO_V1_NEXMIND_AUTONOMOUS_CREATIVE_AUTHORITY_INTEGRATED_SOURCE_2026-08-14.zip`  
**Input SHA-256:** `d7e2fb6c0e0b3e760a2f791a2970cfd7165f5356b090a2b90ca8137ede162b0a`  
**UI boundary:** no main Studio redesign  
**Creative boundary:** NexMind/Directors/family execution logic unchanged  
**Status:** **IMPLEMENTATION PASS / LIVE PAYMENT READINESS OPEN / PRODUCTION DEPLOYMENT CERTIFICATION OPEN**

## 1. Recovered authority

This branch preserves the recovered Branch C contract: anonymous `Draft` is the guest/pre-auth intent envelope; authenticated `Production` is the canonical lifecycle authority; promotion preserves the same UUID; browser owner/state fields are not authority.

It preserves and completes Branch E semantics: customer money is USD balance in integer cents; quotes are server-authoritative, locked and expiring; client price fields cannot authorize purchase; debit + entitlement + durable workflow are atomic; low balance never destroys the production; funding settlement and technical refund are idempotent; the welcome discount is server policy, not a browser flag.

Architecture Core remains the post-promotion production authority. No second Studio lifecycle, ledger, wallet, production family, Director authority or creative planner was introduced.

## 2. Implemented account/authentication authority

- Approved **email magic-link auth** with one-use, expiring challenge tokens stored only as keyed hashes.
- Magic-link claim, user/identity resolution and session creation are one serializable transaction, so a failed session write does not burn a valid recovery link.
- 30-day server sessions use random bearer values with keyed HMAC hashes in storage, HttpOnly cookies, SameSite=Lax and Secure in production.
- Session inventory and revoke-other-sessions endpoint.
- Guest draft/auth continuation remains Branch C stable-ID handoff; auth does not create a replacement production.
- No social provider is exposed because no canonical approved social-provider contract was recovered. `AuthIdentity` supports later explicitly approved providers without inventing one now.
- Deleted accounts cannot be resurrected through an old email link/session.

## 3. Commerce authority

- USD balance only; customer-facing history maps internal legacy event names to `BALANCE_ADDED`, `PRODUCTION_PAYMENT`, `PRODUCTION_REFUND`, or `ADJUSTMENT`.
- Quote lock: one active Standalone Studio quote per owner/production via `standaloneLockKey` plus serializable retries.
- Purchase recalculates duration price, discount arithmetic, pricing version/rate, ownership and welcome eligibility server-side.
- Same idempotency key replays the original debit; different keys/tabs converge on the unique paid entitlement and return the original paid result.
- Low balance writes `INSUFFICIENT_BALANCE` with zero debit and preserves production/draft/plan identity.
- Exact-production funding computes the shortfall server-side. General USD balance top-up is separately supported.
- Stripe Checkout implementation is real code, not a mock: server creates Checkout Sessions, provider amount/currency/reference are revalidated, only signature-verified webhooks or authenticated server reconciliation may settle funding.
- Provider settlement posts one `FUNDING_CREDIT`; retry/replayed delivery cannot double-fund.
- Paid production purchase remains a separate ledger debit after funding settles, so external funds are not lost if production purchase/job creation fails.
- Permanent no-deliverable technical failure may create one linked technical refund; a delivered production cannot use that automatic refund path.
- Worker retry exhaustion can reach canonical `PRODUCTION_FAILED` and invoke the technical refund authority without changing creative quality logic.

## 4. Payment readiness boundary

**Payment is not certified ready in this handoff.** The code intentionally fails closed unless a configured provider passes production configuration checks. No mock, deterministic repository, test key, browser redirect, or local webhook simulation is counted as live payment evidence.

Live readiness requires all gates in `BLOCKERS.md`, including a live Stripe configuration, signed webhook delivery against the deployed endpoint, real PostgreSQL concurrency, and reconciliation of an actual provider settlement into the real ledger.

## 5. Upload + asset security

- Upload size/type allowlist and filename normalization.
- Byte-signature MIME detection; declared MIME mismatch rejected.
- Active PDF actions/embedded executable-style features rejected before storage.
- New uploads enter a private quarantine namespace and are `ANALYSING/QUARANTINED`, never `READY`.
- ClamAV INSTREAM scanner worker is fail-closed: missing/unavailable scanner never marks an asset clean.
- Only a clean scanner verdict moves bytes to the final private source namespace and marks the Source `READY/CLEAN`.
- Signed/capability delivery tickets store only a keyed token hash, expire quickly, have atomic use limits, and are owner-scoped at issuance.
- Delivery responses never expose private object-storage keys.
- Production-linked tickets now have a database FK and are deleted with the production.

## 6. Owner isolation + abuse controls

- Owner is derived from the authenticated server session, not accepted from client owner fields.
- Owner filters are applied to productions, sources, sessions, funding reconciliation, billing history and ticket issuance.
- Authenticated mutations enforce configured-origin checks; production does not trust the request `Host` as an alternate origin.
- General mutation user/IP rate limits plus tighter email, funding, upload, delivery and account-data limits.
- Payment webhooks accept only raw-body signature-verified provider events.
- Common embedded live-secret signatures are scanned by the branch QA; no matches were found.

## 7. Audit + notifications

- Durable `AuditEvent` records cover auth, sessions, uploads, delivery, account requests and critical billing transitions.
- Database trigger makes audit rows append-only (`UPDATE` and `DELETE` rejected).
- Funding settlement and technical refund audit writes occur in the same serializable transaction as the money movement.
- Durable in-app notifications have per-user dedupe keys; funding and refund notifications are idempotent.

## 8. Account export/deletion

- Account export is queued, owner-scoped and returned through one-use signed delivery; stored object keys/provider references are redacted from export payloads.
- Export artifacts expire after seven days and the worker physically removes expired export objects.
- Deletion requires literal confirmation, a session created within the previous 15 minutes, and zero remaining USD balance. Money is never silently discarded.
- Deletion removes sessions, auth identities/challenges, signed tickets, notifications, source media/quarantine, production media, Brand/Cast/Series/Memory and productions.
- Old email magic links are invalidated and previous export objects are removed.
- A pseudonymous user tombstone and financial/audit records are retained so immutable ledger/reversal and security evidence are not falsified. Production policy/legal review must set retention periods before public launch.

## 9. Provider-data minimization

Stripe metadata contains only the opaque funding-intent identifier required for settlement. Studio user ID and production ID are not sent as Stripe metadata.

## 10. Security headers

Global headers retain CSP, frame denial, `nosniff`, strict referrer policy and no-store API responses; production also adds HSTS and a restrictive Permissions-Policy. The existing Next runtime CSP still permits inline script/style for compatibility; nonce-based CSP hardening is listed as a defense-in-depth deployment item rather than silently risking UI breakage in this branch.

## 11. Fresh evidence

| Gate | Result |
|---|---:|
| Trust/security static/adversarial contract QA | **43/43 PASS** |
| Runtime Stripe-signature/upload helper tests | **7/7 PASS** |
| Deterministic adversarial billing model | **14/14 PASS** |
| Architecture Core regression | **32/32 PASS** |
| Standalone product regression | **10/10 PASS** |
| TypeScript/TSX transpile syntax audit | **127/127 PASS** |
| Real PostgreSQL adversarial suite | **12 cases delivered / NOT RUN here** |
| Live Stripe settlement/webhook | **OPEN — no live credentials/environment evidence** |
| Production ClamAV scanner | **OPEN — no deployed scanner evidence** |
| Node 24 + Prisma 7 dependency-complete build/migration | **OPEN** |

The deterministic billing model is supporting contract evidence only and is **not** used as payment-readiness evidence.

## 12. Files delivered

- integrated source archive;
- patch archive containing only changed/added files;
- executable 12-case real-PostgreSQL adversarial suite;
- deterministic billing and runtime-security tests;
- security review;
- authority map;
- blockers/release gates;
- test results and SHA-256 manifests.

## 13. Verdict

**Trust/commerce/account implementation: PASS at code/contract level.**  
**Main Studio UI redesign: none.**  
**NexMind/Director/family creative logic: unchanged.**  
**Payment readiness: NOT CLAIMED.**  
**Production security/deployment certification: OPEN until the real environment gates are executed and pass.**
