# Z.E.R.O Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Z.E.R.O Central System dashboard — a Next.js/TypeScript/Tailwind UI replicating the reference HUD layout (sidebar, header, central core visualizer, side panels, bottom widget row), driven by static mock data behind a swappable hook.

**Architecture:** A new self-contained Next.js 14 App Router project at `dashboard/` (sibling to `jarvis/`, no code coupling). One `DashboardData` type + one static mock object + one `useDashboardData()` hook is the single seam between presentation and data; every panel is its own component under `dashboard/components/dashboard/`, composed by `app/page.tsx` into the 3-zone grid plus bottom row described in the spec.

**Tech Stack:** Next.js 14 (App Router), TypeScript, TailwindCSS, `lucide-react`, `framer-motion`. No 3D library — the core visualizer is SVG + framer-motion per the approved design.

**Spec:** `docs/superpowers/specs/2026-07-04-zero-dashboard-design.md`

## Global Constraints

- All code lives under `dashboard/`, npm-managed, independent of the Python `jarvis/` package.
- No hardcoded hex colors inside components — every color/radius comes from the `zero.*` Tailwind theme tokens defined in Task 2.
- Every panel is its own file under `dashboard/components/dashboard/`.
- All presentational components consume data only via `useDashboardData()` — never import `lib/mock-data.ts` directly.
- Uppercase for HUD section labels (via the shared `.hud-label` class), values/proper nouns cased as authored in the data.
- No automated test framework for this pass — verification per task is `npx tsc --noEmit` (from `dashboard/`), plus one final `npm run build` + dev-server visual check against the spec (Task 24).
- No real backend/API/WebSocket wiring, no auth, no routes beyond the single dashboard page, no functional assistant chat handler.

---

### Task 1: Scaffold the Next.js project

**Files:**
- Create: `dashboard/` (via `create-next-app`)
- Modify: `dashboard/package.json` (add `framer-motion`, `lucide-react`)

**Interfaces:**
- Produces: a runnable Next.js App Router project at `dashboard/` with TypeScript + Tailwind already configured by the scaffolder.

- [ ] **Step 1: Scaffold the app**

Run from the repo root (`/Users/bernumeno/jarvis-project`):

```bash
npx create-next-app@latest dashboard --typescript --tailwind --app --no-src-dir --eslint --import-alias "@/*"
```

Answer prompts with defaults if asked interactively (App Router: yes, `src/` dir: no — already passed as flags).

- [ ] **Step 2: Install extra dependencies**

```bash
cd dashboard && npm install framer-motion lucide-react
```

- [ ] **Step 3: Verify the scaffold builds**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors (clean scaffold).

- [ ] **Step 4: Commit**

```bash
cd /Users/bernumeno/jarvis-project
git add dashboard
git commit -m "Scaffold Z.E.R.O dashboard Next.js app"
```

---

### Task 2: Design tokens (Tailwind theme + global styles)

**Files:**
- Modify: `dashboard/tailwind.config.ts`
- Modify: `dashboard/app/globals.css`

**Interfaces:**
- Produces: Tailwind color tokens `zero.bgFrom`, `zero.bgTo`, `zero.accent`, `zero.accentLight`, `zero.surface`, `zero.border`, `zero.text.primary`, `zero.text.muted`; radius token `zero.card`; a global `.hud-label` utility class. Every later task's components reference these exact token names.

- [ ] **Step 1: Extend the Tailwind theme**

