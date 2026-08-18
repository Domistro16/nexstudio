import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";
import { StudioDashboardExperience } from "@/studio-v1/react/StudioDashboardExperience";
export const metadata:Metadata={title:"Dashboard"};
export default async function Page(){const h=await headers();const session=await getSession(new Request("http://localhost/dashboard",{headers:h}));if(!session)redirect("/?signin=1");return <StudioDashboardExperience/>;}
