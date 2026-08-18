import { appendAuditEvent } from "@/lib/audit-log";
import { issueDeliveryTicket } from "@/lib/delivery-tickets";
import { getPrisma } from "@/lib/db";
import { json, problem } from "@/lib/http";
import { requireSession } from "@/lib/route-auth";
import { consumeRateLimit } from "@/lib/rate-limit";
export const runtime="nodejs";
export async function POST(request:Request,context:{params:Promise<{id:string}>}){const auth=await requireSession(request);if(auth.response)return auth.response;const limit=await consumeRateLimit(auth.session!.userId,"asset_delivery_ticket",60,3600000);if(!limit.allowed)return problem(auth.id,429,"DELIVERY_RATE_LIMITED","Too many delivery links","Try again later.");const{id}=await context.params;const source=await getPrisma()!.source.findFirst({where:{id,ownerUserId:auth.session!.userId,status:"READY",securityStatus:"CLEAN"}});if(!source?.objectKey)return problem(auth.id,404,"ASSET_NOT_READY","Asset is unavailable","Only clean, ready assets can be delivered.");const ticket=await issueDeliveryTicket({userId:auth.session!.userId,purpose:"SOURCE",sourceId:source.id,objectKey:source.objectKey,maxUses:1});await appendAuditEvent({request,requestId:auth.id,actorUserId:auth.session!.userId,action:"ASSET_DELIVERY_ISSUED",entityType:"Source",entityId:source.id,after:{ticketId:ticket.ticketId,expiresAt:ticket.expiresAt.toISOString()}});return json({url:`/api/v1/delivery/${ticket.token}`,expiresAt:ticket.expiresAt.toISOString()},auth.id);}
