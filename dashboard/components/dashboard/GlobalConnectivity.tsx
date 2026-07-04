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
