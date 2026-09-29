import React from "react";
import type { TradingStats } from "../types/dashboard";

interface Props {
  stats: TradingStats;
}

export const TradingStatistics: React.FC<Props> = ({ stats }) => {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Session Statistics
        </span>
        <span className="text-[10px] text-zinc-500 font-mono">OBSERVED</span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 py-2 text-xs font-mono">
        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">Laya Calls</span>
          <span className="text-zinc-200 font-semibold tabular-nums">
            {stats.laya_calls.toLocaleString()}
          </span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">Accepted Signals</span>
          <span className="text-cyan-400 font-semibold tabular-nums">
            {stats.accepted_signals}
          </span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">BUY Decisions</span>
          <span className="text-emerald-400 tabular-nums">{stats.buy_decisions}</span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">Position Switches</span>
          <span className="text-zinc-300 tabular-nums">{stats.position_switches}</span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">SELL Decisions</span>
          <span className="text-rose-400 tabular-nums">{stats.sell_decisions}</span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">Completed Trades</span>
          <span className="text-zinc-200 tabular-nums">{stats.completed_trades}</span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">HOLD Decisions</span>
          <span className="text-zinc-400 tabular-nums">{stats.hold_decisions}</span>
        </div>

        <div className="flex justify-between text-zinc-400">
          <span className="font-sans text-[11px]">Win / Loss</span>
          <span className="tabular-nums">
            <span className="text-emerald-400">{stats.winning_trades}</span>
            <span className="text-zinc-600"> / </span>
            <span className="text-rose-400">{stats.losing_trades}</span>
          </span>
        </div>
      </div>

      <div className="border-t border-zinc-800/80 pt-2 flex items-center justify-between text-xs font-mono">
        <span className="text-zinc-400 font-sans">Observed Win Rate</span>
        <span
          className={`font-bold tabular-nums ${
            stats.win_rate >= 50 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {stats.win_rate.toFixed(1)}%
        </span>
      </div>
    </div>
  );
};
