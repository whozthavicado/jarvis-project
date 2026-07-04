import { Send } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function AssistantWidget() {
  const { userName } = useDashboardData();

  return (
    <Panel label="Z.E.R.O Assistant">
      <div className="flex items-center gap-3 mb-3">
        <span className="relative flex h-10 w-10 items-center justify-center rounded-full bg-zero-accent/20 text-zero-accent shadow-[0_0_16px_rgba(46,155,255,0.5)]">
          Z
        </span>
        <div>
          <p className="text-sm text-white">How can I help you today, {userName}?</p>
          <p className="hud-label text-[9px] text-zero-text-muted">
            Ask about systems, projects, or resources
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 rounded-lg border border-zero-border px-3 py-2">
        <input
          type="text"
          placeholder="Type a command..."
          className="flex-1 bg-transparent text-xs text-white placeholder:text-zero-text-muted outline-none"
        />
        <Send size={14} className="text-zero-accent" />
      </div>
    </Panel>
  );
}
