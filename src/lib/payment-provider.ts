import { createHmac, timingSafeEqual } from "node:crypto";
import { env } from "./env";

type CheckoutSession={id:string;url:string|null;payment_status?:string;status?:string;amount_total?:number|null;currency?:string|null;client_reference_id?:string|null;metadata?:Record<string,string>|null};

function stripeConfigured(){return env.paymentProvider==="stripe"&&Boolean(env.stripeSecretKey)&&Boolean(env.stripeWebhookSecret);}
export function paymentProviderStatus(){
  const configured=stripeConfigured();
  const liveKey=env.stripeSecretKey.startsWith("sk_live_");
  return {provider:env.paymentProvider,configured,liveKey,readyForLive:configured&&(!env.stripeLiveRequired||liveKey)};
}
async function stripeRequest<T>(path:string,init:{method?:string;body?:URLSearchParams;idempotencyKey?:string}={}){
  if(!stripeConfigured())throw new Error("STUDIO_PAYMENT_PROVIDER_NOT_CONFIGURED");
  const response=await fetch(`https://api.stripe.com${path}`,{method:init.method||"GET",headers:{authorization:`Bearer ${env.stripeSecretKey}`,...(init.body?{"content-type":"application/x-www-form-urlencoded"}:{}),...(init.idempotencyKey?{"Idempotency-Key":init.idempotencyKey}:{})},body:init.body?.toString(),cache:"no-store"});
  const payload=await response.json().catch(()=>null) as (T&{error?:{message?:string}})|null;
  if(!response.ok)throw new Error(`PAYMENT_PROVIDER_ERROR:${payload?.error?.message||response.status}`);
  return payload as T;
}
export async function createFundingCheckout(input:{fundingIntentId:string;userId:string;amountMinor:number;productionId?:string|null;description:string;returnPath:string;idempotencyKey:string}){
  const body=new URLSearchParams();
  body.set("mode","payment");body.set("client_reference_id",input.fundingIntentId);
  body.set("success_url",`${env.appOrigin}${input.returnPath}${input.returnPath.includes("?")?"&":"?"}funding=success&session_id={CHECKOUT_SESSION_ID}`);
  body.set("cancel_url",`${env.appOrigin}${input.returnPath}${input.returnPath.includes("?")?"&":"?"}funding=cancelled`);
  body.set("line_items[0][price_data][currency]","usd");body.set("line_items[0][price_data][unit_amount]",String(input.amountMinor));body.set("line_items[0][price_data][product_data][name]","Studio balance funding");body.set("line_items[0][price_data][product_data][description]",input.description);body.set("line_items[0][quantity]","1");
  // Minimize provider-side account data: the opaque funding-intent id is sufficient
  // for reconciliation. Do not send Studio user/production identifiers as metadata.
  body.set("metadata[funding_intent_id]",input.fundingIntentId);
  return stripeRequest<CheckoutSession>("/v1/checkout/sessions",{method:"POST",body,idempotencyKey:input.idempotencyKey});
}
export async function retrieveFundingCheckout(sessionId:string){return stripeRequest<CheckoutSession>(`/v1/checkout/sessions/${encodeURIComponent(sessionId)}`);}

export function verifyStripeWebhook(rawBody:string,signatureHeader:string|null,toleranceSeconds=300){
  if(!stripeConfigured())throw new Error("STUDIO_PAYMENT_PROVIDER_NOT_CONFIGURED");
  if(!signatureHeader)throw new Error("PAYMENT_WEBHOOK_SIGNATURE_MISSING");
  const parts=signatureHeader.split(",").map(v=>v.trim().split("=",2));const timestamp=parts.find(([k])=>k==="t")?.[1];const signatures=parts.filter(([k])=>k==="v1").map(([,v])=>v).filter(Boolean);
  if(!timestamp||!signatures.length)throw new Error("PAYMENT_WEBHOOK_SIGNATURE_INVALID");
  const seconds=Number(timestamp);if(!Number.isFinite(seconds)||Math.abs(Math.floor(Date.now()/1000)-seconds)>toleranceSeconds)throw new Error("PAYMENT_WEBHOOK_SIGNATURE_EXPIRED");
  const expected=createHmac("sha256",env.stripeWebhookSecret).update(`${timestamp}.${rawBody}`).digest("hex");
  const expectedBuffer=Buffer.from(expected,"hex");
  const ok=signatures.some(sig=>{try{const actual=Buffer.from(sig,"hex");return actual.length===expectedBuffer.length&&timingSafeEqual(actual,expectedBuffer);}catch{return false;}});
  if(!ok)throw new Error("PAYMENT_WEBHOOK_SIGNATURE_INVALID");
  return JSON.parse(rawBody) as {id:string;type:string;data:{object:CheckoutSession}};
}
