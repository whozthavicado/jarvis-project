import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function KeyProjects() {
  const { keyProjects } = useDashboardData();

  return (
    <Panel label="Key Projects">
      <ul className="space-y-4">
        {keyProjects.map((project) => (
          <li key={project.id}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-white">{project.name}</span>
              <span className="hud-label text-[9px] text-zero-text-muted">{project.phase}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-zero-border">
              <div
                className="h-1.5 rounded-full bg-zero-accent"
                style={{ width: `${project.progress}%` }}
              />
            </div>
            <span className="text-[10px] text-zero-text-muted">{project.progress}%</span>
          </li>
        ))}
      </ul>
      <button className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white">
        View All Projects
      </button>
    </Panel>
  );
}
