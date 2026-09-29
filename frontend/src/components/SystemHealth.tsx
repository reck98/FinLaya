import React from "react";
import type { SystemHealth as HealthType } from "../types/dashboard";

interface Props {
  health: HealthType;
  wsConnected: boolean;
}

export const SystemHealth: React.FC<Props> = ({ health, wsConnected }) => {
  const isBotRunning = health.bot_status === "RUNNING";
  const isMarketLive = health.market_data_status === "LIVE";
  const isLayaReady = health.laya_status === "READY";
  const isDbOk = health.database_status === "OK";

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          System Health
        </span>
        <span className="text-[10px] text-zinc-500 font-mono">STATUS</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs font-mono py-1">
        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">FinLaya Bot</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isBotRunning ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span
              className={`text-[10px] font-bold ${
                isBotRunning ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {isBotRunning ? "RUNNING" : "OFFLINE"}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">Market Data</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isMarketLive ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span
              className={`text-[10px] font-bold ${
                isMarketLive ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {health.market_data_status}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">Laya Model</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isLayaReady ? "bg-emerald-400" : "bg-zinc-500"
              }`}
            />
            <span
              className={`text-[10px] font-bold ${
                isLayaReady ? "text-emerald-400" : "text-zinc-400"
              }`}
            >
              {health.laya_status}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">SQLite WAL</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isDbOk ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span
              className={`text-[10px] font-bold ${
                isDbOk ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {health.database_status}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">WebSocket</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                wsConnected ? "bg-emerald-400" : "bg-rose-400 animate-pulse"
              }`}
            />
            <span
              className={`text-[10px] font-bold ${
                wsConnected ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {wsConnected ? "CONNECTED" : "RETRYING"}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between bg-zinc-950/60 p-1.5 rounded border border-zinc-800/50">
          <span className="text-zinc-400 font-sans text-[11px]">Dashboard</span>
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span className="text-[10px] font-bold text-emerald-400">ONLINE</span>
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800/80 pt-2 flex items-center justify-between text-[11px] font-mono text-zinc-500">
        <span>Last heartbeat:</span>
        <span className="text-zinc-400 tabular-nums">
          {health.seconds_since_heartbeat !== null
            ? `${health.seconds_since_heartbeat}s ago`
            : "No heartbeat"}
        </span>
      </div>
    </div>
  );
};
