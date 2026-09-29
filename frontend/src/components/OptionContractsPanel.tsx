import React from "react";
import type { MarketData, Position } from "../types/dashboard";
import { formatPrice } from "../utils/formatters";

interface Props {
  market: MarketData;
  position: Position;
  strike: number | null;
}

export const OptionContractsPanel: React.FC<Props> = ({ market, position, strike }) => {
  const isHoldingCE = position.side === "LONG_CE";
  const isHoldingPE = position.side === "LONG_PE";

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Selected Option Contracts
        </span>
        <span className="text-[10px] text-zinc-500 font-mono">FIXED STRIKE</span>
      </div>

      <div className="grid grid-cols-2 gap-3 py-2">
        {/* CE Contract Card */}
        <div
          className={`rounded p-2.5 border transition-all ${
            isHoldingCE
              ? "bg-emerald-950/30 border-emerald-500/80 ring-1 ring-emerald-500/30"
              : "bg-zinc-950/60 border-zinc-800/60"
          }`}
        >
          <div className="flex items-center justify-between border-b border-zinc-800/60 pb-1.5 mb-1.5">
            <span className="font-mono text-xs font-bold text-zinc-100">
              {strike ? `${strike} CE` : "CE CONTRACT"}
            </span>
            {isHoldingCE && (
              <span className="rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 px-1.5 py-0.2 text-[9px] font-mono font-bold">
                HELD
              </span>
            )}
          </div>

          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between items-baseline">
              <span className="text-zinc-500 text-[10px] font-sans uppercase">LTP</span>
              <span className="font-bold text-zinc-100 text-sm tabular-nums">
                ₹{formatPrice(market.ce_ltp)}
              </span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">Bid / Ask</span>
              <span className="tabular-nums">
                {formatPrice(market.ce_bid)} / {formatPrice(market.ce_ask)}
              </span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">Volume</span>
              <span className="tabular-nums">{market.ce_volume.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">OI</span>
              <span className="tabular-nums">{market.ce_oi.toLocaleString("en-IN")}</span>
            </div>
          </div>
        </div>

        {/* PE Contract Card */}
        <div
          className={`rounded p-2.5 border transition-all ${
            isHoldingPE
              ? "bg-rose-950/30 border-rose-500/80 ring-1 ring-rose-500/30"
              : "bg-zinc-950/60 border-zinc-800/60"
          }`}
        >
          <div className="flex items-center justify-between border-b border-zinc-800/60 pb-1.5 mb-1.5">
            <span className="font-mono text-xs font-bold text-zinc-100">
              {strike ? `${strike} PE` : "PE CONTRACT"}
            </span>
            {isHoldingPE && (
              <span className="rounded bg-rose-500/20 text-rose-400 border border-rose-500/40 px-1.5 py-0.2 text-[9px] font-mono font-bold">
                HELD
              </span>
            )}
          </div>

          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between items-baseline">
              <span className="text-zinc-500 text-[10px] font-sans uppercase">LTP</span>
              <span className="font-bold text-zinc-100 text-sm tabular-nums">
                ₹{formatPrice(market.pe_ltp)}
              </span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">Bid / Ask</span>
              <span className="tabular-nums">
                {formatPrice(market.pe_bid)} / {formatPrice(market.pe_ask)}
              </span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">Volume</span>
              <span className="tabular-nums">{market.pe_volume.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex justify-between text-zinc-400 text-[11px]">
              <span className="text-zinc-500 font-sans">OI</span>
              <span className="tabular-nums">{market.pe_oi.toLocaleString("en-IN")}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
