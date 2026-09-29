import React, { useState } from "react";
import { useFinLayaSocket } from "./hooks/useFinLayaSocket";
import { useTradingClock } from "./hooks/useTradingClock";
import { TopStatusBar } from "./components/TopStatusBar";
import { SessionHeader } from "./components/SessionHeader";
import { OfflineBanner } from "./components/OfflineBanner";
import { NiftyMarketPanel } from "./components/NiftyMarketPanel";
import { PositionCard } from "./components/PositionCard";
import { PnLSummary } from "./components/PnLSummary";
import { OptionContractsPanel } from "./components/OptionContractsPanel";
import { LayaDecisionPanel } from "./components/LayaDecisionPanel";
import { TradingStatistics } from "./components/TradingStatistics";
import { PnLChart } from "./components/PnLChart";
import { LayaEventStream } from "./components/LayaEventStream";
import { LayaInferenceTable } from "./components/LayaInferenceTable";
import { RecentTrades } from "./components/RecentTrades";
import { SystemEventFeed } from "./components/SystemEventFeed";
import { SystemHealth } from "./components/SystemHealth";

export const App: React.FC = () => {
  const { snapshot, wsConnected } = useFinLayaSocket();
  const { istTime, elapsed, remaining } = useTradingClock();
  const [streamTab, setStreamTab] = useState<"stream" | "calls">("stream");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-zinc-800">
      {/* 1. Sticky Top Status Bar */}
      <TopStatusBar
        health={snapshot.health}
        market={snapshot.market}
        istTime={istTime}
        wsConnected={wsConnected}
      />

      {/* 2. Session Header */}
      <SessionHeader
        session={snapshot.session}
        elapsed={elapsed}
        remaining={remaining}
      />

      {/* 3. Offline / Waiting Notice */}
      <OfflineBanner
        health={snapshot.health}
        sessionId={snapshot.session.id}
      />

      {/* 4. Main Observability Workspace */}
      <main className="flex-1 p-4 max-w-[1720px] w-full mx-auto space-y-4">
        {/* Row 1: Core Telemetry (3 Columns) */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <NiftyMarketPanel
            market={snapshot.market}
            selectedStrike={snapshot.session.selected_strike}
            secondsSinceMarket={snapshot.health.seconds_since_market}
          />
          <PositionCard position={snapshot.position} />
          <PnLSummary pnl={snapshot.pnl} />
        </section>

        {/* Row 2: Contracts & Decision Engine (3 Columns) */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <OptionContractsPanel
            market={snapshot.market}
            position={snapshot.position}
            strike={snapshot.session.selected_strike}
          />
          <LayaDecisionPanel decision={snapshot.latest_decision} />
          <TradingStatistics stats={snapshot.stats} />
        </section>

        {/* Row 3: Intraday P&L Curve */}
        <section className="w-full">
          <PnLChart
            history={snapshot.pnl.history}
            currentPnl={snapshot.pnl.total}
          />
        </section>

        {/* Row 4: Laya Inference Telemetry (Stream & Call Log) */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between mb-1.5 px-1">
              <span className="text-xs font-mono text-zinc-400 font-semibold uppercase">
                Laya Decisions (0.5s)
              </span>
              <div className="flex gap-1 text-[10px] font-mono">
                <button
                  onClick={() => setStreamTab("stream")}
                  className={`px-2 py-0.5 rounded ${
                    streamTab === "stream"
                      ? "bg-zinc-800 text-zinc-100 font-bold"
                      : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  Decision Stream
                </button>
                <button
                  onClick={() => setStreamTab("calls")}
                  className={`px-2 py-0.5 rounded ${
                    streamTab === "calls"
                      ? "bg-zinc-800 text-zinc-100 font-bold"
                      : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  Inference Calls
                </button>
              </div>
            </div>
            {streamTab === "stream" ? (
              <LayaEventStream decisions={snapshot.recent_decisions} />
            ) : (
              <LayaInferenceTable decisions={snapshot.recent_decisions} />
            )}
          </div>

          <div className="flex flex-col h-full">
            <div className="mb-1.5 px-1">
              <span className="text-xs font-mono text-zinc-400 font-semibold uppercase">
                Paper Execution Fills
              </span>
            </div>
            <RecentTrades orders={snapshot.recent_orders} />
          </div>
        </section>

        {/* Row 5: System Logs & Infrastructure Health */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <SystemEventFeed events={snapshot.recent_events} />
          </div>
          <div>
            <SystemHealth
              health={snapshot.health}
              wsConnected={wsConnected}
            />
          </div>
        </section>
      </main>

      {/* 5. Minimal Desktop Footer */}
      <footer className="border-t border-zinc-900 bg-zinc-950 px-4 py-2 text-[11px] font-mono text-zinc-600 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span>FinLaya Paper Trading Terminal</span>
          <span>•</span>
          <span className="text-zinc-500">Read-Only Interface</span>
          <span>•</span>
          <span>No Real Orders Submitted</span>
        </div>
        <div>
          <span>Local Model: convaiinnovations/laya</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
