import React from "react";
import type { LayaDecision } from "../types/dashboard";
import { formatPercent, formatTime, formatMilliseconds } from "../utils/formatters";

interface Props {
  decisions: LayaDecision[];
}

export const LayaEventStream: React.FC<Props> = ({ decisions }) => {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            Live Laya Decision Stream
          </span>
          <span className="rounded bg-zinc-800 px-1.5 py-0.2 text-[10px] font-mono text-zinc-400">
            {decisions.length} / 100
          </span>
        </div>
        <span className="text-[10px] text-zinc-500 font-mono">NEWEST TOP</span>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[260px] font-mono text-xs">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-zinc-950 text-[10px] text-zinc-500 border-b border-zinc-800 uppercase font-sans">
            <tr>
              <th className="py-1 px-2">Time</th>
              <th className="py-1 px-2">Position</th>
              <th className="py-1 px-2">Decision</th>
              <th className="py-1 px-2">Confidence</th>
              <th className="py-1 px-2">Latency</th>
              <th className="py-1 px-2">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {decisions.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-zinc-600 font-sans text-xs">
                  No decision events recorded yet.
                </td>
              </tr>
            ) : (
              decisions.map((d, i) => {
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
                    <td className="py-1 px-2 text-zinc-300">{d.position_before}</td>
                    <td className={`py-1 px-2 tabular-nums ${badgeColor}`}>{d.action}</td>
                    <td className="py-1 px-2 text-zinc-200 tabular-nums font-semibold">
                      {formatPercent(d.confidence)}
                    </td>
                    <td className="py-1 px-2 text-zinc-400 tabular-nums">
                      {d.inference_latency_ms.toFixed(0)}ms
                    </td>
                    <td className="py-1 px-2 text-cyan-400 font-medium text-[11px]">
                      {d.result || (d.accepted ? "ACCEPTED" : "HOLD")}
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
