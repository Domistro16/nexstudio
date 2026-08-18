import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { Prisma, StudioProductionFamily } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { readObject, writeObject } from "@/lib/object-storage";
import { completeStudioActivity } from "@/lib/studio-workflow";
import { appendStudioWorkflowEvent, appendStudioWorkflowEventTx, assertStudioActivityLease, assertStudioActivityLeaseTx, ensureStudioWorkflowActivityTx } from "@/studio-v1/architecture/workflow-durability";
import { allocateProductionVersionNumberTx, transitionCanonicalStudioStateTx } from "@/studio-v1/architecture/core";
import { canonicalHash } from "@/studio-v1/architecture/hash";
import { saveLineageSnapshotTx } from "@/studio-v1/architecture/lineage";
import { saveStudioArtifact } from "@/lib/studio-governance";
import { captureFilmMemorySnapshotTx } from "@/studio-v1/memory/production-input";
import { assembleP8MultimodalReviewPackage } from "@/studio-v1/nexmind-p8/multimodal-evidence";
import { nextRepairContext, queueAutonomousP8Finalization, queueAutonomousP8Repair, saveCreativeMemoryObservation } from "@/studio-v1/nexmind-p8/autonomy";
import { assertInternalReviewEvidenceEligible, familyEngineAuthority } from "./authority";
import { executeStudioFamilyEngine } from "./bridge";

function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function sha(value: unknown) { return createHash("sha256").update(JSON.stringify(value)).digest("hex"); }

const event = appendStudioWorkflowEvent;

