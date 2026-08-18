import { randomUUID } from "node:crypto";
import type { Prisma, StudioProductionFamily } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { latestSuccessfulStudioPlanPreview } from "@/studio-v1/plan-preview";
import { allocateProjectVersionTx, transitionCanonicalStudioStateTx } from "@/studio-v1/architecture/core";
import { capturePaidInputLineageTx } from "@/studio-v1/architecture/lineage";
import { assertStudioProductionRuntimeReady } from "@/studio-v1/runtime-readiness";

export const STANDALONE_STUDIO_BILLING = Object.freeze({
  currency: "USD" as const,
  baseRatePerFinishedMinuteMinor: 200,
  pricingVersion: "studio-v1-usd-duration-2026-08-13",
  quoteTtlSeconds: 900,
  firstProductionDiscountEnabled: process.env.STUDIO_FIRST_PRODUCTION_DISCOUNT_ENABLED?.trim() !== "false",
  firstProductionDiscountPercent: Number.parseInt(process.env.STUDIO_FIRST_PRODUCTION_DISCOUNT_PERCENT || "10", 10),
  firstProductionDiscountCode: "WELCOME_FIRST_PRODUCTION",
});


async function withSerializableRetry<T>(prisma: NonNullable<ReturnType<typeof getPrisma>>, work:(tx:Prisma.TransactionClient)=>Promise<T>):Promise<T>{
  for(let attempt=0;attempt<5;attempt+=1){
    try{return await prisma.$transaction(work, { isolationLevel: "Serializable" });}
    catch(error){const code=(error as {code?:string}).code;const retry=code==="P2034"||code==="P2002";if(!retry||attempt===4)throw error;await new Promise(resolve=>setTimeout(resolve,10*(2**attempt)+Math.floor(Math.random()*20)));}
  }
  throw new Error("SERIALIZABLE_RETRY_EXHAUSTED");
}

export function standaloneDurationPriceMinor(seconds: number) {
  if (!Number.isInteger(seconds) || seconds < 1 || seconds > 180) throw new Error("INVALID_APPROVED_DURATION");
  // Integer round-half-up: rate * seconds / 60.
  return Math.floor((seconds * STANDALONE_STUDIO_BILLING.baseRatePerFinishedMinuteMinor + 30) / 60);
}

export function formatUsdMinor(amount: number) {
  return `$${(amount / 100).toFixed(2)}`;
}

function discountMinor(base: number, percent: number) {
  return Math.floor((base * percent + 50) / 100);
}

async function standaloneCommercialSnapshot(userId: string, productionId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio billing.");
  const [draft, production] = await Promise.all([
    prisma.draft.findFirst({ where: { id: productionId, ownerUserId: userId, family: { not: null }, prompt: { not: null } } }),
    prisma.production.findFirst({ where: { id: productionId, ownerUserId: userId } }),
  ]);
  if (!draft?.family || !production) throw new Error("PRODUCTION_NOT_FOUND");
  const preview = await latestSuccessfulStudioPlanPreview(userId, productionId);
  if (!preview) throw new Error("PLAN_PREVIEW_REQUIRED");
  return {
    draft,
    production,
    family: draft.family,
    planPreviewId: preview.id,
    approvedDurationSeconds: preview.recommendedDuration,
    approvedPlanVersion: 1,
  };
}

export async function standaloneStudioBalance(userId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio billing.");
  const account = await prisma.studioCreditAccount.upsert({ where: { userId }, create: { userId, balanceMinor: 0 }, update: {} });
  return { currency: "USD" as const, availableMinor: account.balanceMinor, pendingMinor: 0, updatedAt: account.updatedAt.toISOString() };
}

