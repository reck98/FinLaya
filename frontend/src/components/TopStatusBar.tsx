import React from "react";
import type { MarketData, SystemHealth } from "../types/dashboard";
import { formatPrice } from "../utils/formatters";

interface Props {
  health: SystemHealth;
  market: MarketData;
  istTime: string;
  wsConnected: boolean;
}

export const TopStatusBar: React.FC<Props> = ({ health, market, istTime, wsConnected }) => {
  const isBotRunning = health.bot_status === "RUNNING";
  const isMarketLive = health.market_data_status === "LIVE";
  const isLayaReady = health.laya_status === "READY";

  const spotChange =
    market.nifty_spot && market.nifty_prev_close
      ? market.nifty_spot - market.nifty_prev_close
      : 0;
  const spotChangePct =
    market.nifty_prev_close > 0 ? (spotChange / market.nifty_prev_close) * 100 : 0;
  const isPositive = spotChange >= 0;

  return (
    <header className="border-b border-zinc-800/80 bg-zinc-950/90 px-4 py-2.5 backdrop-blur sticky top-0 z-50">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Brand & Statuses */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="font-bold tracking-wider text-zinc-100 text-sm">FINLAYA</span>
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">
              PAPER
            </span>
          </div>

          <div className="h-3.5 w-px bg-zinc-800" />

          {/* Bot Status */}
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                isBotRunning ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-rose-500"
              }`}
            />
            <span className="font-mono font-medium text-zinc-300">
              {isBotRunning ? "RUNNING" : "BOT OFFLINE"}
            </span>
          </div>

          <div className="h-3.5 w-px bg-zinc-800" />

          {/* Laya Status */}
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                isLayaReady ? "bg-emerald-500" : "bg-zinc-600"
              }`}
            />
            <span className="text-zinc-400">LAYA:</span>
            <span className="font-mono text-zinc-300">{health.laya_status}</span>
          </div>

          <div className="h-3.5 w-px bg-zinc-800" />

          {/* Market Data Feed */}
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                isMarketLive ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            <span className="text-zinc-400">FEED:</span>
            <span className="font-mono text-zinc-300">{health.market_data_status}</span>
          </div>

          <div className="h-3.5 w-px bg-zinc-800" />

          {/* WebSocket */}
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                wsConnected ? "bg-emerald-500" : "bg-rose-500 animate-pulse"
              }`}
            />
            <span className="text-zinc-400">WS:</span>
            <span className="font-mono text-zinc-300">
              {wsConnected ? "CONNECTED" : "RECONNECTING"}
            </span>
          </div>

          {health.is_mock && (
            <span className="rounded bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300 uppercase tracking-wide">
              MOCK DATA
            </span>
          )}
        </div>

        {/* Right: NIFTY Spot Quote & IST Clock */}
        <div className="flex items-center gap-4">
          {market.nifty_spot > 0 && (
            <div className="flex items-center gap-2 font-mono">
              <span className="text-zinc-400 font-sans">NIFTY 50</span>
              <span className="font-semibold text-zinc-100 tabular-nums">
                {formatPrice(market.nifty_spot)}
              </span>
              <span
                className={`text-[11px] tabular-nums ${
                  isPositive ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {isPositive ? "+" : ""}
                {spotChange.toFixed(2)} ({isPositive ? "+" : ""}
                {spotChangePct.toFixed(2)}%)
              </span>
            </div>
          )}

          <div className="h-3.5 w-px bg-zinc-800" />

          <div className="font-mono text-zinc-300 tabular-nums font-medium bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded">
            {istTime}
          </div>
        </div>
      </div>
    </header>
  );
};
