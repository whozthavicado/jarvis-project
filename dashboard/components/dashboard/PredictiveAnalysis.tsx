import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function PredictiveAnalysis() {
  const { predictiveTrend, predictiveProjectionPercent } = useDashboardData();

  const values = predictiveTrend.map((p) => p.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const points = predictiveTrend
    .map((p, i) => {
      const x = (i / (predictiveTrend.length - 1)) * 100;
      const y = 40 - ((p.value - min) / range) * 40;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <Panel label="Predictive Analysis">
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label text-[9px] text-zero-text-muted">30-Day Trend</span>
        <span className="text-xs font-semibold text-zero-accent">
          +{predictiveProjectionPercent}%
        </span>
      </div>
      <svg viewBox="0 0 100 40" className="h-16 w-full text-zero-accent">
        <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={points} />
      </svg>
    </Panel>
  );
}
