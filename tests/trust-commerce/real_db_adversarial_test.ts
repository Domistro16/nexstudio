/**
 * Destructive, staging-only adversarial test against the actual Prisma/PostgreSQL
 * repository and the actual Studio billing service. This file is release evidence
 * only when it executes against a migrated PostgreSQL staging clone with the same
 * database/version/transaction semantics as production.
 */
import { randomUUID } from "node:crypto";
import assert from "node:assert/strict";

const databaseUrl = process.env.TRUST_TEST_DATABASE_URL?.trim();
if (!databaseUrl || process.env.TRUST_TEST_ALLOW_DESTRUCTIVE !== "true") {
  console.error("REAL_DB_GATE_NOT_RUN: set TRUST_TEST_DATABASE_URL and TRUST_TEST_ALLOW_DESTRUCTIVE=true for a dedicated disposable PostgreSQL staging database.");
  process.exit(2);
}
if (/prod(uction)?/i.test(databaseUrl) && process.env.TRUST_TEST_ALLOW_PRODUCTION_DATABASE !== "I_ACCEPT_DATA_LOSS") {
  console.error("REFUSING_PRODUCTION_LIKE_DATABASE_URL");
  process.exit(2);
}
process.env.DATABASE_URL = databaseUrl;
process.env.STUDIO_FIRST_PRODUCTION_DISCOUNT_ENABLED = "true";
process.env.STUDIO_FIRST_PRODUCTION_DISCOUNT_PERCENT = "10";

const [{ getPrisma }, billing] = await Promise.all([
  import("../../src/lib/db"),
  import("../../src/studio-v1/billing"),
]);
const prisma = getPrisma();
if (!prisma) throw new Error("TEST_DATABASE_NOT_AVAILABLE");

const createdUsers: string[] = [];
const results: Array<{ name: string; ok: boolean; detail?: string }> = [];
const record = async (name: string, fn: () => Promise<void>) => {
  try { await fn(); results.push({ name, ok: true }); }
  catch (error) { results.push({ name, ok: false, detail: error instanceof Error ? error.message : String(error) }); }
};

function previewJson(duration = 30) {
  const quarter = Math.floor(duration / 4);
  return {
    thesis: "Explain the product benefit clearly and concisely.",
    recommendedDuration: duration,
    beats: [
      { start: 0, end: quarter, purposeTitle: "Problem", description: "Establish the audience problem." },
      { start: quarter, end: quarter * 2, purposeTitle: "Approach", description: "Introduce the product approach." },
      { start: quarter * 2, end: quarter * 3, purposeTitle: "Proof", description: "Show why the approach is useful." },
      { start: quarter * 3, end: duration, purposeTitle: "Close", description: "End with the core takeaway." },
    ],
    missingInput: [],
  };
}

async function makeUser(balanceMinor = 1000) {
  const suffix = randomUUID();
  const user = await prisma.user.create({ data: { email: `trust-${suffix}@example.test`, displayName: "Trust Gate" } });
  createdUsers.push(user.id);
  await prisma.studioCreditAccount.create({ data: { userId: user.id, balanceMinor } });
  return user;
}

async function makeProduction(userId: string, state: "PLAN_READY" | "PAYMENT_REQUIRED" = "PLAN_READY", duration = 30) {
  const id = randomUUID();
  await prisma.draft.create({ data: {
    id, ownerUserId: userId, title: "Adversarial billing gate", family: "EXPLAINER", videoType: "explainer",
    prompt: "Create a concise explainer for a production-grade adversarial billing test.", studioState: state,
    sources: [], duration, aspectRatio: "16:9",
  } });
  await prisma.production.create({ data: {
    id, ownerUserId: userId, title: "Adversarial billing gate", status: "DIRECTION_READY", studioState: state, direction: {},
  } });
  const request = await prisma.studioPlanPreviewRequest.create({ data: {
    userId, productionId: id, idempotencyKeyHash: randomUUID(), bodyHash: randomUUID(), requestFingerprint: randomUUID(),
    state: "SUCCEEDED", policyVersion: "real-db-gate", provider: "test-fixture-not-payment-provider", model: "fixture", reasoningEffort: "none",
    responseJson: previewJson(duration), completedAt: new Date(),
  } });
  return { id, planPreviewId: request.id };
}

async function setBalance(userId: string, amount: number) {
  await prisma.studioCreditAccount.update({ where: { userId }, data: { balanceMinor: amount } });
}

