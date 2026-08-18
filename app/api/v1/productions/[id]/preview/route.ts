import path from "node:path";
import { requireSession } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { problem } from "@/lib/http";
import { readObject } from "@/lib/object-storage";
export const runtime="nodejs";
function type(key:string){const ext=path.extname(key).toLowerCase();return ext===".webm"?"video/webm":ext===".mov"?"video/quicktime":"video/mp4";}
export async function GET(request:Request,context:{params:Promise<{id:string}>}){const auth=await requireSession(request);if(auth.response)return auth.response;const{id}=await context.params;const production=await getPrisma()!.production.findFirst({where:{id,ownerUserId:auth.session!.userId},include:{currentVersion:true}});const key=production?.currentVersion?.previewObjectKey;if(!production||!key)return problem(auth.id,404,"PRODUCTION_PREVIEW_NOT_FOUND","Production preview not found","This production does not have a persisted preview yet.");const bytes=await readObject(key).catch(()=>null);if(!bytes)return problem(auth.id,404,"PRODUCTION_PREVIEW_MISSING","Production preview unavailable","The persisted preview could not be read.");return new Response(bytes,{headers:{"content-type":type(key),"content-length":String(bytes.byteLength),"cache-control":"private, no-store","x-content-type-options":"nosniff","content-disposition":"inline","x-studio-media":"verified-production-preview"}});}
