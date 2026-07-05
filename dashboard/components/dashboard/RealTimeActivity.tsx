"use client";

import { Bot, Server, FolderKanban, User } from "lucide-react";
import { useZeroBackend } from "@/hooks/useZeroBackend";
import { Panel } from "./ui/Panel";
import { ActivityEntry } from "@/lib/types";

const ACTOR_ICONS: Record<ActivityEntry["actor"], typeof Bot> = {
  "Z.E.R.O": Bot,
  System: Server,
  Project: FolderKanban,
  User: User,
};

function relativeTime(minutesAgo: number): string {
  if (minutesAgo < 60) return `${minutesAgo} mins ago`;
  const hours = Math.floor(minutesAgo / 60);
  return `${hours}h ago`;
}

export function RealTimeActivity() {
  const { activityFeed } = useZeroBackend();

  return (
    <Panel label="Real-Time Activity">
      <ul className="space-y-3">
        {activityFeed.map((entry) => {
          const Icon = ACTOR_ICONS[entry.actor];
          return (
            <li key={entry.id} className="flex items-start gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zero-accent/15 text-zero-accent">
                <Icon size={14} />
              </span>
              <div>
                <p className="text-xs text-white">{entry.description}</p>
                <p className="hud-label text-[9px] text-zero-text-muted">
                  {entry.actor} · {relativeTime(entry.minutesAgo)}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <button className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white">
        View All Activity
      </button>
    </Panel>
  );
}
