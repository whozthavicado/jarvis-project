"use client";

import { useEffect, useMemo, useState } from "react";
import { Bell, Search, Settings } from "lucide-react";
import { useZeroBackend } from "@/hooks/useZeroBackend";
import { useSettings } from "@/hooks/useSettings";
import { useNavigation, SECTION_IDS } from "@/hooks/useNavigation";

const ACTOR_TO_SECTION: Record<string, keyof typeof SECTION_IDS> = {
  Project: "projects",
  System: "system",
};

export function Header() {
  const [now, setNow] = useState<Date | null>(null);
  const { activityFeed } = useZeroBackend();
  const { open: openSettings } = useSettings();
  const { goTo } = useNavigation();

  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return activityFeed.filter((e) => e.description.toLowerCase().includes(q)).slice(0, 8);
  }, [query, activityFeed]);

  const time = now
    ? now.toLocaleTimeString("en-US", { hour12: false })
    : "--:--:--";
  const date = now
    ? now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
    : "";

  return (
    <header className="relative flex items-center justify-between border-b border-zero-border px-8 py-4">
      <div className="w-32" />
      <h2 className="hud-label text-sm tracking-[0.3em] text-white">
        Z.E.R.O Central System
      </h2>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm font-semibold text-zero-accent tabular-nums">{time}</p>
          <p className="hud-label text-[9px] text-zero-text-muted">{date}</p>
        </div>
        <div className="flex items-center gap-3 text-zero-text-muted">
          <button
            aria-label="Search"
            onClick={() => {
              setSearchOpen((v) => !v);
              setNotifOpen(false);
            }}
            className="hover:text-white"
          >
            <Search size={16} />
          </button>
          <button
            aria-label="Notifications"
            onClick={() => {
              setNotifOpen((v) => !v);
              setSearchOpen(false);
            }}
            className="relative hover:text-white"
          >
            <Bell size={16} />
            {activityFeed.length > 0 && (
              <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-zero-accent" />
            )}
          </button>
          <button aria-label="Settings" onClick={openSettings} className="hover:text-white">
            <Settings size={16} />
          </button>
        </div>
      </div>

      {searchOpen && (
        <div className="absolute right-8 top-16 z-40 w-80 rounded-zero border border-zero-border bg-zero-surface p-4 shadow-2xl">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search activity..."
            className="mb-2 w-full rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
          />
          <ul className="max-h-64 space-y-2 overflow-y-auto">
            {query.trim() && results.length === 0 && (
              <li className="hud-label text-[10px] text-zero-text-muted">No matches</li>
            )}
            {results.map((r) => (
              <li key={r.id} className="text-xs text-white">
                <button
                  onClick={() => {
                    const section = ACTOR_TO_SECTION[r.actor] ?? "communications";
                    goTo(section);
                    setSearchOpen(false);
                  }}
                  className="text-left hover:text-zero-accent"
                >
                  {r.description}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {notifOpen && (
        <div className="absolute right-8 top-16 z-40 w-80 rounded-zero border border-zero-border bg-zero-surface p-4 shadow-2xl">
          <p className="hud-label mb-2 text-[9px] text-zero-text-muted">Recent Activity</p>
          <ul className="max-h-64 space-y-2 overflow-y-auto">
            {activityFeed.length === 0 && (
              <li className="hud-label text-[10px] text-zero-text-muted">Nothing yet</li>
            )}
            {activityFeed.slice(0, 8).map((entry) => (
              <li key={entry.id} className="text-xs text-white">
                <span className="text-zero-accent">{entry.actor}</span>: {entry.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
}
