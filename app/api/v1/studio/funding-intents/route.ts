import { z } from "zod";
import { appendAuditEvent } from "@/lib/audit-log";
import { json, problem, zodProblem } from "@/lib/http";
import { createFundingCheckout, paymentProviderStatus, retrieveFundingCheckout } from "@/lib/payment-provider";
import { idempotencyKey, requireSession } from "@/lib/route-auth";
import { consumeRateLimit } from "@/lib/rate-limit";
import { attachFundingProviderSession, createOrLoadStandaloneFundingIntent, failStandaloneFundingIntent } from "@/studio-v1/billing";
export const runtime="nodejs";
const schema=z.object({productionId:z.string().uuid().optional(),quoteId:z.string().uuid().optional(),purpose:z.enum(["EXACT_PRODUCTION","BALANCE_TOPUP"]).default("EXACT_PRODUCTION"),requestedTopupMinor:z.number().int().min(100).max(1000000).optional()}).strict();
export async function POST(request:Request){
  const auth=await requireSession(request);if(auth.response)return auth.response;const limit=await consumeRateLimit(auth.session!.userId,"funding_intent",20,3600000);if(!limit.allowed)return problem(auth.id,429,"FUNDING_RATE_LIMITED","Too many funding attempts",`Wait ${limit.retryAfterSeconds} seconds.`);const key=idempotencyKey(request,auth.id);if(key.response)return key.response;
  const parsed=schema.safeParse(await request.json().catch(()=>null));if(!parsed.success)return zodProblem(auth.id,parsed.error);
  const provider=paymentProviderStatus();if(!provider.configured||!provider.readyForLive)return problem(auth.id,503,"STUDIO_PAYMENT_PROVIDER_NOT_CONFIGURED","Online funding is unavailable","Your production and approved plan remain saved. A verified live payment provider must be configured before funding is enabled.");
  try{
    const intent=await createOrLoadStandaloneFundingIntent({userId:auth.session!.userId,productionId:parsed.data.productionId,quoteId:parsed.data.quoteId,purpose:parsed.data.purpose,requestedTopupMinor:parsed.data.requestedTopupMinor,idempotencyKey:key.value!});
    let checkoutUrl=(intent as {providerCheckoutUrl?:string|null}).providerCheckoutUrl??null;let providerReference=intent.providerReference;
    if(providerReference&&!checkoutUrl){const session=await retrieveFundingCheckout(providerReference);checkoutUrl=session.url;}
    if(!providerReference){
      try{
        const returnPath=intent.productionId?`/production/${intent.productionId}`:"/dashboard/billing";
        const session=await createFundingCheckout({fundingIntentId:intent.id,userId:intent.userId,amountMinor:intent.amountMinor,productionId:intent.productionId,description:intent.productionId?"Funding required to continue the approved Studio production":"Studio balance funding",returnPath,idempotencyKey:`stripe-checkout:${intent.id}`});
        if(!session.id||!session.url)throw new Error("PAYMENT_PROVIDER_SESSION_INVALID");providerReference=session.id;checkoutUrl=session.url;await attachFundingProviderSession({userId:intent.userId,fundingIntentId:intent.id,providerReference:session.id,checkoutUrl:session.url});
      }catch(error){await failStandaloneFundingIntent({fundingIntentId:intent.id,reason:error instanceof Error?error.message:"PAYMENT_PROVIDER_CREATE_FAILED"});throw error;}
    }
    await appendAuditEvent({request,requestId:auth.id,actorUserId:auth.session!.userId,action:"FUNDING_INTENT_CREATED",entityType:"StudioFundingIntent",entityId:intent.id,after:{purpose:intent.purpose,amountMinor:intent.amountMinor,currency:"USD",productionId:intent.productionId}});
    return json({fundingIntentId:intent.id,status:"PAYMENT_PENDING",amountMinor:intent.amountMinor,currency:"USD",checkoutUrl,productionId:intent.productionId},auth.id);
  }catch(error){const code=error instanceof Error?error.message:"FUNDING_FAILED";const client=new Set(["QUOTE_NOT_FOUND","QUOTE_EXPIRED","FUNDING_STATE_INVALID","FUNDING_NOT_REQUIRED","TOPUP_AMOUNT_INVALID","FUNDING_PRODUCTION_QUOTE_REQUIRED","IDEMPOTENCY_CONFLICT"]);if(client.has(code))return problem(auth.id,409,code,"Funding could not start","Refresh the saved production and try again.");console.error("Studio funding intent failed",error);return problem(auth.id,503,"FUNDING_PROVIDER_UNAVAILABLE","Online funding could not start","Your USD balance and production remain unchanged. Try again after the payment service recovers.");}
}
