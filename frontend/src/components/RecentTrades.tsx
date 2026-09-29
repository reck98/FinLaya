import React from "react";
import type { Order } from "../types/dashboard";
import { formatCurrency, formatPrice, formatTime, formatMilliseconds } from "../utils/formatters";

interface Props {
  orders: Order[];
}

export const RecentTrades: React.FC<Props> = ({ orders }) => {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            Recent Executed Orders (Paper)
          </span>
          <span className="rounded bg-zinc-800 px-1.5 py-0.2 text-[10px] font-mono text-zinc-400">
            {orders.length}
          </span>
        </div>
        <span className="text-[10px] text-zinc-500 font-mono">SIMULATED FILLS</span>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[260px] font-mono text-xs">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-zinc-950 text-[10px] text-zinc-500 border-b border-zinc-800 uppercase font-sans">
            <tr>
              <th className="py-1 px-2">Time</th>
              <th className="py-1 px-2">Contract</th>
              <th className="py-1 px-2">Side</th>
              <th className="py-1 px-2">Qty</th>
              <th className="py-1 px-2">Price</th>
              <th className="py-1 px-2">Realized P&L</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {orders.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-zinc-600 font-sans text-xs">
                  No orders executed yet in this session.
                </td>
              </tr>
            ) : (
              orders.map((o, i) => {
                const isBuy = o.side === "BUY";
                const pnl = o.realized_pnl;

                return (
                  <tr
                    key={o.order_id ?? `${o.timestamp}-${i}`}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-1 px-2 text-zinc-400 tabular-nums">
                      {formatTime(o.timestamp)}
                      {formatMilliseconds(o.timestamp)}
                    </td>
                    <td className="py-1 px-2 text-zinc-200 font-medium">{o.instrument}</td>
                    <td
                      className={`py-1 px-2 font-bold ${
                        isBuy ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {o.side}
                    </td>
                    <td className="py-1 px-2 text-zinc-300 tabular-nums">{o.quantity}</td>
                    <td className="py-1 px-2 text-zinc-200 tabular-nums">
                      ₹{formatPrice(o.fill_price)}
                    </td>
                    <td className="py-1 px-2 tabular-nums font-semibold">
                      {pnl !== undefined && pnl !== null ? (
                        <span className={pnl >= 0 ? "text-emerald-400" : "text-rose-400"}>
                          {formatCurrency(pnl)}
                        </span>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
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
