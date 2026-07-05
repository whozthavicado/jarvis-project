"use client";

import { useZeroBackend } from "@/hooks/useZeroBackend";

const STATUS_LABEL: Record<string, string> = {
  idle: "Intelligent Core Active",
  thinking: "Z.E.R.O is thinking…",
  speaking: "Z.E.R.O is speaking…",
};

const STATUS_DOT_CLASS: Record<string, string> = {
  idle: "bg-zero-accent",
  thinking: "bg-amber-400",
  speaking: "bg-emerald-400",
};

export function CenterHeader() {
  const { coreStatus } = useZeroBackend();
  const dotClass = STATUS_DOT_CLASS[coreStatus] ?? STATUS_DOT_CLASS.idle;
  const label = STATUS_LABEL[coreStatus] ?? STATUS_LABEL.idle;

  return (
    <div className="flex items-start justify-between">
      <div>
        <h1 className="text-4xl font-bold text-white">Z.E.R.O</h1>
        <p className="hud-label text-xs text-zero-text-muted mt-1">
          Your System. Your Vision. Our Future.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${dotClass}`}
            />
            <span className={`relative inline-flex h-2 w-2 rounded-full ${dotClass}`} />
          </span>
          <span className="hud-label text-[10px] text-zero-accent">{label}</span>
        </div>
      </div>

      <div className="text-right">
        <p className="hud-label text-xs text-white">Global Priority</p>
        <p className="hud-label text-[9px] text-zero-text-muted mt-1">
          Innovate · Connect · Scale
        </p>
        <div className="mt-2 flex justify-end gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className={`h-1.5 w-1.5 rounded-full ${i === 0 ? "bg-zero-accent" : "bg-zero-border"}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
