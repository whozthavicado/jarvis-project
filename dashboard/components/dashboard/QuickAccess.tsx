import { Star, LayoutDashboard, BarChart3, Settings, Plus } from "lucide-react";
import { Panel } from "./ui/Panel";

const ITEMS = [
  { icon: Star, label: "Favorites" },
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: BarChart3, label: "Analytics" },
  { icon: Settings, label: "Config" },
  { icon: Plus, label: "Add" },
];

export function QuickAccess() {
  return (
    <Panel label="Quick Access">
      <div className="flex gap-2">
        {ITEMS.map(({ icon: Icon, label }) => (
          <button
            key={label}
            aria-label={label}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-zero-border text-zero-text-muted hover:text-zero-accent"
          >
            <Icon size={16} />
          </button>
        ))}
      </div>
    </Panel>
  );
}
