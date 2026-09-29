import React from "react";
import type { SystemHealth } from "../types/dashboard";

interface Props {
  health: SystemHealth;
  sessionId: number | null;
}

export const OfflineBanner: React.FC<Props> = ({ health, sessionId }) => {
  if (health.is_mock) return null;

  const isOffline = health.bot_status === "OFFLINE";
  const isWaiting = health.bot_status === "WAITING" || !sessionId;

  if (!isOffline && !isWaiting) return null;

  return (
    <div className="bg-amber-950/40 border-b border-amber-800/60 px-4 py-2 text-xs font-mono flex items-center justify-between text-amber-200">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
        <span className="font-bold">
          {isOffline ? "BOT OFFLINE" : "WAITING FOR SESSION"}
        </span>
        <span className="text-amber-400/80">
          {isOffline
            ? health.seconds_since_heartbeat !== null
              ? `Last heartbeat: ${health.seconds_since_heartbeat}s ago`
              : "No heartbeat detected from Terminal 1 (`uv run finlaya run`)"
            : "FinLaya trading bot has not initiated today's session yet."}
        </span>
      </div>

      <div className="text-[11px] text-amber-400/70">
        Displaying last known persistent state from SQLite
      </div>
    </div>
  );
};
