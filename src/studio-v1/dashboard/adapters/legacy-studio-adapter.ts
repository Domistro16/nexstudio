import type { StudioAsset, StudioAssetKind, StudioAssetStatus } from "../domain/assets.js";
import type { StudioBalance, StudioBillingEntry } from "../domain/billing.js";

/**
 * Compatibility only. These adapters let the standalone dashboard consume the
 * strongest existing Studio persistence concepts without importing unrelated product UI,
 * marketplace, wallet, reputation or pricing semantics.
 */
export interface LegacySourceRecord {
  id: string;
  name?: string | null;
  kind: string;
  mimeType?: string | null;
  sizeBytes?: number | bigint | null;
  isReusable?: boolean;
  rights?: unknown;
  status: string;
  previewUrl?: string | null;
  productionId?: string | null;
  createdAt: string | Date;
  updatedAt: string | Date;
}

export interface LegacyCreditAccount { balanceMinor: number; updatedAt?: string | Date; }
export interface LegacyLedgerRecord {
  id: string;
  type: string;
  amountMinor: number;
  productionId?: string | null;
  status: string;
  createdAt: string | Date;
  completedAt?: string | Date | null;
  metadata?: { description?: string } | null;
}

function iso(value: string | Date | undefined | null): string {
  if (!value) return new Date(0).toISOString();
  return value instanceof Date ? value.toISOString() : value;
}

function mapKind(record: LegacySourceRecord): StudioAssetKind {
  const mime = record.mimeType ?? "";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  if (/pdf|document|text|word/i.test(mime) || record.kind === "TEXT") return "document";
  if (/csv|json|spreadsheet/i.test(mime)) return "data";
  return "other";
}

function mapStatus(value: string): StudioAssetStatus {
  if (value === "READY") return "ready";
  if (["FAILED", "BLOCKED"].includes(value)) return "failed";
  return "processing";
}

function rightsAttested(rights: unknown): boolean | null {
  if (!rights || typeof rights !== "object") return null;
  const value = rights as Record<string, unknown>;
  if (typeof value.attested === "boolean") return value.attested;
  if (typeof value.rightsAttested === "boolean") return value.rightsAttested;
  return null;
}

export function assetFromLegacySource(record: LegacySourceRecord): StudioAsset {
  return {
    id: record.id,
    name: record.name?.trim() || "Untitled asset",
    kind: mapKind(record),
    mimeType: record.mimeType ?? null,
    sizeBytes: typeof record.sizeBytes === "bigint" ? Number(record.sizeBytes) : record.sizeBytes ?? null,
    reusable: Boolean(record.isReusable),
    rightsAttested: rightsAttested(record.rights),
    status: mapStatus(record.status),
    previewUrl: record.previewUrl ?? null,
    sourceProductionId: record.productionId ?? null,
    createdAt: iso(record.createdAt),
    updatedAt: iso(record.updatedAt),
  };
}

export function balanceFromLegacyAccount(record: LegacyCreditAccount, currency = "USD"): StudioBalance {
  return { currency, availableMinor: record.balanceMinor, pendingMinor: 0, updatedAt: iso(record.updatedAt) };
}

export function billingEntryFromLegacyLedger(record: LegacyLedgerRecord, currency = "USD"): StudioBillingEntry {
  return {
    id: record.id,
    type: record.type,
    amountMinor: record.amountMinor,
    currency,
    productionId: record.productionId ?? null,
    status: record.status,
    createdAt: iso(record.createdAt),
    completedAt: record.completedAt ? iso(record.completedAt) : null,
    description: record.metadata?.description ?? null,
  };
}
