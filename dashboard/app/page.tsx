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
