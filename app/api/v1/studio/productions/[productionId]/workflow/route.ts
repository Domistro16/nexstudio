import { z } from "zod";
import { json, problem } from "@/lib/http";
import { requireSession } from "@/lib/route-auth";
import { standaloneWorkflowProjection } from "@/studio-v1/nexmind-p8/workflow";
export const runtime = "nodejs";
type Context = { params: Promise<{ productionId: string }> };
export async function GET(request: Request, context: Context) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const { productionId } = await context.params;
  if (!z.string().uuid().safeParse(productionId).success) return problem(auth.id, 404, "PRODUCTION_NOT_FOUND", "Production not found", "This production is unavailable.");
  const projection = await standaloneWorkflowProjection(auth.session!.userId, productionId);
  if (!projection) return problem(auth.id, 404, "PRODUCTION_WORKFLOW_NOT_FOUND", "Production workflow not found", "This production has not entered the paid workflow yet.");
  return json(projection, auth.id);
}