try {
  await record("parallel quote locking leaves exactly one active quote", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id);
    const attempts = await Promise.allSettled(Array.from({ length: 12 }, () => billing.createStandaloneStudioQuote(user.id, p.id)));
    assert.equal(attempts.filter(x => x.status === "fulfilled").length, 12);
    const rows = await prisma.studioPurchaseQuote.findMany({ where: { userId: user.id, productionId: p.id, mode: "STANDALONE_STUDIO" } });
    assert.equal(rows.filter(x => x.standaloneStatus === "OPEN" && x.standaloneLockKey).length, 1);
    assert.equal(rows.filter(x => x.standaloneStatus === "OPEN").length, 1);
  });

  await record("25 parallel different purchase keys yield one debit, entitlement and workflow", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id);
    const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    const calls = await Promise.allSettled(Array.from({ length: 25 }, (_, i) => billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: `parallel-purchase-${i}-${randomUUID()}` })));
    assert.equal(calls.filter(x => x.status === "fulfilled").length, 25);
    const [debits, entitlements, workflows, account] = await Promise.all([
      prisma.studioLedgerEntry.findMany({ where: { userId: user.id, productionId: p.id, type: "STUDIO_PRODUCTION_DEBIT" } }),
      prisma.studioProductionEntitlement.findMany({ where: { userId: user.id, productionId: p.id } }),
      prisma.studioWorkflowRun.findMany({ where: { productionId: p.id } }),
      prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } }),
    ]);
    assert.equal(debits.length, 1); assert.equal(entitlements.length, 1); assert.equal(workflows.length, 1);
    assert.equal(account.balanceMinor, 1000 - quote.finalAmountMinor);
  });

  await record("same idempotency key replay returns original purchase", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id);
    const quote = await billing.createStandaloneStudioQuote(user.id, p.id); const key = `same-key-${randomUUID()}`;
    const first = await billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: key });
    const second = await billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: key });
    assert.equal(first.ok, true); assert.equal(second.ok, true);
    if (first.ok && second.ok) { assert.equal(first.debitTransactionId, second.debitTransactionId); assert.equal(second.reused, true); }
  });

  await record("cross-owner purchase cannot observe or debit another account", async () => {
    const victim = await makeUser(1000); const attacker = await makeUser(1000); const p = await makeProduction(victim.id);
    const quote = await billing.createStandaloneStudioQuote(victim.id, p.id);
    await assert.rejects(() => billing.purchaseStandaloneStudioProduction({ userId: attacker.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() }), /PRODUCTION_NOT_FOUND|QUOTE_NOT_FOUND/);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: attacker.id } })).balanceMinor, 1000);
  });

  await record("expired quote cannot debit", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id); const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    await prisma.studioPurchaseQuote.update({ where: { id: quote.quoteId }, data: { expiresAt: new Date(Date.now() - 1000) } });
    await assert.rejects(() => billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() }), /QUOTE_EXPIRED/);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } })).balanceMinor, 1000);
  });

  await record("tampered quote arithmetic is revalidated server-side", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id); const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    await prisma.studioPurchaseQuote.update({ where: { id: quote.quoteId }, data: { amountMinor: 1, finalAmountMinor: 1 } });
    await assert.rejects(() => billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() }), /QUOTE_MISMATCH/);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } })).balanceMinor, 1000);
  });

  await record("low balance creates no debit and preserves stable production identity", async () => {
    const user = await makeUser(0); const p = await makeProduction(user.id); const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    const result = await billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() });
    assert.equal(result.ok, false);
    assert.equal(await prisma.studioLedgerEntry.count({ where: { userId: user.id, productionId: p.id, type: "STUDIO_PRODUCTION_DEBIT" } }), 0);
    const [draft, production] = await Promise.all([prisma.draft.findUniqueOrThrow({ where: { id: p.id } }), prisma.production.findUniqueOrThrow({ where: { id: p.id } })]);
    assert.equal(draft.id, production.id); assert.equal(production.studioState, "INSUFFICIENT_BALANCE");
  });

  await record("25 duplicate provider settlements credit exactly once", async () => {
    const user = await makeUser(0);
    const intent = await prisma.studioFundingIntent.create({ data: { userId: user.id, currency: "USD", amountMinor: 275, purpose: "BALANCE_TOPUP", status: "PAYMENT_PENDING", idempotencyKey: randomUUID(), provider: "stripe", providerReference: `cs_test_${randomUUID()}` } });
    const calls = await Promise.allSettled(Array.from({ length: 25 }, () => billing.settleStandaloneFundingIntent({ fundingIntentId: intent.id, providerReference: intent.providerReference!, amountMinor: 275, currency: "USD" })));
    assert.equal(calls.filter(x => x.status === "fulfilled").length, 25);
    assert.equal(await prisma.studioLedgerEntry.count({ where: { userId: user.id, type: "FUNDING_CREDIT" } }), 1);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } })).balanceMinor, 275);
  });

  await record("provider amount mismatch cannot credit", async () => {
    const user = await makeUser(0);
    const intent = await prisma.studioFundingIntent.create({ data: { userId: user.id, currency: "USD", amountMinor: 275, purpose: "BALANCE_TOPUP", status: "PAYMENT_PENDING", idempotencyKey: randomUUID(), provider: "stripe", providerReference: `cs_test_${randomUUID()}` } });
    await assert.rejects(() => billing.settleStandaloneFundingIntent({ fundingIntentId: intent.id, providerReference: intent.providerReference!, amountMinor: 274, currency: "USD" }), /FUNDING_SETTLEMENT_MISMATCH/);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } })).balanceMinor, 0);
  });

  await record("welcome discount cannot be redeemed concurrently across two productions", async () => {
    const user = await makeUser(1000); const p1 = await makeProduction(user.id); const p2 = await makeProduction(user.id);
    const [q1, q2] = await Promise.all([billing.createStandaloneStudioQuote(user.id, p1.id), billing.createStandaloneStudioQuote(user.id, p2.id)]);
    assert.ok(q1.discount && q2.discount);
    const r = await Promise.allSettled([
      billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p1.id, quoteId: q1.quoteId, idempotencyKey: randomUUID() }),
      billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p2.id, quoteId: q2.quoteId, idempotencyKey: randomUUID() }),
    ]);
    assert.equal(await prisma.studioWelcomeRedemption.count({ where: { userId: user.id } }), 1);
    assert.equal(await prisma.studioLedgerEntry.count({ where: { userId: user.id, type: "STUDIO_PRODUCTION_DEBIT" } }), 1);
    assert.equal(r.filter(x => x.status === "fulfilled").length, 1);
  });

  await record("25 terminal-failure refund replays restore paid amount once", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id); const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    const purchase = await billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() });
    assert.equal(purchase.ok, true);
    await prisma.production.update({ where: { id: p.id }, data: { studioState: "PRODUCTION_FAILED", status: "FAILED", currentVersionId: null } });
    const calls = await Promise.allSettled(Array.from({ length: 25 }, () => billing.refundPermanentTechnicalFailure({ userId: user.id, productionId: p.id, reason: "REAL_DB_GATE" })));
    assert.equal(calls.filter(x => x.status === "fulfilled").length, 25);
    assert.equal(await prisma.studioLedgerEntry.count({ where: { userId: user.id, productionId: p.id, type: "STUDIO_TECHNICAL_REFUND" } }), 1);
    assert.equal((await prisma.studioCreditAccount.findUniqueOrThrow({ where: { userId: user.id } })).balanceMinor, 1000);
  });

  await record("automatic technical refund is blocked when a deliverable exists", async () => {
    const user = await makeUser(1000); const p = await makeProduction(user.id); const quote = await billing.createStandaloneStudioQuote(user.id, p.id);
    const purchase = await billing.purchaseStandaloneStudioProduction({ userId: user.id, productionId: p.id, quoteId: quote.quoteId, idempotencyKey: randomUUID() }); assert.equal(purchase.ok, true);
    const version = await prisma.productionVersion.create({ data: { productionId: p.id, versionNumber: 1, manifest: {}, sourceHash: "b".repeat(64), outputObjectKey: `outputs/${p.id}/v1.mp4`, outputSha256: "a".repeat(64), lineageHash: randomUUID() } });
    await prisma.production.update({ where: { id: p.id }, data: { studioState: "PRODUCTION_FAILED", status: "FAILED", currentVersionId: version.id } });
    await assert.rejects(() => billing.refundPermanentTechnicalFailure({ userId: user.id, productionId: p.id }), /REFUND_DELIVERABLE_EXISTS/);
    assert.equal(await prisma.studioLedgerEntry.count({ where: { userId: user.id, productionId: p.id, type: "STUDIO_TECHNICAL_REFUND" } }), 0);
  });

  const failed = results.filter(x => !x.ok);
  console.log(JSON.stringify({ schema: "StudioTrustCommerceRealPostgresAdversarial V1", pass: failed.length === 0, passed: results.length - failed.length, total: results.length, databaseEvidence: "REAL_POSTGRESQL", results }, null, 2));
  if (failed.length) process.exitCode = 1;
} finally {
  // Only delete users minted by this run. Their cascades clean every fixture.
  for (const userId of createdUsers.reverse()) {
    await prisma.user.delete({ where: { id: userId } }).catch(() => undefined);
  }
  await prisma.$disconnect();
}