export async function createStandaloneStudioQuote(userId: string, productionId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio billing.");
  const snapshot = await standaloneCommercialSnapshot(userId, productionId);
  if (!new Set(["PLAN_READY", "PAYMENT_REQUIRED", "INSUFFICIENT_BALANCE"]).has(snapshot.production.studioState)) throw new Error("QUOTE_STATE_INVALID");

  assertStudioProductionRuntimeReady({ family: snapshot.family, voiceRequired: Boolean(snapshot.draft.voicePreference && !/^(none|silent|no voice)$/i.test(String(snapshot.draft.voicePreference))), authoredArtRequired: snapshot.family === "EXPLAINER", musicRequired: false });

  return withSerializableRetry(prisma, async (tx) => {
    const now = new Date();
    const account = await tx.studioCreditAccount.upsert({ where: { userId }, create: { userId, balanceMinor: 0 }, update: {} });
    const open = await tx.studioPurchaseQuote.findMany({ where: { userId, productionId, mode: "STANDALONE_STUDIO", standaloneStatus: "OPEN" } });
    for (const old of open) {
      await tx.studioPurchaseQuote.update({ where: { id: old.id }, data: old.expiresAt <= now ? { standaloneStatus: "EXPIRED", standaloneLockKey: null } : { standaloneStatus: "SUPERSEDED", standaloneLockKey: null, supersededAt: now } });
    }
    const [priorDebit, priorWelcome] = await Promise.all([
      tx.studioLedgerEntry.findFirst({ where: { userId, type: "STUDIO_PRODUCTION_DEBIT", status: { in: ["COMPLETED", "POSTED"] } } }),
      tx.studioWelcomeRedemption.findUnique({ where: { userId_discountCode: { userId, discountCode: STANDALONE_STUDIO_BILLING.firstProductionDiscountCode } } }),
    ]);
    const welcomeEligible = STANDALONE_STUDIO_BILLING.firstProductionDiscountEnabled && !priorDebit && !priorWelcome;
    const percent = welcomeEligible ? Math.max(0, Math.min(100, STANDALONE_STUDIO_BILLING.firstProductionDiscountPercent)) : 0;
    const baseAmountMinor = standaloneDurationPriceMinor(snapshot.approvedDurationSeconds);
    const discountAmount = percent ? discountMinor(baseAmountMinor, percent) : 0;
    const finalAmountMinor = Math.max(0, baseAmountMinor - discountAmount);
    const expiresAt = new Date(now.getTime() + STANDALONE_STUDIO_BILLING.quoteTtlSeconds * 1000);
    const required = Math.max(0, finalAmountMinor - account.balanceMinor);
    const quote = await tx.studioPurchaseQuote.create({
      data: {
        userId,
        productionId,
        mode: "STANDALONE_STUDIO",
        variant: snapshot.family,
        amountMinor: finalAmountMinor,
        displayAmount: formatUsdMinor(finalAmountMinor),
        currency: "USD",
        pricingVersion: STANDALONE_STUDIO_BILLING.pricingVersion,
        accountBalanceMinor: account.balanceMinor,
        sufficientBalance: account.balanceMinor >= finalAmountMinor,
        expiresAt,
        draftId: productionId,
        quoteVersion: 1,
        family: snapshot.family,
        planPreviewId: snapshot.planPreviewId,
        approvedPlanVersion: snapshot.approvedPlanVersion,
        approvedDurationSeconds: snapshot.approvedDurationSeconds,
        baseRatePerFinishedMinuteMinor: STANDALONE_STUDIO_BILLING.baseRatePerFinishedMinuteMinor,
        baseAmountMinor,
        firstProductionDiscountEligible: welcomeEligible,
        discountCode: welcomeEligible ? STANDALONE_STUDIO_BILLING.firstProductionDiscountCode : null,
        discountPercent: percent,
        discountAmountMinor: discountAmount,
        finalAmountMinor,
        amountRequiredMinorAtQuote: required,
        standaloneStatus: "OPEN",
        standaloneLockKey: `standalone:${userId}:${productionId}`,
      },
    });
    await transitionCanonicalStudioStateTx(tx, {
      productionId, ownerUserId: userId, to: "PAYMENT_REQUIRED",
      actor: { type: "service", id: "studio-billing", reason: "QUOTE_CREATED", metadata: { quoteId: quote.id } },
    });
    await tx.production.update({ where: { id: productionId }, data: { status: "AWAITING_PAYMENT" } });
    return {
      quoteId: quote.id,
      pricingVersion: quote.pricingVersion,
      productionId,
      family: snapshot.family,
      planPreviewId: snapshot.planPreviewId,
      approvedDurationSeconds: snapshot.approvedDurationSeconds,
      baseRatePerFinishedMinuteMinor: STANDALONE_STUDIO_BILLING.baseRatePerFinishedMinuteMinor,
      baseAmountMinor,
      discount: welcomeEligible ? { code: STANDALONE_STUDIO_BILLING.firstProductionDiscountCode, percent, amountMinor: discountAmount } : null,
      finalAmountMinor,
      displayAmount: formatUsdMinor(finalAmountMinor),
      currency: "USD" as const,
      accountBalanceMinor: account.balanceMinor,
      balanceAfterPurchaseMinor: account.balanceMinor - finalAmountMinor,
      amountRequiredMinor: required,
      sufficientBalance: account.balanceMinor >= finalAmountMinor,
      expiresAt: expiresAt.toISOString(),
    };
  });
}

