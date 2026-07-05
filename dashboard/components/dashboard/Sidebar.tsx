"use client";

import {
  LayoutDashboard, Cpu, BarChart3, FolderKanban, MessageSquare,
  Workflow, Database, ShieldCheck, Settings,
} from "lucide-react";
import { useNavigation, SectionKey } from "@/hooks/useNavigation";
import { useSettings } from "@/hooks/useSettings";

const NAV_ITEMS: { label: string; icon: typeof LayoutDashboard; section?: SectionKey }[] = [
  { label: "Dashboard", icon: LayoutDashboard, section: "dashboard" },
  { label: "System", icon: Cpu, section: "system" },
  { label: "Analysis", icon: BarChart3, section: "analysis" },
  { label: "Projects", icon: FolderKanban, section: "projects" },
  { label: "Communications", icon: MessageSquare, section: "communications" },
  { label: "Automation", icon: Workflow, section: "automation" },
  { label: "Resources", icon: Database, section: "resources" },
  { label: "Security", icon: ShieldCheck, section: "security" },
  { label: "Configuration", icon: Settings }, // no page section -- opens Settings instead
];

export function Sidebar() {
  const { activeSection, goTo } = useNavigation();
  const { open: openSettings } = useSettings();

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
          {NAV_ITEMS.map(({ label, icon: Icon, section }) => {
            const active = section != null && section === activeSection;
            return (
              <button
                key={label}
                onClick={() => (section ? goTo(section) : openSettings())}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-left ${
                  active
                    ? "bg-zero-accent/15 text-zero-accent"
                    : "text-zero-text-muted hover:text-white"
                }`}
              >
                <Icon size={16} />
                <span>{label}</span>
              </button>
            );
          })}
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
