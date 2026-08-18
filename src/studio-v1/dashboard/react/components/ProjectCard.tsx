import type { DashboardProject } from "../../domain/dashboard.js";
function familyLabel(value: DashboardProject["family"]): string { return value.replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase()); }
export function ProjectCard({ project, onOpen }: { project: DashboardProject; onOpen: (id: string) => void }) {
  const video = project.previewUrl || (!project.coverUrl ? project.latestOutputUrl : null);
  return <button className={`sf-project-card sf-${project.statusTone}`} onClick={() => onOpen(project.id)}>
    <div className="sf-project-cover" data-has-cover={project.coverUrl || video ? "true" : "false"}>
      {project.coverUrl ? <img src={project.coverUrl} alt=""/> : video ? <video src={`${video}${video.includes("?")?"&":"?"}disposition=inline`} muted playsInline preload="metadata" aria-hidden="true"/> : <div className="sf-no-preview"><span>{familyLabel(project.family)}</span><strong>No production preview yet</strong></div>}
      {project.coverUrl || video ? <span>{familyLabel(project.family)}</span> : null}
    </div>
    <div className="sf-project-copy"><div className="sf-status-row"><span className="sf-status">{project.statusLabel}</span><time dateTime={project.updatedAt}>{new Date(project.updatedAt).toLocaleDateString()}</time></div><h2>{project.title}</h2><p>{project.videoType}{project.durationSeconds ? ` · ${project.durationSeconds}s` : ""}{project.aspectRatio ? ` · ${project.aspectRatio}` : ""}{project.episodeOrdinal ? ` · Episode ${project.episodeOrdinal}` : ""}</p></div>
  </button>;
}
