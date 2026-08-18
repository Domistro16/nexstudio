import { requireSession } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { json } from "@/lib/http";
import { appendAuditEvent } from "@/lib/audit-log";
export const runtime="nodejs";
export async function GET(request:Request){const auth=await requireSession(request);if(auth.response)return auth.response;const rows=await getPrisma()!.session.findMany({where:{userId:auth.session!.userId,status:"ACTIVE",revokedAt:null,expiresAt:{gt:new Date()}},orderBy:{lastSeenAt:"desc"},take:50});return json({sessions:rows.map(row=>({id:row.id,current:row.id===auth.session!.id,userAgent:row.userAgent,lastSeenAt:row.lastSeenAt.toISOString(),createdAt:row.createdAt.toISOString(),expiresAt:row.expiresAt.toISOString()}))},auth.id);}
export async function DELETE(request:Request){const auth=await requireSession(request);if(auth.response)return auth.response;const prisma=getPrisma()!;const result=await prisma.session.updateMany({where:{userId:auth.session!.userId,id:{not:auth.session!.id},status:"ACTIVE",revokedAt:null},data:{status:"REVOKED",revokedAt:new Date()}});await appendAuditEvent({request,requestId:auth.id,actorUserId:auth.session!.userId,action:"SESSIONS_REVOKED_OTHER",entityType:"User",entityId:auth.session!.userId,after:{count:result.count}});return json({revoked:result.count},auth.id);}
