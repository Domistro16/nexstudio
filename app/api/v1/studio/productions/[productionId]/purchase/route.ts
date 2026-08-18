import { z } from "zod";
import { requireSession, requireTrustedOrigin, idempotencyKey } from "@/lib/route-auth";
import { json, problem, zodProblem } from "@/lib/http";
import { purchaseStandaloneStudioProduction } from "@/studio-v1/billing";
export const runtime = "nodejs";
const schema = z.object({ quoteId: z.string().uuid() }).strict();
export async function POST(request: Request, context: { params: Promise<{ productionId: string }> }) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const originError = requireTrustedOrigin(request, auth.id); if (originError) return originError;
  const key = idempotencyKey(request, auth.id); if (key.response) return key.response;
  const parsed = schema.safeParse(await request.json().catch(() => null)); if (!parsed.success) return zodProblem(auth.id, parsed.error);
  const { productionId } = await context.params;
  try {
    const result = await purchaseStandaloneStudioProduction({ userId: auth.session!.userId, productionId, quoteId: parsed.data.quoteId, idempotencyKey: key.value! });
    if (!result.ok) return json(result, auth.id, { status: 409 });
    return json(result, auth.id);
  } catch (error) {
    const code = error instanceof Error ? error.message : "PURCHASE_FAILED";
    const client = new Set(["QUOTE_NOT_FOUND","QUOTE_EXPIRED","QUOTE_NOT_OPEN","QUOTE_MISMATCH","WELCOME_DISCOUNT_NO_LONGER_ELIGIBLE","PURCHASE_STATE_INVALID","IDEMPOTENCY_CONFLICT"]);
    if (client.has(code)) return problem(auth.id, 409, code, "Production could not start", code === "QUOTE_EXPIRED" ? "Refresh the price and approve again." : "Refresh this production and try again.");
    console.error("Standalone Studio purchase failed", error);
    return problem(auth.id, 500, "PURCHASE_FAILED", "Production could not start", "No additional charge should be attempted until this request status is resolved.");
  }
}
