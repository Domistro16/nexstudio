import { requireSession, requireTrustedOrigin } from "@/lib/route-auth";
import { json, problem } from "@/lib/http";
import { createStandaloneStudioQuote } from "@/studio-v1/billing";
export const runtime = "nodejs";
export async function POST(request: Request, context: { params: Promise<{ productionId: string }> }) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const originError = requireTrustedOrigin(request, auth.id); if (originError) return originError;
  const { productionId } = await context.params;
  try { return json(await createStandaloneStudioQuote(auth.session!.userId, productionId), auth.id); }
  catch (error) {
    const code = error instanceof Error ? error.message : "QUOTE_FAILED";
    if (code === "PRODUCTION_NOT_FOUND") return problem(auth.id, 404, code, "Production not found", "This production is unavailable.");
    if (code === "PLAN_PREVIEW_REQUIRED") return problem(auth.id, 409, code, "Plan required", "Review the production plan before pricing.");
    if (code === "QUOTE_STATE_INVALID") return problem(auth.id, 409, code, "Production is not ready for pricing", "Return to the current production step.");
    console.error("Standalone Studio quote failed", error);
    return problem(auth.id, 500, "QUOTE_FAILED", "Price could not be prepared", "Try again without changing the approved production.");
  }
}
