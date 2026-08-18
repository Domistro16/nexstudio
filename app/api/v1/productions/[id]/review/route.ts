import { z } from "zod";
import { requireSession, requireTrustedOrigin } from "@/lib/route-auth";
import { getPrisma } from "@/lib/db";
import { json, problem, zodProblem } from "@/lib/http";
import { transitionCanonicalStudioStateTx } from "@/studio-v1/architecture/core";
import { queueStandaloneCustomerRevision } from "@/studio-v1/revisions";

export const runtime="nodejs";
const schema=z.discriminatedUnion("action",[
  z.object({action:z.literal("approve")}),
  z.object({action:z.literal("revision"),note:z.string().trim().min(2).max(2000),timestampSeconds:z.number().min(0).max(3600).nullable().optional()}),
]);

export async function POST(request:Request,context:{params:Promise<{id:string}>}){
  const auth=await requireSession(request);
  if(auth.response)return auth.response;
  const origin=requireTrustedOrigin(request,auth.id);
  if(origin)return origin;
  const body=schema.safeParse(await request.json().catch(()=>null));
  if(!body.success)return zodProblem(auth.id,body.error);
  const{id}=await context.params;
  const prisma=getPrisma()!;
  const production=await prisma.production.findFirst({where:{id,ownerUserId:auth.session!.userId},include:{currentVersion:true}});
  if(!production?.currentVersion)return problem(auth.id,404,"PRODUCTION_NOT_FOUND","Production not found","This finished production is unavailable.");

  if(body.data.action==="approve"){
    try {
      await prisma.$transaction(async(tx)=>{
        const current=await tx.production.findFirst({where:{id,ownerUserId:auth.session!.userId},include:{currentVersion:true}});
        if(!current?.currentVersion)throw new Error("PRODUCTION_NOT_FOUND");
        if(current.studioState==="COMPLETE"&&current.currentVersion.approvedAt)return;
        if(current.studioState!=="FINAL_REVIEW")throw new Error("PRODUCTION_NOT_IN_FINAL_REVIEW");
        const approvedAt=new Date();
        await tx.productionVersion.update({where:{id:current.currentVersion.id},data:{approvedAt}});
        await tx.production.update({where:{id},data:{status:"APPROVED",approverUserId:auth.session!.userId}});
        await transitionCanonicalStudioStateTx(tx,{
          productionId:id,
          ownerUserId:auth.session!.userId,
          to:"COMPLETE",
          actor:{type:"user",id:auth.session!.userId,reason:"CUSTOMER_APPROVED_FINAL_VERSION",requestId:auth.id,metadata:{productionVersionId:current.currentVersion.id,versionNumber:current.currentVersion.versionNumber}},
        });
      },{isolationLevel:"Serializable"});
      return json({status:"approved",productionId:id},auth.id);
    } catch(error) {
      const code=error instanceof Error?error.message:"APPROVAL_FAILED";
      return problem(auth.id,409,code,"Film could not be approved","The production remains unchanged.");
    }
  }

  try{
    const result=await queueStandaloneCustomerRevision({userId:auth.session!.userId,productionId:id,versionId:production.currentVersion.id,instruction:body.data.note,timestampSeconds:body.data.timestampSeconds??null});
    return json({status:"revision_queued",...result},auth.id,{status:202});
  }catch(error){
    const code=error instanceof Error?error.message:"REVISION_FAILED";
    return problem(auth.id,409,code,"Revision could not be queued","The existing paid production remains intact.");
  }
}
