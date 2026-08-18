import { z } from "zod";
import { requireSession, requireTrustedOrigin } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { json, problem, zodProblem } from "@/lib/http";
import { appendStudioMemoryVersion, tombstoneStudioMemory } from "@/studio-v1/memory/service";

export const runtime = "nodejs";
const patchSchema = z.object({ content: z.record(z.string(), z.unknown()), category: z.string().trim().min(1).max(80).optional(), label: z.string().trim().max(240).nullable().optional(), effectiveState: z.enum(["ACTIVE","INACTIVE"]).default("ACTIVE"), effectiveFromEpisodeOrdinal: z.number().int().positive().nullable().optional(), reason: z.string().trim().max(500).nullable().optional() });

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const auth = await requireSession(request); if (auth.response) return auth.response; const origin = requireTrustedOrigin(request, auth.id); if (origin) return origin;
  const body = patchSchema.safeParse(await request.json().catch(() => null)); if (!body.success) return zodProblem(auth.id, body.error); const { id } = await context.params; const prisma = getPrisma()!;
  const item = await prisma.studioMemoryItem.findFirst({ where: { id, ownerUserId: auth.session!.userId } }); if (!item) return problem(auth.id,404,"MEMORY_NOT_FOUND","Memory not found","No remembered item was changed.");
  try { const result = await appendStudioMemoryVersion({ prisma, ownerUserId: auth.session!.userId, scope:item.scope, scopeRefId:item.scopeRefId, key:item.key, category:body.data.category??item.category, label:body.data.label===undefined?item.label:body.data.label, content:body.data.content, effectiveState:body.data.effectiveState, effectiveFromEpisodeOrdinal:body.data.effectiveFromEpisodeOrdinal, provenance:{source:"CUSTOMER",recordedAt:new Date().toISOString(),customerConfirmed:true,note:"Customer edited remembered information."}, createdByType:"customer",createdById:auth.session!.userId,reason:body.data.reason??"CUSTOMER_EDIT" }); return json({memoryItemId:item.id,versionId:result.version.id,versionNumber:result.version.versionNumber},auth.id); }
  catch(error){const code=error instanceof Error?error.message:"MEMORY_EDIT_FAILED";return problem(auth.id,409,code,"Memory could not be edited","Prior versions remain intact.");}
}

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }) {
  const auth=await requireSession(request);if(auth.response)return auth.response;const origin=requireTrustedOrigin(request,auth.id);if(origin)return origin;const{id}=await context.params;
  try{const result=await tombstoneStudioMemory({prisma:getPrisma()!,ownerUserId:auth.session!.userId,memoryItemId:id,createdById:auth.session!.userId});return json({memoryItemId:id,deletedForFutureUse:true,tombstoneVersion:result.version.versionNumber},auth.id);}
  catch(error){const code=error instanceof Error?error.message:"MEMORY_DELETE_FAILED";return problem(auth.id,404,code,"Memory could not be deleted","Historical production snapshots remain immutable.");}
}
