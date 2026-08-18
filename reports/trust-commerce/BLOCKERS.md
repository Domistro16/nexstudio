# Release Blockers — Trust / Commerce / Account

**Do not mark Studio payment-ready or public-secure until every REQUIRED gate below passes on the frozen release build.**

| ID | Gate | Status | Required evidence |
|---|---|---|---|
| TC-01 | Node >=24 + Prisma 7 dependency-complete validation | OPEN | `prisma validate`, `prisma generate`, `tsc --noEmit`, production Next build |
| TC-02 | V1 baseline + trust migration | OPEN | Empty-DB bootstrap + real V1 staging adoption + no drift |
| TC-03 | Real PostgreSQL billing concurrency | OPEN | 12-case delivered suite passes; no double debit/fund/refund/redemption |
| TC-04 | Live Stripe funding | OPEN | Live Checkout + real settlement + real USD ledger credit |
| TC-05 | Signed webhook delivery/replay | OPEN | Production endpoint verifies genuine signature; duplicate delivery is idempotent |
| TC-06 | Provider mismatch/failure recovery | OPEN | Wrong amount/currency/reference rejected; provider failure preserves production/balance |
| TC-07 | Production ClamAV | OPEN | clean, malicious-test and scanner-down cases through real worker |
| TC-08 | Private object store | OPEN | bucket non-public; least privilege; encryption; lifecycle tested |
| TC-09 | Edge upload body limit | OPEN | proxy/platform enforces body ceiling before application buffering |
| TC-10 | Account export/delete staging run | OPEN | export download/expiry; zero-balance delete; media purge; old-session/link invalidation |
| TC-11 | Retention/privacy policy approval | OPEN | documented ledger/audit/tombstone/payment-processor retention |
| TC-12 | CSP nonce/hash hardening | OPEN (defense-in-depth) | remove `unsafe-inline` after Next production build/e2e validation |
| TC-13 | Operational monitoring | OPEN | alerts for auth abuse, webhook failures, scanner failures, audit write failures |

A test-mode Stripe key, mocked provider, in-memory repository, deterministic model, browser success redirect or manually edited database row **cannot** close TC-04/TC-05.
