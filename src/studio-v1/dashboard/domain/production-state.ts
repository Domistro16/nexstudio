export const PRODUCTION_STATES = [
  "DRAFT",
  "AUTH_REQUIRED",
  "PLANNING",
  "PLAN_READY",
  "PAYMENT_REQUIRED",
  "PAYMENT_PENDING",
  "PRODUCTION",
  "FINAL_REVIEW",
  "COMPLETE",
  "INSUFFICIENT_BALANCE",
  "PRODUCTION_FAILED",
  "TECHNICAL_RETRY",
  "REVISION_REQUESTED",
] as const;

export type ProductionState = (typeof PRODUCTION_STATES)[number];

export type DashboardStatusTone = "attention" | "active" | "ready" | "recovering" | "neutral";

export interface HumanProductionStatus {
  label: string;
  tone: DashboardStatusTone;
  needsAction: boolean;
  active: boolean;
  priority: number;
}

const STATUS_MAP: Record<ProductionState, HumanProductionStatus> = {
  DRAFT: { label: "Draft", tone: "neutral", needsAction: false, active: true, priority: 55 },
  AUTH_REQUIRED: { label: "Sign in to continue", tone: "attention", needsAction: true, active: true, priority: 85 },
  PLANNING: { label: "Planning", tone: "active", needsAction: false, active: true, priority: 45 },
  PLAN_READY: { label: "Plan ready", tone: "attention", needsAction: true, active: true, priority: 95 },
  PAYMENT_REQUIRED: { label: "Needs your approval", tone: "attention", needsAction: true, active: true, priority: 90 },
  PAYMENT_PENDING: { label: "Starting production", tone: "active", needsAction: false, active: true, priority: 60 },
  PRODUCTION: { label: "In production", tone: "active", needsAction: false, active: true, priority: 65 },
  FINAL_REVIEW: { label: "Needs your approval", tone: "attention", needsAction: true, active: true, priority: 100 },
  COMPLETE: { label: "Ready", tone: "ready", needsAction: false, active: false, priority: 10 },
  INSUFFICIENT_BALANCE: { label: "Balance needed", tone: "attention", needsAction: true, active: true, priority: 92 },
  PRODUCTION_FAILED: { label: "Recovering production", tone: "recovering", needsAction: false, active: true, priority: 75 },
  TECHNICAL_RETRY: { label: "Recovering production", tone: "recovering", needsAction: false, active: true, priority: 78 },
  REVISION_REQUESTED: { label: "Revision requested", tone: "attention", needsAction: true, active: true, priority: 97 },
};

export function humanStatusFor(state: ProductionState): HumanProductionStatus {
  return STATUS_MAP[state];
}
