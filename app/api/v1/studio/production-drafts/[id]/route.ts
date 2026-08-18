import { z } from "zod";
import { studioProductionFamilies } from "@/domain/studio-production-draft";
import { json, problem, zodProblem } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { ProductionDraftService } from "@/lib/studio-production-draft-core";
import { studioDraftProblem } from "@/lib/studio-production-draft-http";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { resolveStudioDraftRequestActor } from "@/lib/studio-production-draft-request";

export const runtime = "nodejs";
type Context = { params: Promise<{ id: string }> };
const service = new ProductionDraftService(new PrismaProductionDraftRepository());

const sourceSchema = z.object({
  id: z.string().max(200).optional(),
  kind: z.enum(["URL", "UPLOAD", "LIBRARY", "TEXT"]),
  label: z.string().trim().max(160).nullable().optional(),
  reference: z.string().max(20_000).nullable().optional(),
  mimeType: z.string().trim().max(200).nullable().optional(),
});

const patchSchema = z.object({
  family: z.enum(studioProductionFamilies).optional(),
  videoType: z.string().trim().min(1).max(120).optional(),
  prompt: z.string().trim().min(1).max(20_000).optional(),
  sources: z.array(sourceSchema).max(100).optional(),
  duration: z.number().int().min(1).max(86_400).nullable().optional(),
  aspectRatio: z.string().trim().min(1).max(32).nullable().optional(),
  voicePreference: z.string().trim().max(200).nullable().optional(),
  brandContext: z.record(z.string(), z.unknown()).nullable().optional(),
}).strict();

export async function GET(request: Request, context: Context) {
  const access = await resolveStudioDraftRequestActor(request);
  if (access.response) return access.response;
  if (!access.actor) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.");
  const { id } = await context.params;
  if (!z.string().uuid().safeParse(id).success) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.");
  try {
    return json(await service.get(id, access.actor), access.id);
  } catch (error) {
    return studioDraftProblem(access.id, error);
  }
}

export async function PATCH(request: Request, context: Context) {
  const access = await resolveStudioDraftRequestActor(request, { mutation: true });
  if (access.response) return access.response;
  const originError = requireTrustedOrigin(request, access.id);
  if (originError) return originError;
  if (!access.actor) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.");
  const { id } = await context.params;
  if (!z.string().uuid().safeParse(id).success) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.");
  const parsed = patchSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return zodProblem(access.id, parsed.error);
  try {
    return json(await service.update(id, access.actor, parsed.data), access.id);
  } catch (error) {
    return studioDraftProblem(access.id, error);
  }
}