Edit `dashboard/tailwind.config.ts` so the `theme.extend` block includes:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        zero: {
          bgFrom: "#05070C",
          bgTo: "#0A0E16",
          accent: "#2E9BFF",
          accentLight: "#5AC8FF",
          surface: "#0D1420",
          border: "rgba(255,255,255,0.08)",
          text: {
            primary: "#FFFFFF",
            muted: "#7C8BA6",
          },
        },
      },
      borderRadius: {
        zero: "18px",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Global background + HUD label utility**

Replace the contents of `dashboard/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    background: linear-gradient(180deg, theme('colors.zero.bgFrom'), theme('colors.zero.bgTo'));
    color: theme('colors.zero.text.primary');
    min-height: 100vh;
  }
}

@layer utilities {
  .hud-label {
    @apply uppercase tracking-widest font-semibold;
  }
}
```

- [ ] **Step 3: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/tailwind.config.ts dashboard/app/globals.css
git commit -m "Add Z.E.R.O design tokens to Tailwind config"
```

---

### Task 3: Domain types, mock data, and data hook

**Files:**
- Create: `dashboard/lib/types.ts`
- Create: `dashboard/lib/mock-data.ts`
- Create: `dashboard/hooks/useDashboardData.ts`

**Interfaces:**
- Produces: `DashboardData` interface and every nested type below; `useDashboardData(): DashboardData`. Every component task from here on imports types from `@/lib/types` and data via `@/hooks/useDashboardData`.

- [ ] **Step 1: Write the types**

Create `dashboard/lib/types.ts`:

```ts
export interface SparklinePoint {
  t: number;
  v: number;
}

export interface SystemMetric {
  id: string;
  label: string;
  value: number; // percent 0-100
  history: SparklinePoint[];
}

export interface PredictivePoint {
  day: number;
  value: number;
}

export interface ResourceCategory {
  id: string;
  label: string;
  percent: number;
  colorClass: string; // Tailwind background class, e.g. "bg-zero-accent"
}

export interface ActiveModule {
  id: string;
  name: string;
  icon: "brain" | "graduation-cap" | "line-chart" | "cog" | "shield-check";
  status: "active" | "idle";
}

export interface KeyProject {
  id: string;
  name: string;
  phase: "executing" | "planning";
  progress: number; // 0-100
}

export interface ExecutiveSummary {
  activeProjects: number;
  tasksInProgress: number;
  tasksProgressPercent: number;
  estimatedImpactPercent: number;
  impactHistory: number[];
}

export interface ActivityEntry {
  id: string;
  actor: "Z.E.R.O" | "System" | "Project" | "User";
  description: string;
  minutesAgo: number;
}

export interface ConnectivityNode {
  x: number; // 0-100, percent of map width
  y: number; // 0-100, percent of map height
}

export interface SecurityStatus {
  level: number;
  encryptionActive: boolean;
  protected: boolean;
}

export interface DashboardData {
  userName: string;
  syncPercent: number;
  systemMetrics: SystemMetric[];
  predictiveTrend: PredictivePoint[];
  predictiveProjectionPercent: number;
  resourceDistribution: ResourceCategory[];
  resourceTotalPercent: number;
  activeModules: ActiveModule[];
  keyProjects: KeyProject[];
  executiveSummary: ExecutiveSummary;
  activityFeed: ActivityEntry[];
  quote: { text: string; author: string };
  connectivityNodes: ConnectivityNode[];
  security: SecurityStatus;
}
```

- [ ] **Step 2: Write the mock data**

Create `dashboard/lib/mock-data.ts`:

```ts
import { DashboardData } from "./types";

function sparkline(base: number, spread: number): { t: number; v: number }[] {
  return Array.from({ length: 12 }, (_, i) => ({
    t: i,
    v: Math.max(0, Math.min(100, base + Math.sin(i / 1.5) * spread)),
  }));
}

export const mockDashboardData: DashboardData = {
  userName: "Bernumeno",
  syncPercent: 89,
  systemMetrics: [
    { id: "cpu", label: "CPU", value: 42, history: sparkline(42, 8) },
    { id: "memory", label: "Memory", value: 61, history: sparkline(61, 6) },
    { id: "network", label: "Network", value: 34, history: sparkline(34, 12) },
    { id: "storage", label: "Storage", value: 77, history: sparkline(77, 3) },
  ],
  predictiveTrend: Array.from({ length: 30 }, (_, i) => ({
    day: i + 1,
    value: 50 + i * 1.4 + Math.sin(i / 3) * 5,
  })),
  predictiveProjectionPercent: 23,
  resourceDistribution: [
    { id: "compute", label: "Compute", percent: 38, colorClass: "bg-zero-accent" },
    { id: "storage", label: "Storage", percent: 27, colorClass: "bg-zero-accentLight" },
    { id: "network", label: "Network", percent: 21, colorClass: "bg-blue-300" },
    { id: "reserve", label: "Reserve", percent: 14, colorClass: "bg-blue-900" },
  ],
  resourceTotalPercent: 86,
  activeModules: [
    { id: "intelligence", name: "Intelligence", icon: "brain", status: "active" },
    { id: "learning", name: "Learning", icon: "graduation-cap", status: "active" },
    { id: "predictive", name: "Predictive Analysis", icon: "line-chart", status: "active" },
    { id: "automation", name: "Automation", icon: "cog", status: "active" },
    { id: "security", name: "Security", icon: "shield-check", status: "active" },
  ],
  keyProjects: [
    { id: "expansion", name: "Market Expansion", phase: "executing", progress: 68 },
    { id: "platform", name: "Platform Rebuild", phase: "executing", progress: 41 },
    { id: "partnership", name: "Partnership Program", phase: "planning", progress: 12 },
  ],
  executiveSummary: {
    activeProjects: 7,
    tasksInProgress: 19,
    tasksProgressPercent: 64,
    estimatedImpactPercent: 31,
    impactHistory: [12, 18, 15, 22, 27, 24, 31],
  },
  activityFeed: [
    { id: "1", actor: "Z.E.R.O", description: "Completed market trend synthesis", minutesAgo: 2 },
    { id: "2", actor: "Project", description: "Platform Rebuild milestone 3 marked executing", minutesAgo: 14 },
    { id: "3", actor: "System", description: "Nightly backup completed successfully", minutesAgo: 41 },
    { id: "4", actor: "User", description: "Reviewed Partnership Program brief", minutesAgo: 96 },
  ],
  quote: {
    text: "Innovation distinguishes between a leader and a follower.",
    author: "Steve Jobs",
  },
  connectivityNodes: [
    { x: 18, y: 32 }, { x: 24, y: 55 }, { x: 46, y: 28 }, { x: 52, y: 60 },
    { x: 68, y: 22 }, { x: 74, y: 48 }, { x: 82, y: 65 }, { x: 33, y: 70 },
  ],
  security: {
    level: 5,
    encryptionActive: true,
    protected: true,
  },
};
```

- [ ] **Step 3: Write the hook**

Create `dashboard/hooks/useDashboardData.ts`:

```ts
import { DashboardData } from "@/lib/types";
import { mockDashboardData } from "@/lib/mock-data";

export function useDashboardData(): DashboardData {
  return mockDashboardData;
}
```

- [ ] **Step 4: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib dashboard/hooks
git commit -m "Add Z.E.R.O dashboard mock data and data hook"
```

---

### Task 4: Shared UI primitives — Panel and SectionLabel

**Files:**
- Create: `dashboard/components/dashboard/ui/SectionLabel.tsx`
- Create: `dashboard/components/dashboard/ui/Panel.tsx`

**Interfaces:**
- Consumes: nothing (pure presentational).
- Produces: `<SectionLabel>` and `<Panel label? action? className? children>` — every later panel component wraps its content in `<Panel>`.

- [ ] **Step 1: Write SectionLabel**

Create `dashboard/components/dashboard/ui/SectionLabel.tsx`:

```tsx
export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="hud-label text-xs text-zero-text-muted">{children}</span>;
}
```

- [ ] **Step 2: Write Panel**

Create `dashboard/components/dashboard/ui/Panel.tsx`:

```tsx
import { SectionLabel } from "./SectionLabel";

interface PanelProps {
  label?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function Panel({ label, action, className = "", children }: PanelProps) {
  return (
    <div
      className={`rounded-zero border border-zero-border bg-zero-surface/60 backdrop-blur-sm p-5 ${className}`}
    >
      {(label || action) && (
        <div className="flex items-center justify-between mb-4">
          {label && <SectionLabel>{label}</SectionLabel>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/dashboard/ui
git commit -m "Add shared Panel and SectionLabel primitives"
```

---

### Task 5: Sidebar

**Files:**
- Create: `dashboard/components/dashboard/Sidebar.tsx`

**Interfaces:**
- Consumes: nothing (static nav content, no dynamic data needed for this pass).
- Produces: `<Sidebar />`, a fixed-width nav column used by `app/page.tsx` (Task 22).

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/Sidebar.tsx`:

```tsx
import {
  LayoutDashboard, Cpu, BarChart3, FolderKanban, MessageSquare,
  Workflow, Database, ShieldCheck, Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "System", icon: Cpu, active: false },
  { label: "Analysis", icon: BarChart3, active: false },
  { label: "Projects", icon: FolderKanban, active: false },
  { label: "Communications", icon: MessageSquare, active: false },
  { label: "Automation", icon: Workflow, active: false },
  { label: "Resources", icon: Database, active: false },
  { label: "Security", icon: ShieldCheck, active: false },
  { label: "Configuration", icon: Settings, active: false },
];

