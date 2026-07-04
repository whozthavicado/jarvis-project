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
