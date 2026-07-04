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
