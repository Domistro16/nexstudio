import { useStudioWork } from "../hooks.js";
import { ErrorState, LoadState } from "./shared.js";
import { ProjectCard } from "./ProjectCard.js";
import type { DashboardProject } from "../../domain/dashboard.js";
const PRODUCTION_STATES = new Set(["PLANNING","PAYMENT_PENDING","PRODUCTION","PRODUCTION_FAILED","TECHNICAL_RETRY"]);
function DeskSection({ title, description, projects, onOpenProject }: { title: string; description: string; projects: DashboardProject[]; onOpenProject: (id: string) => void }) {
  if (!projects.length) return null;
  return <section className="sf-work-section"><div className="sf-section-head"><div><span>{title}</span><h2>{title}</h2><p>{description}</p></div></div><div className="sf-project-grid">{projects.map((project) => <ProjectCard key={project.id} project={project} onOpen={onOpenProject}/>)}</div></section>;
}
export function WorkRoute({ onOpenProject, onCreate }: { onOpenProject: (id: string) => void; onCreate: () => void }) {
  const work = useStudioWork(); if (work.loading) return <LoadState label="Loading your work"/>; if (work.error) return <ErrorState message={work.error} onRetry={work.refresh}/>;
  const projects = work.data?.projects ?? []; const needsYou=projects.filter(p=>p.needsAction); const inProduction=projects.filter(p=>!p.needsAction&&PRODUCTION_STATES.has(p.state)); const surfaced=new Set([...needsYou,...inProduction].map(p=>p.id)); const recent=projects.filter(p=>!surfaced.has(p.id)).slice(0,12);
  return <section className="sf-route sf-work-route"><header className="sf-route-head"><div><span>Dashboard</span><h1>Your work.</h1><p>The work that needs you, the films underway, and your latest production history.</p></div><button className="sf-primary" onClick={onCreate}>Create</button></header>{projects.length?<div className="sf-work-stack"><DeskSection title="Needs you" description="Approvals, balance or revision decisions waiting on you." projects={needsYou} onOpenProject={onOpenProject}/><DeskSection title="In production" description="Work Studio is actively planning, producing or recovering." projects={inProduction} onOpenProject={onOpenProject}/><DeskSection title="Recent work" description="Drafts and completed productions, ordered by the latest real change." projects={recent} onOpenProject={onOpenProject}/>{!needsYou.length&&!inProduction.length&&!recent.length?<p className="sf-muted">No current work.</p>:null}</div>:<div className="sf-empty"><h2>No work yet.</h2><p>Your first real production will appear here as soon as you create it.</p><button className="sf-primary" onClick={onCreate}>Create your first production</button></div>}</section>;
}
