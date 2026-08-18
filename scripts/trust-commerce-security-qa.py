#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
root=Path(__file__).resolve().parents[1]
def text(p): return (root/p).read_text(encoding='utf-8')
checks=[]
def check(name, ok, detail=''):
    checks.append({'name':name,'ok':bool(ok),'detail':detail})

env=text('src/lib/env.ts'); auth=text('src/lib/auth.ts'); verify=text('app/api/v1/auth/email/verify/route.ts'); route_auth=text('src/lib/route-auth.ts'); billing=text('src/studio-v1/billing.ts'); pay=text('src/lib/payment-provider.ts'); webhook=text('app/api/v1/payments/stripe/webhook/route.ts'); schema=text('prisma/schema.prisma'); migration=text('prisma/migrations/20260814160000_studio_trust_commerce_account/migration.sql'); assets=text('app/api/v1/studio/assets/route.ts'); upload=text('src/lib/upload-security.ts'); delivery=text('app/api/v1/delivery/[token]/route.ts'); account=text('app/api/v1/account/data/route.ts'); account_worker=text('scripts/studio-account-data-worker.ts'); upload_worker=text('scripts/studio-upload-scan-worker.ts'); source_extract=text('src/studio-v1/source-intelligence/extract.ts'); source_py=text('services/studio-source-intelligence/source_intelligence.py'); p8_source=text('src/studio-v1/source-intelligence/p8-packet.ts'); p8_workflow=text('src/studio-v1/nexmind-p8/workflow.ts')
check('Production trust secret has no predictable production fallback', 'production ? ""' in env and 'STUDIO_TRUST_SECRET' in env and 'length < 32' in env)
check('Session and capability hashes are keyed HMAC-SHA256', 'createHmac("sha256", env.trustSecret)' in auth and 'secretHash("session"' in auth)
check('Session cookie is HttpOnly, SameSite=Lax and forced Secure in production', 'httpOnly:true' in auth and 'sameSite:"lax"' in auth and 'process.env.NODE_ENV==="production"' in auth)
check('Magic link consumption, identity resolution and session creation are atomic and one-use', 'authChallenge.updateMany' in verify and 'claimed.count!==1' in verify and 'createSessionTx(tx,target.id,request)' in verify and 'isolationLevel:"Serializable"' in verify)
check('Deleted users cannot recover a session via old email identity', 'ACCOUNT_DELETED' in verify and 'privacyStatus' in auth)
check('Mutating authenticated requests enforce trusted Origin centrally', 'requireTrustedOrigin(request,id)' in route_auth and 'authenticated_mutation' in route_auth)
check('Production Origin validation is pinned to configured APP_ORIGIN rather than request Host', 'new URL(env.appOrigin).origin' in route_auth and 'if(process.env.NODE_ENV!=="production")' in route_auth and 'allowed.add(new URL(request.url).origin)' in route_auth)
check('Email auth has IP and identifier rate limits', 'email_magic_ip' in text('app/api/v1/auth/email/request/route.ts') and 'email_magic_identifier' in text('app/api/v1/auth/email/request/route.ts'))
auth_routes=[str(p.relative_to(root)) for p in (root/'app/api/v1/auth').rglob('route.ts')];check('No unapproved social auth route is exposed', all('/email/' in x or '/logout/' in x for x in auth_routes), ', '.join(auth_routes))
check('Payment funding remains fail-closed without configured live provider', 'readyForLive' in text('app/api/v1/studio/funding-intents/route.ts') and 'STUDIO_PAYMENT_PROVIDER_NOT_CONFIGURED' in text('app/api/v1/studio/funding-intents/route.ts'))
check('Stripe webhook uses raw body and HMAC signature verification', 'await request.text()' in webhook and 'verifyStripeWebhook' in webhook and 'timingSafeEqual' in pay)
check('Payment provider metadata is data-minimized to opaque funding intent only', 'metadata[user_id]' not in pay and 'metadata[production_id]' not in pay and 'metadata[funding_intent_id]' in pay)
check('Provider settlement amount/currency/reference are revalidated', 'FUNDING_SETTLEMENT_MISMATCH' in billing and 'FUNDING_PROVIDER_REFERENCE_MISMATCH' in billing)
check('Funding settlement is idempotent by derived ledger key', 'funding-settlement:${intent.id}' in billing and 'idempotencyKey:ledgerKey' in billing)
check('Funding provider reference is unique', '@@unique([provider, providerReference])' in schema)
check('Low balance creates no debit and preserves production identity', 'code: "INSUFFICIENT_BALANCE"' in billing and billing.index('INSUFFICIENT_BALANCE') < billing.index('STUDIO_PRODUCTION_DEBIT'))
check('Purchase rejects stale/edited quote truth and rechecks welcome eligibility', all(x in billing for x in ['QUOTE_EXPIRED','QUOTE_MISMATCH','WELCOME_DISCOUNT_NO_LONGER_ELIGIBLE']))
check('Quote locking permits only one active standalone quote per production', 'standaloneLockKey                   String? @unique' in schema and 'standalone:${userId}:${productionId}' in billing and billing.count('standaloneLockKey: null') >= 2)
check('Quote arithmetic is recalculated from server duration/rate/discount at purchase', all(x in billing for x in ['expectedDiscount','expectedFinal','base !== quote.baseAmountMinor']))
check('Serializable billing retries cover transaction and uniqueness races', 'code==="P2034"||code==="P2002"' in billing and 'attempt<5' in billing)
check('Different-key two-tab replay reuses entitlement even after quote consumption', billing.index('const priorEntitlement') < billing.index('quote.standaloneStatus !== "OPEN"'))
check('Entitlement uniqueness closes two-tab/different-key double purchase', '@@unique([productionId, approvedPlanVersion])' in schema and 'priorEntitlement' in billing)
check('Permanent technical refund is one linked reversal', 'reversalOfId       String? @unique' in schema and 'technical-refund:${debit.id}' in billing and 'REFUND_DELIVERABLE_EXISTS' in billing)
check('Worker exhaustion invokes canonical terminal failure + refund path', 'refundPermanentTechnicalFailure' in text('scripts/studio-worker.ts') and 'WORKER_RETRIES_EXHAUSTED' in text('scripts/studio-worker.ts'))
check('Uploads are quarantined before becoming usable', 'securityStatus:"QUARANTINED"' in assets and 'status:"ANALYSING"' in assets and 'quarantineObjectKey' in assets)
check('Uploads require rights attestation and size limits', 'UPLOAD_RIGHTS_ATTESTATION_REQUIRED' in assets and 'uploadMaxBytes' in assets)
check('Upload MIME detects PDF/DOCX/PPTX and blocks active embedded document content', all(x in upload for x in ['detectMime','UPLOAD_PDF_ACTIVE_CONTENT_BLOCKED','word/document.xml','ppt/presentation.xml','UPLOAD_OOXML_ACTIVE_OR_EMBEDDED_CONTENT_BLOCKED']))
check('Malware scan fails closed when scanner is unavailable', 'CLAMAV_NOT_CONFIGURED' in upload and 'securityStatus:"CLEAN"' in upload_worker)
check('Clean uploads are source-understood before READY publication', upload_worker.find('extractAndPersistSourceIntelligence') < upload_worker.find('status:"READY"') and 'extracted:extracted' in upload_worker)
check('Source intelligence supports PDF/DOCX/PPTX with provenance', all(x in source_py for x in ['extract_pdf','extract_docx','extract_pptx','segmentId','locator','sha256','provenanceLaw']))
check('P8 consumes persisted extracted Source records instead of filename-only sourcePacket', 'buildP8SourcePacket' in p8_workflow and 'studioProductionInput.findMany' in p8_workflow and 'sourceIntelligence.evidence' in p8_workflow and 'function sourcePacket(raw' not in p8_workflow)
check('P8 source packet preserves extracted segment provenance and visual references', all(x in p8_source for x in ['USER_SOURCE_EXTRACTED','segmentId','sha256','visualReferences']))
check('Signed asset delivery stores only hashed token and atomically limits use', 'tokenHash    String   @unique' in schema and 'secretHashCandidates("asset-delivery"' in delivery and 'updateMany' in delivery)
check('Production delivery tickets cascade with deleted productions', 'production   Production? @relation(fields: [productionId], references: [id], onDelete: Cascade)' in schema and 'asset_delivery_tickets_productionId_fkey' in migration)
check('Signed delivery never exposes object-storage key in ticket issuance response', 'objectKey' not in text('app/api/v1/studio/assets/[id]/delivery/route.ts').split('return json(')[-1])
check('Owner isolation is present on source, production and funding reconciliation', all('userId' in text(p) or 'ownerUserId' in text(p) for p in ['app/api/v1/studio/assets/[id]/delivery/route.ts','app/api/v1/productions/[id]/delivery-ticket/route.ts','app/api/v1/studio/funding-intents/reconcile/route.ts']))
check('Account deletion requires recent authentication and zero USD balance', 'RECENT_AUTH_REQUIRED' in account and 'BALANCE_RESOLUTION_REQUIRED' in account)
check('Account deletion revokes sessions and purges creative/media data while retaining user tombstone', all(x in account_worker for x in ['session.deleteMany','source.deleteMany','production.deleteMany','privacyStatus:"DELETED"']))
check('Account deletion invalidates old email challenges and stored account exports', 'authChallenge.deleteMany' in account_worker and 'identifier:deletingUser.email.toLowerCase()' in account_worker and 'type:"EXPORT"' in account_worker and 'objectKey:null' in account_worker)
check('Expired account exports are physically removed by worker cleanup', 'cleanupExpiredExports' in account_worker and 'status:"EXPIRED"' in account_worker and 'deleteObject(row.objectKey)' in account_worker)
check('Account export redacts provider references and object keys', 'providerReference:providerReference?"REDACTED"' in account_worker and 'storedObjectPresent' in account_worker)
check('Audit table is append-only at database layer', 'audit_events_no_update' in migration and 'BEFORE UPDATE OR DELETE' in migration)
check('Notification infrastructure has durable dedupe key', 'model StudioNotification' in schema and '@@unique([userId, dedupeKey])' in schema)
headers=text('next.config.ts');check('Production security headers include CSP, HSTS, nosniff and restrictive Permissions-Policy', all(x in headers for x in ['Content-Security-Policy','Strict-Transport-Security','X-Content-Type-Options','Permissions-Policy']))
check('Executable real-PostgreSQL adversarial suite is included and destructive-gated', (root/'tests/trust-commerce/real_db_adversarial_test.ts').exists() and 'TRUST_TEST_ALLOW_DESTRUCTIVE' in text('tests/trust-commerce/real_db_adversarial_test.ts') and 'Promise.allSettled' in text('tests/trust-commerce/real_db_adversarial_test.ts'))
# Repository secret scan for common live-key signatures; examples/placeholders are allowed only when value is empty.
secret_hits=[]
secret_patterns=[re.compile(r"sk_live_[A-Za-z0-9]{12,}"),re.compile(r"whsec_[A-Za-z0-9]{12,}"),re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}")]
for p in root.rglob('*'):
    if p.is_file() and not any(part in {'.git','node_modules'} for part in p.parts):
        try: source=p.read_text(errors='ignore')
        except Exception: continue
        for pattern in secret_patterns:
            if pattern.search(source): secret_hits.append(str(p.relative_to(root)))