async function routeFamilyEngineCreativeReplan(input:{
  run:{id:string;productionId:string;projectVersion:number};
  family:StudioProductionFamily;
  authorityId:string;
  context:Record<string,unknown>;
  result:{code?:string;detail?:string;repairRequest?:Record<string,unknown>};
  activity:{id:string;workerId:string};
  phase:"INTERNAL_EVIDENCE"|"LOCKED_FINAL";
}) {
  const prisma=getPrisma()!;
  const nx=record(input.context.nexmind);
  const currentRepair=record(nx.autonomousRepair);
  const provided=record(input.result.repairRequest);
  const round=Math.max(1,Number(currentRepair.repairRound||0)+1);
  const seed={
    round,
    escalation_scope:String(provided.escalation_scope||"UPSTREAM_VISUAL_STRATEGY"),
    invalidate_slots:Array.isArray(provided.invalidate_slots)?provided.invalidate_slots:["visual_concept","art_direction","storyboard","cinematography","editorial_rhythm","motion_performance","sound_direction"],
    issues:Array.isArray(provided.issues)?provided.issues:[input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED",input.result.detail||""].filter(Boolean),
    revision_plan:Array.isArray(provided.revision_plan)?provided.revision_plan:["Preserve the film thesis and factual intent. Re-author the realization into the strongest premium-executable strategy; never lower the quality floor or silently substitute generic presentation primitives."],
    quality_reasons:Array.isArray(provided.quality_reasons)?provided.quality_reasons:[input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED"],
    production_disposition:"CONTINUE_REPLANNING",
    quality_floor_may_weaken:false,
    silent_generic_fallback_allowed:false,
  };
  const repairContext=nextRepairContext(currentRepair,seed,String(nx.stateHash||"")||null,String(nx.finalBoardHash||"")||null);
  await prisma.$transaction(async(tx)=>{
    await assertStudioActivityLeaseTx(tx,input.activity.id,input.activity.workerId);
    const nexmind={...nx,status:"RUNNING",code:input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED",phase:"AUTONOMOUS_REPAIR",customerPhase:"INTERNAL_REVIEW",autonomousRepair:repairContext,
      ...(input.phase==="LOCKED_FINAL"?{creativeLockArtifactId:null,creativeLockArtifactHash:null,creativeLockMode:null,engineDispatch:null}:{}),updatedAt:new Date().toISOString()};
    await tx.studioWorkflowRun.update({where:{id:input.run.id},data:{status:"RUNNING",blockedReason:null,context:{...input.context,nexmind,engineEvidence:{status:"REPLAN_REQUIRED",family:input.family,authorityId:input.authorityId,code:input.result.code,detail:input.result.detail,repairRound:round,updatedAt:new Date().toISOString()},...(input.phase==="LOCKED_FINAL"?{finalOutput:{status:"REPLANNING",family:input.family,authorityId:input.authorityId,repairRound:round,updatedAt:new Date().toISOString()}}:{})} as Prisma.InputJsonValue}});
    await transitionCanonicalStudioStateTx(tx,{productionId:input.run.productionId,to:"PRODUCTION",actor:{type:"service",id:"studio-family-engine",reason:"FAMILY_ENGINE_CREATIVE_REPLAN",metadata:{workflowRunId:input.run.id,family:input.family,authorityId:input.authorityId,code:input.result.code,repairRound:round,phase:input.phase}}});
  },{isolationLevel:"Serializable"});
  await saveCreativeMemoryObservation({productionId:input.run.productionId,projectVersion:input.run.projectVersion,workflowRunId:input.run.id,family:input.family,resultCode:input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED",finalReview:null,qualityEvidence:{source:"FAMILY_ENGINE",authorityId:input.authorityId,detail:input.result.detail||""},repairRequest:repairContext});
  await event(input.run.id,"FAMILY_ENGINE_CREATIVE_REPLAN_QUEUED",{family:input.family,authorityId:input.authorityId,code:input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED",repairRound:round,phase:input.phase});
  await queueAutonomousP8Repair({workflowRunId:input.run.id,productionId:input.run.productionId,projectVersion:input.run.projectVersion,repairContext});
  await completeStudioActivity(input.activity.id,input.activity.workerId,{status:"REPLAN_REQUIRED",code:input.result.code||"FAMILY_ENGINE_CREATIVE_REPLAN_REQUIRED",repairRound:round});
  return repairContext;
}

async function materializeReferenceMedia(sources: unknown, outputDirectory: string) {
  const items = Array.isArray(sources) ? sources : [];
  const out: Array<{ assetId: string; path: string; mimeType: string; name?: string }> = [];
  for (let index = 0; index < items.length; index++) {
    const source = record(items[index]);
    const kind = String(source.kind || "");
    const reference = String(source.reference || "");
    const mimeType = String(source.mimeType || "");
    if (!(kind === "UPLOAD" || kind === "LIBRARY") || !reference || !(mimeType.startsWith("video/") || mimeType.startsWith("image/"))) continue;
    try {
      const bytes = await readObject(reference);
      const ext = mimeType.startsWith("video/") ? (mimeType.includes("quicktime") ? "mov" : "mp4") : (mimeType.includes("png") ? "png" : "jpg");
      const target = path.join(outputDirectory, `reference-${index + 1}.${ext}`);
      await writeFile(target, bytes);
      out.push({ assetId: String(source.id || `reference-${index + 1}`), path: target, mimeType, name: String(source.label || `Reference ${index + 1}`) });
    } catch {
      throw new Error(`STUDIO_REFERENCE_MEDIA_MATERIALIZATION_FAILED:${reference}`);
    }
  }
  return out;
}

export async function queueStandaloneFamilyReviewEvidence(input:{workflowRunId:string;productionId:string;projectVersion:number;creativeStateArtifactId:string;creativeStateArtifactHash:string;family:StudioProductionFamily}) {
  const prisma=getPrisma()!;
  const authority=assertInternalReviewEvidenceEligible(input.family);
  const key=`${input.productionId}:standalone:v${input.projectVersion}:family-review-evidence:${input.creativeStateArtifactHash}:${authority.authorityId}`;
  return prisma.$transaction(async(tx)=>{
    const ensured=await ensureStudioWorkflowActivityTx(tx,{
      workflowRunId:input.workflowRunId,
      activityType:"BUILD_STANDALONE_FAMILY_REVIEW_EVIDENCE",
      workerClass:"CREATIVE",
      idempotencyKey:key,
      status:"QUEUED",
      attempts:0,
      maxAttempts:2,
      input:{productionId:input.productionId,projectVersion:input.projectVersion,creativeStateArtifactId:input.creativeStateArtifactId,creativeStateArtifactHash:input.creativeStateArtifactHash,family:input.family,authorityId:authority.authorityId} as Prisma.InputJsonValue,
    });
    if(!ensured.created)return ensured.activity;
    const run=await tx.studioWorkflowRun.findUniqueOrThrow({where:{id:input.workflowRunId}});
    const context=record(run.context);
    await tx.studioWorkflowRun.update({where:{id:run.id},data:{status:"RUNNING",context:{...context,engineEvidence:{status:"QUEUED",family:input.family,authorityId:authority.authorityId,activityId:ensured.activity.id,updatedAt:new Date().toISOString()}} as Prisma.InputJsonValue}});
    await appendStudioWorkflowEventTx(tx,run.id,"FAMILY_INTERNAL_EVIDENCE_QUEUED",{family:input.family,authorityId:authority.authorityId,activityId:ensured.activity.id});
    return ensured.activity;
  },{isolationLevel:"Serializable"});
}

const artifactTypes={VIDEO:"INTERNAL_REVIEW_VIDEO",AUDIO_MIX:"INTERNAL_REVIEW_AUDIO_MIX",CONTACT_SHEET:"INTERNAL_REVIEW_CONTACT_SHEET"} as const;

export async function runStandaloneFamilyReviewEvidenceActivity(activity:{id:string;workflowRunId:string;workerId:string}) {
  const prisma=getPrisma()!;const run=await prisma.studioWorkflowRun.findUniqueOrThrow({where:{id:activity.workflowRunId}});const draft=await prisma.draft.findUniqueOrThrow({where:{id:run.productionId}});if(!draft.family)throw new Error("STUDIO_FAMILY_MISSING");const authority=assertInternalReviewEvidenceEligible(draft.family);const context=record(run.context);const nx=record(context.nexmind);const creativeStateId=String(nx.creativeStateArtifactId||"");const creativeStateHash=String(nx.creativeStateArtifactHash||"");if(!creativeStateId||!creativeStateHash)throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISSING");const creative=await prisma.studioArtifact.findFirst({where:{id:creativeStateId,productionId:run.productionId,artifactType:"NEXMIND_P8_CREATIVE_STATE",contentHash:creativeStateHash}});if(!creative)throw new Error("NEXMIND_CREATIVE_STATE_ARTIFACT_MISMATCH");const content=record(creative.content);const finalBoard=record(content.finalBoard);if(!Object.keys(finalBoard).length)throw new Error("NEXMIND_FINAL_BOARD_MISSING");
  const entitlement=await prisma.studioProductionEntitlement.findFirst({where:{productionId:run.productionId},orderBy:[{approvedPlanVersion:"desc"},{createdAt:"desc"}]});const quote=entitlement?.quoteId?await prisma.studioPurchaseQuote.findUnique({where:{id:entitlement.quoteId}}):null;const outputDirectory=await mkdir(path.join(os.tmpdir(),`studio-family-${activity.id}`),{recursive:true}).then(()=>path.join(os.tmpdir(),`studio-family-${activity.id}`));
  const memoryInputSnapshotId=String(context.memoryInputSnapshotId||"");const memoryInputSnapshotHash=String(context.memoryInputSnapshotHash||"");
  const memoryInput=memoryInputSnapshotId?await prisma.studioMemorySnapshot.findFirst({where:{id:memoryInputSnapshotId,productionId:run.productionId,projectVersion:run.projectVersion,snapshotType:"MEMORY_INPUT",contentHash:memoryInputSnapshotHash}}):null;
  if(!memoryInput)throw new Error("PRODUCTION_MEMORY_INPUT_LINEAGE_MISSING");
  const memoryContent=record(memoryInput.content);const brandAuthority=record(memoryContent.brandAuthority);
  const brandMaterial={schema:"StudioBrandExecutionV1" as const,memoryInputSnapshotId:memoryInput.id,memoryInputSnapshotHash:memoryInput.contentHash,brandAuthority,productionBrandContext:record(draft.brandContext)};
  const brandExecution={...brandMaterial,brandExecutionHash:canonicalHash(brandMaterial)};
  try {
    const referenceMedia = await materializeReferenceMedia(draft.sources, outputDirectory);
    const result=await executeStudioFamilyEngine({schema:"StudioFamilyEngineRequestV1",operation:"BUILD_INTERNAL_REVIEW_EVIDENCE",family:draft.family,authorityId:authority.authorityId,productionId:run.productionId,creativeStateArtifactId:creative.id,creativeStateArtifactHash:creative.contentHash,durationSeconds:Number(quote?.approvedDurationSeconds||draft.duration||60),aspectRatio:draft.aspectRatio,voicePreference:draft.voicePreference,outputDirectory,finalBoard,creativeCheckpoint:record(content.checkpoint),creativeDossier:record(content.dossier),referenceMedia,brandExecution});
    if(result.status==="REPLAN_REQUIRED") {await routeFamilyEngineCreativeReplan({run:{id:run.id,productionId:run.productionId,projectVersion:run.projectVersion},family:draft.family,authorityId:authority.authorityId,context,result,activity,phase:"INTERNAL_EVIDENCE"});return result;}
    if(result.status==="TECHNICAL_RETRY_REQUIRED") {
      await assertStudioActivityLease(activity.id,activity.workerId);
      await prisma.studioWorkflowRun.update({where:{id:run.id},data:{status:"RUNNING",blockedReason:null,context:{...context,engineEvidence:{status:"TECHNICAL_RETRY",family:draft.family,authorityId:authority.authorityId,code:result.code,detail:result.detail,updatedAt:new Date().toISOString()}} as Prisma.InputJsonValue}});
      await event(run.id,"FAMILY_INTERNAL_EVIDENCE_TECHNICAL_RECOVERY_REQUIRED",{family:draft.family,authorityId:authority.authorityId,code:result.code||"FAMILY_ENGINE_TECHNICAL_RETRY_REQUIRED"});
      throw new Error(`FAMILY_ENGINE_TECHNICAL_RETRY_REQUIRED:${result.code||"UNKNOWN"}:${result.detail||""}`);
    }
    if(result.status!=="EVIDENCE_READY"||!result.artifacts?.length)throw new Error("FAMILY_ENGINE_EVIDENCE_RESULT_INCOMPLETE");
    await assertStudioActivityLease(activity.id,activity.workerId);
    const saved=[] as Array<{id:string;contentHash:string;kind:"VIDEO"|"AUDIO_MIX"|"CONTACT_SHEET"}>;
    for(const media of result.artifacts){const bytes=await readFile(media.path);const actual=createHash("sha256").update(bytes).digest("hex");if(actual!==media.sha256)throw new Error(`FAMILY_ENGINE_MEDIA_HASH_MISMATCH:${media.kind}`);const ext=media.kind==="VIDEO"?"mp4":media.kind==="AUDIO_MIX"?"wav":"jpg";const objectKey=`productions/${run.productionId}/studio-v1/v${run.projectVersion}/internal-review/${media.kind.toLowerCase()}-${actual}.${ext}`;await writeObject(objectKey,bytes,{contentType:media.mimeType});const art=await saveStudioArtifact({productionId:run.productionId,projectVersion:run.projectVersion,artifactType:artifactTypes[media.kind],status:"candidate",content:{schema:"StudioInternalReviewMediaV1",family:draft.family,authorityId:authority.authorityId,kind:media.kind,objectKey,mimeType:media.mimeType,mediaSha256:actual,bytes:bytes.byteLength,executionPlanSchema:result.executionPlanSchema??null,executionPlanHash:result.executionPlanHash??null,executionPlanAuthority:result.executionPlanAuthority??null,enginePlanHash:result.enginePlanHash??null,technicalQa:result.technicalQa??null},inputs:[{artifactId:creative.id,sha256:creative.contentHash}],createdBy:{type:"service",role:"studio_family_engine_review_adapter",runId:run.id}});saved.push({id:art.id,contentHash:art.contentHash,kind:media.kind});}
    if(result.enginePlanPath){const planBytes=await readFile(result.enginePlanPath);const planSha=createHash("sha256").update(planBytes).digest("hex");const objectKey=`productions/${run.productionId}/studio-v1/v${run.projectVersion}/internal-review/engine-plan-${planSha}.json`;await writeObject(objectKey,planBytes,{contentType:"application/json"});await saveStudioArtifact({productionId:run.productionId,projectVersion:run.projectVersion,artifactType:"INTERNAL_REVIEW_ENGINE_PLAN",status:"candidate",content:{schema:"StudioInternalReviewEnginePlanV1",family:draft.family,authorityId:authority.authorityId,objectKey,sha256:planSha,executionPlanSchema:result.executionPlanSchema??null,executionPlanHash:result.executionPlanHash??null,enginePlanHash:result.enginePlanHash??null,creativeChoiceIntroduced:false},inputs:[{artifactId:creative.id,sha256:creative.contentHash}],createdBy:{type:"service",role:"studio_family_engine_review_adapter",runId:run.id}});}
    const pkg=await assembleP8MultimodalReviewPackage({productionId:run.productionId,operatorUserId:"",requestId:activity.id,body:{artifacts:saved.map(x=>({artifactId:x.id,kind:x.kind})),audioExpected:result.audioExpected!==false},creator:{type:"service",role:"family_engine_evidence_packager",runId:run.id}});
    await assertStudioActivityLease(activity.id,activity.workerId);
    const latest=await prisma.studioWorkflowRun.findUniqueOrThrow({where:{id:run.id}});const latestContext=record(latest.context);await prisma.studioWorkflowRun.update({where:{id:run.id},data:{status:"WAITING",blockedReason:null,context:{...latestContext,engineEvidence:{status:"READY",family:draft.family,authorityId:authority.authorityId,multimodalReviewPackageArtifactId:pkg.id,multimodalReviewPackageArtifactHash:pkg.contentHash,mediaArtifactIds:saved.map(x=>x.id),updatedAt:new Date().toISOString()}} as Prisma.InputJsonValue}});await event(run.id,"FAMILY_INTERNAL_EVIDENCE_READY",{family:draft.family,authorityId:authority.authorityId,multimodalReviewPackageArtifactId:pkg.id});await queueAutonomousP8Finalization(run.productionId);await completeStudioActivity(activity.id,activity.workerId,{status:"EVIDENCE_READY",family:draft.family,multimodalReviewPackageArtifactId:pkg.id,artifactIds:saved.map(x=>x.id)});return result;
  } finally {await rm(outputDirectory,{recursive:true,force:true}).catch(()=>{});}
}

export async function queueReviewedFinalOutputPromotion(input:{workflowRunId:string;productionId:string;projectVersion:number;creativeLockArtifactId:string;creativeLockArtifactHash:string;family:StudioProductionFamily}) {
  const prisma=getPrisma()!;
  const authority=familyEngineAuthority(input.family);
  const key=`${input.productionId}:standalone:v${input.projectVersion}:promote-reviewed-final:${input.creativeLockArtifactHash}`;
  return prisma.$transaction(async(tx)=>{
    const ensured=await ensureStudioWorkflowActivityTx(tx,{
      workflowRunId:input.workflowRunId,
      activityType:"PROMOTE_REVIEWED_FINAL_OUTPUT",
      workerClass:"CREATIVE",
      idempotencyKey:key,status:"QUEUED",attempts:0,maxAttempts:2,
      input:{productionId:input.productionId,projectVersion:input.projectVersion,creativeLockArtifactId:input.creativeLockArtifactId,creativeLockArtifactHash:input.creativeLockArtifactHash,family:input.family,authorityId:authority.authorityId} as Prisma.InputJsonValue,
    });
    if(!ensured.created)return ensured.activity;
    const run=await tx.studioWorkflowRun.findUniqueOrThrow({where:{id:input.workflowRunId}});const context=record(run.context);
    await tx.studioWorkflowRun.update({where:{id:run.id},data:{status:"RUNNING",context:{...context,finalOutput:{status:"QUEUED_PROMOTION",family:input.family,authorityId:authority.authorityId,activityId:ensured.activity.id,updatedAt:new Date().toISOString()}} as Prisma.InputJsonValue}});
    await appendStudioWorkflowEventTx(tx,run.id,"REVIEWED_FINAL_PROMOTION_QUEUED",{family:input.family,authorityId:authority.authorityId,activityId:ensured.activity.id});
    return ensured.activity;
  },{isolationLevel:"Serializable"});
}

export async function runReviewedFinalOutputPromotionActivity(activity:{id:string;workflowRunId:string;workerId:string}) {
  const prisma=getPrisma()!;
  const run=await prisma.studioWorkflowRun.findUniqueOrThrow({where:{id:activity.workflowRunId}});
  const draft=await prisma.draft.findUniqueOrThrow({where:{id:run.productionId}});if(!draft.family)throw new Error("STUDIO_FAMILY_MISSING");
  const authority=familyEngineAuthority(draft.family);const ctx=record(run.context);const nx=record(ctx.nexmind);
  const lockId=String(nx.creativeLockArtifactId||"");const lockHash=String(nx.creativeLockArtifactHash||"");
  const inputSnapshotId=String(ctx.inputLineageSnapshotId||"");const inputSnapshotHash=String(ctx.inputLineageSnapshotHash||"");
  const memoryInputSnapshotId=String(ctx.memoryInputSnapshotId||"");const memoryInputSnapshotHash=String(ctx.memoryInputSnapshotHash||"");const entitlementId=String(ctx.paidEntitlementId||"");
  if(!lockId||!lockHash)throw new Error("NEXMIND_CREATIVE_LOCK_ARTIFACT_MISSING");
  const lock=await prisma.studioArtifact.findFirst({where:{id:lockId,productionId:run.productionId,artifactType:"NEXMIND_P8_CREATIVE_LOCK",contentHash:lockHash}});if(!lock)throw new Error("NEXMIND_CREATIVE_LOCK_ARTIFACT_MISMATCH");
  const lockContent=record(lock.content);const reviewedVideoArtifactId=String(lockContent.reviewedVideoArtifactId||"");const reviewedVideoMediaSha256=String(lockContent.reviewedVideoMediaSha256||"");const executionPlanHash=String(lockContent.executionPlanHash||"");
  if(!reviewedVideoArtifactId||!/^[a-f0-9]{64}$/i.test(reviewedVideoMediaSha256))throw new Error("CREATIVE_LOCK_REVIEWED_VIDEO_IDENTITY_MISSING");
  const reviewed=await prisma.studioArtifact.findFirst({where:{id:reviewedVideoArtifactId,productionId:run.productionId,artifactType:"INTERNAL_REVIEW_VIDEO"}});if(!reviewed)throw new Error("REVIEWED_VIDEO_ARTIFACT_MISSING");
  const reviewedContent=record(reviewed.content);const objectKey=String(reviewedContent.objectKey||"");if(!objectKey)throw new Error("REVIEWED_VIDEO_OBJECT_KEY_MISSING");
  const bytes=await readObject(objectKey);const outputSha256=createHash("sha256").update(bytes).digest("hex");
  if(outputSha256!==reviewedVideoMediaSha256||String(reviewedContent.mediaSha256||"")!==reviewedVideoMediaSha256)throw new Error("REVIEWED_VIDEO_BYTE_IDENTITY_MISMATCH");
  const outputKey=`productions/${run.productionId}/studio-v1/final/project-v${run.projectVersion}/output-${outputSha256}.mp4`;await writeObject(outputKey,bytes,{contentType:"video/mp4"});
  const copied=await readObject(outputKey);const copiedSha=createHash("sha256").update(copied).digest("hex");if(copiedSha!==outputSha256)throw new Error("FINAL_PROMOTION_COPY_HASH_MISMATCH");

  const entitlement=await prisma.studioProductionEntitlement.findFirst({where:{id:entitlementId,productionId:run.productionId}});if(!entitlement)throw new Error("PAID_ENTITLEMENT_LINEAGE_MISMATCH");
  const inputLineage=await prisma.studioLineageSnapshot.findFirst({where:{id:inputSnapshotId,productionId:run.productionId,projectVersion:run.projectVersion,contentHash:inputSnapshotHash}});if(!inputLineage)throw new Error("PRODUCTION_INPUT_LINEAGE_MISMATCH");
  const memoryInputLineage=await prisma.studioMemorySnapshot.findFirst({where:{id:memoryInputSnapshotId,productionId:run.productionId,projectVersion:run.projectVersion,snapshotType:"MEMORY_INPUT",contentHash:memoryInputSnapshotHash}});if(!memoryInputLineage)throw new Error("PRODUCTION_MEMORY_INPUT_LINEAGE_MISMATCH");
  const finalBoard=record(lockContent.finalBoard);
  const lineageMaterial={schema:"StudioFinalOutputLineageV2",productionId:run.productionId,workflowRunId:run.id,projectVersion:run.projectVersion,inputSnapshot:{id:inputLineage.id,hash:inputLineage.contentHash,type:inputLineage.snapshotType},memoryInputSnapshot:{id:memoryInputLineage.id,hash:memoryInputLineage.contentHash,type:memoryInputLineage.snapshotType},entitlement:{id:entitlement.id,quoteId:entitlement.quoteId,approvedPlanVersion:entitlement.approvedPlanVersion},creativeLock:{artifactId:lock.id,hash:lock.contentHash},reviewedMedia:{artifactId:reviewed.id,artifactHash:reviewed.contentHash,mediaSha256:reviewedVideoMediaSha256,mediaSetSha256:String(lockContent.mediaSetSha256||"")},execution:{family:draft.family,authorityId:authority.authorityId,executionPlanHash:executionPlanHash||String(reviewedContent.executionPlanHash||"")||null,enginePlanHash:String(reviewedContent.enginePlanHash||"")||null},output:{sha256:outputSha256,mimeType:"video/mp4",objectKey:outputKey,byteForBytePromotion:true}};
  const lineageHash=canonicalHash(lineageMaterial);
  const version=await prisma.$transaction(async(tx)=>{
    await assertStudioActivityLeaseTx(tx,activity.id,activity.workerId);const existing=await tx.productionVersion.findUnique({where:{lineageHash}});if(existing)return existing;
    const versionNumber=await allocateProductionVersionNumberTx(tx,run.productionId);const filmMemorySnapshot=await captureFilmMemorySnapshotTx(tx,{productionId:run.productionId,projectVersion:run.projectVersion,finalBoard,family:draft.family!,authorityId:authority.authorityId,outputSha256});
    const finalSnapshot=await saveLineageSnapshotTx(tx,{productionId:run.productionId,projectVersion:run.projectVersion,snapshotType:"FINAL_OUTPUT",content:{...lineageMaterial,versionNumber,lineageHash}});
    const created=await tx.productionVersion.create({data:{productionId:run.productionId,versionNumber,outputObjectKey:outputKey,previewObjectKey:outputKey,thumbnailObjectKey:null,manifest:{schema:"StandaloneStudioFinalV3",family:draft.family,authorityId:authority.authorityId,creativeLockArtifactId:lock.id,creativeLockArtifactHash:lock.contentHash,reviewedVideoArtifactId:reviewed.id,reviewedVideoArtifactHash:reviewed.contentHash,reviewedVideoMediaSha256,mediaSetSha256:String(lockContent.mediaSetSha256||""),executionPlanHash:lineageMaterial.execution.executionPlanHash,enginePlanHash:lineageMaterial.execution.enginePlanHash,outputHash:outputSha256,outputMimeType:"video/mp4",byteForByteReviewedPromotion:true,lineage:{productionId:run.productionId,workflowRunId:run.id,projectVersion:run.projectVersion,inputSnapshotId:inputLineage.id,inputSnapshotHash:inputLineage.contentHash,memoryInputSnapshotId:memoryInputLineage.id,memoryInputSnapshotHash:memoryInputLineage.contentHash,filmMemorySnapshotId:filmMemorySnapshot.id,filmMemorySnapshotHash:filmMemorySnapshot.contentHash,finalSnapshotId:finalSnapshot.id,finalSnapshotHash:finalSnapshot.contentHash,lineageHash}} as Prisma.InputJsonValue,sourceHash:canonicalHash({input:inputLineage.contentHash,memory:memoryInputLineage.contentHash,lock:lock.contentHash,reviewedVideo:reviewedVideoMediaSha256,executionPlan:lineageMaterial.execution.executionPlanHash,output:outputSha256}),workflowRunId:run.id,entitlementId:entitlement.id,quoteId:entitlement.quoteId,inputSnapshotId:inputLineage.id,inputSnapshotHash:inputLineage.contentHash,memoryInputSnapshotId:memoryInputLineage.id,memoryInputSnapshotHash:memoryInputLineage.contentHash,creativeLockArtifactId:lock.id,creativeLockHash:lock.contentHash,outputSha256,lineageHash}});
    await tx.production.update({where:{id:run.productionId},data:{status:"VERSION_READY",currentVersionId:created.id,failureCode:null}});await transitionCanonicalStudioStateTx(tx,{productionId:run.productionId,to:"FINAL_REVIEW",actor:{type:"worker",id:activity.workerId,reason:"REVIEWED_FINAL_BYTES_PROMOTED",metadata:{workflowRunId:run.id,productionVersionId:created.id,lineageHash,outputSha256}}});
    await tx.studioWorkflowRun.update({where:{id:run.id},data:{status:"WAITING",blockedReason:null,context:{...ctx,finalOutput:{status:"READY_FOR_CUSTOMER_REVIEW",versionId:created.id,outputObjectKey:outputKey,outputSha256,reviewedVideoSha256:reviewedVideoMediaSha256,byteForBytePromotion:true,updatedAt:new Date().toISOString()}} as Prisma.InputJsonValue}});return created;
  },{isolationLevel:"Serializable"});
  await event(run.id,"REVIEWED_FINAL_OUTPUT_PROMOTED",{versionId:version.id,versionNumber:version.versionNumber,outputSha256,lineageHash,reviewedVideoMediaSha256});await completeStudioActivity(activity.id,activity.workerId,{status:"FINAL_OUTPUT_READY",versionId:version.id,versionNumber:version.versionNumber,outputSha256,lineageHash,reviewedVideoMediaSha256});return {status:"FINAL_OUTPUT_READY",outputSha256,lineageHash,reviewedVideoMediaSha256};
}
