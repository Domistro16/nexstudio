# Production Security Review — Studio Trust / Commerce / Account

**Review date:** 2026-08-14  
**Review result:** **CODE-LEVEL SECURITY PASS WITH OPEN DEPLOYMENT GATES**  
**Payment readiness:** **NOT CERTIFIED**

## Threat model reviewed

The branch was reviewed against account takeover, session replay, CSRF/origin confusion, IDOR/cross-owner reads, price/discount tampering, double debit, double settlement, double refund, quote replay, low-balance interruption, webhook forgery/replay, unsafe file upload, object-key disclosure, bearer-link replay, secret leakage, request flooding, deletion/export leakage and loss of audit evidence.

## High-impact controls present

| Area | Control | Code-level result |
|---|---|---|
| Magic links | keyed secret hash, expiry, atomic one-use claim | PASS |
| Session recovery | identity + session creation atomic with link claim | PASS |
| Sessions | HttpOnly/Secure/SameSite; server revocation | PASS |
| CSRF | configured-origin enforcement on authenticated mutations | PASS |
| Owner isolation | server session ownership filters; no client owner authority | PASS |
| Quote integrity | server calculation + version/rate/discount revalidation | PASS |
| Quote locking | one active lock per owner/production | PASS |
| Debit idempotency | request key + unique entitlement + serializable retries | PASS |
| Funding settlement | provider ref/amount/currency validation + derived ledger key | PASS |
| Technical refund | linked unique reversal; deliverable check | PASS |
| Webhook authenticity | raw-body Stripe HMAC verification + timestamp tolerance | PASS |
| Upload ingress | size/type/signature checks + active-PDF rejection | PASS |
| Malware | quarantine and fail-closed scanner promotion | PASS |
| Asset delivery | hashed, short-lived, limited-use capability tickets | PASS |
| Audit | append-only DB trigger; critical money events transactional | PASS |
| Secrets | production secret requirement; no live-key literals found | PASS |
| Account export | signed one-use download; object/provider refs redacted | PASS |
| Account deletion | recent-auth + zero-balance guard + data/media purge | PASS |

## Security defects corrected during this branch

1. Predictable development secret could otherwise become a silent production fallback. Production now requires a strong configured trust secret.
2. Email magic-link consumption could race. It now uses a serializable transaction and atomic update.
3. Magic-link consumption and session creation were separated by a commit boundary. They are now one transaction.
4. Production Origin validation could accept the incoming request Host as an alternate trusted origin. Production now pins to configured `APP_ORIGIN`.
5. Different purchase keys/tabs could safely avoid a second charge but fail to recover once the quote was consumed. Entitlement reuse now precedes consumed-quote/state rejection.
6. Active Standalone quotes had no single-active database lock. `standaloneLockKey` is unique and cleared on consume/expiry/supersession.
7. Purchase now re-derives discount/final arithmetic instead of trusting stored final cents alone.
8. Funding settlement/refund authorities missing from the integrated live source were implemented with serializable idempotent ledger operations.
9. Uploads are no longer accepted directly into reusable state; quarantine + scanner promotion is mandatory.
10. Production delivery tickets now cascade with the production and do not survive project deletion.
11. Expired account-export objects and deletion-time exports are physically removed.
12. Stripe metadata was reduced to opaque funding-intent identity only.

## Open deployment/security gates

These are release blockers where code inspection cannot substitute for environment evidence:

- **Node 24 / Prisma 7:** run `prisma validate`, `prisma generate`, full `tsc --noEmit`, Next production build.
- **Database baseline/adoption:** Architecture Core's pre-existing V1 baseline migration blocker remains open; validate baseline + trust migration on empty DB and real V1 staging clone.
- **Real PostgreSQL concurrency:** execute `tests/trust-commerce/real_db_adversarial_test.ts` on the production-equivalent PostgreSQL version with at least the delivered parallel purchase/settlement/refund/quote/welcome races.
- **Live payment provider:** configure production Stripe live credentials, prove Checkout creation, signed webhook receipt, duplicate event delivery, amount/reference mismatch rejection, reconciliation and a real ledger credit. Test-mode or mocked payment does not close this gate.
- **Production malware scanner:** deploy ClamAV (or approved replacement) and prove clean/malicious/scanner-down behavior through the actual upload worker.
- **Private object storage:** prove bucket/container is non-public, credentials are least-privilege, transport encryption is enforced, and lifecycle rules match export/quarantine retention.
- **Ingress limits:** enforce request-body limits at the edge/reverse proxy so chunked oversized multipart bodies cannot consume unbounded application memory before the application file-size check.
- **CSP defense-in-depth:** move the production Next runtime from `unsafe-inline` to a nonce/hash CSP after validating framework/runtime compatibility. Current CSP is materially protective but not the strongest XSS posture.
- **Retention/legal policy:** set explicit retention periods for ledger/audit/tombstone and reconcile contractual/legal deletion duties for processor-held payment records before public launch.
- **Operational abuse:** configure alerting for auth/funding/upload anomalies and audit-write failures; rate limits are implemented but operational thresholds require production traffic tuning.

## Security evidence verdict

No Critical/High code defect identified in the final static/adversarial pass is left knowingly unmitigated in the source overlay. That statement does **not** certify the deployment: the live provider, database, scanner, object-storage and build gates above remain mandatory.
