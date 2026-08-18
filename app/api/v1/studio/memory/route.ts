import { z } from "zod";
import { requireSession, requireTrustedOrigin } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { json, problem, zodProblem } from "@/lib/http";
import { appendStudioMemoryVersion, inspectStudioMemory } from "@/studio-v1/memory/service";
import { STUDIO_MEMORY_SCOPES } from "@/studio-v1/memory/contracts";

export const runtime = "nodejs";
const scopeSchema = z.enum(STUDIO_MEMORY_SCOPES);
const writeSchema = z.object({
  scope: scopeSchema, scopeRefId: z.string().uuid(), key: z.string().trim().min(1).max(160), category: z.string().trim().min(1).max(80), label: z.string().trim().max(240).nullable().optional(),
  content: z.record(z.string(), z.unknown()), provenance: z.record(z.string(), z.unknown()).default({}),
  effectiveState: z.enum(["ACTIVE", "INACTIVE"]).default("ACTIVE"), effectiveFrom: z.string().datetime().optional(), effectiveUntil: z.string().datetime().nullable().optional(),
  effectiveFromEpisodeOrdinal: z.number().int().positive().nullable().optional(), effectiveUntilEpisodeOrdinal: z.number().int().positive().nullable().optional(), reason: z.string().trim().max(500).nullable().optional(),
});

export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const url = new URL(request.url); const rawScope = url.searchParams.get("scope"); const scopeRefId = url.searchParams.get("scopeRefId") || undefined;
  const scope = rawScope ? scopeSchema.safeParse(rawScope) : null;
  if (scope && !scope.success) return problem(auth.id, 400, "INVALID_MEMORY_SCOPE", "Invalid memory scope", "Use Account, Brand, Cast, Series or Production memory.");
  const memories = await inspectStudioMemory(getPrisma()!, auth.session!.userId, scope?.success ? scope.data : undefined, scopeRefId);
  return json({ memories, customerControl: { inspect: true, editByAppendOnlyVersion: true, deleteByTombstone: true } }, auth.id);
}

export async function POST(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const origin = requireTrustedOrigin(request, auth.id); if (origin) return origin;
  const body = writeSchema.safeParse(await request.json().catch(() => null)); if (!body.success) return zodProblem(auth.id, body.error);
  try {
    const result = await appendStudioMemoryVersion({ prisma: getPrisma()!, ownerUserId: auth.session!.userId, ...body.data,
      effectiveFrom: body.data.effectiveFrom ? new Date(body.data.effectiveFrom) : undefined,
      effectiveUntil: body.data.effectiveUntil ? new Date(body.data.effectiveUntil) : body.data.effectiveUntil,
      provenance: { source: "CUSTOMER", recordedAt: new Date().toISOString(), customerConfirmed: true, ...body.data.provenance },
      createdByType: "customer", createdById: auth.session!.userId,
    });
    return json({ memoryItemId: result.item.id, versionId: result.version.id, versionNumber: result.version.versionNumber, effectiveState: result.version.effectiveState }, auth.id, { status: 201 });
  } catch (error) { const code = error instanceof Error ? error.message : "MEMORY_WRITE_FAILED"; return problem(auth.id, 409, code, "Memory could not be saved", "Existing production history remains unchanged."); }
}
