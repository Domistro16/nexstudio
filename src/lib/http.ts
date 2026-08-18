import { randomUUID } from "node:crypto";
import type { ZodError } from "zod";
export function requestId(request:Request){return request.headers.get("x-request-id")?.slice(0,120)||randomUUID();}
export function json(data:unknown,id:string,init:ResponseInit={}){const headers=new Headers(init.headers);headers.set("content-type","application/json; charset=utf-8");headers.set("x-request-id",id);headers.set("cache-control","no-store");return new Response(JSON.stringify({data,requestId:id}),{...init,headers});}
export function problem(id:string,status:number,code:string,title:string,detail:string,actions?:unknown[]){return new Response(JSON.stringify({type:`urn:studio:problem:${code.toLowerCase()}`,title,status,detail,code,requestId:id,actions:actions||[]}),{status,headers:{"content-type":"application/problem+json","cache-control":"no-store","x-request-id":id}});}
export function zodProblem(id:string,error:ZodError){return problem(id,422,"VALIDATION_ERROR","Check the request","One or more fields are invalid.",error.issues.map(i=>({path:i.path.join("."),message:i.message})));}