type PurchaseResult =
  | { ok: true; reused: boolean; productionId: string; quoteId: string; entitlementId: string; debitTransactionId: string; workflowRunId: string; amountPaidMinor: number; balanceAfterMinor: number; welcomeDiscountApplied: boolean }
  | { ok: false; code: "INSUFFICIENT_BALANCE"; productionId: string; quoteId: string; amountRequiredMinor: number; balanceMinor: number };

export async function purchaseStandaloneStudioProduction(input: { userId: string; productionId: string; quoteId: string; idempotencyKey: string }): Promise<PurchaseResult> {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio billing.");
  if (!input.idempotencyKey.trim()) throw new Error("IDEMPOTENCY_KEY_REQUIRED");
  const readinessSnapshot = await standaloneCommercialSnapshot(input.userId, input.productionId);
  assertStudioProductionRuntimeReady({ family: readinessSnapshot.family, voiceRequired: Boolean(readinessSnapshot.draft.voicePreference && !/^(none|silent|no voice)$/i.test(String(readinessSnapshot.draft.voicePreference))), authoredArtRequired: readinessSnapshot.family === "EXPLAINER", musicRequired: false });
  return withSerializableRetry(prisma, async (tx) => {
    const existingLedger = await tx.studioLedgerEntry.findUnique({ where: { idempotencyKey: input.idempotencyKey } });
    if (existingLedger?.productionId === input.productionId && existingLedger.quoteId === input.quoteId && existingLedger.type === "STUDIO_PRODUCTION_DEBIT") {
      const entitlement = await tx.studioProductionEntitlement.findFirst({ where: { productionId: input.productionId, debitTransactionId: existingLedger.id } });
      const workflow = entitlement?.workflowRunId ? await tx.studioWorkflowRun.findUnique({ where: { id: entitlement.workflowRunId } }) : null;
      if (!entitlement || !workflow) throw new Error("IDEMPOTENT_PURCHASE_INCOMPLETE");
      return { ok: true as const, reused: true, productionId: input.productionId, quoteId: input.quoteId, entitlementId: entitlement.id, debitTransactionId: existingLedger.id, workflowRunId: workflow.id, amountPaidMinor: Math.abs(existingLedger.amountMinor), balanceAfterMinor: existingLedger.balanceAfterMinor, welcomeDiscountApplied: entitlement.welcomeDiscountApplied };
    }
    if (existingLedger) throw new Error("IDEMPOTENCY_CONFLICT");

    const [draft, production] = await Promise.all([
      tx.draft.findFirst({ where: { id: input.productionId, ownerUserId: input.userId, family: { not: null } } }),
      tx.production.findFirst({ where: { id: input.productionId, ownerUserId: input.userId } }),
    ]);
    if (!draft?.family || !production) throw new Error("PRODUCTION_NOT_FOUND");
    const quote = await tx.studioPurchaseQuote.findFirst({ where: { id: input.quoteId, userId: input.userId, productionId: input.productionId, mode: "STANDALONE_STUDIO" } });
    if (!quote) throw new Error("QUOTE_NOT_FOUND");
    if (!quote.family || !quote.approvedDurationSeconds || !quote.approvedPlanVersion || quote.finalAmountMinor == null || !quote.planPreviewId) throw new Error("QUOTE_CONTRACT_INCOMPLETE");

    // Entitlement uniqueness is stronger than request-key idempotency. A second tab may
    // arrive with a different key after the winning transaction has consumed the quote.
    // Reuse the already-paid result before applying OPEN/expiry checks to that same plan.
    const priorEntitlement = await tx.studioProductionEntitlement.findUnique({ where: { productionId_approvedPlanVersion: { productionId: input.productionId, approvedPlanVersion: quote.approvedPlanVersion } } });
    if (priorEntitlement) {
      const priorLedger = priorEntitlement.debitTransactionId ? await tx.studioLedgerEntry.findUnique({ where: { id: priorEntitlement.debitTransactionId } }) : null;
      const workflow = priorEntitlement.workflowRunId ? await tx.studioWorkflowRun.findUnique({ where: { id: priorEntitlement.workflowRunId } }) : null;
      if (priorLedger && workflow) return { ok: true as const, reused: true, productionId: input.productionId, quoteId: priorEntitlement.quoteId ?? input.quoteId, entitlementId: priorEntitlement.id, debitTransactionId: priorLedger.id, workflowRunId: workflow.id, amountPaidMinor: Math.abs(priorLedger.amountMinor), balanceAfterMinor: priorLedger.balanceAfterMinor, welcomeDiscountApplied: priorEntitlement.welcomeDiscountApplied };
      throw new Error("PRODUCTION_ENTITLEMENT_CONFLICT");
    }

    if (!new Set(["PAYMENT_REQUIRED", "INSUFFICIENT_BALANCE", "PAYMENT_PENDING"]).has(production.studioState)) throw new Error("PURCHASE_STATE_INVALID");
    if (quote.expiresAt <= new Date()) {
      await tx.studioPurchaseQuote.update({ where: { id: quote.id }, data: { standaloneStatus: "EXPIRED", standaloneLockKey: null } });
      throw new Error("QUOTE_EXPIRED");
    }
    if (quote.standaloneStatus !== "OPEN") throw new Error("QUOTE_NOT_OPEN");
    if (quote.family !== draft.family || quote.pricingVersion !== STANDALONE_STUDIO_BILLING.pricingVersion || quote.baseRatePerFinishedMinuteMinor !== STANDALONE_STUDIO_BILLING.baseRatePerFinishedMinuteMinor) throw new Error("QUOTE_MISMATCH");
    const base = standaloneDurationPriceMinor(quote.approvedDurationSeconds);
    const percent = quote.discountPercent ?? 0;
    if (!Number.isInteger(percent) || percent < 0 || percent > 100) throw new Error("QUOTE_MISMATCH");
    const expectedDiscount = percent ? discountMinor(base, percent) : 0;
    const expectedFinal = Math.max(0, base - expectedDiscount);
    if (base !== quote.baseAmountMinor || quote.discountAmountMinor !== expectedDiscount || quote.finalAmountMinor !== expectedFinal || quote.amountMinor !== expectedFinal) throw new Error("QUOTE_MISMATCH");
    if ((percent > 0) !== Boolean(quote.discountCode) || (percent > 0 && quote.discountCode !== STANDALONE_STUDIO_BILLING.firstProductionDiscountCode)) throw new Error("QUOTE_MISMATCH");

    const account = await tx.studioCreditAccount.upsert({ where: { userId: input.userId }, create: { userId: input.userId, balanceMinor: 0 }, update: {} });
    if (account.balanceMinor < quote.finalAmountMinor) {
      const required = quote.finalAmountMinor - account.balanceMinor;
      await transitionCanonicalStudioStateTx(tx, {
        productionId: input.productionId, ownerUserId: input.userId, to: "INSUFFICIENT_BALANCE",
        actor: { type: "service", id: "studio-billing", reason: "INSUFFICIENT_BALANCE", metadata: { quoteId: input.quoteId } },
      });
      return { ok: false as const, code: "INSUFFICIENT_BALANCE" as const, productionId: input.productionId, quoteId: input.quoteId, amountRequiredMinor: required, balanceMinor: account.balanceMinor };
    }

    // Re-check welcome eligibility at purchase, not just quote creation.
    if ((quote.discountPercent ?? 0) > 0) {
      const [priorDebit, redemption] = await Promise.all([
        tx.studioLedgerEntry.findFirst({ where: { userId: input.userId, type: "STUDIO_PRODUCTION_DEBIT", status: { in: ["COMPLETED", "POSTED"] } } }),
        tx.studioWelcomeRedemption.findUnique({ where: { userId_discountCode: { userId: input.userId, discountCode: quote.discountCode! } } }),
      ]);
      if (priorDebit || redemption) throw new Error("WELCOME_DISCOUNT_NO_LONGER_ELIGIBLE");
    }

    const claimed = await tx.studioCreditAccount.updateMany({ where: { userId: input.userId, balanceMinor: { gte: quote.finalAmountMinor } }, data: { balanceMinor: { decrement: quote.finalAmountMinor } } });
    if (claimed.count !== 1) {
      await transitionCanonicalStudioStateTx(tx, {
        productionId: input.productionId, ownerUserId: input.userId, to: "INSUFFICIENT_BALANCE",
        actor: { type: "service", id: "studio-billing", reason: "BALANCE_RACE_LOST", metadata: { quoteId: input.quoteId } },
      });
      const latest = await tx.studioCreditAccount.findUniqueOrThrow({ where: { userId: input.userId } });
      return { ok: false as const, code: "INSUFFICIENT_BALANCE" as const, productionId: input.productionId, quoteId: input.quoteId, amountRequiredMinor: Math.max(0, quote.finalAmountMinor - latest.balanceMinor), balanceMinor: latest.balanceMinor };
    }
    const after = await tx.studioCreditAccount.findUniqueOrThrow({ where: { userId: input.userId } });
    const debitId = randomUUID();
    const ledger = await tx.studioLedgerEntry.create({
      data: {
        id: debitId,
        userId: input.userId,
        productionId: input.productionId,
        draftId: input.productionId,
        quoteId: quote.id,
        idempotencyKey: input.idempotencyKey,
        type: "STUDIO_PRODUCTION_DEBIT",
        amountMinor: -quote.finalAmountMinor,
        balanceBeforeMinor: after.balanceMinor + quote.finalAmountMinor,
        balanceAfterMinor: after.balanceMinor,
        mode: "standalone-studio",
        variant: draft.family,
        currency: "USD",
        status: "COMPLETED",
        metadata: { pricingVersion: quote.pricingVersion, planPreviewId: quote.planPreviewId, approvedDurationSeconds: quote.approvedDurationSeconds, discountCode: quote.discountCode } as Prisma.InputJsonValue,
        completedAt: new Date(),
      },
    });
    if ((quote.discountPercent ?? 0) > 0 && quote.discountCode) {
      await tx.studioWelcomeRedemption.create({ data: { userId: input.userId, discountCode: quote.discountCode, productionId: input.productionId } });
    }
    const entitlement = await tx.studioProductionEntitlement.create({
      data: {
        userId: input.userId,
        productionId: input.productionId,
        draftId: input.productionId,
        approvedPlanVersion: quote.approvedPlanVersion,
        planPreviewId: quote.planPreviewId,
        source: "PAID",
        quoteId: quote.id,
        debitTransactionId: ledger.id,
        amountPaidMinor: quote.finalAmountMinor,
        currency: "USD",
        welcomeDiscountApplied: (quote.discountPercent ?? 0) > 0,
      },
    });

    const projectVersion = await allocateProjectVersionTx(tx, input.productionId);
    const inputLineage = await capturePaidInputLineageTx(tx, {
      productionId: input.productionId, userId: input.userId, projectVersion, entitlementId: entitlement.id, quoteId: quote.id,
    });
    const workflow = await tx.studioWorkflowRun.create({
      data: {
        productionId: input.productionId,
        workflowId: `${input.productionId}:standalone:v${projectVersion}`,
        workflowType: "STANDALONE_STUDIO_CREATE_VIDEO",
        status: "RUNNING",
        stage: "PROJECT_CREATED",
        projectVersion,
        approvalMode: "fully_managed",
        policy: { fullNexMindRequired: true, planPreviewIsNotCreativeLock: true } as Prisma.InputJsonValue,
        context: {
          paidEntitlementId: entitlement.id, planPreviewId: quote.planPreviewId, family: draft.family, videoType: draft.videoType,
          inputLineageSnapshotId: inputLineage.id, inputLineageSnapshotHash: inputLineage.contentHash,
          nexmind: { status: "QUEUED", phase: "CAPABILITY_GRAPH_VALIDATED", customerPhase: "PREPARING" },
        } as Prisma.InputJsonValue,
        events: { create: { sequence: 1, eventType: "PAID_WORKFLOW_ENVELOPE_CREATED", toStage: "PROJECT_CREATED", payload: { entitlementId: entitlement.id, inputLineageSnapshotId: inputLineage.id, inputLineageSnapshotHash: inputLineage.contentHash } as Prisma.InputJsonValue } },
        activities: { create: { activityType: "RUN_STANDALONE_NEXMIND_P8", workerClass: "CREATIVE", idempotencyKey: `${input.productionId}:standalone:v${projectVersion}:nexmind-p8`, status: "QUEUED", attempts: 0, maxAttempts: 3, input: { productionId: input.productionId, projectVersion } as Prisma.InputJsonValue } },
      },
    });
    await tx.studioProductionEntitlement.update({ where: { id: entitlement.id }, data: { workflowRunId: workflow.id } });
    await tx.studioPurchaseQuote.update({ where: { id: quote.id }, data: { standaloneStatus: "CONSUMED", standaloneLockKey: null, consumedAt: new Date() } });
    await transitionCanonicalStudioStateTx(tx, {
      productionId: input.productionId, ownerUserId: input.userId, to: "PRODUCTION",
      actor: { type: "service", id: "studio-billing", reason: "PAID_ENTITLEMENT_COMMITTED", metadata: { quoteId: quote.id, entitlementId: entitlement.id, workflowRunId: workflow.id } },
    });
    await tx.production.update({ where: { id: input.productionId }, data: { status: "PAID", priceAtomic: BigInt(quote.finalAmountMinor), payerWallet: null } });
    return { ok: true as const, reused: false, productionId: input.productionId, quoteId: quote.id, entitlementId: entitlement.id, debitTransactionId: ledger.id, workflowRunId: workflow.id, amountPaidMinor: quote.finalAmountMinor, balanceAfterMinor: after.balanceMinor, welcomeDiscountApplied: entitlement.welcomeDiscountApplied };
  });
}

