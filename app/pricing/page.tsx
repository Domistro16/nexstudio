import type { Metadata } from "next";
import { headers } from "next/headers";
import { getSession } from "@/lib/auth";
import { StudioPricingExperience } from "@/studio-v1/react/StudioPricingExperience";
export const metadata:Metadata={title:"Pricing",description:"Studio video production pricing."};
export default async function Page(){const h=await headers();const session=await getSession(new Request("http://localhost/pricing",{headers:h}));return <StudioPricingExperience authenticated={Boolean(session)}/>}
