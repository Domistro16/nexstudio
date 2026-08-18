# Real PostgreSQL + live-provider adversarial gates

These gates are mandatory before `paymentReady=true`. They intentionally cannot be satisfied by the deterministic model test.

1. Apply the canonical baseline + Architecture Core + Trust/Commerce migration to a PostgreSQL staging clone with Prisma 7 / Node >=24.
2. Send 25 concurrent purchase requests for one production using the same key; assert one debit, one entitlement, one workflow.
3. Send 25 concurrent purchase requests with different keys; assert the unique production/plan entitlement still permits one debit only.
4. Race welcome-eligible first purchases for two different productions; assert one welcome redemption and at most one discounted debit.
5. Deliver the same signed Stripe event at least 25 times and concurrently; assert one `FUNDING_CREDIT` and one balance increase.
6. Replay a different Stripe Session against an existing funding intent; assert reference mismatch and no ledger movement.
7. Send a signature-invalid webhook, a stale signature, a wrong amount, and wrong currency; assert zero ledger movement.
8. Kill the app after provider payment but before production debit; assert funding stays in USD balance and purchase can resume safely.
9. Kill the app during purchase transaction; assert either full debit+entitlement+workflow commit or no debit.
10. Trigger permanent no-deliverable technical failure concurrently; assert exactly one linked refund reversal.
11. Attempt automatic technical refund after a deliverable exists; assert rejection.
12. Repeat all owner-scoped billing and delivery endpoints using a second user's session; assert 404/authorization-safe rejection and no existence leak.
13. Upload clean and malware test fixtures through quarantine; assert only scanner-clean sources become `READY`.
14. Exercise account export/deletion on a staging account; assert object deletion, session revocation, retained financial tombstone, and positive-balance deletion block.
15. Verify live Stripe account mode, webhook endpoint secret, successful real low-value funding, webhook receipt, and bank/card settlement in the target launch geography.
