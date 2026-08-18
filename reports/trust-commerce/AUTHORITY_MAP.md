# Authority Map — Trust / Commerce / Account

| Domain | Canonical authority | Rule |
|---|---|---|
| Guest production intent | Branch C `Draft` | Anonymous/pre-auth envelope only |
| Authenticated lifecycle | Architecture Core `Production.studioState` | All trusted post-promotion transitions are server-side |
| Production identity | `Production.id == Draft.id` | Stable from first prompt through auth/payment/revision |
| Email identity | `AuthIdentity(provider=EMAIL)` + verified magic challenge | Social providers remain disabled until explicitly approved |
| Session | `Session` DB row + HttpOnly bearer cookie | Client cannot author user identity |
| USD balance | `StudioCreditAccount.balanceMinor` | Legacy internal physical name; customer semantics are USD balance |
| Quote | `StudioPurchaseQuote` | Server duration/rate/discount snapshot; one active standalone lock |
| Price policy | `STANDALONE_STUDIO_BILLING` | Integer USD cents; pricingVersion must change with policy |
| Welcome policy | server quote/purchase revalidation + `StudioWelcomeRedemption` | Unique per owner/discount code |
| Paid production | `StudioProductionEntitlement` | Unique per production + approved plan; binds workflow/debit |
| Funding | `StudioFundingIntent` + verified provider settlement | Browser redirect is never proof of payment |
| Ledger | immutable `StudioLedgerEntry` semantics | Funding, debit and refund are separate idempotent entries |
| Technical refund | reversal linked to paid debit | At most one automatic refund; no deliverable allowed |
| Billing history | owner-scoped ledger projection | Public names contain no credits/tokens/crypto wording |
| Notifications | `StudioNotification` | Owner-scoped durable dedupe |
| Upload | `Source` + `UploadScanJob` | Quarantine until approved scanner CLEAN verdict |
| Asset delivery | `AssetDeliveryTicket` | Short-lived hashed capability; object key remains private |
| Rate limit | `RateLimitBucket` | Persistent per-key/category/window counters |
| Audit | `AuditEvent` + immutable DB trigger | Critical monetary audit is transaction-bound |
| Export/delete | `AccountDataRequest` worker | Recent-auth/zero-balance deletion; signed expiring exports |
| Creative authority | existing NexMind/P8/Directors/family engines | **Not modified by this branch** |
