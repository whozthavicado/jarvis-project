"use client";

import { useMemo, useState } from "react";
import { Star } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useFavorites } from "@/hooks/useFavorites";
import { Panel } from "./ui/Panel";
import { Modal } from "./ui/Modal";
import { KeyProject } from "@/lib/types";

function favoriteId(projectId: string): string {
  return `project:${projectId}`;
}

function ProjectRow({ project }: { project: KeyProject }) {
  const { isFavorite, toggle } = useFavorites();
  const favId = favoriteId(project.id);

  return (
    <li>
      <div className="flex items-center justify-between mb-1">
        <span className="flex items-center gap-2 text-sm text-white">
          {project.name}
          <button
            aria-label={isFavorite(favId) ? "Unfavorite" : "Favorite"}
            onClick={() => toggle(favId)}
            className={isFavorite(favId) ? "text-zero-accent" : "text-zero-text-muted hover:text-white"}
          >
            <Star size={12} fill={isFavorite(favId) ? "currentColor" : "none"} />
          </button>
        </span>
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
  );
}

export function KeyProjects() {
  const { keyProjects } = useDashboardData();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(
    () => keyProjects.filter((p) => p.name.toLowerCase().includes(filter.toLowerCase())),
    [keyProjects, filter]
  );

  return (
    <Panel label="Key Projects">
      <ul className="space-y-4">
        {keyProjects.map((project) => (
          <ProjectRow key={project.id} project={project} />
        ))}
      </ul>
      <button
        onClick={() => setOpen(true)}
        className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white"
      >
        View All Projects
      </button>

      {open && (
        <Modal title="All Projects" onClose={() => setOpen(false)}>
          <input
            autoFocus
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter projects..."
            className="mb-3 w-full rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
          />
          <ul className="max-h-80 space-y-4 overflow-y-auto">
            {filtered.map((project) => (
              <ProjectRow key={project.id} project={project} />
            ))}
            {filtered.length === 0 && (
              <li className="hud-label text-[10px] text-zero-text-muted">No matches</li>
            )}
          </ul>
        </Modal>
      )}
    </Panel>
  );
}
