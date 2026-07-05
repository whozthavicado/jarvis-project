"use client";

import dynamic from "next/dynamic";

// Client-only: positions come from Math.cos/sin, which aren't guaranteed
// bit-identical between server (Node) and browser JS engines, causing a
// hydration mismatch if server-rendered.
export const CoreVisualizerClient = dynamic(
  () => import("./CoreVisualizer").then((m) => m.CoreVisualizer),
  { ssr: false, loading: () => <div className="h-[340px] w-full" /> }
);
