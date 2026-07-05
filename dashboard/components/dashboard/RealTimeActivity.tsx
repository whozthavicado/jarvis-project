"use client";

import { useMemo, useState } from "react";
import { Bot, Server, FolderKanban, User } from "lucide-react";
import { useZeroBackend } from "@/hooks/useZeroBackend";
import { Panel } from "./ui/Panel";
import { Modal } from "./ui/Modal";
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

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  const Icon = ACTOR_ICONS[entry.actor];
  return (
    <li className="flex items-start gap-3">
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
}

export function RealTimeActivity() {
  const { activityFeed } = useZeroBackend();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(
    () =>
      activityFeed.filter((e) => e.description.toLowerCase().includes(filter.toLowerCase())),
    [activityFeed, filter]
  );

  return (
    <Panel label="Real-Time Activity">
      <ul className="space-y-3">
        {activityFeed.map((entry) => (
          <ActivityRow key={entry.id} entry={entry} />
        ))}
      </ul>
      <button
        onClick={() => setOpen(true)}
        className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white"
      >
        View All Activity
      </button>

      {open && (
        <Modal title="All Activity" onClose={() => setOpen(false)}>
          <input
            autoFocus
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter activity..."
            className="mb-3 w-full rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
          />
          <ul className="max-h-80 space-y-3 overflow-y-auto">
            {filtered.map((entry) => (
              <ActivityRow key={entry.id} entry={entry} />
            ))}
            {filtered.length === 0 && (
              <li className="hud-label text-[10px] text-zero-text-muted">No matches</li>
            )}
          </ul>
        </Modal>
      )}
    </Panel>
  );
}