export async function standaloneBillingHistory(userId: string) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database is required for Studio billing.");
  const rows = await prisma.studioLedgerEntry.findMany({ where: { userId, currency: "USD" }, orderBy: { createdAt: "desc" }, take: 100 });
  return rows.map((row) => ({
    id: row.id,
    type: row.type,
    amountMinor: row.amountMinor,
    currency: "USD",
    productionId: row.productionId,
    status: row.status,
    createdAt: row.createdAt.toISOString(),
    completedAt: row.completedAt?.toISOString() ?? null,
    description: typeof (row.metadata as Record<string, unknown> | null)?.reason === "string" ? String((row.metadata as Record<string, unknown>).reason) : null,
  }));
}

export type FundingPurpose = "EXACT_PRODUCTION" | "BALANCE_TOPUP";
export async function createOrLoadStandaloneFundingIntent(input:{userId:string;productionId?:string;quoteId?:string;purpose:FundingPurpose;requestedTopupMinor?:number;idempotencyKey:string}){
  const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for Studio billing.");
  if(!input.idempotencyKey.trim())throw new Error("IDEMPOTENCY_KEY_REQUIRED");
  return withSerializableRetry(prisma, async tx=>{
    const existing=await tx.studioFundingIntent.findUnique({where:{userId_idempotencyKey:{userId:input.userId,idempotencyKey:input.idempotencyKey}}});
    if(existing){
      const same=existing.purpose===input.purpose&&existing.productionId===(input.productionId??null)&&existing.quoteId===(input.quoteId??null);
      if(!same)throw new Error("IDEMPOTENCY_CONFLICT");return existing;
    }
    let amountMinor=0;let productionId:string|null=null;let quoteId:string|null=null;
    if(input.purpose==="EXACT_PRODUCTION"){
      if(!input.productionId||!input.quoteId)throw new Error("FUNDING_PRODUCTION_QUOTE_REQUIRED");
      const [production,quote,account]=await Promise.all([
        tx.production.findFirst({where:{id:input.productionId,ownerUserId:input.userId}}),
        tx.studioPurchaseQuote.findFirst({where:{id:input.quoteId,userId:input.userId,productionId:input.productionId,mode:"STANDALONE_STUDIO"}}),
        tx.studioCreditAccount.upsert({where:{userId:input.userId},create:{userId:input.userId,balanceMinor:0},update:{}}),
      ]);
      if(!production||!quote)throw new Error("QUOTE_NOT_FOUND");
      if(quote.expiresAt<=new Date()||quote.standaloneStatus!=="OPEN")throw new Error("QUOTE_EXPIRED");
      if(!new Set(["PAYMENT_REQUIRED","INSUFFICIENT_BALANCE","PAYMENT_PENDING"]).has(production.studioState))throw new Error("FUNDING_STATE_INVALID");
      amountMinor=Math.max(0,quote.finalAmountMinor!-account.balanceMinor);if(amountMinor<=0)throw new Error("FUNDING_NOT_REQUIRED");productionId=input.productionId;quoteId=input.quoteId;
      if(production.studioState!=="PAYMENT_PENDING")await transitionCanonicalStudioStateTx(tx,{productionId,ownerUserId:input.userId,to:"PAYMENT_PENDING",actor:{type:"service",id:"studio-billing",reason:"FUNDING_INTENT_CREATED",metadata:{quoteId}}});
      await tx.production.update({where:{id:productionId},data:{status:"PAYMENT_PENDING"}});
    }else{
      amountMinor=input.requestedTopupMinor??0;if(!Number.isInteger(amountMinor)||amountMinor<100||amountMinor>1000000)throw new Error("TOPUP_AMOUNT_INVALID");
    }
    return tx.studioFundingIntent.create({data:{userId:input.userId,productionId,quoteId,currency:"USD",amountMinor,purpose:input.purpose,status:"CREATED",idempotencyKey:input.idempotencyKey,provider:"stripe"}});
  });
}

