import React from "react";
import type { PnLData } from "../types/dashboard";
import { formatCurrency } from "../utils/formatters";

interface Props {
  pnl: PnLData;
}

export const PnLSummary: React.FC<Props> = ({ pnl }) => {
  const isTotalPositive = pnl.total >= 0;
  const isRealizedPositive = pnl.realized >= 0;
  const isUnrealizedPositive = pnl.unrealized >= 0;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Profit & Loss
        </span>
        <span className="text-[10px] text-zinc-500 font-mono">TODAY</span>
      </div>

      <div className="py-2 space-y-2 text-xs font-mono">
        <div className="flex items-center justify-between text-zinc-400">
          <span>Realized Today</span>
          <span
            className={`font-semibold tabular-nums ${
              isRealizedPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {formatCurrency(pnl.realized)}
          </span>
        </div>

        <div className="flex items-center justify-between text-zinc-400">
          <span>Unrealized</span>
          <span
            className={`font-semibold tabular-nums ${
              isUnrealizedPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {formatCurrency(pnl.unrealized)}
          </span>
        </div>

        <div className="border-t border-zinc-800 pt-2 flex items-baseline justify-between">
          <span className="text-zinc-200 font-sans font-bold text-sm">TOTAL P&L</span>
          <span
            className={`text-xl font-bold tabular-nums tracking-tight ${
              isTotalPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {formatCurrency(pnl.total)}
          </span>
        </div>
      </div>
    </div>
  );
};
