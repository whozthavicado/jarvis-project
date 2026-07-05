"use client";

import { useMemo, useState } from "react";
import { Brain, GraduationCap, LineChart, Cog, ShieldCheck, Star } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useFavorites } from "@/hooks/useFavorites";
import { Panel } from "./ui/Panel";
import { Modal } from "./ui/Modal";
import { ActiveModule } from "@/lib/types";

const ICONS: Record<ActiveModule["icon"], typeof Brain> = {
  brain: Brain,
  "graduation-cap": GraduationCap,
  "line-chart": LineChart,
  cog: Cog,
  "shield-check": ShieldCheck,
};

function favoriteId(moduleId: string): string {
  return `module:${moduleId}`;
}

function ModuleRow({ mod }: { mod: ActiveModule }) {
  const Icon = ICONS[mod.icon];
  const { isFavorite, toggle } = useFavorites();
  const favId = favoriteId(mod.id);

  return (
    <li className="flex items-center justify-between">
      <span className="flex items-center gap-3 text-sm text-white">
        <Icon size={16} className="text-zero-accent" />
        {mod.name}
      </span>
      <span className="flex items-center gap-2">
        <span className="hud-label text-[9px] text-zero-accent">{mod.status}</span>
        <button
          aria-label={isFavorite(favId) ? "Unfavorite" : "Favorite"}
          onClick={() => toggle(favId)}
          className={isFavorite(favId) ? "text-zero-accent" : "text-zero-text-muted hover:text-white"}
        >
          <Star size={14} fill={isFavorite(favId) ? "currentColor" : "none"} />
        </button>
      </span>
    </li>
  );
}

export function ActiveModules() {
  const { activeModules } = useDashboardData();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(
    () => activeModules.filter((m) => m.name.toLowerCase().includes(filter.toLowerCase())),
    [activeModules, filter]
  );

  return (
    <Panel label="Active Modules">
      <ul className="space-y-3">
        {activeModules.map((mod) => (
          <ModuleRow key={mod.id} mod={mod} />
        ))}
      </ul>
      <button
        onClick={() => setOpen(true)}
        className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white"
      >
        View All Modules
      </button>

      {open && (
        <Modal title="All Modules" onClose={() => setOpen(false)}>
          <input
            autoFocus
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter modules..."
            className="mb-3 w-full rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
          />
          <ul className="max-h-80 space-y-3 overflow-y-auto">
            {filtered.map((mod) => (
              <ModuleRow key={mod.id} mod={mod} />
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
