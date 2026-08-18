import { getPrisma } from "@/lib/db";
import { verifyStripeWebhook } from "@/lib/payment-provider";
import { failStandaloneFundingIntent, settleStandaloneFundingIntent } from "@/studio-v1/billing";
export const runtime="nodejs";
export async function POST(request:Request){
  const length=Number(request.headers.get("content-length")||0);if(length>1024*1024)return new Response("payload too large",{status:413});
  const raw=await request.text();let event:ReturnType<typeof verifyStripeWebhook>;
  try{event=verifyStripeWebhook(raw,request.headers.get("stripe-signature"));}catch(error){console.warn("Rejected Stripe webhook",error instanceof Error?error.message:"invalid");return new Response("invalid signature",{status:400});}
  const session=event.data.object;const intentId=session.client_reference_id||session.metadata?.funding_intent_id;if(!intentId)return new Response("ignored",{status:200});
  const intent=await getPrisma()!.studioFundingIntent.findFirst({where:{id:intentId,provider:"stripe"}});if(!intent)return new Response("ignored",{status:200});
  if(session.id&&intent.providerReference&&session.id!==intent.providerReference)return new Response("reference mismatch",{status:409});
  try{
    if((event.type==="checkout.session.completed"||event.type==="checkout.session.async_payment_succeeded")&&session.payment_status==="paid"){
      if(typeof session.amount_total!=="number"||!session.currency)return new Response("amount missing",{status:409});
      await settleStandaloneFundingIntent({fundingIntentId:intent.id,providerReference:session.id,amountMinor:session.amount_total,currency:session.currency});
    }else if(event.type==="checkout.session.async_payment_failed"||event.type==="checkout.session.expired"){
      await failStandaloneFundingIntent({fundingIntentId:intent.id,reason:event.type,cancelled:event.type==="checkout.session.expired"});
    }
    return new Response("ok",{status:200});
  }catch(error){console.error("Stripe funding webhook processing failed",error);return new Response("retry",{status:500});}
}
