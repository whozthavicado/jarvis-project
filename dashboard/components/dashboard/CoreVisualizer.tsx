"use client";

import { motion } from "framer-motion";

const RING_RADII = [60, 95, 130, 165];
const NODE_ANGLES = [15, 55, 95, 140, 190, 230, 270, 310, 340];

export function CoreVisualizer() {
  const center = 200;

  return (
    <div className="flex items-center justify-center py-6">
      <svg viewBox="0 0 400 400" className="h-[340px] w-[340px]">
        <defs>
          <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#5AC8FF" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#5AC8FF" stopOpacity="0" />
          </radialGradient>
        </defs>

        <circle cx={center} cy={center} r={180} fill="url(#core-glow)" />

        {RING_RADII.map((r) => (
          <circle
            key={r}
            cx={center}
            cy={center}
            r={r}
            fill="none"
            stroke="#2E9BFF"
            strokeOpacity={0.25}
            strokeWidth={1}
          />
        ))}

        {NODE_ANGLES.map((deg) => {
          const rad = (deg * Math.PI) / 180;
          const x2 = center + Math.cos(rad) * 165;
          const y2 = center + Math.sin(rad) * 165;
          return (
            <line
              key={deg}
              x1={center}
              y1={center}
              x2={x2}
              y2={y2}
              stroke="#2E9BFF"
              strokeOpacity={0.15}
              strokeWidth={1}
            />
          );
        })}

        {NODE_ANGLES.map((deg, i) => {
          const r = RING_RADII[i % RING_RADII.length];
          const rad = (deg * Math.PI) / 180;
          const x = center + Math.cos(rad) * r;
          const y = center + Math.sin(rad) * r;
          return (
            <motion.circle
              key={`node-${deg}`}
              cx={x}
              cy={y}
              r={3}
              fill="#5AC8FF"
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 2.5, repeat: Infinity, delay: i * 0.2 }}
            />
          );
        })}

        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "200px 200px" }}
        >
          <circle
            cx={center}
            cy={center}
            r={110}
            fill="none"
            stroke="#5AC8FF"
            strokeOpacity={0.4}
            strokeDasharray="4 10"
            strokeWidth={1.5}
          />
        </motion.g>
      </svg>

      <div className="absolute flex flex-col items-center text-center">
        <p className="text-lg font-bold tracking-widest text-white">Z.E.R.O</p>
        <p className="hud-label text-[10px] text-zero-accent">Active</p>
      </div>
    </div>
  );
}