export async function attachFundingProviderSession(input:{userId:string;fundingIntentId:string;providerReference:string;checkoutUrl:string}){
  const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for Studio billing.");
  const row=await prisma.studioFundingIntent.findFirst({where:{id:input.fundingIntentId,userId:input.userId}});if(!row)throw new Error("FUNDING_INTENT_NOT_FOUND");
  if(row.providerReference&&row.providerReference!==input.providerReference)throw new Error("FUNDING_PROVIDER_REFERENCE_CONFLICT");
  return prisma.studioFundingIntent.update({where:{id:row.id},data:{providerReference:input.providerReference,providerCheckoutUrl:input.checkoutUrl,status:"PAYMENT_PENDING"}});
}

export async function settleStandaloneFundingIntent(input:{fundingIntentId:string;providerReference:string;amountMinor:number;currency:string}){
  const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for Studio billing.");
  return withSerializableRetry(prisma, async tx=>{
    const intent=await tx.studioFundingIntent.findUnique({where:{id:input.fundingIntentId}});if(!intent)throw new Error("FUNDING_INTENT_NOT_FOUND");
    if(intent.providerReference&&intent.providerReference!==input.providerReference)throw new Error("FUNDING_PROVIDER_REFERENCE_MISMATCH");
    if(intent.amountMinor!==input.amountMinor||intent.currency!==input.currency.toUpperCase())throw new Error("FUNDING_SETTLEMENT_MISMATCH");
    const ledgerKey=`funding-settlement:${intent.id}`;const prior=await tx.studioLedgerEntry.findUnique({where:{idempotencyKey:ledgerKey}});
    if(prior){if(intent.status!=="SETTLED")await tx.studioFundingIntent.update({where:{id:intent.id},data:{status:"SETTLED",settledAt:intent.settledAt??new Date(),completedAt:intent.completedAt??new Date()}});return{reused:true,intent,ledger:prior};}
    if(new Set(["FAILED","CANCELLED"]).has(intent.status))throw new Error("FUNDING_INTENT_TERMINAL");
    const account=await tx.studioCreditAccount.upsert({where:{userId:intent.userId},create:{userId:intent.userId,balanceMinor:0},update:{}});
    const updated=await tx.studioCreditAccount.update({where:{userId:intent.userId},data:{balanceMinor:{increment:intent.amountMinor}}});
    const ledger=await tx.studioLedgerEntry.create({data:{userId:intent.userId,productionId:intent.productionId,draftId:intent.productionId,quoteId:intent.quoteId,idempotencyKey:ledgerKey,externalReference:input.providerReference,type:"FUNDING_CREDIT",amountMinor:intent.amountMinor,balanceBeforeMinor:account.balanceMinor,balanceAfterMinor:updated.balanceMinor,mode:"standalone-studio",currency:"USD",status:"COMPLETED",metadata:{fundingIntentId:intent.id,purpose:intent.purpose,provider:intent.provider} as Prisma.InputJsonValue,completedAt:new Date()}});
    const settled=await tx.studioFundingIntent.update({where:{id:intent.id},data:{providerReference:input.providerReference,status:"SETTLED",settledAt:new Date(),completedAt:new Date()}});
    await tx.studioNotification.upsert({where:{userId_dedupeKey:{userId:intent.userId,dedupeKey:`funding-settled:${intent.id}`}},create:{userId:intent.userId,type:"BILLING",title:"Balance updated",body:`$${(intent.amountMinor/100).toFixed(2)} was added to your Studio balance.`,href:intent.productionId?`/production/${intent.productionId}`:"/dashboard/billing",dedupeKey:`funding-settled:${intent.id}`},update:{}});
    await tx.auditEvent.create({data:{actorUserId:null,action:"FUNDING_SETTLED",entityType:"StudioFundingIntent",entityId:intent.id,requestId:`provider:${input.providerReference}`,after:{amountMinor:intent.amountMinor,currency:"USD",ledgerId:ledger.id} as Prisma.InputJsonValue}});
    if(intent.productionId){
      const production=await tx.production.findFirst({where:{id:intent.productionId,ownerUserId:intent.userId}});
      if(production?.studioState==="PAYMENT_PENDING"){
        const quote=intent.quoteId?await tx.studioPurchaseQuote.findFirst({where:{id:intent.quoteId,userId:intent.userId,productionId:intent.productionId}}):null;
        const sufficient=Boolean(quote&&quote.standaloneStatus==="OPEN"&&quote.expiresAt>new Date()&&updated.balanceMinor>=Number(quote.finalAmountMinor??quote.amountMinor));
        await transitionCanonicalStudioStateTx(tx,{productionId:intent.productionId,ownerUserId:intent.userId,to:sufficient?"PAYMENT_REQUIRED":"INSUFFICIENT_BALANCE",actor:{type:"service",id:"studio-billing",reason:"FUNDING_SETTLED",metadata:{fundingIntentId:intent.id,ledgerId:ledger.id}}});
        await tx.production.update({where:{id:intent.productionId},data:{status:"AWAITING_PAYMENT"}});
      }
    }
    return{reused:false,intent:settled,ledger};
  });
}

