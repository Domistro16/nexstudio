import { createHash, createHmac, randomBytes } from "node:crypto";
import type { NextResponse } from "next/server";
import type { Prisma } from "@/generated/prisma/client";
import { getPrisma } from "./db";
import { env } from "./env";
export const SESSION_COOKIE = "studio_session";
const SESSION_DAYS = 30;
export const sha256 = (value:string) => createHash("sha256").update(value).digest("hex");
export const keyedHash = (purpose:string,value:string) => createHmac("sha256", env.trustSecret).update(`${purpose}\0${value}`).digest("hex");
export const secretHash = (purpose:string,value:string) => keyedHash(purpose,value);
export const secretHashCandidates = (purpose:string,value:string) => Array.from(new Set([keyedHash(purpose,value), sha256(value)]));
export const randomToken = (bytes=32) => randomBytes(bytes).toString("base64url");
const sessionInclude = { user: true } satisfies Prisma.SessionInclude;
type SessionWithUser = Prisma.SessionGetPayload<{ include: typeof sessionInclude }>;
function cookieValues(request:Request,name:string){const raw=request.headers.get("cookie")||"";return raw.split(";").map(p=>p.trim().split("=")).filter(([k])=>k===name).map(([, ...v])=>decodeURIComponent(v.join("="))).filter(Boolean);}
export async function getSession(request:Request):Promise<SessionWithUser|null>{const prisma=getPrisma();if(!prisma)return null;const now=new Date();for(const token of cookieValues(request,SESSION_COOKIE)){const hashes=secretHashCandidates("session",token);const candidate=await prisma.session.findFirst({where:{tokenHash:{in:hashes}},include:sessionInclude});const privacyStatus=(candidate?.user as {privacyStatus?:string}|undefined)?.privacyStatus;if(candidate&&candidate.status==="ACTIVE"&&!candidate.revokedAt&&candidate.expiresAt>now&&privacyStatus!=="DELETED"){if(now.getTime()-candidate.lastSeenAt.getTime()>300000)void prisma.session.update({where:{id:candidate.id},data:{lastSeenAt:now}}).catch(()=>undefined);return candidate;}}return null;}
function sessionData(userId:string,request:Request){const token=randomToken();const expiresAt=new Date(Date.now()+SESSION_DAYS*86400000);const rawIp=request.headers.get("cf-connecting-ip")||request.headers.get("x-real-ip")||request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()||null;return{token,expiresAt,data:{userId,tokenHash:secretHash("session",token),expiresAt,userAgent:request.headers.get("user-agent")?.slice(0,500),ipHash:rawIp?keyedHash("ip",rawIp):null}};}
export async function createSessionTx(tx:Prisma.TransactionClient,userId:string,request:Request){const session=sessionData(userId,request);await tx.session.create({data:session.data});return{token:session.token,expiresAt:session.expiresAt};}
export async function createSession(userId:string,request:Request){const prisma=getPrisma();if(!prisma)throw new Error("Persistent database is required for authentication.");const session=sessionData(userId,request);await prisma.session.create({data:session.data});return{token:session.token,expiresAt:session.expiresAt};}
export function setSessionCookie(response:NextResponse,token:string,expiresAt:Date,request:Request){response.cookies.set(SESSION_COOKIE,token,{httpOnly:true,sameSite:"lax",secure:process.env.NODE_ENV==="production"||new URL(request.url).protocol==="https:",path:"/",expires:expiresAt});}
export function clearSessionCookie(response:NextResponse){response.cookies.set(SESSION_COOKIE,"",{httpOnly:true,sameSite:"lax",secure:process.env.NODE_ENV==="production",path:"/",expires:new Date(0)});}
export function publicUser(user:{id:string;email:string|null;displayName:string|null;avatarUrl:string|null;settings:unknown}){return{id:user.id,email:user.email,displayName:user.displayName,avatarUrl:user.avatarUrl,settings:user.settings};}
