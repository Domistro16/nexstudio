import { z } from "zod";
import { getPrisma } from "@/lib/db";
import { json, zodProblem } from "@/lib/http";
import { requireSession } from "@/lib/route-auth";
export const runtime="nodejs";
export async function GET(request:Request){const auth=await requireSession(request);if(auth.response)return auth.response;const rows=await getPrisma()!.studioNotification.findMany({where:{userId:auth.session!.userId},orderBy:{createdAt:"desc"},take:100});return json({items:rows.map(r=>({id:r.id,type:r.type,title:r.title,body:r.body,href:r.href,readAt:r.readAt?.toISOString()??null,createdAt:r.createdAt.toISOString()}))},auth.id);}
const schema=z.object({ids:z.array(z.string().uuid()).max(100)}).strict();
export async function PATCH(request:Request){const auth=await requireSession(request);if(auth.response)return auth.response;const parsed=schema.safeParse(await request.json().catch(()=>null));if(!parsed.success)return zodProblem(auth.id,parsed.error);const result=await getPrisma()!.studioNotification.updateMany({where:{id:{in:parsed.data.ids},userId:auth.session!.userId},data:{readAt:new Date()}});return json({updated:result.count},auth.id);}