export async function failStandaloneFundingIntent(input:{fundingIntentId:string;reason:string;cancelled?:boolean}){
  const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for Studio billing.");
  return withSerializableRetry(prisma, async tx=>{
    const intent=await tx.studioFundingIntent.findUnique({where:{id:input.fundingIntentId}});if(!intent)throw new Error("FUNDING_INTENT_NOT_FOUND");if(intent.status==="SETTLED")return intent;
    const updated=await tx.studioFundingIntent.update({where:{id:intent.id},data:{status:input.cancelled?"CANCELLED":"FAILED",failureReason:input.reason.slice(0,500),completedAt:new Date()}});
    if(intent.productionId){const production=await tx.production.findFirst({where:{id:intent.productionId,ownerUserId:intent.userId}});if(production?.studioState==="PAYMENT_PENDING"){const account=await tx.studioCreditAccount.upsert({where:{userId:intent.userId},create:{userId:intent.userId,balanceMinor:0},update:{}});const quote=intent.quoteId?await tx.studioPurchaseQuote.findFirst({where:{id:intent.quoteId,userId:intent.userId}}):null;const sufficient=Boolean(quote&&quote.standaloneStatus==="OPEN"&&quote.expiresAt>new Date()&&account.balanceMinor>=Number(quote.finalAmountMinor??quote.amountMinor));await transitionCanonicalStudioStateTx(tx,{productionId:intent.productionId,ownerUserId:intent.userId,to:sufficient?"PAYMENT_REQUIRED":"INSUFFICIENT_BALANCE",actor:{type:"service",id:"studio-billing",reason:"FUNDING_FAILED",metadata:{fundingIntentId:intent.id}}});await tx.production.update({where:{id:intent.productionId},data:{status:"AWAITING_PAYMENT"}});}}
    return updated;
  });
}

