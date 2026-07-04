# Z.E.R.O Dashboard — Design Spec

Date: 2026-07-04

## Goal

Build the Z.E.R.O Central System dashboard: a visual, data-mocked control-panel UI replicating a reference layout (sidebar nav, top header, central 3D-styled core visualizer, module/summary side panels, bottom widget row). No real backend yet — data is mocked behind a single hook so it can be swapped for live API/WebSocket data later.

This is a new, independent frontend subsystem alongside the existing Python `jarvis/` voice-assistant backend in this repo. It has no code dependency on `jarvis/` today; the mock-data seam (`useDashboardData`) is where a future integration would attach.

## Stack & Location

- New directory: `dashboard/` at repo root, sibling to `jarvis/`.
- Next.js 14 (App Router), TypeScript, TailwindCSS, npm as package manager.
- `lucide-react` for icons.
- `framer-motion` for the core visualizer's pulse/rotation animation.
- Scaffold via `npx create-next-app@latest dashboard --typescript --tailwind --app --no-src-dir`.

## Visual Theme (design tokens)

Defined as Tailwind theme extensions in `dashboard/tailwind.config.ts` — no raw hex values inside components.

- `zero.bg`: gradient stops from `#05070C` to `#0A0E16` (page background).
- `zero.accent`: `#2E9BFF` → `#5AC8FF` (neon electric blue; glows, lines, charts, status text).
- `zero.surface`: `#0D1420` (translucent dark blue card surface).
- `zero.border`: white/blue at 8–10% opacity (1px card borders).
- `zero.text.primary`: pure white. `zero.text.muted`: faint bluish-gray.
- Radius token `zero.card`: 16–20px, used on every panel.
- Typography: system sans for body text; a wide-tracking uppercase utility class (e.g. `.hud-label`) for section labels like "GLOBAL PRIORITY", "ACTIVE MODULES". Labels uppercase, values/proper nouns lowercase-cased as authored (per source data), matching the "corporate HUD" tone.

## Data Layer

- `dashboard/lib/mock-data.ts`: exports a single `DashboardData` TypeScript interface covering every panel's data needs (system metrics, sparkline series, predictive trend series, resource distribution categories, active modules, key projects, executive summary figures, activity feed entries, quote, connectivity map points, security status) plus one static object satisfying it. All figures plausible for a personal/business management system — no placeholder/lorem content.
- `dashboard/hooks/useDashboardData.ts`: returns that mock object today. Every presentation component consumes data through this hook, never importing `mock-data.ts` directly — this is the intended swap point for a real API/WebSocket source later, and requires no component changes when that happens.

## Layout & Components

All dashboard-specific components live under `dashboard/components/dashboard/`.

**Shared primitives**
- `ui/Panel.tsx` — the recurring card shell (border, radius, padding, uppercase label header). Every panel below composes this instead of repeating border/radius/spacing classes.
- `ui/SectionLabel.tsx` — the uppercase wide-tracking label element.

**Shell**
- `Sidebar.tsx` — fixed ~260px width: Z.E.R.O logo + subtitle, personal branding block (monogram circle, name, tagline), vertical nav (Dashboard/System/Analysis/Projects/Communications/Automation/Resources/Security/Configuration, Dashboard active), footer (version, "CORE ACTIVE" status, mini wave chart, "SYSTEM STATUS: OPTIMAL").
- `Header.tsx` — full-width top bar: centered "Z.E.R.O CENTRAL SYSTEM" title, right-aligned live clock (client component, updates via `setInterval`) + date + quick-access icons.

**Center column**
- `CenterHeader.tsx` — large "Z.E.R.O" title, tagline, pulsing-dot "INTELLIGENT CORE ACTIVE" indicator, "GLOBAL PRIORITY" block with subtext and pagination dots.
- `CoreVisualizer.tsx` — SVG concentric rings, radial lines, scattered glowing node dots, slow rotation/pulse via framer-motion, centered "Z.E.R.O — ACTIVE" text. 2D/SVG treatment (not a real 3D/three.js scene), per approved design.
- `SyncProgressBar.tsx` — "GLOBAL SYNCHRONIZATION" bar with percentage.
- `SystemPerformance.tsx` — CPU/Memory/Network/Storage, each with a % value and an inline SVG sparkline.
- `PredictiveAnalysis.tsx` — 30-day SVG trend line with a projection label.
- `ResourceDistribution.tsx` — central SVG donut (total %) with a category legend (color swatch + percentage).

**Top-right column (inside main grid)**
- `ActiveModules.tsx` — Intelligence/Learning/Predictive Analysis/Automation/Security, each with icon, name, "Active" status; "VIEW ALL MODULES" button.
- `KeyProjects.tsx` — project list with name, sub-status (executing/planning), progress bar + percentage; "VIEW ALL PROJECTS" button.

**Right sidebar column (independent of main 3-col grid)**
- `ExecutiveSummary.tsx` — active projects count, tasks-in-progress with a % progress ring, estimated impact with a mini bar chart.
- `RealTimeActivity.tsx` — feed list (avatar/icon, actor, event description, relative time); "VIEW ALL ACTIVITY" button.
- `AssistantWidget.tsx` — glowing avatar, personalized greeting ("How can I help you today, Bernumeno?"), short description, "Type a command..." input + send button (UI only, no wiring to the Python backend in this scope).
- `QuickAccess.tsx` — row of square icon buttons (favorites, dashboard, analytics, config, add).

**Bottom row (3 equal-width widgets, full content width)**
- `QuoteWidget.tsx` — decorative quotation marks, quote text, attribution.
- `GlobalConnectivity.tsx` — stylized SVG world dot-map in blue.
- `EncryptionSecurity.tsx` — lock/shield icon with glow, "SYSTEM PROTECTED" / "LEVEL 5" / "ACTIVE ENCRYPTION" text, status dots.

**Composition**: `app/page.tsx` assembles `Sidebar` + `Header` + the 3-zone main grid + bottom row, sourcing all data from `useDashboardData()` once and passing slices down as props.

## Responsive Behavior

Below `lg` breakpoint, the grid collapses to a single column. Order (via Tailwind `order-*` utilities): Core visualizer/center column first, then Executive Summary, then remaining panels in their existing top-to-bottom order. Sidebar collapses per standard responsive nav pattern (not specified further — implementation plan can choose a simple collapse/hamburger without a separate design round since it's not a described focal point).

## Out of Scope

- No real backend/API/WebSocket wiring — mock data only, behind the `useDashboardData` seam.
- No functional assistant chat (input renders, no send handler wired to any LLM).
- No auth, no persistence, no routes beyond the single dashboard page.
- No integration with the existing Python `jarvis/` package in this pass.

## Testing

No automated test framework specified for this pass — visual/UI correctness will be verified by running the dev server and reviewing the rendered page against this spec (per the project's UI verification practice), not by unit tests. Component props (via the `DashboardData` interface) are TypeScript-checked at build time.
