import { useDashboardData } from "@/hooks/useDashboardData";

export function SyncProgressBar() {
  const { syncPercent } = useDashboardData();

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label text-[10px] text-zero-text-muted">
          Global Synchronization
        </span>
        <span className="text-xs font-semibold text-zero-accent">{syncPercent}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-zero-border">
        <div
          className="h-1.5 rounded-full bg-zero-accent"
          style={{ width: `${syncPercent}%` }}
        />
      </div>
    </div>
  );
}
