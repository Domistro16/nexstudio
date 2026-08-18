import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { Prisma } from "@/generated/prisma/client";
import { getPrisma } from "@/lib/db";
import { readObject } from "@/lib/object-storage";
import { completeStudioActivity } from "@/lib/studio-workflow";
import { appendStudioWorkflowEvent, appendStudioWorkflowEventTx, assertStudioActivityLease, assertStudioActivityLeaseTx, ensureStudioWorkflowActivityTx } from "@/studio-v1/architecture/workflow-durability";
import { transitionCanonicalStudioStateTx } from "@/studio-v1/architecture/core";
import { saveStudioArtifact } from "@/lib/studio-governance";
import { familyEngineAuthority } from "@/studio-v1/production-engines/authority";
import { queueStandaloneFamilyReviewEvidence, queueReviewedFinalOutputPromotion } from "@/studio-v1/production-engines/workflow";
import { captureProductionMemoryInputSnapshot } from "@/studio-v1/memory/production-input";
import { evaluateSeriesAntiRepetition } from "@/studio-v1/memory/policies";
import { executeStudioNexMindP8 } from "./bridge";
import { analyzeStandaloneReferenceLanguage } from "./reference-language";
import { buildP8SourcePacket } from "@/studio-v1/source-intelligence/p8-packet";
import { STUDIO_NEXMIND_CREATIVE_STATE_CONTRACT, assertStudioNexMindCreativeState } from "./creative-state";
import { STUDIO_AUTONOMY_POLICY, loadStudioTasteCalibration, productionMemoryPacketToCreativeRefs, saveStudioTasteCalibrationSample, saveCreativeMemoryObservation, nextRepairContext, queueAutonomousP8Finalization, queueAutonomousP8Repair } from "./autonomy";
import type { NexMindP8Phase, NexMindP8Result, StudioNexMindP8FinalizeRequest, StudioNexMindP8Request } from "./contract";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? value : []; }
function sha(value: unknown) { return createHash("sha256").update(JSON.stringify(value)).digest("hex"); }


function mediaSetSha256(items:Array<{artifact_id:string;kind:string;media_sha256:string;object_key:string}>) {
  const ordered=[...items].sort((a,b)=>a.artifact_id.localeCompare(b.artifact_id));
  return createHash("sha256").update(JSON.stringify(ordered)).digest("hex");
}

async function runTool(bin:string,args:string[],cwd?:string) {
  return new Promise<{stdout:string;stderr:string}>((resolve,reject)=>{
    const child=spawn(bin,args,{cwd,windowsHide:true,stdio:["ignore","pipe","pipe"]});let stdout="",stderr="";
    child.stdout.setEncoding("utf8");child.stderr.setEncoding("utf8");child.stdout.on("data",d=>stdout+=d);child.stderr.on("data",d=>stderr=(stderr+d).slice(-12000));
    child.once("error",reject);child.once("exit",code=>code===0?resolve({stdout,stderr}):reject(new Error(`MEDIA_TOOL_FAILED:${bin}:${code}:${stderr}`)));
  });
}

async function buildExactPerceptualMedia(mm:Record<string,unknown>, audioExpected:boolean) {
  const artifacts=array(mm.artifacts).map(record);
  const verified:Array<{artifact_id:string;kind:string;media_sha256:string;object_key:string}> = [];
  for(const item of artifacts){
    const artifact_id=String(item.artifact_id||"");const kind=String(item.kind||"");const media_sha256=String(item.media_sha256||"");const object_key=String(item.object_key||"");
    if(!artifact_id||!kind||!media_sha256||!object_key)continue;
    const bytes=await readObject(object_key);const actual=createHash("sha256").update(bytes).digest("hex");if(actual!==media_sha256)throw new Error(`NEXMIND_FINALIZATION_MEDIA_BYTE_HASH_MISMATCH:${artifact_id}`);
    verified.push({artifact_id,kind,media_sha256,object_key});
  }
  const computed=mediaSetSha256(verified);if(computed!==String(mm.mediaSetSha256||""))throw new Error("NEXMIND_FINALIZATION_MEDIA_SET_HASH_MISMATCH");
  const video=verified.find(x=>x.kind==="VIDEO");if(!video)throw new Error("NEXMIND_FINALIZATION_REVIEW_VIDEO_MISSING");
  const videoBytes=await readObject(video.object_key);const tmp=await mkdir(path.join(os.tmpdir(),`p8-perceptual-${createHash("sha256").update(video.media_sha256).digest("hex").slice(0,12)}`),{recursive:true}).then(()=>path.join(os.tmpdir(),`p8-perceptual-${createHash("sha256").update(video.media_sha256).digest("hex").slice(0,12)}`));
  try{
    const input=path.join(tmp,"reviewed.mp4");await writeFile(input,videoBytes);const ffprobe=process.env.STUDIO_FFPROBE_BIN?.trim()||"ffprobe";const ffmpeg=process.env.STUDIO_FFMPEG_BIN?.trim()||"ffmpeg";
    const probe=await runTool(ffprobe,["-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",input]);const duration=Math.max(0.1,Number(probe.stdout.trim())||0.1);
    const timestamps=[0.05,0.25,0.5,0.75,0.95].map(f=>Math.max(0,Math.min(duration-0.02,duration*f)));const temporalFrames=[] as Array<{timestampSeconds:number;sha256:string;dataUrl:string}>;
    for(let i=0;i<timestamps.length;i++){const out=path.join(tmp,`frame-${i}.jpg`);await runTool(ffmpeg,["-y","-ss",timestamps[i].toFixed(3),"-i",input,"-frames:v","1","-vf","scale='min(960,iw)':-2", "-q:v","3",out]);const bytes=await readFile(out);const h=createHash("sha256").update(bytes).digest("hex");temporalFrames.push({timestampSeconds:Number(timestamps[i].toFixed(3)),sha256:h,dataUrl:`data:image/jpeg;base64,${bytes.toString("base64")}`});}
    let audio:null|{sha256:string;mimeType:string;sampleRate:number;channels:number;dataUrl:string}=null;
    try{const out=path.join(tmp,"reviewed-audio.mp3");await runTool(ffmpeg,["-y","-i",input,"-vn","-ar","48000","-ac","2","-b:a","96k",out]);const bytes=await readFile(out);if(bytes.byteLength>0){const h=createHash("sha256").update(bytes).digest("hex");audio={sha256:h,mimeType:"audio/mpeg",sampleRate:48000,channels:2,dataUrl:`data:audio/mpeg;base64,${bytes.toString("base64")}`};}}catch(error){if(audioExpected)throw error;}
    if(audioExpected&&!audio)throw new Error("NEXMIND_FINALIZATION_REVIEW_VIDEO_AUDIO_MISSING");
    return {mediaSetSha256:computed,videoArtifactId:video.artifact_id,videoMediaSha256:video.media_sha256,temporalFrames,audio};
  }finally{await rm(tmp,{recursive:true,force:true}).catch(()=>{});}
}

