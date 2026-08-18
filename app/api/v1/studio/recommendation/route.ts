import { z } from "zod";
import { callNexMindDetailed, parseProviderJson } from "@/lib/nexmind";
import { consumeRateLimit, requestIpHash } from "@/lib/rate-limit";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { json, problem, requestId, zodProblem } from "@/lib/http";
import { nexMindRoleRouting } from "@/lib/nexmind-routing";
import { PRODUCTION_REGISTRY } from "@/studio-v1/public/registry/production-family-registry";
import { getPublicVideoTypes } from "@/studio-v1/public/registry/selectors";

export const runtime="nodejs";
const inputSchema=z.object({prompt:z.string().trim().min(8).max(3000)}).strict();
const outputSchema={type:"object",additionalProperties:false,required:["family","videoType","reason"],properties:{family:{type:"string"},videoType:{type:"string"},reason:{type:"string",minLength:1,maxLength:180}}} as const;

export async function POST(request:Request){
  const id=requestId(request);const origin=requireTrustedOrigin(request,id);if(origin)return origin;
  const parsed=inputSchema.safeParse(await request.json().catch(()=>null));if(!parsed.success)return zodProblem(id,parsed.error);
  const candidates=PRODUCTION_REGISTRY.families.flatMap((family)=>getPublicVideoTypes(PRODUCTION_REGISTRY,family.id)).map((item)=>({family:item.family,videoType:item.id,name:item.name,description:item.shortDescription}));
  if(!candidates.length)return json({status:"unavailable"},id);
  const limit=await consumeRateLimit(requestIpHash(request),"studio_public_recommendation_ip",20,60*60_000);if(!limit.allowed)return problem(id,429,"RECOMMENDATION_RATE_LIMITED","Recommendation temporarily unavailable",`Try again in ${limit.retryAfterSeconds} seconds.`);
  try{
    const routing=nexMindRoleRouting("studio_plan_preview");
    const result=await callNexMindDetailed([
      {role:"system",content:"Choose exactly one certified Studio production type from the supplied candidates that best fits the customer brief. Do not invent capabilities. Return only the selected family, videoType and one short customer-facing reason."},
      {role:"user",content:JSON.stringify({brief:parsed.data.prompt,candidates})},
    ],{model:routing.model,apiUrl:process.env.STUDIO_PLAN_PREVIEW_OPENAI_API_URL?.trim()||"https://api.openai.com/v1",apiKey:process.env.STUDIO_PLAN_PREVIEW_OPENAI_API_KEY?.trim()||process.env.OPENAI_API_KEY?.trim(),maxTokens:180,timeoutMs:8_000,jsonSchema:{name:"studio_public_recommendation",schema:outputSchema as unknown as Record<string,unknown>}});
    const value=parseProviderJson(result.content) as {family?:string;videoType?:string;reason?:string};
    const selected=candidates.find((candidate)=>candidate.family===value.family&&candidate.videoType===value.videoType);
    if(!selected||typeof value.reason!=="string"||!value.reason.trim())return problem(id,503,"RECOMMENDATION_INVALID","Recommendation unavailable","Studio did not return a certified starting point.");
    return json({status:"ready",recommendation:{family:selected.family,videoType:selected.videoType,reason:value.reason.trim().slice(0,180)}},id);
  }catch{return problem(id,503,"RECOMMENDATION_UNAVAILABLE","Recommendation unavailable","Choose a certified production type directly, or try again later.");}
}
