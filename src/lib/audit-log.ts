import type { Prisma } from "@/generated/prisma/client";
import { getPrisma } from "./db";
import { requestIpHash } from "./rate-limit";

export async function appendAuditEvent(input:{request:Request;requestId:string;actorUserId?:string|null;action:string;entityType:string;entityId:string;before?:unknown;after?:unknown}){
  const prisma=getPrisma(); if(!prisma) return;
  const safe=(value:unknown)=> value == null ? undefined : value as Prisma.InputJsonValue;
  await prisma.auditEvent.create({data:{actorUserId:input.actorUserId??null,action:input.action,entityType:input.entityType,entityId:input.entityId,requestId:input.requestId,ipHash:requestIpHash(input.request),before:safe(input.before),after:safe(input.after)}}).catch(()=>undefined);
}