async function materializeSourceVisualEvidence(refs: ReturnType<typeof buildP8SourcePacket>["visualReferences"], briefText = "") {
  // Context budgets may bound one model request, but may never destroy or choose
  // evidence by source order. Rank by brief relevance, then source-balance; record
  // every omission explicitly so another batch can retrieve it later.
  const maxRawBytes=24*1024*1024;
  const terms=new Set(briefText.toLowerCase().split(/[^a-z0-9]+/).filter(x=>x.length>3));
  const relevance=(ref:(typeof refs)[number])=>{
    const hay=`${ref.sourceLabel} ${ref.locator} ${ref.role}`.toLowerCase();let score=0;for(const t of terms)if(hay.includes(t))score+=1;return score;
  };
  const ranked=[...refs].sort((a,b)=>relevance(b)-relevance(a)||a.sourceId.localeCompare(b.sourceId)||String(a.locator).localeCompare(String(b.locator)));
  const balanced:typeof refs=[];const perSource=new Map<string,(typeof refs)[number][]>();
  for(const ref of ranked){const bucket=perSource.get(ref.sourceId)??[];bucket.push(ref);perSource.set(ref.sourceId,bucket);}
  let depth=0;while(true){let added=false;for(const sourceId of [...perSource.keys()].sort()){const item=perSource.get(sourceId)?.[depth];if(item){balanced.push(item);added=true;}}if(!added)break;depth++;}
  const evidence:Array<{sourceId:string;sourceLabel:string;page:number|null;locator:string;role:string;sha256:string;mimeType:string;dataUrl:string}>=[];
  const omitted:Array<{sourceId:string;locator:string;sha256:string;reason:string}>=[];const warnings:string[]=[];let used=0;
  for(const ref of balanced){
    try{
      const bytes=await readObject(ref.objectKey);const actual=createHash("sha256").update(bytes).digest("hex");
      if(actual!==ref.sha256)throw new Error(`SOURCE_VISUAL_EVIDENCE_HASH_MISMATCH:${ref.sourceId}:${ref.locator}`);
      if(bytes.byteLength>maxRawBytes){omitted.push({sourceId:ref.sourceId,locator:ref.locator,sha256:actual,reason:"SINGLE_ITEM_EXCEEDS_CONTEXT_BYTE_BUDGET"});continue;}
      if(used+bytes.byteLength>maxRawBytes){omitted.push({sourceId:ref.sourceId,locator:ref.locator,sha256:actual,reason:"CURRENT_BATCH_CONTEXT_BYTE_BUDGET"});continue;}
      used+=bytes.byteLength;evidence.push({sourceId:ref.sourceId,sourceLabel:ref.sourceLabel,page:ref.page,locator:ref.locator,role:ref.role,sha256:actual,mimeType:ref.mimeType,dataUrl:`data:${ref.mimeType};base64,${bytes.toString("base64")}`});
    }catch(error){
      if(error instanceof Error&&error.message.startsWith("SOURCE_VISUAL_EVIDENCE_HASH_MISMATCH"))throw error;
      warnings.push(`${ref.sourceId}:${ref.locator}:SOURCE_VISUAL_EVIDENCE_OBJECT_UNAVAILABLE`);
    }
  }
  if(omitted.length)warnings.push(`SOURCE_VISUAL_EVIDENCE_BATCH_OMISSIONS_EXPLICIT:${omitted.length}`);
  return {evidence,warnings,omitted,rawBytes:used,totalIndexed:refs.length};
}

const appendEvent = appendStudioWorkflowEvent;

function customerPhase(phase: NexMindP8Phase) {
  switch (phase) {
    case "CAPABILITY_GRAPH_VALIDATED":
    case "SOURCE_INTELLIGENCE": return "PREPARING";
    case "STORY": return "SHAPING_STORY";
    case "VISUAL_CONCEPT":
    case "ART_DIRECTION": return "VISUAL_DIRECTION";
    case "STORYBOARD":
    case "CINEMATOGRAPHY":
    case "EDITORIAL_RHYTHM": return "DIRECTING_FILM";
    case "MOTION_PERFORMANCE": return "DIRECTING_PERFORMANCE";
    case "SOUND_DIRECTION": return "DESIGNING_SOUND";
    case "FINAL_PRODUCER":
    case "AUTONOMOUS_REPAIR":
    case "HUMAN_REVIEW_REQUIRED": return "INTERNAL_REVIEW";
    case "DEPARTMENTS_COMPLETE": return "RENDERING_REVIEW_FILM";
    case "CREATIVE_LOCKED": return "CREATIVE_LOCKED";
  }
}

async function persistProgress(workflowRunId: string, activityId: string, workerId: string, phase: NexMindP8Phase, payload: Record<string, unknown>) {
  const prisma = getPrisma()!;
  await assertStudioActivityLease(activityId, workerId);
  const run = await prisma.studioWorkflowRun.findUniqueOrThrow({ where: { id: workflowRunId } });
  const context = record(run.context);
  const current = record(context.nexmind);
  await prisma.studioWorkflowRun.update({
    where: { id: workflowRunId },
    data: { context: { ...context, nexmind: { ...current, status: "RUNNING", phase, customerPhase: customerPhase(phase), updatedAt: new Date().toISOString() } } as Prisma.InputJsonValue },
  });
  await appendEvent(workflowRunId, `NEXMIND_${phase}`, { phase, customerPhase: customerPhase(phase), evidence: phase === "CAPABILITY_GRAPH_VALIDATED" ? payload : undefined });
}

