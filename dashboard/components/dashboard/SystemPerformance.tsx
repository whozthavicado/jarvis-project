import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";
import { SystemMetric } from "@/lib/types";

function Sparkline({ history }: { history: SystemMetric["history"] }) {
  const max = Math.max(...history.map((p) => p.v));
  const min = Math.min(...history.map((p) => p.v));
  const range = max - min || 1;
  const points = history
    .map((p, i) => {
      const x = (i / (history.length - 1)) * 100;
      const y = 20 - ((p.v - min) / range) * 20;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 20" className="h-5 w-full text-zero-accent">
      <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={points} />
    </svg>
  );
}

export function SystemPerformance() {
  const { systemMetrics } = useDashboardData();

  return (
    <Panel label="System Performance">
      <div className="grid grid-cols-2 gap-4">
        {systemMetrics.map((metric) => (
          <div key={metric.id}>
            <div className="flex items-baseline justify-between">
              <span className="hud-label text-[9px] text-zero-text-muted">{metric.label}</span>
              <span className="text-sm font-semibold text-white">{metric.value}%</span>
            </div>
            <Sparkline history={metric.history} />
          </div>
        ))}
      </div>
    </Panel>
  );
}
