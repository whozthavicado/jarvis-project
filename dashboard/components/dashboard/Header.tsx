"use client";

import { useEffect, useState } from "react";
import { Bell, Search, Settings } from "lucide-react";

export function Header() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const time = now
    ? now.toLocaleTimeString("en-US", { hour12: false })
    : "--:--:--";
  const date = now
    ? now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
    : "";

  return (
    <header className="flex items-center justify-between border-b border-zero-border px-8 py-4">
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
          <Search size={16} className="hover:text-white" />
          <Bell size={16} className="hover:text-white" />
          <Settings size={16} className="hover:text-white" />
        </div>
      </div>
    </header>
  );
}
