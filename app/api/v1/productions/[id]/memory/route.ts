import { z } from "zod";
import { requireSession, requireTrustedOrigin } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { json, problem, zodProblem } from "@/lib/http";
import { appendStudioMemoryVersion } from "@/studio-v1/memory/service";
import { resolveProductionMemoryPacket } from "@/studio-v1/memory/resolver";
import { STUDIO_MEMORY_WRITE_MODES } from "@/studio-v1/memory/contracts";
import { ProductionDraftService } from "@/lib/studio-production-draft-core";
import { PrismaProductionDraftRepository } from "@/lib/studio-production-draft-repository";
import { syncClaimedDraftToCanonicalProduction } from "@/studio-v1/architecture/core";

export const runtime="nodejs";
const configureSchema=z.object({action:z.literal("configure"),brandId:z.string().uuid().nullable().optional(),seriesId:z.string().uuid().nullable().optional(),episodeOrdinal:z.number().int().positive().nullable().optional(),castMemberIds:z.array(z.string().uuid()).max(12).default([])});
const rememberSchema=z.object({action:z.literal("remember"),writeMode:z.enum(STUDIO_MEMORY_WRITE_MODES),key:z.string().trim().min(1).max(160),category:z.string().trim().min(1).max(80),label:z.string().trim().max(240).nullable().optional(),content:z.record(z.string(),z.unknown()),targetCastMemberId:z.string().uuid().nullable().optional(),futureEpisodeOrdinal:z.number().int().positive().nullable().optional(),reason:z.string().trim().max(500).nullable().optional()});
const schema=z.discriminatedUnion("action",[configureSchema,rememberSchema]);
async function ensureCanonicalProduction(productionId:string,userId:string){
  const prisma=getPrisma()!;
  const existing=await prisma.production.findFirst({where:{id:productionId,ownerUserId:userId}});
  if(existing)return existing;
  const service=new ProductionDraftService(new PrismaProductionDraftRepository());
  const draft=await service.get(productionId,{kind:"USER",userId});
  await syncClaimedDraftToCanonicalProduction(draft);
  return prisma.production.findFirst({where:{id:productionId,ownerUserId:userId}});
}
const CONFIGURABLE_STATES=new Set(["DRAFT","AUTH_REQUIRED","PLANNING","PLAN_READY","PAYMENT_REQUIRED","INSUFFICIENT_BALANCE"]);


export async function GET(request:Request,context:{params:Promise<{id:string}>}){const auth=await requireSession(request);if(auth.response)return auth.response;const{id}=await context.params;try{await ensureCanonicalProduction(id,auth.session!.userId);const packet=await resolveProductionMemoryPacket(getPrisma()!,{productionId:id,ownerUserId:auth.session!.userId,projectVersion:0});return json({effectiveMemory:packet,immutableSnapshotCreatedAtProductionStart:true},auth.id);}catch(error){const code=error instanceof Error?error.message:"MEMORY_READ_FAILED";return problem(auth.id,404,code,"Production memory unavailable","No remembered information was changed.");}}

