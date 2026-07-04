import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function ExecutiveSummary() {
  const { executiveSummary } = useDashboardData();
  const { activeProjects, tasksInProgress, tasksProgressPercent, estimatedImpactPercent, impactHistory } =
    executiveSummary;

  const circumference = 2 * Math.PI * 18;
  const dash = (tasksProgressPercent / 100) * circumference;
  const maxImpact = Math.max(...impactHistory);

  return (
    <Panel label="Executive Summary">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="hud-label text-[9px] text-zero-text-muted">Active Projects</p>
          <p className="text-2xl font-bold text-white">{activeProjects}</p>
        </div>

        <div className="flex items-center gap-2">
          <svg viewBox="0 0 44 44" className="h-11 w-11 -rotate-90">
            <circle cx="22" cy="22" r="18" fill="none" stroke="#0D1420" strokeWidth="5" />
            <circle
              cx="22"
              cy="22"
              r="18"
              fill="none"
              stroke="#2E9BFF"
              strokeWidth="5"
              strokeDasharray={`${dash} ${circumference - dash}`}
            />
          </svg>
          <div>
            <p className="hud-label text-[9px] text-zero-text-muted">Tasks</p>
            <p className="text-sm font-semibold text-white">{tasksInProgress}</p>
          </div>
        </div>

        <div className="col-span-2">
          <div className="flex items-baseline justify-between mb-1">
            <span className="hud-label text-[9px] text-zero-text-muted">Estimated Impact</span>
            <span className="text-sm font-semibold text-zero-accent">
              {estimatedImpactPercent}%
            </span>
          </div>
          <div className="flex h-8 items-end gap-1">
            {impactHistory.map((v, i) => (
              <div
                key={i}
                className="flex-1 rounded-t bg-zero-accent/60"
                style={{ height: `${(v / maxImpact) * 100}%` }}
              />
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}
