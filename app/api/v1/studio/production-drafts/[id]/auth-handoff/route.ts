import { z } from "zod";
import { json, problem } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { ProductionDraftService } from "@/lib/studio-production-draft-core";
import { studioDraftProblem } from "@/lib/studio-production-draft-http";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { resolveStudioDraftRequestActor } from "@/lib/studio-production-draft-request";

export const runtime = "nodejs";
type Context = { params: Promise<{ id: string }> };
const service = new ProductionDraftService(new PrismaProductionDraftRepository());

async function actorAndId(request: Request, context: Context) {
  const access = await resolveStudioDraftRequestActor(request, { mutation: true });
  if (access.response) return { access, id: null, response: access.response };
  const originError = requireTrustedOrigin(request, access.id);
  if (originError) return { access, id: null, response: originError };
  if (!access.actor) return { access, id: null, response: problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.") };
  const { id } = await context.params;
  if (!z.string().uuid().safeParse(id).success) return { access, id: null, response: problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.") };
  return { access, id, response: null };
}

export async function POST(request: Request, context: Context) {
  const resolved = await actorAndId(request, context);
  if (resolved.response || !resolved.id || !resolved.access.actor) return resolved.response!;
  try {
    return json(await service.beginAuthHandoff(resolved.id, resolved.access.actor), resolved.access.id);
  } catch (error) {
    return studioDraftProblem(resolved.access.id, error);
  }
}

export async function DELETE(request: Request, context: Context) {
  const resolved = await actorAndId(request, context);
  if (resolved.response || !resolved.id || !resolved.access.actor) return resolved.response!;
  try {
    return json(await service.cancelAuthHandoff(resolved.id, resolved.access.actor), resolved.access.id);
  } catch (error) {
    return studioDraftProblem(resolved.access.id, error);
  }
}
