import { Suspense } from "react";
import { NewProductionBrief } from "@/studio-v1/react/NewProductionBrief";
export default function Page(){return <Suspense fallback={<div className="sv1-root sv1-calm"><main className="sv1-room">Preparing your brief…</main></div>}><NewProductionBrief/></Suspense>;}
