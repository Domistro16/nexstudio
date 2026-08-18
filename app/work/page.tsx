import type { Metadata } from "next";
import { headers } from "next/headers";
import { getSession } from "@/lib/auth";
import { StudioWorkExperience } from "@/studio-v1/react/StudioWorkExperience";
export const metadata:Metadata={title:"Work",description:"Certified work made through the Studio release pipeline."};
export default async function Page(){const h=await headers();const session=await getSession(new Request("http://localhost/work",{headers:h}));return <StudioWorkExperience authenticated={Boolean(session)}/>}
