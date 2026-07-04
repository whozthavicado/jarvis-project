import { ShieldCheck } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function EncryptionSecurity() {
  const { security } = useDashboardData();

  return (
    <Panel className="flex flex-col items-center justify-center text-center">
      <ShieldCheck
        size={32}
        className="mb-2 text-zero-accent drop-shadow-[0_0_10px_rgba(46,155,255,0.6)]"
      />
      <p className="hud-label text-xs text-white">
        {security.protected ? "System Protected" : "System At Risk"}
      </p>
      <p className="hud-label text-[9px] text-zero-accent mt-1">Level {security.level}</p>
      <div className="mt-3 flex items-center gap-2">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            security.encryptionActive ? "bg-zero-accent" : "bg-zero-border"
          }`}
        />
        <span className="hud-label text-[9px] text-zero-text-muted">
          Active Encryption
        </span>
      </div>
    </Panel>
  );
}