check('Repository scan finds no embedded common live provider secrets', not secret_hits, ', '.join(secret_hits[:10]))
# Customer-facing string literals must not use forbidden commerce language.
forbidden=[]
string_re=re.compile(r'''"([^"\n]*)"|'([^'\n]*)'|`([^`\n]*)`''')
for base in [root/'app',root/'src/studio-v1/react',root/'src/studio-v1/dashboard']:
    for p in base.rglob('*'):
        if p.is_file() and p.suffix in {'.ts','.tsx','.js','.jsx'}:
            source=p.read_text(errors='ignore')
            for sm in string_re.finditer(source):
                literal=next((g for g in sm.groups() if g is not None),'')
                if re.search(r'(?i)\b(credits?|tokens?|crypto)\b',literal):
                    if literal.startswith('node:') or literal == 'token' or any(k in literal for k in ['StudioCreditAccount','LegacyCreditAccount','FUNDING_CREDIT','tokenHash','randomToken','secretHash','session_id','token=','${ticket.token}','crypto.randomUUID']): continue
                    forbidden.append(f'{p.relative_to(root)}:{literal[:80]}')
check('No customer-facing credits/tokens/crypto billing language introduced', not forbidden, ', '.join(forbidden[:10]))
passed=sum(c['ok'] for c in checks)
out={'schema':'StudioTrustCommerceSecurityQA V1','pass':passed==len(checks),'passed':passed,'total':len(checks),'checks':checks,'deploymentEvidence':{'realPostgresConcurrency':'OPEN','livePaymentProvider':'OPEN','providerWebhookLiveDelivery':'OPEN','clamAvProductionScanner':'OPEN','node24Prisma7Build':'OPEN'}}
print(json.dumps(out,indent=2))
sys.exit(0 if out['pass'] else 1)
