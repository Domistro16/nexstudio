import { WorkRoute } from "./WorkRoute.js";
import { SeriesRoute } from "./SeriesRoute.js";
import { BrandRoute } from "./BrandRoute.js";
import { AssetsRoute } from "./AssetsRoute.js";
import { BillingRoute } from "./BillingRoute.js";
export type DashboardSection = "work" | "series" | "brand" | "assets" | "billing";
const SECONDARY: Array<[DashboardSection,string]>=[["work","Your work"],["series","Series"],["brand","Brand"],["assets","Assets"],["billing","Billing"]];
export interface AuthenticatedStudioShellProps { section: DashboardSection; onSectionChange:(section:DashboardSection)=>void; onCreate:()=>void; onOpenProject:(id:string)=>void; onSignOut?:()=>void; }
export function AuthenticatedStudioShell({section,onSectionChange,onCreate,onOpenProject,onSignOut}:AuthenticatedStudioShellProps){return <div className="sf-shell"><header className="sf-topbar"><button className="sf-wordmark" onClick={()=>onSectionChange("work")}>Studio</button><nav aria-label="Authenticated navigation"><button className="active" onClick={()=>onSectionChange("work")}>Dashboard</button><button onClick={onCreate}>Create</button></nav><div className="sf-account">{onSignOut?<button onClick={onSignOut}>Sign out</button>:<span>Account</span>}</div></header><div className="sf-dashboard-frame"><aside className="sf-dashboard-nav" aria-label="Dashboard sections">{SECONDARY.map(([value,label])=><button key={value} className={section===value?"active":""} onClick={()=>onSectionChange(value)}>{label}</button>)}</aside><main className="sf-main">{section==="work"?<WorkRoute onOpenProject={onOpenProject} onCreate={onCreate}/>:section==="series"?<SeriesRoute onOpenProject={onOpenProject}/>:section==="brand"?<BrandRoute/>:section==="assets"?<AssetsRoute/>:<BillingRoute/>}</main></div></div>}