export async function POST(request:Request,context:{params:Promise<{id:string}>}){
  const auth=await requireSession(request);if(auth.response)return auth.response;const origin=requireTrustedOrigin(request,auth.id);if(origin)return origin;const body=schema.safeParse(await request.json().catch(()=>null));if(!body.success)return zodProblem(auth.id,body.error);const{id}=await context.params;const prisma=getPrisma()!;
  const production=await ensureCanonicalProduction(id,auth.session!.userId);if(!production)return problem(auth.id,404,"PRODUCTION_NOT_FOUND","Production not found","No memory was changed.");
  if(body.data.action==="configure"){
    if(!CONFIGURABLE_STATES.has(production.studioState))return problem(auth.id,409,"PRODUCTION_MEMORY_INPUT_LOCKED","Production context is locked","Brand, Series and Cast selection is frozen once paid execution begins. Future memory can still be updated without changing this production.");
    const brandId=body.data.brandId===undefined?production.brandId:body.data.brandId;const seriesId=body.data.seriesId===undefined?production.seriesId:body.data.seriesId;
    if(brandId&&!await prisma.studioBrand.findFirst({where:{id:brandId,ownerUserId:auth.session!.userId}}))return problem(auth.id,404,"BRAND_NOT_FOUND","Brand not found","Production memory selection was not changed.");
    if(seriesId&&!await prisma.studioSeries.findFirst({where:{id:seriesId,ownerUserId:auth.session!.userId}}))return problem(auth.id,404,"SERIES_NOT_FOUND","Series not found","Production memory selection was not changed.");
    const cast=body.data.castMemberIds.length?await prisma.studioCastMember.findMany({where:{id:{in:body.data.castMemberIds},ownerUserId:auth.session!.userId}}):[];if(cast.length!==new Set(body.data.castMemberIds).size)return problem(auth.id,404,"CAST_NOT_FOUND","Cast member not found","Production memory selection was not changed.");
    try{await prisma.$transaction(async(tx)=>{await tx.production.update({where:{id},data:{brandId,seriesId}});await tx.studioProductionCastMember.deleteMany({where:{productionId:id}});if(body.data.castMemberIds.length)await tx.studioProductionCastMember.createMany({data:body.data.castMemberIds.map((castMemberId,ordinal)=>({productionId:id,castMemberId,ordinal}))});if(seriesId&&body.data.episodeOrdinal){await tx.studioSeriesEpisode.upsert({where:{productionId:id},create:{seriesId,productionId:id,episodeOrdinal:body.data.episodeOrdinal},update:{seriesId,episodeOrdinal:body.data.episodeOrdinal}});}else if(!seriesId){await tx.studioSeriesEpisode.deleteMany({where:{productionId:id}});}}, {isolationLevel:"Serializable"});return json({productionId:id,brandId,seriesId,castMemberIds:body.data.castMemberIds,episodeOrdinal:body.data.episodeOrdinal??null},auth.id);}catch(error){const code=error instanceof Error?error.message:"MEMORY_CONFIGURATION_FAILED";return problem(auth.id,409,code,"Production memory selection could not be saved","Existing production history remains unchanged.");}
  }

  const write=body.data;let scope:"PRODUCTION"|"BRAND"|"SERIES"|"CAST";let scopeRefId:string;let effectiveFromEpisodeOrdinal:number|null=null;
  if(write.writeMode==="THIS_PRODUCTION_ONLY"){scope="PRODUCTION";scopeRefId=id;}
  else if(write.writeMode==="REMEMBER_FOR_BRAND"){if(!production.brandId)return problem(auth.id,409,"BRAND_REQUIRED","No Brand selected","Select a Brand before remembering this for Brand.");scope="BRAND";scopeRefId=production.brandId;}
  else if(write.writeMode==="REMEMBER_FOR_SERIES"){if(!production.seriesId)return problem(auth.id,409,"SERIES_REQUIRED","No Series selected","Select a Series before remembering this for Series.");scope="SERIES";scopeRefId=production.seriesId;}
  else if(write.writeMode==="UPDATE_CHARACTER_GOING_FORWARD"){if(!write.targetCastMemberId)return problem(auth.id,400,"CAST_REQUIRED","Cast member required","Choose the character to update.");scope="CAST";scopeRefId=write.targetCastMemberId;}
  else {if(!write.futureEpisodeOrdinal)return problem(auth.id,400,"FUTURE_EPISODE_REQUIRED","Future episode required","Choose the first episode that should use this update.");effectiveFromEpisodeOrdinal=write.futureEpisodeOrdinal;if(write.targetCastMemberId){scope="CAST";scopeRefId=write.targetCastMemberId;}else{if(!production.seriesId)return problem(auth.id,409,"SERIES_REQUIRED","No Series selected","Select a Series before applying a future episode update.");scope="SERIES";scopeRefId=production.seriesId;}}
  try{const result=await appendStudioMemoryVersion({prisma,ownerUserId:auth.session!.userId,scope,scopeRefId,key:write.key,category:write.category,label:write.label,content:write.content,effectiveFromEpisodeOrdinal,provenance:{source:"CUSTOMER",sourceProductionId:id,sourceProductionVersionId:production.currentVersionId,recordedAt:new Date().toISOString(),customerConfirmed:true,note:`Studio memory write mode: ${write.writeMode}`},sourceProductionId:id,sourceProductionVersionId:production.currentVersionId,createdByType:"customer",createdById:auth.session!.userId,reason:write.reason??write.writeMode});return json({writeMode:write.writeMode,memoryItemId:result.item.id,versionNumber:result.version.versionNumber,scope,scopeRefId,effectiveFromEpisodeOrdinal},auth.id,{status:201});}catch(error){const code=error instanceof Error?error.message:"MEMORY_WRITE_FAILED";return problem(auth.id,409,code,"Memory could not be saved","Completed productions and prior memory versions remain unchanged.");}
}
