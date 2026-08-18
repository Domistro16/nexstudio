import { appendAuditEvent } from "@/lib/audit-log";
import { issueDeliveryTicket } from "@/lib/delivery-tickets";
import { getPrisma } from "@/lib/db";
import { json, problem } from "@/lib/http";
import { requireSession } from "@/lib/route-auth";
import { consumeRateLimit } from "@/lib/rate-limit";
export const runtime="nodejs";
export async function POST(request:Request,context:{params:Promise<{id:string}>}){const auth=await requireSession(request);if(auth.response)return auth.response;const limit=await consumeRateLimit(auth.session!.userId,"production_delivery_ticket",60,3600000);if(!limit.allowed)return problem(auth.id,429,"DELIVERY_RATE_LIMITED","Too many delivery links","Try again later.");const{id}=await context.params;const production=await getPrisma()!.production.findFirst({where:{id,ownerUserId:auth.session!.userId},include:{currentVersion:true}});const objectKey=production?.currentVersion?.outputObjectKey;if(!production||!objectKey)return problem(auth.id,404,"PRODUCTION_OUTPUT_NOT_FOUND","Production output not found","A finished output is required.");const ticket=await issueDeliveryTicket({userId:auth.session!.userId,purpose:"PRODUCTION_OUTPUT",productionId:production.id,objectKey,maxUses:2});await appendAuditEvent({request,requestId:auth.id,actorUserId:auth.session!.userId,action:"PRODUCTION_DELIVERY_ISSUED",entityType:"Production",entityId:production.id,after:{ticketId:ticket.ticketId,expiresAt:ticket.expiresAt.toISOString()}});return json({url:`/api/v1/delivery/${ticket.token}`,expiresAt:ticket.expiresAt.toISOString()},auth.id);}
