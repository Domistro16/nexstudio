import { getSession } from "./auth";
import { problem, requestId } from "./http";
import { consumeRateLimit, requestIpHash } from "./rate-limit";
import {
  getOrCreateStudioAnonymousSession,
  readStudioAnonymousSession,
  type StudioAnonymousSession,
} from "./studio-anonymous-session";
import type { DraftActor } from "./studio-production-draft-core";

export type StudioDraftRequestActor = {
  id: string;
  actor: DraftActor | null;
  anonymousSession: StudioAnonymousSession | null;
  userId: string | null;
  response: Response | null;
};

export async function resolveStudioDraftRequestActor(
  request: Request,
  options: { createAnonymous?: boolean; mutation?: boolean } = {},
): Promise<StudioDraftRequestActor> {
  const id = requestId(request);
  const session = await getSession(request);

  if (session) {
    if (options.mutation) {
      const [accountLimit, ipLimit] = await Promise.all([
        consumeRateLimit(session.userId, "studio_draft_mutation", 120, 60_000),
        consumeRateLimit(requestIpHash(request), "studio_draft_mutation_ip", 240, 60_000),
      ]);
      if (!accountLimit.allowed || !ipLimit.allowed) {
        const limited = accountLimit.allowed ? ipLimit : accountLimit;
        return {
          id,
          actor: null,
          anonymousSession: null,
          userId: null,
          response: problem(id, 429, "STUDIO_DRAFT_RATE_LIMITED", "Too many draft changes", `Wait ${limited.retryAfterSeconds} seconds before trying again.`),
        };
      }
    }
    return {
      id,
      actor: { kind: "USER", userId: session.userId },
      anonymousSession: readStudioAnonymousSession(request),
      userId: session.userId,
      response: null,
    };
  }

  if (options.mutation) {
    const limit = await consumeRateLimit(requestIpHash(request), "studio_guest_draft_mutation", 60, 60_000);
    if (!limit.allowed) {
      return {
        id,
        actor: null,
        anonymousSession: null,
        userId: null,
        response: problem(id, 429, "STUDIO_GUEST_DRAFT_RATE_LIMITED", "Too many draft changes", `Wait ${limit.retryAfterSeconds} seconds before trying again.`),
      };
    }
  }

  const anonymousSession = options.createAnonymous
    ? getOrCreateStudioAnonymousSession(request)
    : readStudioAnonymousSession(request);

  return {
    id,
    actor: anonymousSession ? {
      kind: "ANONYMOUS",
      anonymousSessionId: anonymousSession.id,
      anonymousSessionSecretHash: anonymousSession.secretHash,
      expiresAt: anonymousSession.expiresAt,
    } : null,
    anonymousSession,
    userId: null,
    response: null,
  };
}
