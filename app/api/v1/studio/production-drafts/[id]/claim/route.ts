import { z } from "zod";
import { json, problem } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { ProductionDraftService, type DraftActor } from "@/lib/studio-production-draft-core";
import { studioDraftProblem } from "@/lib/studio-production-draft-http";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { resolveStudioDraftRequestActor } from "@/lib/studio-production-draft-request";
import { syncClaimedDraftToCanonicalProduction } from "@/studio-v1/architecture/core";

export const runtime = "nodejs";
type Context = { params: Promise<{ id: string }> };
const service = new ProductionDraftService(new PrismaProductionDraftRepository());

export async function POST(request: Request, context: Context) {
  const access = await resolveStudioDraftRequestActor(request, { mutation: true });
  if (access.response) return access.response;
  const originError = requireTrustedOrigin(request, access.id);
  if (originError) return originError;
  if (!access.userId) return problem(access.id, 401, "AUTHENTICATION_REQUIRED", "Sign in required", "Complete sign-in, then resume this same Studio draft.");
  const { id } = await context.params;
  if (!z.string().uuid().safeParse(id).success) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "The draft is unavailable.");

  const anonymousActor: Extract<DraftActor, { kind: "ANONYMOUS" }> | null = access.anonymousSession ? {
    kind: "ANONYMOUS",
    anonymousSessionId: access.anonymousSession.id,
    anonymousSessionSecretHash: access.anonymousSession.secretHash,
    expiresAt: access.anonymousSession.expiresAt,
  } : null;

  try {
    const draft = await service.claim(id, access.userId, anonymousActor);
    await syncClaimedDraftToCanonicalProduction(draft);
    return json(draft, access.id);
  } catch (error) {
    return studioDraftProblem(access.id, error);
  }
}
