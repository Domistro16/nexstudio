import { randomToken, secretHash } from "./auth";
import { getPrisma } from "./db";
import { env } from "./env";

export async function issueDeliveryTicket(input:{userId:string;purpose:"SOURCE"|"PRODUCTION_OUTPUT"|"ACCOUNT_EXPORT";sourceId?:string;productionId?:string;objectKey:string;ttlSeconds?:number;maxUses?:number}){
  const prisma=getPrisma();if(!prisma)throw new Error("DATABASE_REQUIRED");const token=randomToken(32);const expiresAt=new Date(Date.now()+(input.ttlSeconds??env.assetTicketTtlSeconds)*1000);
  const row=await prisma.assetDeliveryTicket.create({data:{userId:input.userId,sourceId:input.sourceId??null,productionId:input.productionId??null,objectKey:input.objectKey,purpose:input.purpose,tokenHash:secretHash("asset-delivery",token),maxUses:Math.max(1,Math.min(20,input.maxUses??1)),expiresAt}});
  return{ticketId:row.id,token,expiresAt};
}
