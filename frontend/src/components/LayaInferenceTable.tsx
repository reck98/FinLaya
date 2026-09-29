import React from "react";
import type { LayaDecision } from "../types/dashboard";
import { formatPercent, formatTime, formatMilliseconds } from "../utils/formatters";

interface Props {
  decisions: LayaDecision[];
}

export const LayaInferenceTable: React.FC<Props> = ({ decisions }) => {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            Laya Inference Activity
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">CALL LOG</span>
        </div>
        <span className="text-[10px] text-zinc-500 font-mono">ALL CALLS</span>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[260px] font-mono text-xs">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-zinc-950 text-[10px] text-zinc-500 border-b border-zinc-800 uppercase font-sans">
            <tr>
              <th className="py-1 px-2">Time</th>
              <th className="py-1 px-2">Call ID</th>
              <th className="py-1 px-2">Position</th>
              <th className="py-1 px-2">Options Prompted</th>
              <th className="py-1 px-2">Decision</th>
              <th className="py-1 px-2">Confidence</th>
              <th className="py-1 px-2">Latency</th>
              <th className="py-1 px-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {decisions.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-zinc-600 font-sans text-xs">
                  No inference calls recorded.
                </td>
              </tr>
            ) : (
              decisions.map((d, i) => {
                const callId = d.id ? `#${d.id}` : `#a${(1000 + i).toString(16)}`;
                const isFlat = d.position_before === "FLAT";
                const optionsDisplay = isFlat ? "BUY / SELL" : "BUY / SELL / HOLD";

                const isBuy = d.action === "BUY";
                const isSell = d.action === "SELL";
                const badgeColor = isBuy
                  ? "text-emerald-400 font-bold"
                  : isSell
                  ? "text-rose-400 font-bold"
                  : "text-zinc-400";

                return (
                  <tr
                    key={d.id ?? `${d.timestamp}-${i}`}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-1 px-2 text-zinc-400 tabular-nums">
                      {formatTime(d.timestamp)}
                      {formatMilliseconds(d.timestamp)}
                    </td>
                    <td className="py-1 px-2 text-zinc-500 tabular-nums">{callId}</td>
                    <td className="py-1 px-2 text-zinc-300">{d.position_before}</td>
                    <td className="py-1 px-2">
                      <span className="rounded bg-zinc-950 px-1.5 py-0.5 text-[10px] text-zinc-400 border border-zinc-800/60">
                        {optionsDisplay}
                      </span>
                    </td>
                    <td className={`py-1 px-2 tabular-nums ${badgeColor}`}>{d.action}</td>
                    <td className="py-1 px-2 text-zinc-200 tabular-nums">
                      {formatPercent(d.confidence)}
                    </td>
                    <td className="py-1 px-2 text-zinc-400 tabular-nums">
                      {d.inference_latency_ms.toFixed(0)}ms
                    </td>
                    <td className="py-1 px-2">
                      <span className="text-emerald-400 text-[10px] font-bold">OK</span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