export async function refundPermanentTechnicalFailure(input:{userId:string;productionId:string;reason?:string}){
  const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for Studio billing.");
  return withSerializableRetry(prisma, async tx=>{
    const production=await tx.production.findFirst({where:{id:input.productionId,ownerUserId:input.userId},include:{currentVersion:true}});if(!production)throw new Error("PRODUCTION_NOT_FOUND");
    if(production.studioState!=="PRODUCTION_FAILED")throw new Error("REFUND_STATE_INVALID");if(production.currentVersion?.outputObjectKey)throw new Error("REFUND_DELIVERABLE_EXISTS");
    const entitlement=await tx.studioProductionEntitlement.findFirst({where:{productionId:input.productionId,userId:input.userId,source:"PAID"},orderBy:{createdAt:"desc"}});if(!entitlement?.debitTransactionId)throw new Error("REFUND_PAID_ENTITLEMENT_REQUIRED");
    const debit=await tx.studioLedgerEntry.findFirst({where:{id:entitlement.debitTransactionId,userId:input.userId,type:"STUDIO_PRODUCTION_DEBIT",status:{in:["COMPLETED","POSTED"]}}});if(!debit)throw new Error("REFUND_DEBIT_NOT_FOUND");
    const prior=await tx.studioLedgerEntry.findFirst({where:{reversalOfId:debit.id}});if(prior)return{reused:true,refund:prior};
    const account=await tx.studioCreditAccount.upsert({where:{userId:input.userId},create:{userId:input.userId,balanceMinor:0},update:{}});const amount=Math.abs(debit.amountMinor);const after=await tx.studioCreditAccount.update({where:{userId:input.userId},data:{balanceMinor:{increment:amount}}});
    const refund=await tx.studioLedgerEntry.create({data:{userId:input.userId,productionId:input.productionId,draftId:input.productionId,quoteId:debit.quoteId,idempotencyKey:`technical-refund:${debit.id}`,type:"STUDIO_TECHNICAL_REFUND",amountMinor:amount,balanceBeforeMinor:account.balanceMinor,balanceAfterMinor:after.balanceMinor,mode:"standalone-studio",currency:"USD",status:"COMPLETED",reversalOfId:debit.id,metadata:{reason:input.reason??"PERMANENT_TECHNICAL_FAILURE",entitlementId:entitlement.id} as Prisma.InputJsonValue,completedAt:new Date()}});
    await tx.production.update({where:{id:input.productionId},data:{status:"REFUNDED"}});
    await tx.studioNotification.upsert({where:{userId_dedupeKey:{userId:input.userId,dedupeKey:`technical-refund:${debit.id}`}},create:{userId:input.userId,type:"BILLING",title:"Production refunded",body:`$${(amount/100).toFixed(2)} was returned to your Studio balance after a permanent technical failure.`,href:`/production/${input.productionId}`,dedupeKey:`technical-refund:${debit.id}`},update:{}});
    await tx.auditEvent.create({data:{actorUserId:null,action:"TECHNICAL_REFUND_POSTED",entityType:"Production",entityId:input.productionId,requestId:`technical-refund:${debit.id}`,after:{amountMinor:amount,currency:"USD",refundLedgerId:refund.id,debitLedgerId:debit.id} as Prisma.InputJsonValue}});
    return{reused:false,refund};
  });
}
