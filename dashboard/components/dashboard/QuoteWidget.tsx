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
