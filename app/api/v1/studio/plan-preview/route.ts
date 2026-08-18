import { z } from "zod";
import { requireSession, requireTrustedOrigin, idempotencyKey } from "@/lib/route-auth";
import { requestId, json, problem, zodProblem } from "@/lib/http";
import { consumeRateLimit, requestIpHash } from "@/lib/rate-limit";
import { ProductionDraftService } from "@/lib/studio-production-draft-core";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { createComplimentaryStudioPlanPreview, latestSuccessfulStudioPlanPreview, STUDIO_PLAN_PREVIEW_POLICY } from "@/studio-v1/plan-preview";
import { syncClaimedDraftToCanonicalProduction, transitionCanonicalStudioState } from "@/studio-v1/architecture/core";
import { getPrisma } from "@/lib/db";

export const runtime = "nodejs";
const requestSchema = z.object({ productionId: z.string().uuid() }).strict();

export async function POST(request: Request) {
  const id = requestId(request);
  const originError = requireTrustedOrigin(request, id);
  if (originError) return originError;
  const auth = await requireSession(request);
  if (auth.response) return auth.response;
  const key = idempotencyKey(request, id);
  if (key.response) return key.response;
  const parsed = requestSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return zodProblem(id, parsed.error);

  const session = auth.session!;
  const verified = Boolean(session.user.email);
  if (!verified) return problem(id, 403, "VERIFIED_ACCOUNT_REQUIRED", "Verify your account to continue", "One verified account receives one complimentary planning pass.");

  const [accountLimit, ipLimit] = await Promise.all([
    consumeRateLimit(session.userId, "studio_plan_preview", STUDIO_PLAN_PREVIEW_POLICY.accountRateLimit.limit, STUDIO_PLAN_PREVIEW_POLICY.accountRateLimit.windowMs),
    consumeRateLimit(requestIpHash(request), "studio_plan_preview_ip", STUDIO_PLAN_PREVIEW_POLICY.ipRateLimit.limit, STUDIO_PLAN_PREVIEW_POLICY.ipRateLimit.windowMs),
  ]);
  if (!accountLimit.allowed || !ipLimit.allowed) {
    const retry = Math.max(accountLimit.retryAfterSeconds, ipLimit.retryAfterSeconds);
    return problem(id, 429, "PLAN_PREVIEW_RATE_LIMITED", "Planning is temporarily limited", `Try again in ${retry} seconds.`);
  }

  const actor = { kind: "USER" as const, userId: session.userId };
  const drafts = new ProductionDraftService(new PrismaProductionDraftRepository());
  let draft;
  try {
    draft = await drafts.get(parsed.data.productionId, actor);
    await syncClaimedDraftToCanonicalProduction(draft);
    if (draft.state === "DRAFT") {
      draft = await drafts.update(draft.id, actor, { state: "PLANNING" });
      await transitionCanonicalStudioState({
        productionId: draft.id,
        ownerUserId: session.userId,
        to: "PLANNING",
        actor: { type: "service", id: "complimentary-plan", reason: "COMPLIMENTARY_PLAN_STARTED", requestId: id },
      });
    }
    if (!new Set(["PLANNING", "PLAN_READY"]).has(draft.state)) {
      return problem(id, 409, "PLAN_PREVIEW_STATE_INVALID", "This production cannot be planned now", `Current state: ${draft.state}.`);
    }
    const preview = await createComplimentaryStudioPlanPreview({
      userId: session.userId,
      productionId: draft.id,
      draft,
      idempotencyKey: key.value!,
    });
    if (preview.status === "needs_input") {
      if (draft.state === "PLANNING") {
        draft = await drafts.update(draft.id, actor, { state: "DRAFT" });
        await transitionCanonicalStudioState({
          productionId: draft.id,
          ownerUserId: session.userId,
          to: "DRAFT",
          actor: { type: "service", id: "complimentary-plan", reason: "COMPLIMENTARY_PLAN_NEEDS_INPUT", requestId: id },
        });
      }
      return json(preview, id, { status: 200 });
    }

    if (draft.state !== "PLAN_READY") draft = await drafts.update(draft.id, actor, { state: "PLAN_READY" });
    await syncClaimedDraftToCanonicalProduction(draft);
    await transitionCanonicalStudioState({
      productionId: draft.id,
      ownerUserId: session.userId,
      to: "PLAN_READY",
      actor: { type: "service", id: "complimentary-plan", reason: "COMPLIMENTARY_PLAN_READY", requestId: id },
    });
    return json(preview, id);
  } catch (error) {
    if (draft?.state === "PLANNING") {
      await drafts.update(draft.id, actor, { state: "DRAFT" }).catch(() => undefined);
      await transitionCanonicalStudioState({
        productionId: draft.id, ownerUserId: session.userId, to: "DRAFT",
        actor: { type: "service", id: "complimentary-plan", reason: "COMPLIMENTARY_PLAN_FAILED", requestId: id },
      }).catch(() => undefined);
    }
    const message = error instanceof Error ? error.message : "Planning failed.";
    if (message.includes("COMPLIMENTARY_PLAN_ALREADY_USED")) return problem(id, 403, "COMPLIMENTARY_PLAN_ALREADY_USED", "Complimentary plan already used", "Your account's complimentary planning pass has already been used.");
    if (message.includes("PLAN_PREVIEW_IN_PROGRESS")) return problem(id, 409, "PLAN_PREVIEW_IN_PROGRESS", "Planning is already underway", "This production is already being planned.");
    if (message.includes("PLAN_PREVIEW_IDEMPOTENCY_CONFLICT")) return problem(id, 409, "IDEMPOTENCY_CONFLICT", "Request changed", "Use a new request key after changing the production brief.");
    console.error("Standalone Studio plan preview failed", error);
    return problem(id, 503, "PLAN_PREVIEW_UNAVAILABLE", "The plan could not be created", "Your complimentary pass was not consumed. Try the same production again.");
  }
}

export async function GET(request: Request) {
  const auth = await requireSession(request);
  if (auth.response) return auth.response;
  const productionId = new URL(request.url).searchParams.get("productionId");
  if (!productionId || !z.string().uuid().safeParse(productionId).success) return problem(auth.id, 422, "PRODUCTION_ID_REQUIRED", "Production required", "Provide a valid production ID.");
  const draft = await getPrisma()!.draft.findFirst({ where: { id: productionId, ownerUserId: auth.session!.userId } });
  if (!draft) return problem(auth.id, 404, "PRODUCTION_NOT_FOUND", "Production not found", "This production is unavailable.");
  const preview = await latestSuccessfulStudioPlanPreview(auth.session!.userId, productionId);
  return json(preview ? { status: "ready", planPreviewId: preview.id, thesis: preview.thesis, recommendedDuration: preview.recommendedDuration, beats: preview.beats, missingInput: preview.missingInput, complimentaryPassConsumed: true, replayed: true } : null, auth.id);
}