async function persistCreativeStateArtifact(input: {
  workflowRunId: string;
  productionId: string;
  projectVersion: number;
  result: NexMindP8Result;
  lineageInputs?: { artifactId: string; sha256: string }[];
  revisionOf?: null | { revisionArtifactId: string; priorCreativeLockArtifactId: string; priorCreativeLockArtifactHash: string };
}) {
  if (!input.result.checkpoint || !input.result.finalBoard || !input.result.stateHash) return null;
  const prisma = getPrisma()!;
  const content = {
    schema: "StudioNexMindP8CreativeStateV2",
    authoritySnapshot: "P8_FINAL_PRODUCER_2026_08_12",
    creativeStateContract: STUDIO_NEXMIND_CREATIVE_STATE_CONTRACT,
    productionId: input.productionId,
    workflowRunId: input.workflowRunId,
    projectVersion: input.projectVersion,
    status: input.result.status,
    code: input.result.code,
    stateHash: input.result.stateHash,
    capabilityGraphHash: input.result.capabilityGraphHash ?? null,
    decisionSlots: input.result.decisionSlots ?? [],
    finalBoardHash: sha(input.result.finalBoard),
    dossierHash: input.result.dossier ? sha(input.result.dossier) : null,
    checkpoint: input.result.checkpoint,
    finalBoard: input.result.finalBoard,
    dossier: input.result.dossier ?? null,
    creativeMemoryRefsHash: sha(array(record(record(input.result.checkpoint).state).creative_memory_refs)),
    filmMemoryHash: sha(record(record(record(input.result.checkpoint).state).film_memory)),
    memoryInputSnapshotId: input.memoryInputSnapshotId,
    memoryInputSnapshotHash: input.memoryInputSnapshotHash,
    revisionOf: input.revisionOf ?? null,
  };
  assertStudioNexMindCreativeState(content);
  const contentHash = sha(content);
  const existing = await prisma.studioArtifact.findFirst({
    where: { productionId: input.productionId, projectVersion: input.projectVersion, artifactType: "NEXMIND_P8_CREATIVE_STATE", contentHash },
    orderBy: { createdAt: "desc" },
  });
  if (existing) return existing;
  return saveStudioArtifact({
    productionId: input.productionId,
    projectVersion: input.projectVersion,
    artifactType: "NEXMIND_P8_CREATIVE_STATE",
    status: "candidate",
    content,
    inputs: input.lineageInputs ?? [],
    createdBy: { type: "service", role: "nexmind_p8_authority_bridge", runId: input.workflowRunId },
  });
}

async function persistUsage(workflowRunId: string, productionId: string, result: NexMindP8Result) {
  const prisma = getPrisma()!;
  for (const audit of result.providerAudits || []) {
    const key = `nexmind-p8:${workflowRunId}:${String(audit.task || "unknown")}:${String(audit.request_hash || sha(audit))}`;
    await prisma.studioUsageEvent.upsert({
      where: { idempotencyKey: key },
      update: {},
      create: {
        productionId,
        workflowRunId,
        provider: String(audit.provider || "unknown"),
        operation: `NEXMIND_P8_${String(audit.task || "UNKNOWN").toUpperCase()}`.slice(0, 120),
        idempotencyKey: key,
        modelCalls: 1,
        status: "COMPLETED",
        providerRequestId: typeof audit.request_id === "string" ? audit.request_id : null,
        metadata: {
          model: audit.model,
          resolvedModel: audit.resolved_model,
          inputTokens: audit.input_tokens ?? 0,
          cachedInputTokens: audit.cached_input_tokens ?? 0,
          outputTokens: audit.output_tokens ?? 0,
          reasoningTokens: audit.reasoning_tokens ?? 0,
        } as Prisma.InputJsonValue,
      },
    });
  }
}

