import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

const RING_COLORS = ["#2E9BFF", "#5AC8FF", "#93C5FD", "#1E3A8A"];

export function ResourceDistribution() {
  const { resourceDistribution, resourceTotalPercent } = useDashboardData();

  const circumference = 2 * Math.PI * 40;
  let offsetAccum = 0;

  return (
    <Panel label="Resource Distribution">
      <div className="flex items-center gap-6">
        <svg viewBox="0 0 100 100" className="h-24 w-24 -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#0D1420" strokeWidth="10" />
          {resourceDistribution.map((cat, i) => {
            const dash = (cat.percent / 100) * circumference;
            const circle = (
              <circle
                key={cat.id}
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke={RING_COLORS[i % RING_COLORS.length]}
                strokeWidth="10"
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offsetAccum}
              />
            );
            offsetAccum += dash;
            return circle;
          })}
        </svg>
        <div className="flex-1">
          <p className="text-lg font-bold text-white mb-2">{resourceTotalPercent}%</p>
          <ul className="space-y-1">
            {resourceDistribution.map((cat, i) => (
              <li key={cat.id} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-zero-text-muted">
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ backgroundColor: RING_COLORS[i % RING_COLORS.length] }}
                  />
                  {cat.label}
                </span>
                <span className="text-white">{cat.percent}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
