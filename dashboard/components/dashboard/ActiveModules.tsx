import { Brain, GraduationCap, LineChart, Cog, ShieldCheck } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";
import { ActiveModule } from "@/lib/types";

const ICONS: Record<ActiveModule["icon"], typeof Brain> = {
  brain: Brain,
  "graduation-cap": GraduationCap,
  "line-chart": LineChart,
  cog: Cog,
  "shield-check": ShieldCheck,
};

export function ActiveModules() {
  const { activeModules } = useDashboardData();

  return (
    <Panel label="Active Modules">
      <ul className="space-y-3">
        {activeModules.map((mod) => {
          const Icon = ICONS[mod.icon];
          return (
            <li key={mod.id} className="flex items-center justify-between">
              <span className="flex items-center gap-3 text-sm text-white">
                <Icon size={16} className="text-zero-accent" />
                {mod.name}
              </span>
              <span className="hud-label text-[9px] text-zero-accent">{mod.status}</span>
            </li>
          );
        })}
      </ul>
      <button className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white">
        View All Modules
      </button>
    </Panel>
  );
}
