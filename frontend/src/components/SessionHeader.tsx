import React from "react";
import type { TradingSession } from "../types/dashboard";

interface Props {
  session: TradingSession;
  elapsed: string;
  remaining: string;
}

export const SessionHeader: React.FC<Props> = ({ session, elapsed, remaining }) => {
  return (
    <div className="bg-zinc-900/60 border-b border-zinc-800/80 px-4 py-2">
      <div className="flex flex-wrap items-center justify-between gap-y-2 gap-x-6 text-xs font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">INSTRUMENT:</span>
            <span className="font-semibold text-zinc-200">NIFTY OPTIONS</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">STRIKE:</span>
            <span className="font-bold text-cyan-400 tabular-nums">
              {session.selected_strike ?? "---"}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">EXPIRY:</span>
            <span className="text-zinc-200 tabular-nums">{session.expiry ?? "---"}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">LOT SIZE:</span>
            <span className="text-zinc-200 tabular-nums">{session.lot_size}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">HOURS:</span>
            <span className="text-zinc-400">09:27 → 15:13</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">ELAPSED:</span>
            <span className="text-zinc-300 tabular-nums">{elapsed}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">REMAINING:</span>
            <span className="text-zinc-300 tabular-nums">{remaining}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 font-sans">SESSION:</span>
            <span className="rounded bg-zinc-800 px-1.5 py-0.2 text-[11px] font-medium text-zinc-300">
              #{session.id ?? 1}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
