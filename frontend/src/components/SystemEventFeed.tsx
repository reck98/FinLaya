import React, { useState } from "react";
import type { EventLog } from "../types/dashboard";
import { formatTime, formatMilliseconds } from "../utils/formatters";

interface Props {
  events: EventLog[];
}

type FilterType = "ALL" | "LAYA" | "ORDERS" | "MARKET" | "ERRORS";

export const SystemEventFeed: React.FC<Props> = ({ events }) => {
  const [filter, setFilter] = useState<FilterType>("ALL");

  const filtered = events.filter((e) => {
    if (filter === "ALL") return true;
    if (filter === "LAYA") return e.event_type.includes("LAYA");
    if (filter === "ORDERS") return e.event_type.includes("ORDER") || e.event_type.includes("POSITION");
    if (filter === "MARKET") return e.event_type.includes("MARKET") || e.event_type.includes("WS");
    if (filter === "ERRORS") return e.level === "ERROR" || e.level === "WARNING";
    return true;
  });

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            System Event Log
          </span>
          <span className="rounded bg-zinc-800 px-1.5 py-0.2 text-[10px] font-mono text-zinc-400">
            {filtered.length}
          </span>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 text-[10px] font-mono">
          {(["ALL", "LAYA", "ORDERS", "MARKET", "ERRORS"] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-0.5 rounded transition-colors ${
                filter === f
                  ? "bg-zinc-700 text-zinc-100 font-bold"
                  : "bg-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[260px] font-mono text-xs">
        <div className="space-y-1">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-zinc-600 font-sans text-xs">
              No matching events found.
            </div>
          ) : (
            filtered.map((e, i) => {
              const isError = e.level === "ERROR";
              const isWarning = e.level === "WARNING";

              return (
                <div
                  key={e.id ?? `${e.timestamp}-${i}`}
                  className={`flex items-start gap-2.5 p-1 rounded transition-colors ${
                    isError
                      ? "bg-rose-950/30 text-rose-300 border-l-2 border-rose-500"
                      : isWarning
                      ? "bg-amber-950/20 text-amber-300 border-l-2 border-amber-500"
                      : "hover:bg-zinc-800/20 text-zinc-300"
                  }`}
                >
                  <span className="text-zinc-500 tabular-nums shrink-0 text-[11px]">
                    {formatTime(e.timestamp)}
                    {formatMilliseconds(e.timestamp)}
                  </span>
                  <span
                    className={`rounded px-1 text-[10px] uppercase font-bold shrink-0 ${
                      isError
                        ? "bg-rose-500/20 text-rose-400"
                        : isWarning
                        ? "bg-amber-500/20 text-amber-400"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {e.event_type}
                  </span>
                  <span className="text-zinc-300 truncate text-[11px]">{e.message}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
