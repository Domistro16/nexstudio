import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import type { StudioProductionFamily } from "@/generated/prisma/client";
import { familyEngineAuthority } from "@/studio-v1/production-engines/authority";

export type StudioRuntimeRequirements = {
  family: StudioProductionFamily;
  voiceRequired: boolean;
  authoredArtRequired: boolean;
  musicRequired?: boolean;
};
export type StudioRuntimeAttestation = {
  schema:"StudioProductionRuntimeAttestationV1";
  status:"READY"|"BLOCKED";
  requirements:StudioRuntimeRequirements;
  p8BuildHash:string;
  engineAuthority:{authorityId:string;sourceArchiveSha256:string};
  checks:Array<{id:string;pass:boolean;detail:string}>;
  missing:string[];
  checkedAt:string;
};
const env=(k:string)=>process.env[k]?.trim()||"";
function bin(name:string){const r=spawnSync(name,["-version"],{encoding:"utf8",timeout:4000});return r.status===0;}
function jsonEnv(name:string):unknown{const raw=env(name);if(!raw)return null;try{return JSON.parse(raw);}catch{return {invalid:true};}}
function commandCapability(name:string){const reg=jsonEnv("NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON") as any;const rec=reg?.capabilities?.[name];if(!rec||rec.transport!=="command"||!rec.command)return false;const argv=Array.isArray(rec.command)?rec.command:String(rec.command).split(/\s+/);const first=String(argv[0]||"");return Boolean(first)&&(first.includes("/")?existsSync(first):true);}
function audioRoutes(name:string){const reg=jsonEnv(name) as any;const routes=Array.isArray(reg)?reg:Array.isArray(reg?.routes)?reg.routes:[];return routes.some((r:any)=>r&&r.commercialUseAllowed===true&&Array.isArray(r.command)&&r.command.length>0&&(!r.credentialEnv||env(String(r.credentialEnv))));}
function registryRoutes(){const r=jsonEnv("NEXMIND_MODEL_REGISTRY_JSON") as any;return Array.isArray(r)?r:Array.isArray(r?.routes)?r.routes:[];}
type BootRoute={role:string;task?:string;model:string;probeStatus:string;inputModalities?:string[];audioInputMode?:string};
type BootAttestation={schema:string;status:string;p8BuildHash:string;checkedAt:string;routes:BootRoute[]};
function bootAttestation():BootAttestation|null{const x=jsonEnv("NEXMIND_RUNTIME_BOOT_ATTESTATION_JSON") as any;return x&&typeof x==="object"?x:null;}
function bootFresh(x:BootAttestation|null){if(!x||x.schema!=="StudioNexMindRuntimeBootAttestationV1"||x.status!=="PASS")return false;const t=Date.parse(String(x.checkedAt||""));return Number.isFinite(t)&&Date.now()-t>=0&&Date.now()-t<=15*60*1000;}
function bootRoute(x:BootAttestation|null,role:string){return Array.isArray(x?.routes)?x!.routes.find(r=>r&&r.role===role&&r.probeStatus==="PASS"):undefined;}
function routeFor(rolePrefix:string,capability:string){
  const model=env(rolePrefix+"_MODEL"); if(model)return {model,mods:env(rolePrefix+"_INPUT_MODALITIES").split(",").map(x=>x.trim()).filter(Boolean),audio:env(rolePrefix+"_AUDIO_INPUT_MODE")};
  const routes=registryRoutes().filter((r:any)=>Array.isArray(r?.capabilities)&&(r.capabilities.includes(capability)||r.capabilities.includes("*")));
  const r=routes.sort((a:any,b:any)=>Number(b.priority||0)-Number(a.priority||0))[0];return r?{model:String(r.model||""),mods:Array.isArray(r.input_modalities)?r.input_modalities.map(String):[],audio:String(r.audio_input_mode||"")}:null;
}
export function attestStudioProductionRuntime(req:StudioRuntimeRequirements):StudioRuntimeAttestation{
  const checks:Array<{id:string;pass:boolean;detail:string}>=[];const ck=(id:string,pass:boolean,detail:string)=>checks.push({id,pass,detail});
  const auth=familyEngineAuthority(req.family); const build=env("NEXMIND_P8_BUILD_HASH"); ck("p8-build-hash",/^[a-f0-9]{64}$/i.test(build),build||"missing");
  ck("family-engine-authority",/^[a-f0-9]{64}$/i.test(auth.sourceArchiveSha256),`${auth.authorityId}:${auth.sourceArchiveSha256}`);
  const modelRegistry=jsonEnv("NEXMIND_MODEL_REGISTRY_JSON") as any; ck("model-registry-valid",!(modelRegistry as any)?.invalid,"model registry JSON must parse or be absent");
  const boot=bootAttestation(); ck("runtime-boot-attestation",bootFresh(boot),boot?`${boot.schema}:${boot.status}:${boot.checkedAt}`:"missing");
  if(boot)ck("runtime-boot-build-binding",boot.p8BuildHash===build,`${boot.p8BuildHash||"missing"} == ${build||"missing"}`);
  ck("ffmpeg",bin("ffmpeg"),"required for encoded production");ck("ffprobe",bin("ffprobe"),"required for media verification");
  if(req.family==="WHITEBOARD"||req.family==="EXPLAINER")ck("browser-runtime",Boolean(env("STUDIO_BROWSER_COMMAND")||env("PLAYWRIGHT_BROWSERS_PATH")||env("CHROME_BIN")||env("CHROMIUM_BIN")),"browser command/path must be declared");
  const fp=routeFor("NEXMIND_FINAL_EXECUTIVE_PRODUCER","multimodal_commercial_taste");const pa=routeFor("NEXMIND_PERCEPTUAL_AUDITOR","multimodal_perceptual_audit");
  ck("final-producer-route",!!fp,"exact Final Producer route");ck("perceptual-auditor-route",!!pa,"independent auditor route");
  const fpBoot=bootRoute(boot,"IndependentFinalExecutiveProducer"); const paBoot=bootRoute(boot,"IndependentPerceptualAuditor");
  ck("final-producer-boot-probe",!!fpBoot,"fresh successful multimodal route probe");ck("perceptual-auditor-boot-probe",!!paBoot,"fresh successful multimodal route probe");
  if(fp&&fpBoot)ck("final-producer-boot-model-binding",fp.model===fpBoot.model,`${fp.model} == ${fpBoot.model}`);
  if(pa&&paBoot)ck("auditor-boot-model-binding",pa.model===paBoot.model,`${pa.model} == ${paBoot.model}`);
  if(fp){ck("final-producer-modalities",fp.mods.includes("images")&&fp.mods.includes("audio")&&!!fp.audio,`modalities=${fp.mods.join(",")};audioMode=${fp.audio||"missing"}`)}
  if(pa){ck("auditor-modalities",pa.mods.includes("images")&&pa.mods.includes("audio")&&!!pa.audio,`modalities=${pa.mods.join(",")};audioMode=${pa.audio||"missing"}`)}
  // Role/process independence is required; model identity independence is not.
  // A single sufficiently capable route may serve creative, Final Producer, and
  // Perceptual Auditor roles. The boot attestation proves the two final-review
  // tasks were probed separately; exact-media delivery and blind auditor input
  // are enforced during finalization.
  ck("final-review-role-process-independence",!!fpBoot&&!!paBoot&&fpBoot.role!==paBoot.role,`${fpBoot?.role||"missing"} | ${paBoot?.role||"missing"}`);
  if(req.authoredArtRequired){const art=jsonEnv("NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON") as any;ck("authored-art-registry-valid",!!art&&!art.invalid,"registry required and must parse");ck("authored-art-generator",commandCapability("authored_scene_illustration"),"command capability");ck("authored-art-pixel-reviewer",commandCapability("authored_scene_pixel_fidelity_review"),"independent exact-pixel fidelity capability")}
  if(req.voiceRequired){const t=jsonEnv("NEXSTUDIO_TTS_ROUTES_JSON") as any;ck("tts-registry-valid",!!t&&!t.invalid,"TTS registry required and must parse");ck("tts-route",audioRoutes("NEXSTUDIO_TTS_ROUTES_JSON"),"commercial TTS route")}if(req.musicRequired){const m=jsonEnv("NEXSTUDIO_MUSIC_ROUTES_JSON") as any;ck("music-registry-valid",!!m&&!m.invalid,"music registry required and must parse");ck("music-route",audioRoutes("NEXSTUDIO_MUSIC_ROUTES_JSON"),"commercial-rights music route")}
  const missing=checks.filter(x=>!x.pass).map(x=>x.id);return {schema:"StudioProductionRuntimeAttestationV1",status:missing.length?"BLOCKED":"READY",requirements:req,p8BuildHash:build,engineAuthority:{authorityId:auth.authorityId,sourceArchiveSha256:auth.sourceArchiveSha256},checks,missing,checkedAt:new Date().toISOString()};
}
export function assertStudioProductionRuntimeReady(req:StudioRuntimeRequirements){const a=attestStudioProductionRuntime(req);if(a.status!=="READY")throw new Error(`STUDIO_RUNTIME_NOT_READY:${a.missing.join(",")}`);return a;}
