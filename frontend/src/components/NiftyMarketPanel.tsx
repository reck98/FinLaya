import React from "react";
import type { MarketData } from "../types/dashboard";
import { formatPrice } from "../utils/formatters";

interface Props {
  market: MarketData;
  selectedStrike: number | null;
  secondsSinceMarket: number | null;
}

export const NiftyMarketPanel: React.FC<Props> = ({
  market,
  selectedStrike,
  secondsSinceMarket,
}) => {
  const spotChange =
    market.nifty_spot && market.nifty_prev_close
      ? market.nifty_spot - market.nifty_prev_close
      : 0;
  const spotChangePct =
    market.nifty_prev_close > 0 ? (spotChange / market.nifty_prev_close) * 100 : 0;
  const isPositive = spotChange >= 0;
  const isStale = secondsSinceMarket !== null && secondsSinceMarket >= 3.0;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Underlying: NIFTY 50
        </span>
        {isStale ? (
          <span className="rounded bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-[10px] font-mono text-amber-400">
            ⚠ STALE — {secondsSinceMarket.toFixed(0)}s
          </span>
        ) : (
          <span className="text-[10px] text-zinc-500 font-mono">
            {secondsSinceMarket !== null ? `LIVE (${secondsSinceMarket}s)` : "WAITING"}
          </span>
        )}
      </div>

      <div className="py-2">
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-2xl font-bold tracking-tight text-zinc-100 tabular-nums">
            {formatPrice(market.nifty_spot)}
          </span>
          <div
            className={`font-mono text-xs font-semibold tabular-nums ${
              isPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {isPositive ? "+" : ""}
            {spotChange.toFixed(2)} ({isPositive ? "+" : ""}
            {spotChangePct.toFixed(2)}%)
          </div>
        </div>

        <div className="mt-2 grid grid-cols-4 gap-1.5 text-center text-xs font-mono bg-zinc-950/60 rounded p-1.5 border border-zinc-800/50">
          <div>
            <span className="text-[9px] text-zinc-500 block uppercase font-sans">Open</span>
            <span className="text-zinc-300 tabular-nums">
              {market.nifty_open ? formatPrice(market.nifty_open) : "---"}
            </span>
          </div>
          <div>
            <span className="text-[9px] text-zinc-500 block uppercase font-sans">High</span>
            <span className="text-zinc-300 tabular-nums">
              {market.nifty_high ? formatPrice(market.nifty_high) : "---"}
            </span>
          </div>
          <div>
            <span className="text-[9px] text-zinc-500 block uppercase font-sans">Low</span>
            <span className="text-zinc-300 tabular-nums">
              {market.nifty_low ? formatPrice(market.nifty_low) : "---"}
            </span>
          </div>
          <div>
            <span className="text-[9px] text-zinc-500 block uppercase font-sans">Prev Close</span>
            <span className="text-zinc-300 tabular-nums">
              {market.nifty_prev_close ? formatPrice(market.nifty_prev_close) : "---"}
            </span>
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800/80 pt-2 flex items-center justify-between text-xs font-mono">
        <span className="text-zinc-400 font-sans">Selected Strike (Fixed)</span>
        <span className="font-bold text-cyan-400 tabular-nums">
          {selectedStrike ?? "---"}
        </span>
      </div>
    </div>
  );
};
