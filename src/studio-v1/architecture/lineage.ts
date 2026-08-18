import type { Prisma } from "@/generated/prisma/client";
import { canonicalHash } from "./hash";

type Tx = Prisma.TransactionClient;

export async function saveLineageSnapshotTx(tx: Tx, input: {
  productionId: string;
  projectVersion: number;
  snapshotType: "PAID_INPUT" | "REVISION_INPUT" | "FINAL_OUTPUT";
  content: Record<string, unknown>;
}) {
  const contentHash = canonicalHash(input.content);
  const existing = await tx.studioLineageSnapshot.findUnique({
    where: {
      productionId_projectVersion_snapshotType: {
        productionId: input.productionId,
        projectVersion: input.projectVersion,
        snapshotType: input.snapshotType,
      },
    },
  });
  if (existing) {
    if (existing.contentHash !== contentHash) throw new Error(`LINEAGE_SNAPSHOT_CONFLICT:${input.snapshotType}`);
    return existing;
  }
  return tx.studioLineageSnapshot.create({
    data: {
      productionId: input.productionId,
      projectVersion: input.projectVersion,
      snapshotType: input.snapshotType,
      content: input.content as Prisma.InputJsonValue,
      contentHash,
    },
  });
}

export async function capturePaidInputLineageTx(tx: Tx, input: {
  productionId: string;
  userId: string;
  projectVersion: number;
  entitlementId: string;
  quoteId: string;
}) {
  const [production, draft, productionInputs, entitlement, quote] = await Promise.all([
    tx.production.findFirst({ where: { id: input.productionId, ownerUserId: input.userId } }),
    tx.draft.findFirst({ where: { id: input.productionId, ownerUserId: input.userId } }),
    tx.studioProductionInput.findMany({ where: { productionId: input.productionId, active: true }, orderBy: { ordinal: "asc" } }),
    tx.studioProductionEntitlement.findUnique({ where: { id: input.entitlementId } }),
    tx.studioPurchaseQuote.findUnique({ where: { id: input.quoteId } }),
  ]);
  if (!production || !draft || !entitlement || !quote) throw new Error("PAID_LINEAGE_INPUT_INCOMPLETE");

  return saveLineageSnapshotTx(tx, {
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    snapshotType: "PAID_INPUT",
    content: {
      schema: "StudioPaidInputLineageV1",
      production: {
        id: production.id,
        ownerUserId: production.ownerUserId,
        canonicalInputHash: production.canonicalInputHash,
        family: draft.family,
        videoType: draft.videoType,
        prompt: draft.prompt,
        duration: draft.duration,
        aspectRatio: draft.aspectRatio,
        voicePreference: draft.voicePreference,
        brandContext: draft.brandContext,
      },
      sources: productionInputs.map((item) => ({
        id: item.id,
        sourceId: item.sourceId,
        ordinal: item.ordinal,
        snapshotHash: item.snapshotHash,
        snapshot: item.snapshot,
      })),
      commercial: {
        quoteId: quote.id,
        pricingVersion: quote.pricingVersion,
        approvedPlanVersion: quote.approvedPlanVersion,
        approvedDurationSeconds: quote.approvedDurationSeconds,
        baseRatePerFinishedMinuteMinor: quote.baseRatePerFinishedMinuteMinor,
        baseAmountMinor: quote.baseAmountMinor,
        discountCode: quote.discountCode,
        discountPercent: quote.discountPercent,
        discountAmountMinor: quote.discountAmountMinor,
        finalAmountMinor: quote.finalAmountMinor,
        currency: quote.currency,
        entitlementId: entitlement.id,
        entitlementSource: entitlement.source,
        amountPaidMinor: entitlement.amountPaidMinor,
      },
    },
  });
}
