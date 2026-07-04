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
