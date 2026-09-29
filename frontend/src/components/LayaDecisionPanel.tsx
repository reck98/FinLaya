import React from "react";
import type { LayaDecision } from "../types/dashboard";
import { formatPercent, formatTime, formatMilliseconds } from "../utils/formatters";

interface Props {
  decision: LayaDecision | null;
}

export const LayaDecisionPanel: React.FC<Props> = ({ decision }) => {
  if (!decision) {
    return (
      <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            Laya Decision
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">0.5s LOOP</span>
        </div>
        <div className="py-8 text-center">
          <div className="font-mono text-sm text-zinc-500">Waiting for model inference...</div>
        </div>
      </div>
    );
  }

  const action = decision.action;
  const isBuy = action === "BUY";
  const isSell = action === "SELL";

  const actionBg = isBuy
    ? "bg-emerald-950/50 text-emerald-400 border-emerald-800/60"
    : isSell
    ? "bg-rose-950/50 text-rose-400 border-rose-800/60"
    : "bg-zinc-800/60 text-zinc-300 border-zinc-700/60";

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
        <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          Laya Decision
        </span>
        <div className="flex items-center gap-1.5 font-mono text-[10px] text-zinc-500">
          <span>LATENCY:</span>
          <span className="text-zinc-300 font-semibold tabular-nums">
            {decision.inference_latency_ms.toFixed(1)}ms
          </span>
        </div>
      </div>

      <div className="py-2 flex flex-col items-center justify-center">
        <div
          className={`rounded-md border px-6 py-1.5 font-mono text-2xl font-black tracking-wider transition-colors duration-150 ${actionBg}`}
        >
          {action}
        </div>
        <div className="mt-1 font-mono text-xs font-semibold text-zinc-300 tabular-nums">
          {formatPercent(decision.confidence)} confidence
        </div>
      </div>

      <div className="border-t border-zinc-800/80 pt-2 grid grid-cols-2 gap-2 text-xs font-mono">
        <div>
          <span className="text-[10px] text-zinc-500 block uppercase font-sans">
            Position Before
          </span>
          <span className="text-zinc-300 font-medium">{decision.position_before}</span>
        </div>

        <div>
          <span className="text-[10px] text-zinc-500 block uppercase font-sans">
            Resulting Action
          </span>
          <span className="text-cyan-400 font-medium">
            {decision.result || decision.position_after || "HOLD"}
          </span>
        </div>

        <div className="col-span-2 flex items-center justify-between text-[11px] text-zinc-500 pt-1 border-t border-zinc-800/40">
          <span>Timestamp</span>
          <span className="tabular-nums text-zinc-400">
            {formatTime(decision.timestamp)}
            {formatMilliseconds(decision.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
};