export function Sidebar() {
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
          {NAV_ITEMS.map(({ label, icon: Icon, active }) => (
            <div
              key={label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                active
                  ? "bg-zero-accent/15 text-zero-accent"
                  : "text-zero-text-muted hover:text-white"
              }`}
            >
              <Icon size={16} />
              <span>{label}</span>
            </div>
          ))}
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/Sidebar.tsx
git commit -m "Add Z.E.R.O dashboard sidebar"
```

---

### Task 6: Header (with live clock)

**Files:**
- Create: `dashboard/components/dashboard/Header.tsx`

**Interfaces:**
- Consumes: nothing external.
- Produces: `<Header />`, a client component (uses `useState`/`useEffect` for the clock).

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/Header.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/Header.tsx
git commit -m "Add Z.E.R.O dashboard header with live clock"
```

---

### Task 7: CenterHeader

**Files:**
- Create: `dashboard/components/dashboard/CenterHeader.tsx`

**Interfaces:**
- Consumes: nothing external (static copy per spec; pagination dots are decorative).
- Produces: `<CenterHeader />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/CenterHeader.tsx`:

```tsx
export function CenterHeader() {
  return (
    <div className="flex items-start justify-between">
      <div>
        <h1 className="text-4xl font-bold text-white">Z.E.R.O</h1>
        <p className="hud-label text-xs text-zero-text-muted mt-1">
          Your System. Your Vision. Our Future.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-zero-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-zero-accent" />
          </span>
          <span className="hud-label text-[10px] text-zero-accent">
            Intelligent Core Active
          </span>
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/CenterHeader.tsx
git commit -m "Add Z.E.R.O dashboard center header"
```

---

### Task 8: CoreVisualizer

**Files:**
- Create: `dashboard/components/dashboard/CoreVisualizer.tsx`

**Interfaces:**
- Consumes: nothing external.
- Produces: `<CoreVisualizer />`, a client component (framer-motion needs `"use client"`).

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/CoreVisualizer.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/CoreVisualizer.tsx
git commit -m "Add Z.E.R.O dashboard core visualizer"
```

---

### Task 9: SyncProgressBar

**Files:**
- Create: `dashboard/components/dashboard/SyncProgressBar.tsx`

**Interfaces:**
- Consumes: `syncPercent: number` from `DashboardData` via `useDashboardData()`.
- Produces: `<SyncProgressBar />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/SyncProgressBar.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";

export function SyncProgressBar() {
  const { syncPercent } = useDashboardData();

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label text-[10px] text-zero-text-muted">
          Global Synchronization
        </span>
        <span className="text-xs font-semibold text-zero-accent">{syncPercent}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-zero-border">
        <div
          className="h-1.5 rounded-full bg-zero-accent"
          style={{ width: `${syncPercent}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/SyncProgressBar.tsx
git commit -m "Add Z.E.R.O dashboard sync progress bar"
```

---

### Task 10: SystemPerformance

**Files:**
- Create: `dashboard/components/dashboard/SystemPerformance.tsx`

**Interfaces:**
- Consumes: `systemMetrics: SystemMetric[]` via `useDashboardData()`; `Panel` from Task 4.
- Produces: `<SystemPerformance />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/SystemPerformance.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";
import { SystemMetric } from "@/lib/types";

function Sparkline({ history }: { history: SystemMetric["history"] }) {
  const max = Math.max(...history.map((p) => p.v));
  const min = Math.min(...history.map((p) => p.v));
  const range = max - min || 1;
  const points = history
    .map((p, i) => {
      const x = (i / (history.length - 1)) * 100;
      const y = 20 - ((p.v - min) / range) * 20;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 20" className="h-5 w-full text-zero-accent">
      <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={points} />
    </svg>
  );
}

export function SystemPerformance() {
  const { systemMetrics } = useDashboardData();

  return (
    <Panel label="System Performance">
      <div className="grid grid-cols-2 gap-4">
        {systemMetrics.map((metric) => (
          <div key={metric.id}>
            <div className="flex items-baseline justify-between">
              <span className="hud-label text-[9px] text-zero-text-muted">{metric.label}</span>
              <span className="text-sm font-semibold text-white">{metric.value}%</span>
            </div>
            <Sparkline history={metric.history} />
          </div>
        ))}
      </div>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/SystemPerformance.tsx
git commit -m "Add Z.E.R.O dashboard system performance panel"
```

---

### Task 11: PredictiveAnalysis

**Files:**
- Create: `dashboard/components/dashboard/PredictiveAnalysis.tsx`

**Interfaces:**
- Consumes: `predictiveTrend: PredictivePoint[]`, `predictiveProjectionPercent: number` via `useDashboardData()`; `Panel`.
- Produces: `<PredictiveAnalysis />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/PredictiveAnalysis.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function PredictiveAnalysis() {
  const { predictiveTrend, predictiveProjectionPercent } = useDashboardData();

  const values = predictiveTrend.map((p) => p.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const points = predictiveTrend
    .map((p, i) => {
      const x = (i / (predictiveTrend.length - 1)) * 100;
      const y = 40 - ((p.value - min) / range) * 40;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <Panel label="Predictive Analysis">
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label text-[9px] text-zero-text-muted">30-Day Trend</span>
        <span className="text-xs font-semibold text-zero-accent">
          +{predictiveProjectionPercent}%
        </span>
      </div>
      <svg viewBox="0 0 100 40" className="h-16 w-full text-zero-accent">
        <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={points} />
      </svg>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/PredictiveAnalysis.tsx
git commit -m "Add Z.E.R.O dashboard predictive analysis panel"
```

---

### Task 12: ResourceDistribution

**Files:**
- Create: `dashboard/components/dashboard/ResourceDistribution.tsx`

**Interfaces:**
- Consumes: `resourceDistribution: ResourceCategory[]`, `resourceTotalPercent: number` via `useDashboardData()`; `Panel`.
- Produces: `<ResourceDistribution />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/ResourceDistribution.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

const RING_COLORS = ["#2E9BFF", "#5AC8FF", "#93C5FD", "#1E3A8A"];

export function ResourceDistribution() {
  const { resourceDistribution, resourceTotalPercent } = useDashboardData();

  const circumference = 2 * Math.PI * 40;
  let offsetAccum = 0;

  return (
    <Panel label="Resource Distribution">
      <div className="flex items-center gap-6">
        <svg viewBox="0 0 100 100" className="h-24 w-24 -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#0D1420" strokeWidth="10" />
          {resourceDistribution.map((cat, i) => {
            const dash = (cat.percent / 100) * circumference;
            const circle = (
              <circle
                key={cat.id}
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke={RING_COLORS[i % RING_COLORS.length]}
                strokeWidth="10"
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offsetAccum}
              />
            );
            offsetAccum += dash;
            return circle;
          })}
        </svg>
        <div className="flex-1">
          <p className="text-lg font-bold text-white mb-2">{resourceTotalPercent}%</p>
          <ul className="space-y-1">
            {resourceDistribution.map((cat, i) => (
              <li key={cat.id} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-zero-text-muted">
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ backgroundColor: RING_COLORS[i % RING_COLORS.length] }}
                  />
                  {cat.label}
                </span>
                <span className="text-white">{cat.percent}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/ResourceDistribution.tsx
git commit -m "Add Z.E.R.O dashboard resource distribution panel"
```

---

### Task 13: ActiveModules

**Files:**
- Create: `dashboard/components/dashboard/ActiveModules.tsx`

**Interfaces:**
- Consumes: `activeModules: ActiveModule[]` via `useDashboardData()`; `Panel`.
- Produces: `<ActiveModules />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/ActiveModules.tsx`:

```tsx
import { Brain, GraduationCap, LineChart, Cog, ShieldCheck } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";
import { ActiveModule } from "@/lib/types";

const ICONS: Record<ActiveModule["icon"], typeof Brain> = {
  brain: Brain,
  "graduation-cap": GraduationCap,
  "line-chart": LineChart,
  cog: Cog,
  "shield-check": ShieldCheck,
};

export function ActiveModules() {
  const { activeModules } = useDashboardData();

  return (
    <Panel label="Active Modules">
      <ul className="space-y-3">
        {activeModules.map((mod) => {
          const Icon = ICONS[mod.icon];
          return (
            <li key={mod.id} className="flex items-center justify-between">
              <span className="flex items-center gap-3 text-sm text-white">
                <Icon size={16} className="text-zero-accent" />
                {mod.name}
              </span>
              <span className="hud-label text-[9px] text-zero-accent">{mod.status}</span>
            </li>
          );
        })}
      </ul>
      <button className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white">
        View All Modules
      </button>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/ActiveModules.tsx
git commit -m "Add Z.E.R.O dashboard active modules panel"
```

---

### Task 14: KeyProjects

**Files:**
- Create: `dashboard/components/dashboard/KeyProjects.tsx`

**Interfaces:**
- Consumes: `keyProjects: KeyProject[]` via `useDashboardData()`; `Panel`.
- Produces: `<KeyProjects />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/KeyProjects.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function KeyProjects() {
  const { keyProjects } = useDashboardData();

  return (
    <Panel label="Key Projects">
      <ul className="space-y-4">
        {keyProjects.map((project) => (
          <li key={project.id}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-white">{project.name}</span>
              <span className="hud-label text-[9px] text-zero-text-muted">{project.phase}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-zero-border">
              <div
                className="h-1.5 rounded-full bg-zero-accent"
                style={{ width: `${project.progress}%` }}
              />
            </div>
            <span className="text-[10px] text-zero-text-muted">{project.progress}%</span>
          </li>
        ))}
      </ul>
      <button className="hud-label mt-4 w-full rounded-lg border border-zero-border py-2 text-[10px] text-zero-text-muted hover:text-white">
        View All Projects
      </button>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/KeyProjects.tsx
git commit -m "Add Z.E.R.O dashboard key projects panel"
```

---

### Task 15: ExecutiveSummary

**Files:**
- Create: `dashboard/components/dashboard/ExecutiveSummary.tsx`

**Interfaces:**
- Consumes: `executiveSummary: ExecutiveSummary` via `useDashboardData()`; `Panel`.
- Produces: `<ExecutiveSummary />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/ExecutiveSummary.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function ExecutiveSummary() {
  const { executiveSummary } = useDashboardData();
  const { activeProjects, tasksInProgress, tasksProgressPercent, estimatedImpactPercent, impactHistory } =
    executiveSummary;

  const circumference = 2 * Math.PI * 18;
  const dash = (tasksProgressPercent / 100) * circumference;
  const maxImpact = Math.max(...impactHistory);

  return (
    <Panel label="Executive Summary">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="hud-label text-[9px] text-zero-text-muted">Active Projects</p>
          <p className="text-2xl font-bold text-white">{activeProjects}</p>
        </div>

        <div className="flex items-center gap-2">
          <svg viewBox="0 0 44 44" className="h-11 w-11 -rotate-90">
            <circle cx="22" cy="22" r="18" fill="none" stroke="#0D1420" strokeWidth="5" />
            <circle
              cx="22"
              cy="22"
              r="18"
              fill="none"
              stroke="#2E9BFF"
              strokeWidth="5"
              strokeDasharray={`${dash} ${circumference - dash}`}
            />
          </svg>
          <div>
            <p className="hud-label text-[9px] text-zero-text-muted">Tasks</p>
            <p className="text-sm font-semibold text-white">{tasksInProgress}</p>
          </div>
        </div>

        <div className="col-span-2">
          <div className="flex items-baseline justify-between mb-1">
            <span className="hud-label text-[9px] text-zero-text-muted">Estimated Impact</span>
            <span className="text-sm font-semibold text-zero-accent">
              {estimatedImpactPercent}%
            </span>
          </div>
          <div className="flex h-8 items-end gap-1">
            {impactHistory.map((v, i) => (
              <div
                key={i}
                className="flex-1 rounded-t bg-zero-accent/60"
                style={{ height: `${(v / maxImpact) * 100}%` }}
              />
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/ExecutiveSummary.tsx
git commit -m "Add Z.E.R.O dashboard executive summary panel"
```

---

### Task 16: RealTimeActivity

**Files:**
- Create: `dashboard/components/dashboard/RealTimeActivity.tsx`

**Interfaces:**
- Consumes: `activityFeed: ActivityEntry[]` via `useDashboardData()`; `Panel`.
- Produces: `<RealTimeActivity />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/RealTimeActivity.tsx`:

```tsx
import { Bot, Server, FolderKanban, User } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
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
  const { activityFeed } = useDashboardData();

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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/RealTimeActivity.tsx
git commit -m "Add Z.E.R.O dashboard real-time activity panel"
```

---

### Task 17: AssistantWidget

**Files:**
- Create: `dashboard/components/dashboard/AssistantWidget.tsx`

**Interfaces:**
- Consumes: `userName: string` via `useDashboardData()`; `Panel`.
- Produces: `<AssistantWidget />`, UI-only (no send handler, out of scope per spec).

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/AssistantWidget.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/AssistantWidget.tsx
git commit -m "Add Z.E.R.O dashboard assistant widget"
```

---

### Task 18: QuickAccess

**Files:**
- Create: `dashboard/components/dashboard/QuickAccess.tsx`

**Interfaces:**
- Consumes: nothing external.
- Produces: `<QuickAccess />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/QuickAccess.tsx`:

```tsx
import { Star, LayoutDashboard, BarChart3, Settings, Plus } from "lucide-react";
import { Panel } from "./ui/Panel";

const ITEMS = [
  { icon: Star, label: "Favorites" },
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: BarChart3, label: "Analytics" },
  { icon: Settings, label: "Config" },
  { icon: Plus, label: "Add" },
];

export function QuickAccess() {
  return (
    <Panel label="Quick Access">
      <div className="flex gap-2">
        {ITEMS.map(({ icon: Icon, label }) => (
          <button
            key={label}
            aria-label={label}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-zero-border text-zero-text-muted hover:text-zero-accent"
          >
            <Icon size={16} />
          </button>
        ))}
      </div>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/QuickAccess.tsx
git commit -m "Add Z.E.R.O dashboard quick access panel"
```

---

### Task 19: QuoteWidget

**Files:**
- Create: `dashboard/components/dashboard/QuoteWidget.tsx`

**Interfaces:**
- Consumes: `quote: { text, author }` via `useDashboardData()`; `Panel`.
- Produces: `<QuoteWidget />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/QuoteWidget.tsx`:

```tsx
import { Quote } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function QuoteWidget() {
  const { quote } = useDashboardData();

  return (
    <Panel className="flex flex-col justify-between">
      <Quote size={28} className="text-zero-accent/40 mb-3" />
      <p className="text-sm text-white leading-relaxed">{quote.text}</p>
      <p className="hud-label mt-3 text-[9px] text-zero-text-muted">— {quote.author}</p>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/QuoteWidget.tsx
git commit -m "Add Z.E.R.O dashboard quote widget"
```

---

### Task 20: GlobalConnectivity

**Files:**
- Create: `dashboard/components/dashboard/GlobalConnectivity.tsx`

**Interfaces:**
- Consumes: `connectivityNodes: ConnectivityNode[]` via `useDashboardData()`; `Panel`.
- Produces: `<GlobalConnectivity />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/GlobalConnectivity.tsx`:

```tsx
import { useDashboardData } from "@/hooks/useDashboardData";
import { Panel } from "./ui/Panel";

export function GlobalConnectivity() {
  const { connectivityNodes } = useDashboardData();

  return (
    <Panel label="Global Connectivity">
      <svg viewBox="0 0 100 60" className="h-24 w-full">
        {connectivityNodes.map((node, i) => (
          <circle
            key={i}
            cx={node.x}
            cy={node.y * 0.6}
            r={1.4}
            fill="#5AC8FF"
            opacity={0.8}
          />
        ))}
        {connectivityNodes.slice(0, -1).map((node, i) => {
          const next = connectivityNodes[i + 1];
          return (
            <line
              key={i}
              x1={node.x}
              y1={node.y * 0.6}
              x2={next.x}
              y2={next.y * 0.6}
              stroke="#2E9BFF"
              strokeOpacity={0.2}
              strokeWidth={0.5}
            />
          );
        })}
      </svg>
    </Panel>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/GlobalConnectivity.tsx
git commit -m "Add Z.E.R.O dashboard global connectivity widget"
```

---

### Task 21: EncryptionSecurity

**Files:**
- Create: `dashboard/components/dashboard/EncryptionSecurity.tsx`

**Interfaces:**
- Consumes: `security: SecurityStatus` via `useDashboardData()`; `Panel`.
- Produces: `<EncryptionSecurity />`.

- [ ] **Step 1: Write the component**

Create `dashboard/components/dashboard/EncryptionSecurity.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dashboard/EncryptionSecurity.tsx
git commit -m "Add Z.E.R.O dashboard encryption/security widget"
```

---

### Task 22: Compose the dashboard page

**Files:**
- Modify: `dashboard/app/layout.tsx`
- Modify: `dashboard/app/page.tsx`

**Interfaces:**
- Consumes: every component from Tasks 5–21.
- Produces: the full rendered dashboard route (`/`).

- [ ] **Step 1: Set page metadata**

Edit `dashboard/app/layout.tsx` so the exported `metadata` object reads:

```ts
export const metadata: Metadata = {
  title: "Z.E.R.O Central System",
  description: "Z.E.R.O personal command dashboard",
};
```

(Keep the rest of the scaffolded `layout.tsx` — root `<html>`/`<body>` structure — as generated in Task 1; only change the `metadata` values and remove the scaffolder's default page-body classes if they conflict with the `body` styling from Task 2.)

- [ ] **Step 2: Compose the page layout**

Replace the contents of `dashboard/app/page.tsx` with:

```tsx
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Header } from "@/components/dashboard/Header";
import { CenterHeader } from "@/components/dashboard/CenterHeader";
import { CoreVisualizer } from "@/components/dashboard/CoreVisualizer";
import { SyncProgressBar } from "@/components/dashboard/SyncProgressBar";
import { SystemPerformance } from "@/components/dashboard/SystemPerformance";
import { PredictiveAnalysis } from "@/components/dashboard/PredictiveAnalysis";
import { ResourceDistribution } from "@/components/dashboard/ResourceDistribution";
import { ActiveModules } from "@/components/dashboard/ActiveModules";
import { KeyProjects } from "@/components/dashboard/KeyProjects";
import { ExecutiveSummary } from "@/components/dashboard/ExecutiveSummary";
import { RealTimeActivity } from "@/components/dashboard/RealTimeActivity";
import { AssistantWidget } from "@/components/dashboard/AssistantWidget";
import { QuickAccess } from "@/components/dashboard/QuickAccess";
import { QuoteWidget } from "@/components/dashboard/QuoteWidget";
import { GlobalConnectivity } from "@/components/dashboard/GlobalConnectivity";
import { EncryptionSecurity } from "@/components/dashboard/EncryptionSecurity";

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <div className="flex-1 flex flex-col">
        <Header />

        <main className="flex-1 p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Center column */}
            <div className="order-1 lg:col-span-8 space-y-6">
              <CenterHeader />
              <CoreVisualizer />
              <SyncProgressBar />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <SystemPerformance />
                <PredictiveAnalysis />
                <ResourceDistribution />
              </div>
            </div>

            {/* Top-right column */}
            <div className="order-3 lg:order-2 lg:col-span-4 space-y-6">
              <ActiveModules />
              <KeyProjects />
            </div>
          </div>

          {/* Right sidebar column, stacked below on mobile per responsive order */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="order-2 lg:order-none lg:col-span-8" />
            <div className="order-2 lg:col-span-4 space-y-6">
              <ExecutiveSummary />
              <RealTimeActivity />
              <AssistantWidget />
              <QuickAccess />
            </div>
          </div>

          {/* Bottom row */}
          <div className="order-4 grid grid-cols-1 md:grid-cols-3 gap-6">
            <QuoteWidget />
            <GlobalConnectivity />
            <EncryptionSecurity />
          </div>
        </main>
      </div>
    </div>
  );
}
```

Note on responsive order: Executive Summary is placed with `order-2` (mobile) so it appears right after the center column content, matching the spec's "Core → Executive Summary → rest" mobile priority; the empty `lg:col-span-8` spacer keeps the two-column desktop grid aligned without duplicating the center column.

- [ ] **Step 3: Verify the full build**

```bash
cd dashboard && npx tsc --noEmit && npm run build
```
Expected: both commands complete with no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/layout.tsx dashboard/app/page.tsx
git commit -m "Compose Z.E.R.O dashboard page layout"
```

---

### Task 23: Remove Next.js boilerplate leftovers

**Files:**
- Modify: `dashboard/app/page.tsx` (already replaced in Task 22 — this task only cleans up unused scaffold assets)
- Delete: any unused scaffolded assets under `dashboard/public/` referenced only by the default `create-next-app` page (e.g. `next.svg`, `vercel.svg`) if no component in this plan uses them

**Interfaces:**
- None — cleanup only.

- [ ] **Step 1: Check for unused scaffold assets**

```bash
cd dashboard && grep -rl "next.svg\|vercel.svg" app components 2>/dev/null || echo "none referenced"
```

- [ ] **Step 2: Remove any files confirmed unreferenced by the grep output**

```bash
cd dashboard && rm -f public/next.svg public/vercel.svg
```
(Skip this step if the grep in Step 1 found references — keep the files in that case.)

- [ ] **Step 3: Verify**

```bash
cd dashboard && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add -A dashboard
git commit -m "Remove unused Next.js scaffold assets"
```

---

### Task 24: Final visual verification

**Files:** none (verification only)

**Interfaces:** none.

- [ ] **Step 1: Run the dev server**

```bash
cd dashboard && npm run dev
```

- [ ] **Step 2: Load the page and compare against the spec**

Open `http://localhost:3000` in a browser. Confirm against `docs/superpowers/specs/2026-07-04-zero-dashboard-design.md`:
- Sidebar, header, center core visualizer, side panels, and bottom row are all present and positioned per the 3-zone + bottom-row layout.
- Dark navy theme with neon blue accents renders correctly (no unstyled/white-background flashes).
- Resizing the browser below the `lg` breakpoint collapses to a single column with the core visualizer and Executive Summary appearing first.
- No console errors in the browser dev tools.

- [ ] **Step 3: Stop the dev server and commit any fixes found during review**

If the visual check surfaces issues, fix them in the relevant component file(s), re-run Step 1–2, then:

```bash
git add dashboard
git commit -m "Fix visual issues found in final dashboard review"
```

If no issues are found, no commit is needed for this task.

---

## Self-Review Notes

- **Spec coverage:** every spec section (sidebar, header, center column incl. core visualizer/sync bar/performance/predictive/resource panels, top-right modules/projects, right-column executive summary/activity/assistant/quick access, bottom row quote/connectivity/security, responsive collapse, design tokens, mock-data seam) maps to a task above.
- **Placeholder scan:** no TBD/TODO markers; every step has real, complete code.
- **Type consistency:** `DashboardData` (Task 3) is the single source of truth for prop shapes — every component in Tasks 5–21 imports from `@/lib/types` and `@/hooks/useDashboardData`, and field names (`syncPercent`, `systemMetrics`, `predictiveTrend`, `predictiveProjectionPercent`, `resourceDistribution`, `resourceTotalPercent`, `activeModules`, `keyProjects`, `executiveSummary`, `activityFeed`, `quote`, `connectivityNodes`, `security`, `userName`) are used identically across all consuming tasks.
