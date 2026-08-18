export interface StudioBalance {
  currency: "USD" | string;
  availableMinor: number;
  pendingMinor: number;
  updatedAt: string;
}

export type StudioLedgerEntryType =
  | "BALANCE_ADDED"
  | "PRODUCTION_PAYMENT"
  | "PRODUCTION_REFUND"
  | "ADJUSTMENT"
  | string;

export interface StudioBillingEntry {
  id: string;
  type: StudioLedgerEntryType;
  amountMinor: number;
  currency: string;
  productionId: string | null;
  status: string;
  createdAt: string;
  completedAt: string | null;
  description: string | null;
}

export interface StudioBillingHistory {
  entries: StudioBillingEntry[];
  nextCursor: string | null;
}

export function formatMinor(amountMinor: number, currency = "USD"): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amountMinor / 100);
}
