import { z } from "zod";
import { getSession, randomToken, secretHash } from "@/lib/auth";
import { appendAuditEvent } from "@/lib/audit-log";
import { getPrisma } from "@/lib/db";
import { env } from "@/lib/env";
import { json, problem, requestId, zodProblem } from "@/lib/http";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { consumeRateLimit, requestIpHash } from "@/lib/rate-limit";
export const runtime="nodejs";
const schema=z.object({email:z.string().trim().email().max(320),next:z.string().trim().max(2000).optional()}).strict();
const safeNext=(v?:string)=>v?.startsWith("/")&&!v.startsWith("//")?v:"/dashboard";
export async function POST(request:Request){
  const id=requestId(request);const origin=requireTrustedOrigin(request,id);if(origin)return origin;
  if(!env.resendApiKey||!env.emailFrom)return problem(id,503,"EMAIL_AUTH_NOT_CONFIGURED","Email access is unavailable","Configure the approved email provider before enabling sign-in.");
  const parsed=schema.safeParse(await request.json().catch(()=>null));if(!parsed.success)return zodProblem(id,parsed.error);
  const prisma=getPrisma();if(!prisma)return problem(id,503,"DATABASE_REQUIRED","Email access is unavailable","A persistent database is required.");
  const email=parsed.data.email.toLowerCase();
  const [ipLimit,emailLimit]=await Promise.all([
    consumeRateLimit(requestIpHash(request),"email_magic_ip",10,3600000),
    consumeRateLimit(secretHash("email-rate",email),"email_magic_identifier",5,3600000),
  ]);
  if(!ipLimit.allowed||!emailLimit.allowed)return problem(id,429,"EMAIL_RATE_LIMITED","Too many email links requested",`Wait ${Math.max(ipLimit.retryAfterSeconds,emailLimit.retryAfterSeconds)} seconds.`);
  const current=await getSession(request);const token=randomToken(32);
  const challenge=await prisma.authChallenge.create({data:{userId:current?.userId,purpose:"EMAIL_MAGIC",identifier:email,secretHash:secretHash("email-magic",token),payload:{next:safeNext(parsed.data.next)},expiresAt:new Date(Date.now()+15*60000)}});
  const verifyOrigin=new URL(env.appOrigin).origin;
  const url=`${verifyOrigin}/api/v1/auth/email/verify?token=${encodeURIComponent(token)}`;
  const res=await fetch("https://api.resend.com/emails",{method:"POST",headers:{authorization:`Bearer ${env.resendApiKey}`,"content-type":"application/json"},body:JSON.stringify({from:env.emailFrom,to:[email],subject:"Your Studio sign-in link",html:`<p>Continue to your Studio:</p><p><a href="${url}">Open Studio</a></p><p>This link expires in 15 minutes and can be used once.</p>`})});
  if(!res.ok){await prisma.authChallenge.delete({where:{id:challenge.id}}).catch(()=>undefined);await appendAuditEvent({request,requestId:id,actorUserId:current?.userId,action:"AUTH_EMAIL_DELIVERY_FAILED",entityType:"AuthChallenge",entityId:challenge.id});return problem(id,503,"EMAIL_DELIVERY_FAILED","Email could not be sent","Try again without changing your saved production.");}
  await appendAuditEvent({request,requestId:id,actorUserId:current?.userId,action:"AUTH_EMAIL_REQUESTED",entityType:"AuthChallenge",entityId:challenge.id,after:{identifierHash:secretHash("email-audit",email),expiresAt:challenge.expiresAt.toISOString()}});
  return json({sent:true,expiresAt:challenge.expiresAt.toISOString()},id);
}
