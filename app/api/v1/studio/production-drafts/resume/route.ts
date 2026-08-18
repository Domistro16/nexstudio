import { z } from "zod";
import { json, problem } from "@/lib/http";
import { ProductionDraftError, ProductionDraftService, type DraftActor } from "@/lib/studio-production-draft-core";
import { studioDraftProblem } from "@/lib/studio-production-draft-http";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { resolveStudioDraftRequestActor } from "@/lib/studio-production-draft-request";

export const runtime = "nodejs";
const service = new ProductionDraftService(new PrismaProductionDraftRepository());
const idSchema = z.string().uuid();

export async function GET(request: Request) {
  const access = await resolveStudioDraftRequestActor(request);
  if (access.response) return access.response;
  if (!access.actor) return problem(access.id, 404, "DRAFT_NOT_FOUND", "Draft not found", "No resumable Studio draft is available for this browser session.");
  const rawId = new URL(request.url).searchParams.get("draftId");
  const id = rawId && idSchema.safeParse(rawId).success ? rawId : null;
  if (rawId && !id) return problem(access.id, 422, "INVALID_DRAFT_ID", "Invalid draft identifier", "The draft identifier is malformed.");
  try {
    return json(await service.resume(access.actor, id), access.id);
  } catch (error) {
    if (error instanceof ProductionDraftError && error.code === "DRAFT_NOT_FOUND" && access.userId && access.anonymousSession) {
      const anonymousActor: Extract<DraftActor, { kind: "ANONYMOUS" }> = {
        kind: "ANONYMOUS",
        anonymousSessionId: access.anonymousSession.id,
        anonymousSessionSecretHash: access.anonymousSession.secretHash,
        expiresAt: access.anonymousSession.expiresAt,
      };
      try {
        return json(await service.resume(anonymousActor, id), access.id);
      } catch {
        // Preserve the normal non-disclosing not-found response below.
      }
    }
    return studioDraftProblem(access.id, error);
  }
}