export async function runStandaloneNexMindP8Activity(activity: { id: string; workflowRunId: string; workerId: string }) {
  const prisma = getPrisma()!;
  const run = await prisma.studioWorkflowRun.findUniqueOrThrow({ where: { id: activity.workflowRunId } });
  if (run.workflowType !== "STANDALONE_STUDIO_CREATE_VIDEO") throw new Error("Standalone NexMind handler received the wrong workflow type.");
  const draft = await prisma.draft.findUniqueOrThrow({ where: { id: run.productionId } });
  const entitlement = await prisma.studioProductionEntitlement.findFirstOrThrow({
    where: { productionId: run.productionId },
    orderBy: [{ approvedPlanVersion: "desc" }, { createdAt: "desc" }],
  });
  const quote = entitlement.quoteId ? await prisma.studioPurchaseQuote.findUnique({ where: { id: entitlement.quoteId } }) : null;
  const preview = entitlement.planPreviewId ? await prisma.studioPlanPreviewRequest.findUnique({ where: { id: entitlement.planPreviewId } }) : null;
  const previewJson = record(preview?.responseJson);
  const productionInputs = await prisma.studioProductionInput.findMany({
    where: { productionId: run.productionId, active: true },
    orderBy: { ordinal: "asc" },
    include: { source: true },
  });
  const sourceIntelligence = buildP8SourcePacket({ rawSources: draft.sources, productionInputs, prompt: draft.prompt || "" });
  const sourceVisualEvidence = await materializeSourceVisualEvidence(sourceIntelligence.visualReferences, draft.prompt || "");
  const sources = sourceIntelligence.summaries;
  const referenceLanguage = await analyzeStandaloneReferenceLanguage(draft.sources);
  const engineAuthority = familyEngineAuthority(draft.family!);
  const runContext = record(run.context);
  const nxContext = record(runContext.nexmind);
  const autonomousRepairContext = Object.keys(record(nxContext.autonomousRepair)).length ? record(nxContext.autonomousRepair) : null;
  const revisionMeta = record(runContext.revision);
  let revisionContext: StudioNexMindP8Request["revisionContext"] = null;
  if (typeof revisionMeta.revisionArtifactId === "string") {
    const revisionArtifact = await prisma.studioArtifact.findFirst({ where: { id: revisionMeta.revisionArtifactId, productionId: run.productionId, projectVersion: run.projectVersion, artifactType: "STANDALONE_REVISION_REQUEST", status: "approved" } });
    if (!revisionArtifact || revisionArtifact.contentHash !== revisionMeta.revisionArtifactHash) throw new Error("STANDALONE_REVISION_ARTIFACT_MISMATCH");
    const revision = artifactContent(revisionArtifact);
    const priorLockId = String(revision.priorCreativeLockArtifactId || "");
    const priorLockHash = String(revision.priorCreativeLockArtifactHash || "");
    const priorLock = await prisma.studioArtifact.findFirst({ where: { id: priorLockId, productionId: run.productionId, artifactType: "NEXMIND_P8_CREATIVE_LOCK", status: "approved" } });
    if (!priorLock || priorLock.contentHash !== priorLockHash) throw new Error("STANDALONE_REVISION_PRIOR_LOCK_MISMATCH");
    const prior = artifactContent(priorLock);
    revisionContext = {
      instruction: String(revision.instruction || ""),
      timestampSeconds: typeof revision.timestampSeconds === "number" ? revision.timestampSeconds : null,
      priorCreativeLockArtifactId: priorLock.id,
      priorCreativeLockArtifactHash: priorLock.contentHash,
      priorFinalBoard: prior.finalBoard ?? null,
      preservationLaw: "PRESERVE_UNAFFECTED_LOCKED_DECISIONS",
    };
  }
  const memoryInputSnapshot = await captureProductionMemoryInputSnapshot(prisma, { productionId: run.productionId, projectVersion: run.projectVersion });
  const memoryPacket = record(memoryInputSnapshot.content);
  const creativeMemory = productionMemoryPacketToCreativeRefs(memoryPacket, memoryInputSnapshot.contentHash);
  await prisma.studioWorkflowRun.update({
    where: { id: run.id },
    data: { context: { ...runContext, memoryInputSnapshotId: memoryInputSnapshot.id, memoryInputSnapshotHash: memoryInputSnapshot.contentHash } as Prisma.InputJsonValue },
  });

  const request: StudioNexMindP8Request = {
    schema: "StudioNexMindP8RequestV1",
    productionId: run.productionId,
    workflowRunId: run.id,
    projectVersion: run.projectVersion,
    family: draft.family!,
    videoType: draft.videoType || "",
    prompt: draft.prompt || "",
    planPreview: preview ? {
      id: preview.id,
      thesis: String(previewJson.thesis || ""),
      recommendedDuration: Number(previewJson.recommendedDuration || quote?.approvedDurationSeconds || draft.duration || 60),
      beats: array(previewJson.beats).map((beat) => record(beat)).map((beat) => ({ start: Number(beat.start || 0), end: Number(beat.end || 0), purposeTitle: String(beat.purposeTitle || ""), description: String(beat.description || "") })),
      authority: "NON_AUTHORITATIVE_COMMERCIAL_PREVIEW",
    } : null,
    sourceSummaries: referenceLanguage ? [...sources, { id: "reference-language-profile", kind: "DERIVED_REFERENCE_LANGUAGE", label: "Reference visual-language analysis", summary: JSON.stringify({ profile: referenceLanguage.profile, styleHint: referenceLanguage.styleHint, sourceName: referenceLanguage.sourceName }) }] : sources,
    evidence: sourceIntelligence.evidence.length
      ? sourceIntelligence.evidence
      : sources.filter((source) => source.summary).map((source, index) => ({ claim_id: `SOURCE-${index + 1}`, claim: source.summary!, source: source.label || source.kind, status: "USER_SUPPLIED" })),
    sourceIntelligence: {
      schema: "StudioP8SourceIntelligencePacketV1",
      extractedSourceCount: sourceIntelligence.extractedSourceCount,
      contextChars: sourceIntelligence.contextChars,
      warnings: [...sourceIntelligence.warnings, ...sourceVisualEvidence.warnings],
      visualReferences: sourceIntelligence.visualReferences,
      provenanceLaw: "SOURCE_SEGMENT_IDS_AND_HASHES_ARE_FACTUAL_PROVENANCE__SOURCE_ANALYST_MAY_SYNTHESIZE_BUT_MAY_NOT_INVENT_OR_RECONCILE_CONTRADICTIONS",
    },
    sourceVisualEvidence: sourceVisualEvidence.evidence,
    sourceVisualEvidenceOmissions: sourceVisualEvidence.omitted,
    durationSeconds: Number(quote?.approvedDurationSeconds || draft.duration || previewJson.recommendedDuration || 60),
    aspectRatio: draft.aspectRatio,
    voicePreference: draft.voicePreference,
    brandContext: {
      ...(draft.brandContext ? record(draft.brandContext) : {}),
      persistentMemory: memoryPacket,
      accountMemory: Array.isArray(memoryPacket.accountMemory) ? memoryPacket.accountMemory : [],
      brandAuthority: record(memoryPacket.brandAuthority),
      seriesMemory: record(memoryPacket.seriesMemory),
      castAuthority: Array.isArray(memoryPacket.castAuthority) ? memoryPacket.castAuthority : [],
      productionMemory: Array.isArray(memoryPacket.productionMemory) ? memoryPacket.productionMemory : [],
      memoryLaw: "IMMUTABLE_MEMORY_INPUT_SNAPSHOT_PER_PROJECT_VERSION",
    },
    referenceLanguageProfile: referenceLanguage?.profile ?? null,
    referenceStyleHint: referenceLanguage?.styleHint ?? null,
    creativeMemory,
    autonomousRepairContext,
    revisionContext,
    capabilityGraph: {
      familyExecutionAuthority: {
        authorityId: engineAuthority.authorityId,
        sourceLabel: engineAuthority.sourceLabel,
        sourceArchiveSha256: engineAuthority.sourceArchiveSha256,
        technicalStatus: engineAuthority.technicalStatus,
        executionBody: engineAuthority.executionBody,
        truthBoundary: engineAuthority.truthBoundary,
        eligibleForInternalReviewEvidence: engineAuthority.eligibleForInternalReviewEvidence,
        eligibleForPublicProduction: engineAuthority.eligibleForPublicProduction,
        dispatchAdapterStatus: engineAuthority.dispatchAdapterStatus,
      },
    },
    policy: { fullNexMindRequired: true, planPreviewIsNotCreativeLock: true },
  };

  await persistProgress(run.id, activity.id, activity.workerId, "CAPABILITY_GRAPH_VALIDATED", {});
  let result = await executeStudioNexMindP8(request, (event) => persistProgress(run.id, activity.id, activity.workerId, event.phase, event.payload));
  const selectedMemory = record(memoryPacket.selected);
  if (typeof selectedMemory.seriesId === "string" && result.finalBoard && !["PROVIDER_UNAVAILABLE", "BLOCKED"].includes(result.status)) {
    const board = record(result.finalBoard);
    const signature = record(board.planSignature);
    const seriesMemory = record(memoryPacket.seriesMemory);
    const history = Array.isArray(seriesMemory.previousEpisodeSignatures) ? seriesMemory.previousEpisodeSignatures.map(record) : [];
    const continuityReasons = record(board.seriesContinuityReasons);
    if (!Object.keys(signature).length) {
      result = { ...result, status: "REVISE", code: "SERIES_PLAN_SIGNATURE_REQUIRED", detail: "Series productions require a structured plan signature so anti-repetition can be evaluated." };
    } else {
      const antiRepetition = evaluateSeriesAntiRepetition({ candidate: signature, history, historyWindow: Number(seriesMemory.antiRepetitionWindow || 2), continuityReasons });
      if (!antiRepetition.passes) {
        result = { ...result, status: "REVISE", code: "SERIES_ANTI_REPETITION_REPAIR_REQUIRED", detail: `Blocked repeated Series dimensions: ${antiRepetition.blockedDimensions.join(",")}` };
      } else {
        await persistProgress(run.id, activity.id, activity.workerId, "DEPARTMENTS_COMPLETE", { seriesAntiRepetition: antiRepetition });
      }
    }
  }
  await persistUsage(run.id, run.productionId, result);
  const revisionLineage = revisionContext && typeof revisionMeta.revisionArtifactId === "string" ? {
    lineageInputs: [
      { artifactId: revisionMeta.revisionArtifactId, sha256: String(revisionMeta.revisionArtifactHash || "") },
      { artifactId: revisionContext.priorCreativeLockArtifactId, sha256: revisionContext.priorCreativeLockArtifactHash },
    ],
    revisionOf: { revisionArtifactId: revisionMeta.revisionArtifactId, priorCreativeLockArtifactId: revisionContext.priorCreativeLockArtifactId, priorCreativeLockArtifactHash: revisionContext.priorCreativeLockArtifactHash },
  } : { lineageInputs: [], revisionOf: null };
  const creativeStateArtifact = ["DEPARTMENTS_COMPLETE", "HUMAN_REVIEW_REQUIRED", "CREATIVE_LOCKED"].includes(result.status)
    ? await persistCreativeStateArtifact({ workflowRunId: run.id, productionId: run.productionId, projectVersion: run.projectVersion, result, memoryInputSnapshotId: memoryInputSnapshot.id, memoryInputSnapshotHash: memoryInputSnapshot.contentHash, ...revisionLineage })
    : null;

  const latest = await prisma.studioWorkflowRun.findUniqueOrThrow({ where: { id: run.id } });
  const context = record(latest.context);
  const publicNexMind = {
    status: result.status,
    code: result.code,
    phase: result.status === "CREATIVE_LOCKED" ? "CREATIVE_LOCKED" : result.status === "DEPARTMENTS_COMPLETE" ? "DEPARTMENTS_COMPLETE" : result.status === "HUMAN_REVIEW_REQUIRED" ? "HUMAN_REVIEW_REQUIRED" : record(context.nexmind).phase,
    customerPhase: result.status === "CREATIVE_LOCKED" ? "CREATIVE_LOCKED" : result.status === "DEPARTMENTS_COMPLETE" ? "RENDERING_REVIEW_FILM" : result.status === "HUMAN_REVIEW_REQUIRED" ? "INTERNAL_REVIEW" : record(context.nexmind).customerPhase,
    stateHash: result.stateHash ?? null,
    capabilityGraphHash: result.capabilityGraphHash ?? null,
    decisionSlots: result.decisionSlots ?? [],
    finalBoardHash: result.finalBoard ? sha(result.finalBoard) : null,
    dossier: result.dossier ?? null,
    creativeStateArtifactId: creativeStateArtifact?.id ?? null,
    creativeStateArtifactHash: creativeStateArtifact?.contentHash ?? null,
    updatedAt: new Date().toISOString(),
  };
  const technical = result.status === "PROVIDER_UNAVAILABLE";
  const blocked = technical;
  const creativeRecovery = result.status === "REVISE" || result.status === "BLOCKED";
  await prisma.$transaction(async (tx) => {
    await assertStudioActivityLeaseTx(tx, activity.id, activity.workerId);
    await tx.studioWorkflowRun.update({
      where: { id: run.id },
      data: {
        status: blocked ? "BLOCKED" : creativeRecovery ? "RUNNING" : "WAITING",
        blockedReason: blocked ? result.code : null,
        context: { ...context, nexmind: publicNexMind, nexmindAuthority: { snapshot: "P8_POST_RENDER_FINAL_AUTHORITY_V1", capabilityGraphHash: result.capabilityGraphHash ?? null, selectedFamily: draft.family } } as Prisma.InputJsonValue,
      },
    });
    await transitionCanonicalStudioStateTx(tx, {
      productionId: run.productionId,
      to: technical ? "TECHNICAL_RETRY" : "PRODUCTION",
      actor: { type: "service", id: "nexmind-p8", reason: technical ? "NEXMIND_PROVIDER_UNAVAILABLE" : creativeRecovery ? "NEXMIND_CREATIVE_RECOVERY" : "NEXMIND_ACTIVITY_RESULT", metadata: { workflowRunId: run.id, status: result.status, code: result.code } },
    });
  }, { isolationLevel: "Serializable" });
  await appendEvent(run.id, result.status === "CREATIVE_LOCKED" ? "NEXMIND_CREATIVE_LOCKED" : result.status === "HUMAN_REVIEW_REQUIRED" ? "NEXMIND_HUMAN_REVIEW_REQUIRED" : result.status === "PROVIDER_UNAVAILABLE" ? "NEXMIND_PROVIDER_BLOCKED" : `NEXMIND_${result.status}`, { status: result.status, code: result.code, stateHash: result.stateHash ?? null, finalBoardHash: result.finalBoard ? sha(result.finalBoard) : null });
  if (result.status === "DEPARTMENTS_COMPLETE" && creativeStateArtifact) {
    await queueStandaloneFamilyReviewEvidence({ workflowRunId: run.id, productionId: run.productionId, projectVersion: run.projectVersion, creativeStateArtifactId: creativeStateArtifact.id, creativeStateArtifactHash: creativeStateArtifact.contentHash, family: draft.family! });
  } else if (result.status === "REVISE") {
    const currentRound = Number(autonomousRepairContext?.repairRound || 0);
    const isSeriesRepetition = result.code === "SERIES_ANTI_REPETITION_REPAIR_REQUIRED" || result.code === "SERIES_PLAN_SIGNATURE_REQUIRED";
    const providedRepair = record(record(result).repairRequest);
    const repairSeed = Object.keys(providedRepair).length ? providedRepair : {
      round: currentRound + 1,
      escalation_scope: isSeriesRepetition ? "UPSTREAM_VISUAL_STRATEGY" : "RESPONSIBLE_DEPARTMENT",
      invalidate_slots: isSeriesRepetition ? ["visual_concept", "art_direction", "cinematography", "editorial_rhythm"] : [],
      issues: [result.code, result.detail || ""].filter(Boolean),
      revision_plan: [isSeriesRepetition ? "Create a materially fresh Series plan while preserving intentional continuity; vary the blocked environment/camera/layout/motif dimensions and emit a complete planSignature." : "Re-enter the responsible NexMind departments with the prior failure evidence; preserve unaffected approved intent and the 9.5 creative quality floor."],
      quality_reasons: [result.code],
      production_disposition: "CONTINUE_REPLANNING",
      quality_floor_may_weaken: false,
      silent_generic_fallback_allowed: false,
    };
    const repairContext = nextRepairContext(autonomousRepairContext, repairSeed, result.stateHash ?? null, result.finalBoard ? sha(result.finalBoard) : null);
    await saveCreativeMemoryObservation({ productionId: run.productionId, projectVersion: run.projectVersion, workflowRunId: run.id, family: draft.family!, resultCode: result.code, finalReview: record(result).finalReview ?? null, qualityEvidence: record(result).autonomousQualityEvidence ?? null, repairRequest: repairContext });
    await queueAutonomousP8Repair({ workflowRunId: run.id, productionId: run.productionId, projectVersion: run.projectVersion, repairContext });
  }
  await completeStudioActivity(activity.id, activity.workerId, { status: result.status, code: result.code, stateHash: result.stateHash ?? null, finalBoardHash: result.finalBoard ? sha(result.finalBoard) : null, checkpoint: result.checkpoint ?? null, finalBoard: result.finalBoard ?? null, dossier: result.dossier ?? null } as unknown as Record<string, unknown>);
  return result;
}

