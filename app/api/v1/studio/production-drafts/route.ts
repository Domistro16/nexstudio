import { z } from "zod";
import { studioProductionFamilies } from "@/domain/studio-production-draft";
import { json, problem, zodProblem } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { setStudioAnonymousSessionCookie } from "@/lib/studio-anonymous-session";
import { ProductionDraftService } from "@/lib/studio-production-draft-core";
import { studioDraftProblem } from "@/lib/studio-production-draft-http";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { resolveStudioDraftRequestActor } from "@/lib/studio-production-draft-request";
import { PRODUCTION_REGISTRY } from "@/studio-v1/public/registry/production-family-registry";
import { getVideoType, isPublicVideoType } from "@/studio-v1/public/registry/selectors";
import type { FamilyId } from "@/studio-v1/public/registry/types";

export const runtime = "nodejs";

const sourceSchema = z.object({
  id: z.string().max(200).optional(),
  kind: z.enum(["URL", "UPLOAD", "LIBRARY", "TEXT"]),
  label: z.string().trim().max(160).nullable().optional(),
  reference: z.string().max(20_000).nullable().optional(),
  mimeType: z.string().trim().max(200).nullable().optional(),
});

const createSchema = z.object({
  id: z.string().uuid(),
  family: z.enum(studioProductionFamilies),
  videoType: z.string().trim().min(1).max(120),
  prompt: z.string().trim().min(1).max(20_000),
  sources: z.array(sourceSchema).max(100).default([]),
  duration: z.number().int().min(1).max(86_400).nullable().optional(),
  aspectRatio: z.string().trim().min(1).max(32).nullable().optional(),
  voicePreference: z.string().trim().max(200).nullable().optional(),
  brandContext: z.record(z.string(), z.unknown()).nullable().optional(),
});


const canonicalToPublicFamily: Record<(typeof studioProductionFamilies)[number], FamilyId> = {
  EXPLAINER: "explainer", WHITEBOARD: "whiteboard", STICKMAN: "stickman", EDITORIAL_MOTION: "editorial-motion",
};

const service = new ProductionDraftService(new PrismaProductionDraftRepository());

export async function POST(request: Request) {
  const access = await resolveStudioDraftRequestActor(request, { createAnonymous: true, mutation: true });
  if (access.response) return access.response;
  const originError = requireTrustedOrigin(request, access.id);
  if (originError) return originError;
  if (!access.actor) return problem(access.id, 401, "DRAFT_ACTOR_REQUIRED", "Draft session unavailable", "Reload Studio and retry the production prompt.");
  const parsed = createSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return zodProblem(access.id, parsed.error);
  const publicFamily = canonicalToPublicFamily[parsed.data.family];
  const publicType = getVideoType(PRODUCTION_REGISTRY, parsed.data.videoType);
  if (!publicType || publicType.family !== publicFamily || !isPublicVideoType(publicType)) {
    return problem(access.id, 409, "PUBLIC_PRODUCTION_TYPE_NOT_CERTIFIED", "Production type unavailable", "This production type is not certified for public production.");
  }

  try {
    const draft = await service.ensure(parsed.data, access.actor);
    const response = json(draft, access.id, { status: 201 });
    if (!access.userId && access.anonymousSession) setStudioAnonymousSessionCookie(response, access.anonymousSession, request);
    return response;
  } catch (error) {
    return studioDraftProblem(access.id, error);
  }
}
