import { useEffect, useRef, useState, useCallback } from "react";
import type { DashboardSnapshot, WebSocketMessage } from "../types/dashboard";

const INITIAL_SNAPSHOT: DashboardSnapshot = {
  session: {
    id: null,
    status: "WAITING",
    trading_date: new Date().toISOString().split("T")[0],
    started_at: null,
    selected_strike: null,
    expiry: null,
    lot_size: 65,
    nifty_spot_at_start: null,
  },
  market: {
    nifty_spot: 0,
    nifty_open: 0,
    nifty_high: 0,
    nifty_low: 0,
    nifty_prev_close: 0,
    ce_ltp: 0,
    pe_ltp: 0,
    ce_bid: 0,
    ce_ask: 0,
    pe_bid: 0,
    pe_ask: 0,
    ce_volume: 0,
    pe_volume: 0,
    ce_oi: 0,
    pe_oi: 0,
    timestamp: null,
    updated_at: 0,
  },
  position: {
    side: "FLAT",
    instrument: null,
    quantity: 0,
    entry_price: 0,
    current_price: 0,
    unrealized_pnl: 0,
    realized_pnl: 0,
    total_pnl: 0,
  },
  pnl: {
    realized: 0,
    unrealized: 0,
    total: 0,
    history: [],
  },
  latest_decision: null,
  recent_decisions: [],
  recent_orders: [],
  recent_events: [],
  stats: {
    laya_calls: 0,
    buy_decisions: 0,
    sell_decisions: 0,
    hold_decisions: 0,
    accepted_signals: 0,
    position_switches: 0,
    completed_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate: 0,
    avg_latency_ms: 0,
    avg_confidence: 0,
  },
  health: {
    bot_status: "WAITING",
    last_heartbeat_time: 0,
    last_heartbeat_iso: null,
    market_data_status: "WAITING",
    laya_status: "WAITING",
    database_status: "OK",
    is_mock: false,
    seconds_since_heartbeat: null,
    seconds_since_market: null,
  },
};

export function useFinLayaSocket() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(INITIAL_SNAPSHOT);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);

  // 1. Initial REST Hydration
  const fetchSnapshot = useCallback(async () => {
    try {
      const res = await fetch("/api/snapshot");
      if (res.ok) {
        const data = await res.json();
        setSnapshot((prev) => ({
          ...prev,
          ...data,
        }));
      }
    } catch {
      // Ignore network errors during startup
    }
  }, []);

  // 2. WebSocket Connection Loop
  const connectWebSocket = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);

          if (msg.type === "snapshot") {
            setSnapshot(msg.data);
            return;
          }

          setSnapshot((prev) => {
            const next = { ...prev };

            if (msg.type === "market_update") {
              const spot = msg.data.nifty_spot || 0;
              let nOpen = prev.market.nifty_open;
              let nHigh = prev.market.nifty_high;
              let nLow = prev.market.nifty_low;

              if (spot > 0) {
                if (nOpen === 0) {
                  nOpen = spot;
                  nHigh = spot;
                  nLow = spot;
                } else {
                  nHigh = Math.max(nHigh, spot);
                  nLow = Math.min(nLow, spot);
                }
              }

              next.market = {
                ...prev.market,
                ...msg.data,
                nifty_open: nOpen,
                nifty_high: nHigh,
                nifty_low: nLow,
                updated_at: Date.now(),
              };
              next.health = {
                ...prev.health,
                market_data_status: "LIVE",
                seconds_since_market: 0,
              };
            } else if (msg.type === "laya_decision") {
              next.latest_decision = msg.data;
              next.recent_decisions = [msg.data, ...prev.recent_decisions].slice(0, 100);

              // Update stats
              const calls = prev.stats.laya_calls + 1;
              const buys = prev.stats.buy_decisions + (msg.data.action === "BUY" ? 1 : 0);
              const sells = prev.stats.sell_decisions + (msg.data.action === "SELL" ? 1 : 0);
              const holds = prev.stats.hold_decisions + (msg.data.action === "HOLD" ? 1 : 0);
              const accepted = prev.stats.accepted_signals + (msg.data.accepted ? 1 : 0);

              next.stats = {
                ...prev.stats,
                laya_calls: calls,
                buy_decisions: buys,
                sell_decisions: sells,
                hold_decisions: holds,
                accepted_signals: accepted,
                avg_latency_ms: Math.round(
                  (prev.stats.avg_latency_ms * (calls - 1) + msg.data.inference_latency_ms) / calls
                ),
                avg_confidence: Number(
                  ((prev.stats.avg_confidence * (calls - 1) + msg.data.confidence) / calls).toFixed(4)
                ),
              };
              next.health = {
                ...prev.health,
                laya_status: "READY",
              };
            } else if (msg.type === "position_update") {
              next.position = {
                ...prev.position,
                ...msg.data,
              };
              next.pnl = {
                ...prev.pnl,
                realized: msg.data.realized_pnl ?? prev.pnl.realized,
                unrealized: msg.data.unrealized_pnl ?? prev.pnl.unrealized,
                total: msg.data.total_pnl ?? prev.pnl.total,
                history: [
                  ...prev.pnl.history,
                  {
                    timestamp: new Date().toLocaleTimeString("en-IN", { hour12: false }),
                    pnl: msg.data.total_pnl ?? prev.pnl.total,
                  },
                ].slice(-300),
              };
            } else if (msg.type === "pnl_update") {
              next.pnl = {
                ...prev.pnl,
                realized: msg.data.realized_pnl ?? prev.pnl.realized,
                unrealized: msg.data.unrealized_pnl ?? prev.pnl.unrealized,
                total: msg.data.total_pnl ?? prev.pnl.total,
              };
              next.position = {
                ...prev.position,
                unrealized_pnl: msg.data.unrealized_pnl ?? prev.position.unrealized_pnl,
                total_pnl: msg.data.total_pnl ?? prev.position.total_pnl,
              };
            } else if (msg.type === "order_update") {
              next.recent_orders = [msg.data, ...prev.recent_orders].slice(0, 50);
            } else if (msg.type === "event_log") {
              next.recent_events = [msg.data, ...prev.recent_events].slice(0, 100);
            } else if (msg.type === "system_status") {
              next.health = {
                ...prev.health,
                ...msg.data,
              };
            } else if (msg.type === "heartbeat") {
              next.health = {
                ...prev.health,
                bot_status: msg.data.status || "RUNNING",
                last_heartbeat_iso: msg.data.timestamp,
                seconds_since_heartbeat: 0,
              };
              if (msg.data.session_id) {
                next.session = {
                  ...prev.session,
                  id: msg.data.session_id,
                };
              }
            }

            return next;
          });
        } catch {
          // Ignore parse errors
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        socketRef.current = null;
        // Exponential backoff reconnect
        const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 10000);
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = window.setTimeout(connectWebSocket, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Reconnect on catch
      reconnectTimeoutRef.current = window.setTimeout(connectWebSocket, 3000);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot();
    connectWebSocket();

    // 1-second interval to increment seconds_since indicators
    const timer = setInterval(() => {
      setSnapshot((prev) => ({
        ...prev,
        health: {
          ...prev.health,
          seconds_since_heartbeat:
            prev.health.seconds_since_heartbeat !== null
              ? prev.health.seconds_since_heartbeat + 1
              : null,
          seconds_since_market:
            prev.health.seconds_since_market !== null
              ? prev.health.seconds_since_market + 1
              : null,
        },
      }));
    }, 1000);

    return () => {
      clearInterval(timer);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [fetchSnapshot, connectWebSocket]);

  return { snapshot, wsConnected };
}
