import {
  LayoutDashboard, Cpu, BarChart3, FolderKanban, MessageSquare,
  Workflow, Database, ShieldCheck, Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "System", icon: Cpu, active: false },
  { label: "Analysis", icon: BarChart3, active: false },
  { label: "Projects", icon: FolderKanban, active: false },
  { label: "Communications", icon: MessageSquare, active: false },
  { label: "Automation", icon: Workflow, active: false },
  { label: "Resources", icon: Database, active: false },
  { label: "Security", icon: ShieldCheck, active: false },
  { label: "Configuration", icon: Settings, active: false },
];

export function Sidebar() {
  return (
    <aside className="hidden lg:flex w-[260px] shrink-0 flex-col justify-between border-r border-zero-border bg-zero-surface/40 p-6">
      <div>
        <div className="mb-8">
          <h1 className="text-xl font-bold tracking-widest text-white">Z.E.R.O</h1>
          <p className="hud-label text-[10px] text-zero-text-muted mt-1">
            Zero Enhanced Reasoning Organization
          </p>
        </div>

        <div className="mb-8 flex items-center gap-3 rounded-zero border border-zero-border p-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zero-accent/20 text-zero-accent font-bold">
            B
          </div>
          <div>
            <p className="text-sm font-semibold text-white">bernumeno</p>
            <p className="hud-label text-[9px] text-zero-text-muted">
              innovation · strategy · impact
            </p>
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map(({ label, icon: Icon, active }) => (
            <div
              key={label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                active
                  ? "bg-zero-accent/15 text-zero-accent"
                  : "text-zero-text-muted hover:text-white"
              }`}
            >
              <Icon size={16} />
              <span>{label}</span>
            </div>
          ))}
        </nav>
      </div>

      <div className="border-t border-zero-border pt-4">
        <p className="hud-label text-[9px] text-zero-text-muted">Z.E.R.O v1.0.0</p>
        <p className="hud-label text-[10px] text-zero-accent mt-1">Core Active</p>
        <svg viewBox="0 0 100 24" className="mt-2 h-6 w-full text-zero-accent">
          <polyline
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            points="0,16 10,10 20,18 30,6 40,14 50,8 60,16 70,4 80,12 90,8 100,14"
          />
        </svg>
        <p className="hud-label text-[9px] text-zero-text-muted mt-2">
          System Status: <span className="text-zero-accent">Optimal</span>
        </p>
      </div>
    </aside>
  );
}
