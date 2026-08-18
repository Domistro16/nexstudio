import { problem } from "./http";
import { ProductionDraftError } from "./studio-production-draft-core";

export function studioDraftProblem(requestIdValue: string, error: unknown) {
  if (error instanceof ProductionDraftError) {
    switch (error.code) {
      case "DRAFT_NOT_FOUND":
        return problem(requestIdValue, 404, error.code, "Draft not found", "The draft is unavailable or you no longer have access to it.");
      case "PROMPT_REQUIRED":
        return problem(requestIdValue, 422, error.code, "Prompt required", error.message);
      case "STALE_DRAFT_STATE":
      case "DRAFT_CLAIM_CONFLICT":
        return problem(requestIdValue, 409, error.code, "Draft changed", error.message);
      default:
        return problem(requestIdValue, 409, error.code, "Draft request rejected", error.message);
    }
  }
  if (error instanceof Error && error.message.startsWith("INVALID_STUDIO_PRODUCTION_STATE_TRANSITION:")) {
    return problem(requestIdValue, 409, "INVALID_STUDIO_PRODUCTION_STATE", "Invalid production state", "The requested lifecycle transition is not allowed from the current state.");
  }
  console.error("Studio production draft request failed", error);
  return problem(
    requestIdValue,
    500,
    "STUDIO_DRAFT_REQUEST_FAILED",
    "Draft request failed",
    process.env.NODE_ENV === "production" ? "The production draft request could not be completed." : error instanceof Error ? error.message : "Unknown draft failure.",
  );
}
