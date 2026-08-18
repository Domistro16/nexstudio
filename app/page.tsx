import type { Metadata } from "next";
import { headers } from "next/headers";
import { getSession } from "@/lib/auth";
import { StudioPublicExperience } from "@/studio-v1/react/StudioPublicExperience";
export const metadata:Metadata={title:"Studio — Make something worth watching",description:"Creative production for humans and agents."};
export default async function Page(){const h=await headers();const session=await getSession(new Request("http://localhost/",{headers:h}));return <StudioPublicExperience authenticated={Boolean(session)}/>;}
