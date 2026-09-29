import React from "react";
import type { Position } from "../types/dashboard";
import { formatCurrency, formatPrice } from "../utils/formatters";

interface Props {
  position: Position;
}

export const PositionCard: React.FC<Props> = ({ position }) => {
  const isFlat = position.side === "FLAT" || position.quantity === 0;
  const isCE = position.side === "LONG_CE";
  const isPE = position.side === "LONG_PE";
  const isProfit = position.unrealized_pnl >= 0;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Current Position
        </span>
        <span
          className={`rounded px-2 py-0.5 text-xs font-mono font-bold tracking-wide ${
            isFlat
              ? "bg-zinc-800 text-zinc-400"
              : isCE
              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/60"
              : isPE
              ? "bg-rose-950/60 text-rose-400 border border-rose-800/60"
              : "bg-zinc-800 text-zinc-400"
          }`}
        >
          {position.side}
        </span>
      </div>

      {isFlat ? (
        <div className="py-6 text-center">
          <div className="font-mono text-sm text-zinc-500">No active position</div>
          <div className="text-xs text-zinc-600 mt-1">Waiting for Laya entry signal</div>
        </div>
      ) : (
        <div className="py-2.5 space-y-2.5">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-zinc-400">Contract</span>
            <span className="font-mono text-sm font-semibold text-zinc-100">
              {position.instrument}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1 text-xs font-mono">
            <div className="bg-zinc-950/60 rounded p-2 border border-zinc-800/50">
              <span className="text-[10px] text-zinc-500 block uppercase">Qty</span>
              <span className="text-zinc-200 font-semibold tabular-nums">
                {position.quantity}
              </span>
            </div>

            <div className="bg-zinc-950/60 rounded p-2 border border-zinc-800/50">
              <span className="text-[10px] text-zinc-500 block uppercase">Entry</span>
              <span className="text-zinc-200 font-semibold tabular-nums">
                ₹{formatPrice(position.entry_price)}
              </span>
            </div>

            <div className="bg-zinc-950/60 rounded p-2 border border-zinc-800/50">
              <span className="text-[10px] text-zinc-500 block uppercase">Current</span>
              <span className="text-zinc-200 font-semibold tabular-nums">
                ₹{formatPrice(position.current_price)}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-zinc-800/60 pt-2 font-mono">
            <span className="text-xs text-zinc-400 font-sans">Unrealized P&L</span>
            <span
              className={`text-base font-bold tabular-nums ${
                isProfit ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {formatCurrency(position.unrealized_pnl)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
