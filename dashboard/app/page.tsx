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

        <main className="flex-1 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Center column: spans both desktop rows so the right-side
                stacks fill in beside it via grid auto-placement */}
            <div className="order-1 lg:col-span-8 lg:row-span-2 space-y-6">
              <CenterHeader />
              <CoreVisualizer />
              <SyncProgressBar />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <SystemPerformance />
                <PredictiveAnalysis />
                <ResourceDistribution />
              </div>
            </div>

            {/* Mobile order: Executive Summary comes right after the
                center column (order-2), before Active Modules/Key
                Projects (order-3), per the spec's mobile priority.
                Desktop order: Active Modules/Key Projects sit above
                Executive Summary in the right column (lg:order-2/3),
                matching the original top-right-column-above-sidebar
                layout. */}
            <div className="order-3 lg:order-2 lg:col-span-4 space-y-6">
              <ActiveModules />
              <KeyProjects />
            </div>

            <div className="order-2 lg:order-3 lg:col-span-4">
              <ExecutiveSummary />
            </div>

            <div className="order-4 lg:col-span-4 space-y-6">
              <RealTimeActivity />
              <AssistantWidget />
              <QuickAccess />
            </div>

            {/* Bottom row: full width, last on every breakpoint */}
            <div className="order-5 lg:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-6">
              <QuoteWidget />
              <GlobalConnectivity />
              <EncryptionSecurity />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
