import { NextResponse } from "next/server";
import { appendAuditEvent } from "@/lib/audit-log";
import { clearSessionCookie, getSession } from "@/lib/auth";
import { getPrisma } from "@/lib/db";
import { requestId } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
export async function POST(request:Request){const id=requestId(request);const origin=requireTrustedOrigin(request,id);if(origin)return origin;const session=await getSession(request);if(session){await getPrisma()?.session.update({where:{id:session.id},data:{status:"REVOKED",revokedAt:new Date()}}).catch(()=>undefined);await appendAuditEvent({request,requestId:id,actorUserId:session.userId,action:"SESSION_LOGOUT",entityType:"Session",entityId:session.id});}const response=NextResponse.json({ok:true},{headers:{"cache-control":"no-store"}});clearSessionCookie(response);return response;}
