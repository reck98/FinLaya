export interface TradingSession {
  id: number | null;
  status: string;
  trading_date: string;
  started_at: string | null;
  ended_at?: string | null;
  selected_strike: number | null;
  expiry: string | null;
  lot_size: number;
  nifty_spot_at_start: number | null;
}

export interface MarketData {
  nifty_spot: number;
  nifty_open: number;
  nifty_high: number;
  nifty_low: number;
  nifty_prev_close: number;
  ce_ltp: number;
  pe_ltp: number;
  ce_bid: number;
  ce_ask: number;
  pe_bid: number;
  pe_ask: number;
  ce_volume: number;
  pe_volume: number;
  ce_oi: number;
  pe_oi: number;
  timestamp: string | null;
  updated_at: number;
}

export interface Position {
  side: "FLAT" | "LONG_CE" | "LONG_PE";
  instrument: string | null;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
}

export interface PnLPoint {
  timestamp: string;
  pnl: number;
}

export interface PnLData {
  realized: number;
  unrealized: number;
  total: number;
  history: PnLPoint[];
}

export interface LayaDecision {
  id?: number;
  session_id: number;
  action: "BUY" | "SELL" | "HOLD" | "NONE";
  confidence: number;
  position_before: string;
  position_after?: string;
  question_options: string[] | string;
  inference_latency_ms: number;
  accepted: boolean | number;
  result?: string;
  timestamp: string;
  state_json?: string;
}

export interface Order {
  id?: number;
  order_id?: number;
  session_id: number;
  instrument: string;
  side: "BUY" | "SELL";
  quantity: number;
  requested_price?: number;
  fill_price: number;
  status: string;
  source?: string;
  realized_pnl?: number | null;
  timestamp: string;
}

export interface EventLog {
  id?: number;
  timestamp: string;
  level: string;
  event_type: string;
  message: string;
  metadata_json?: string;
}

export interface TradingStats {
  laya_calls: number;
  buy_decisions: number;
  sell_decisions: number;
  hold_decisions: number;
  accepted_signals: number;
  position_switches: number;
  completed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_latency_ms: number;
  avg_confidence: number;
}

export interface SystemHealth {
  bot_status: "RUNNING" | "OFFLINE" | "WAITING";
  last_heartbeat_time: number;
  last_heartbeat_iso: string | null;
  market_data_status: "LIVE" | "STALE" | "WAITING";
  laya_status: "READY" | "OFFLINE" | "WAITING";
  database_status: "OK" | "ERROR";
  is_mock: boolean;
  seconds_since_heartbeat: number | null;
  seconds_since_market: number | null;
}

export interface DashboardSnapshot {
  session: TradingSession;
  market: MarketData;
  position: Position;
  pnl: PnLData;
  latest_decision: LayaDecision | null;
  recent_decisions: LayaDecision[];
  recent_orders: Order[];
  recent_events: EventLog[];
  stats: TradingStats;
  health: SystemHealth;
}

export interface WebSocketMessage {
  type:
    | "snapshot"
    | "market_update"
    | "laya_decision"
    | "position_update"
    | "pnl_update"
    | "order_update"
    | "event_log"
    | "system_status"
    | "heartbeat";
  data: any;
}
