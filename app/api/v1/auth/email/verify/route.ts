import { NextResponse } from "next/server";
import { createSessionTx, secretHashCandidates, setSessionCookie } from "@/lib/auth";
import { appendAuditEvent } from "@/lib/audit-log";
import { getPrisma } from "@/lib/db";
import { problem, requestId } from "@/lib/http";
export const runtime="nodejs";
export async function GET(request:Request){
  const id=requestId(request);const token=new URL(request.url).searchParams.get("token");
  if(!token||token.length>512)return problem(id,422,"EMAIL_LINK_INVALID","Sign-in link is incomplete","Request a new Studio sign-in link.");
  const prisma=getPrisma();if(!prisma)return problem(id,503,"DATABASE_REQUIRED","Email sign-in is unavailable","Persistent account storage is required.");
  const hashes=secretHashCandidates("email-magic",token);
  try{
    const result=await prisma.$transaction(async tx=>{
      const challenge=await tx.authChallenge.findFirst({where:{purpose:"EMAIL_MAGIC",secretHash:{in:hashes},usedAt:null,expiresAt:{gt:new Date()}},orderBy:{createdAt:"desc"}});
      if(!challenge)throw new Error("EMAIL_LINK_EXPIRED");
      const claimed=await tx.authChallenge.updateMany({where:{id:challenge.id,usedAt:null,expiresAt:{gt:new Date()}},data:{usedAt:new Date()}});
      if(claimed.count!==1)throw new Error("EMAIL_LINK_ALREADY_USED");
      const email=challenge.identifier.toLowerCase();const payload=challenge.payload as {next?:string|null};const next=payload.next?.startsWith("/")&&!payload.next.startsWith("//")?payload.next:"/dashboard";
      const existing=await tx.user.findUnique({where:{email}});
      if(existing && (existing as {privacyStatus?:string}).privacyStatus==="DELETED")throw new Error("ACCOUNT_DELETED");
      const target=existing
        ? await tx.user.update({where:{id:existing.id},data:{email}})
        : challenge.userId
          ? await tx.user.update({where:{id:challenge.userId},data:{email}})
          : await tx.user.create({data:{email,displayName:email.split("@")[0].replace(/[._-]+/g," ").replace(/\b\w/g,c=>c.toUpperCase()),settings:{}}});
      await tx.authChallenge.update({where:{id:challenge.id},data:{userId:target.id}});
      await tx.authIdentity.upsert({where:{provider_subject:{provider:"EMAIL",subject:email}},create:{userId:target.id,provider:"EMAIL",subject:email,email,emailVerified:true},update:{userId:target.id,email,emailVerified:true}});
      const session=await createSessionTx(tx,target.id,request);
      return{user:target,next,challengeId:challenge.id,session};
    },{isolationLevel:"Serializable"});
    const session=result.session;
    await appendAuditEvent({request,requestId:id,actorUserId:result.user.id,action:"AUTH_EMAIL_VERIFIED",entityType:"AuthChallenge",entityId:result.challengeId});
    const response=NextResponse.redirect(new URL(result.next,new URL(request.url).origin),303);setSessionCookie(response,session.token,session.expiresAt,request);return response;
  }catch(error){
    const code=error instanceof Error?error.message:"EMAIL_LINK_EXPIRED";
    if(code==="ACCOUNT_DELETED")return problem(id,410,code,"Account is no longer active","Contact support if you believe this is incorrect.");
    return problem(id,410,code==="EMAIL_LINK_ALREADY_USED"?code:"EMAIL_LINK_EXPIRED","Sign-in link has expired","Request a new Studio sign-in link.");
  }
}