export async function standaloneWorkflowProjection(userId: string, productionId: string) {
  const prisma = getPrisma()!;
  const production = await prisma.production.findFirst({ where: { id: productionId, ownerUserId: userId }, select: { id: true } });
  if (!production) return null;
  const run = await prisma.studioWorkflowRun.findFirst({ where: { productionId, workflowType: "STANDALONE_STUDIO_CREATE_VIDEO" }, orderBy: { createdAt: "desc" }, include: { events: { orderBy: { sequence: "desc" }, take: 12 } } });
  if (!run) return null;
  const workflowContext = record(run.context);
  const nx = record(workflowContext.nexmind);
  const engineEvidence = record(workflowContext.engineEvidence);
  const finalOutput = record(workflowContext.finalOutput);
  const customerPhase = String(nx.customerPhase || "PREPARING");
  const status = String(nx.status || (run.status === "RUNNING" ? "RUNNING" : "QUEUED"));
  const copy: Record<string, { title: string; detail: string }> = {
    PREPARING: { title: "Preparing the production.", detail: "The Studio is checking the approved brief and what the production system can safely make." },
    SHAPING_STORY: { title: "Shaping the story.", detail: "The production is finding the clearest way to move from the opening idea to the payoff." },
    VISUAL_DIRECTION: { title: "Building the visual direction.", detail: "The Studio is developing the visual language around the approved idea." },
    DIRECTING_FILM: { title: "Directing the film.", detail: "The sequence, pacing and visual progression are being resolved." },
    DIRECTING_PERFORMANCE: { title: "Directing the performance.", detail: "Movement and interaction are being checked against the production’s real capabilities." },
    DESIGNING_SOUND: { title: "Designing the sound.", detail: "Sound is being shaped around the story and motion." },
    INTERNAL_REVIEW: { title: "Final internal review.", detail: "The production has reached the Studio’s internal creative-review gate. Nothing needs to be re-entered." },
    CREATIVE_LOCKED: { title: "Creative direction locked.", detail: "The production has passed the creative authority gate and is ready for the production engines." },
  };
  const base = copy[customerPhase] || copy.PREPARING;
  if (String(engineEvidence.status || "") === "BLOCKED") return { workflowRunId: run.id, status: "ENGINE_EVIDENCE_BLOCKED", phase: "INTERNAL_REVIEW", title: "Production needs an internal repair.", detail: "The Studio stopped at a real execution constraint instead of substituting a weaker scene. Your paid production and approved intent remain intact.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  if (["QUEUED","RUNNING"].includes(String(engineEvidence.status || ""))) return { workflowRunId: run.id, status: String(engineEvidence.status), phase: "INTERNAL_REVIEW", title: "Building the internal review film.", detail: "The approved creative state is being executed by the production engine so the Studio can review real video and sound before Creative Lock.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  if (["QUEUED","RUNNING"].includes(String(finalOutput.status || ""))) return { workflowRunId: run.id, status: String(finalOutput.status), phase: "FINAL_PRODUCTION", title: "Producing the final film.", detail: "Creative Lock has passed. The Studio is executing the locked production for your review.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  if (status === "PROVIDER_UNAVAILABLE") return { workflowRunId: run.id, status, phase: customerPhase, title: "Production is safely paused.", detail: "The Studio cannot reach its production intelligence right now. Your paid production and approved plan remain intact.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  if (status === "REVISE") return { workflowRunId: run.id, status, phase: customerPhase, title: "Refining the production.", detail: "The internal creative gate asked for another pass. Your approved brief remains the authority.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  const engineDispatch = record(nx.engineDispatch);
  if (status === "CREATIVE_LOCKED" && engineDispatch.status === "BLOCKED_RELEASE_GATE") return { workflowRunId: run.id, status, phase: customerPhase, title: "Creative direction locked.", detail: "The film is waiting at the Studio's internal production-release gate. Your approved production remains intact and nothing needs to be re-entered.", needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
  return { workflowRunId: run.id, status, phase: customerPhase, title: base.title, detail: base.detail, needsUserAction: false, events: run.events.map((event) => ({ type: event.eventType, at: event.createdAt.toISOString() })) };
}

function artifactContent(value: { content: unknown }) { return record(value.content); }

export async function queueStandaloneNexMindP8Finalize(productionId: string) {
  return queueAutonomousP8Finalization(productionId);
}

export async function runFinalizeStandaloneNexMindP8Activity(activity: { id: string; workflowRunId: string; workerId: string }) {
  const prisma = getPrisma()!;
  const run = await prisma.studioWorkflowRun.findUniqueOrThrow({ where: { id: activity.workflowRunId } });
  if (run.workflowType !== "STANDALONE_STUDIO_CREATE_VIDEO") throw new Error("Standalone P8 finalizer received the wrong workflow type.");
  const draft = await prisma.draft.findUniqueOrThrow({ where: { id: run.productionId } });
  if (!draft.family) throw new Error("STUDIO_FAMILY_MISSING");
  const persisted = await prisma.studioWorkflowActivity.findUniqueOrThrow({ where: { id: activity.id } });
  const activityInput = record(persisted.input);
  const ids = [activityInput.creativeStateArtifactId, activityInput.multimodalPackageArtifactId, activityInput.humanReviewArtifactId].filter((value): value is string => typeof value === "string" && value.length > 0);
  const artifacts = await prisma.studioArtifact.findMany({ where: { id: { in: ids }, productionId: run.productionId } });
  const byId = new Map(artifacts.map((artifact) => [artifact.id, artifact]));
  const creativeState = byId.get(String(activityInput.creativeStateArtifactId || ""));
  const reviewPackage = byId.get(String(activityInput.multimodalPackageArtifactId || ""));
  const humanReviewArtifact = typeof activityInput.humanReviewArtifactId === "string" ? byId.get(activityInput.humanReviewArtifactId) ?? null : null;
  if (!creativeState || !reviewPackage) throw new Error("NEXMIND_FINALIZATION_ARTIFACT_MISSING");
  if (creativeState.contentHash !== activityInput.creativeStateArtifactHash || reviewPackage.contentHash !== activityInput.multimodalPackageArtifactHash) throw new Error("NEXMIND_FINALIZATION_ARTIFACT_HASH_MISMATCH");
  if (creativeState.artifactType !== "NEXMIND_P8_CREATIVE_STATE" || reviewPackage.artifactType !== "NEXMIND_P8_MULTIMODAL_REVIEW_PACKAGE") throw new Error("NEXMIND_FINALIZATION_ARTIFACT_TYPE_MISMATCH");
  if (humanReviewArtifact) {
    if (humanReviewArtifact.contentHash !== activityInput.humanReviewArtifactHash || humanReviewArtifact.artifactType !== "NEXMIND_P8_BLIND_HUMAN_REVIEW") throw new Error("NEXMIND_FINALIZATION_HUMAN_REVIEW_ARTIFACT_MISMATCH");
  }
  const creative = artifactContent(creativeState);
  const mm = artifactContent(reviewPackage);
  const hr = humanReviewArtifact ? artifactContent(humanReviewArtifact) : null;
  if (hr && (hr.reviewedArtifactId !== reviewPackage.id || hr.reviewedArtifactSha256 !== reviewPackage.contentHash || record(hr.gate).status !== "PASS")) throw new Error("NEXMIND_FINALIZATION_HUMAN_REVIEW_MISMATCH");
  if (mm.creativeStateArtifactId !== creativeState.id || mm.creativeStateArtifactSha256 !== creativeState.contentHash || mm.status !== "COMPLETE") throw new Error("NEXMIND_FINALIZATION_MULTIMODAL_MISMATCH");

  const exactPerceptualMedia = await buildExactPerceptualMedia(mm, mm.audioExpected !== false);
  // Re-materialize the production's hash-bound source/reference visuals for the
  // final reference-independence audit. They are never inferred from text summaries.
  const finalInputs = await prisma.studioProductionInput.findMany({ where: { productionId: run.productionId, active: true }, orderBy: { ordinal: "asc" }, include: { source: true } });
  const finalSourcePacket = buildP8SourcePacket({ rawSources: draft.sources, productionInputs: finalInputs, prompt: draft.prompt || "" });
  const finalReferenceEvidence = await materializeSourceVisualEvidence(finalSourcePacket.visualReferences, draft.prompt || "");
  (exactPerceptualMedia as any).referenceVisuals = finalReferenceEvidence.evidence;
  (exactPerceptualMedia as any).referenceVisualOmissions = finalReferenceEvidence.omitted;
  const calibration = await loadStudioTasteCalibration();
  const request: StudioNexMindP8FinalizeRequest = {
    schema: "StudioNexMindP8FinalizeRequestV1",
    operation: "FINALIZE_WITH_MULTIMODAL_EVIDENCE",
    productionId: run.productionId,
    workflowRunId: run.id,
    checkpoint: creative.checkpoint,
    finalBoard: creative.finalBoard,
    multimodalArtifacts: array(mm.artifacts).map((item) => record(item)).map((item) => ({ artifact_id: String(item.artifact_id || ""), kind: String(item.kind || "") as StudioNexMindP8FinalizeRequest["multimodalArtifacts"][number]["kind"], sha256: String(item.sha256 || ""), media_sha256: String(item.media_sha256 || ""), object_key: String(item.object_key || ""), source: String(item.source || "") })),
    mediaSetSha256: exactPerceptualMedia.mediaSetSha256,
    perceptualMedia: exactPerceptualMedia,
    audioExpected: mm.audioExpected !== false,
    studioTasteCalibration: calibration,
    p8BuildHash: process.env.NEXMIND_P8_BUILD_HASH?.trim() || "",
    autonomyPolicy: { repairRound: Number(activityInput.repairRound || 0) },
    humanReview: hr ? {
      reviewer_id: String(hr.reviewerId || ""), reviewer_provenance: String(hr.reviewerProvenance || ""), blind: true, independent: true,
      scores: Object.fromEntries(Object.entries(record(hr.scores)).map(([key, value]) => [key, Number(value)])),
      hard_rejects: array(hr.hardRejects).map(String), notes: String(hr.notes || ""),
    } : null,
  };
  const result = await executeStudioNexMindP8(request, (event) => persistProgress(run.id, activity.id, activity.workerId, event.phase, event.payload));
  await persistUsage(run.id, run.productionId, result);
  const resultExtra = record(result);
  const latest = await prisma.studioWorkflowRun.findUniqueOrThrow({ where: { id: run.id } });
  const context = record(latest.context);
  const nx = record(context.nexmind);
  let lockArtifact = null;
  let repairContext: Record<string, unknown> | null = null;

  if (result.status === "REVISE" && Object.keys(record(resultExtra.repairRequest)).length) {
    repairContext = nextRepairContext(nx.autonomousRepair, resultExtra.repairRequest, result.stateHash ?? null, result.finalBoard ? sha(result.finalBoard) : null);
    await saveCreativeMemoryObservation({ productionId: run.productionId, projectVersion: run.projectVersion, workflowRunId: run.id, family: draft.family, resultCode: result.code, finalReview: resultExtra.finalReview ?? null, qualityEvidence: resultExtra.autonomousQualityEvidence ?? null, repairRequest: repairContext });
  }

  if (result.status === "CREATIVE_LOCKED" && result.checkpoint && result.finalBoard && result.stateHash) {
    const lockContent = {
      schema: "StudioNexMindP8CreativeLockV2",
      authoritySnapshot: "P8_AUTONOMOUS_CREATIVE_AUTHORITY_2026_08_14",
      productionId: run.productionId,
      workflowRunId: run.id,
      projectVersion: run.projectVersion,
      stateHash: result.stateHash,
      finalBoardHash: sha(result.finalBoard),
      checkpoint: result.checkpoint,
      finalBoard: result.finalBoard,
      dossier: result.dossier ?? null,
      multimodalPackageArtifactId: reviewPackage.id,
      multimodalPackageArtifactSha256: reviewPackage.contentHash,
      mediaSetSha256: exactPerceptualMedia.mediaSetSha256,
      reviewedVideoArtifactId: exactPerceptualMedia.videoArtifactId,
      reviewedVideoMediaSha256: exactPerceptualMedia.videoMediaSha256,
      executionPlanHash: String(record((array(mm.artifacts).map(record).find(x=>String(x.kind||"")==="VIDEO")||{})).executionPlanHash || ""),
      creativeLockMode: String(resultExtra.creativeLockMode || (humanReviewArtifact ? "HUMAN_CALIBRATION_BRIDGE" : "AUTONOMOUS_CALIBRATED")),
      memoryInputSnapshotId: String(creative.memoryInputSnapshotId || ""),
      memoryInputSnapshotHash: String(creative.memoryInputSnapshotHash || ""),
      finalReview: resultExtra.finalReview ?? null,
      finalReviewHash: resultExtra.finalReview ? sha(resultExtra.finalReview) : null,
      autonomousQualityEvidence: resultExtra.autonomousQualityEvidence ?? null,
      studioTasteCalibration: resultExtra.studioTasteCalibration ?? null,
      humanReviewArtifactId: humanReviewArtifact?.id ?? null,
      humanReviewArtifactSha256: humanReviewArtifact?.contentHash ?? null,
    };
    const contentHash = sha(lockContent);
    const lockInputs = [{ artifactId: creativeState.id, sha256: creativeState.contentHash }, { artifactId: reviewPackage.id, sha256: reviewPackage.contentHash }];
    if (humanReviewArtifact) lockInputs.push({ artifactId: humanReviewArtifact.id, sha256: humanReviewArtifact.contentHash });
    lockArtifact = await prisma.studioArtifact.findFirst({ where: { productionId: run.productionId, projectVersion: run.projectVersion, artifactType: "NEXMIND_P8_CREATIVE_LOCK", contentHash } })
      ?? await saveStudioArtifact({ productionId: run.productionId, projectVersion: run.projectVersion, artifactType: "NEXMIND_P8_CREATIVE_LOCK", status: "approved", content: lockContent, inputs: lockInputs, createdBy: { type: "service", role: "nexmind_p8_creative_lock", runId: run.id } });
    if (humanReviewArtifact && Object.keys(record(resultExtra.finalReview)).length) {
      await saveStudioTasteCalibrationSample({ productionId: run.productionId, projectVersion: run.projectVersion, family: draft.family, workflowRunId: run.id, multimodalPackageArtifact: reviewPackage, humanReviewArtifact, machineReview: record(resultExtra.finalReview), p8BuildHash: process.env.NEXMIND_P8_BUILD_HASH?.trim() || "", judgeEnsembleHash: String(resultExtra.judgeEnsembleHash || "") });
    }
  }

  const technical = result.status === "PROVIDER_UNAVAILABLE";
  const blocked = technical;
  const creativeRecovery = result.status === "REVISE" || result.status === "BLOCKED";
  const locked = result.status === "CREATIVE_LOCKED" && Boolean(lockArtifact);
  const engineAuthority = familyEngineAuthority(draft.family);
  await prisma.$transaction(async (tx) => {
    await assertStudioActivityLeaseTx(tx, activity.id, activity.workerId);
    await tx.studioWorkflowRun.update({ where: { id: run.id }, data: {
      status: blocked ? "BLOCKED" : repairContext || creativeRecovery ? "RUNNING" : "WAITING",
      blockedReason: blocked ? result.code : null,
      context: { ...context, nexmind: {
        ...nx,
        status: repairContext ? "RUNNING" : result.status,
        code: result.code,
        phase: locked ? "CREATIVE_LOCKED" : repairContext ? "AUTONOMOUS_REPAIR" : result.status === "HUMAN_REVIEW_REQUIRED" ? "HUMAN_REVIEW_REQUIRED" : "FINAL_PRODUCER",
        customerPhase: locked ? "CREATIVE_LOCKED" : "INTERNAL_REVIEW",
        stateHash: result.stateHash ?? nx.stateHash ?? null,
        finalBoardHash: result.finalBoard ? sha(result.finalBoard) : nx.finalBoardHash ?? null,
        creativeLockArtifactId: lockArtifact?.id ?? null,
        creativeLockArtifactHash: lockArtifact?.contentHash ?? null,
        autonomousRepair: repairContext ?? nx.autonomousRepair ?? null,
        autonomousQualityEvidence: resultExtra.autonomousQualityEvidence ?? null,
        studioTasteCalibration: resultExtra.studioTasteCalibration ?? null,
        creativeLockMode: resultExtra.creativeLockMode ?? null,
        engineDispatch: locked ? { status: engineAuthority.dispatchAdapterStatus === "READY" && engineAuthority.eligibleForPublicProduction ? "READY" : "BLOCKED_RELEASE_GATE", authorityId: engineAuthority.authorityId, reason: engineAuthority.truthBoundary } : null,
        updatedAt: new Date().toISOString(),
      } } as Prisma.InputJsonValue,
    } });
    await transitionCanonicalStudioStateTx(tx, {
      productionId: run.productionId,
      to: technical ? "TECHNICAL_RETRY" : "PRODUCTION",
      actor: { type: "service", id: "nexmind-p8", reason: technical ? "NEXMIND_FINALIZE_PROVIDER_UNAVAILABLE" : creativeRecovery ? "NEXMIND_FINALIZE_CREATIVE_RECOVERY" : "NEXMIND_FINALIZE_RESULT", metadata: { workflowRunId: run.id, status: result.status, code: result.code, creativeLockArtifactId: lockArtifact?.id ?? null, autonomousRepairRound: repairContext?.repairRound ?? null } },
    });
  }, { isolationLevel: "Serializable" });

  await appendEvent(run.id, locked ? "NEXMIND_P8_CREATIVE_LOCK_COMMITTED" : repairContext ? "NEXMIND_P8_AUTONOMOUS_REPAIR_REQUIRED" : `NEXMIND_P8_FINALIZE_${result.status}`, { status: result.status, code: result.code, creativeLockArtifactId: lockArtifact?.id ?? null, multimodalPackageArtifactId: reviewPackage.id, humanReviewArtifactId: humanReviewArtifact?.id ?? null, creativeLockMode: resultExtra.creativeLockMode ?? null, repairRound: repairContext?.repairRound ?? null });
  if (repairContext) {
    await queueAutonomousP8Repair({ workflowRunId: run.id, productionId: run.productionId, projectVersion: run.projectVersion, repairContext });
  } else if (locked && lockArtifact) {
    await queueReviewedFinalOutputPromotion({ workflowRunId: run.id, productionId: run.productionId, projectVersion: run.projectVersion, creativeLockArtifactId: lockArtifact.id, creativeLockArtifactHash: lockArtifact.contentHash, family: draft.family });
  }
  await completeStudioActivity(activity.id, activity.workerId, { status: result.status, code: result.code, stateHash: result.stateHash ?? null, creativeLockArtifactId: lockArtifact?.id ?? null, repairRound: repairContext?.repairRound ?? null } as unknown as Record<string, unknown>);
  return result;
}

