import { headers } from "next/headers";
import { getSession } from "@/lib/auth";
import { ProductionWorkspace } from "@/studio-v1/react/ProductionWorkspace";
export default async function Page({params,searchParams}:{params:Promise<{id:string}>;searchParams:Promise<{claim?:string;continue?:string}>}){const[{id},q,h]=await Promise.all([params,searchParams,headers()]);const session=await getSession(new Request(`http://localhost/production/${id}`,{headers:h}));return <ProductionWorkspace draftId={id} authenticated={Boolean(session)} continueAfterAuth={q.claim==="1"&&q.continue==="1"}/>;}
