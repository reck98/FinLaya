# FinLaya — Local Laya NIFTY Options Paper-Trading System

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Package Manager: uv](https://img.shields.io/badge/package_manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Mode: Paper Trading Only](https://img.shields.io/badge/mode-paper--trading--only-green.svg)](#paper-trading-disclaimer)
[![Model: Laya Local](https://img.shields.io/badge/model-convaiinnovations%2Flaya-orange.svg)](https://huggingface.co/convaiinnovations/laya)

**FinLaya** is an experimental quantitative paper-trading research system that uses the open-source **Laya decision model** running locally to generate `BUY`, `SELL`, and `HOLD` directional decisions for NIFTY options from live market state.

---

## 1. What FinLaya Is

FinLaya is a deterministic, observable options execution simulator designed for quantitative research. It connects to live market data feeds from Upstox, synthesizes rolling 1-minute OHLCV candles and technical indicators, queries a locally hosted non-autoregressive decision model (Laya) at a 0.5-second cadence, and executes simulated paper trades on a single near-the-money contract pair (CE and PE) using an atomic two-phase finite-state machine.

Every decision, state snapshot, order, simulated fill, and latency metric is persisted to an indexed SQLite database to support post-session quantitative evaluation.

---

## 2. Architecture

```text
               Upstox API v2 / v3
          ┌─────────────┴─────────────┐
          │                           │
  [REST Metadata & Expiry]    [WebSocket Feeder V3]
          │                           │
          ▼                           ▼
[Instrument Discovery]       [Market Data Cache]
 (Strike & Expiry Locked)             │
          │                   ┌───────┴───────┐
          │                   ▼               ▼
          │            [Candle Engine] [Technical Indicators]
          │                   │               │
          └───────────────┬───┴───────────────┘
                          ▼
              [Feature Engine Snapshot]
                          │
                          ▼
            [Local Laya Decision Model]
              (Typed Choice Classifier)
                          │
                          ▼
              [Strategy State Machine]
                          │
                          ▼
          [Atomic Order & Transition Manager]
                          │
                          ▼
              [Paper Execution Broker]
              (Bid/Ask Matching + LTP)
                          │
                          ▼
               [SQLite Persistence Layer]
            (finlaya.db + Structured Logs)
```

The system is strictly decoupled into distinct layers:
* **Broker & Instruments**: Validates market open, retrieves NIFTY spot, calculates nearest 50-point strike, checks expiry days, and verifies lot sizes.
* **Market Data & Features**: Aggregates ticks into rolling 1-minute candles, calculates indicators (SMA, EMA, RSI, MACD, ATR, VWAP, Bollinger Bands), and builds immutable snapshots.
* **Laya Decision Model**: Preloaded in memory; runs local typed choice inference with zero hosted LLM dependencies.
* **Strategy & State Machine**: Implements single-lot directional positions (`FLAT`, `LONG_CE`, `LONG_PE`) with atomic two-phase transitions.
* **Execution & Risk**: Matches market orders against live quotes (ask for BUY, bid for SELL), calculates simulated slippage, and enforces single-lot constraints.
* **Persistence & Observability**: Stores complete research telemetry in SQLite and outputs structured JSON-lines logs.

---

## 3. Trading Strategy Rules

1. **Fixed Near-the-Money Strike**:
   * At `09:27:00 Asia/Kolkata`, the live NIFTY 50 spot price is obtained and rounded to the nearest 50-point strike using standard round half-up:
     $$\text{Strike} = \left\lfloor \frac{\text{Spot}}{50} + 0.5 \right\rfloor \times 50$$
   * This strike is **fixed and immutable** for the entire trading session. The system never rolls strikes dynamically.
2. **Contract Pair Discovery**:
   * The CE and PE contracts corresponding to the selected strike and the nearest future expiry are resolved dynamically via Upstox metadata.
3. **No Expiry-Day Trading**:
   * If today is an authoritative NIFTY expiry day according to Upstox contract metadata, the system logs `NIFTY_EXPIRY_DAY` and **aborts immediately without trading**.
4. **Position States**:
   * Only three states exist: `FLAT`, `LONG_CE`, and `LONG_PE`.
   * Exactly **one configured lot** is traded. No averaging, pyramiding, naked options, or multi-leg positions are permitted.
5. **Decision Cadence & Transitions**:
   * Decisions are evaluated every 0.5 seconds using a drift-free monotonic clock scheduler.
   * **FLAT**: Laya is asked to choose between `BUY` and `SELL`.
     * `BUY` ($\ge 0.60$ confidence) $\rightarrow$ Enter `LONG_CE`.
     * `SELL` ($\ge 0.60$ confidence) $\rightarrow$ Enter `LONG_PE`.
     * Below threshold $\rightarrow$ Remain `FLAT` and continue polling.
   * **LONG_CE**: Laya is asked to choose between `BUY`, `SELL`, and `HOLD`.
     * `BUY` or `HOLD` $\rightarrow$ Remain `LONG_CE` (no order submitted).
     * `SELL` ($\ge 0.60$ confidence) $\rightarrow$ Atomically exit CE, verify `FLAT`, enter PE, verify `LONG_PE`.
   * **LONG_PE**: Laya is asked to choose between `BUY`, `SELL`, and `HOLD`.
     * `SELL` or `HOLD` $\rightarrow$ Remain `LONG_PE` (no order submitted).
     * `BUY` ($\ge 0.60$ confidence) $\rightarrow$ Atomically exit PE, verify `FLAT`, enter CE, verify `LONG_CE`.
6. **Forced Exit**:
   * At `15:13:00 Asia/Kolkata`, decision generation stops immediately. Local pending orders are cancelled, open positions are squared off to `FLAT`, and the session is marked completed.

---

## 4. Laya Model Integration

FinLaya integrates the official open-source **Laya** model:
* **Repository**: [https://github.com/NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)
* **Model Family**: [https://huggingface.co/convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya)

### Key Characteristics:
* **Non-Autoregressive System 1 Inference**: Unlike generative LLMs that predict token by token, Laya computes probability distributions over defined choices in a single forward pass (~10–30ms on GPU, ~30–50ms on CPU).
* **Strict Typed Output**: The model output is strictly parsed into:
  ```python
  class LayaDecision(BaseModel):
      action: Literal["BUY", "SELL", "HOLD"]
      confidence: float  # 0.0 <= confidence <= 1.0
  ```
* **No Natural Language / No Hallucinations**: Prompt templates define discrete choice criteria. No prose is generated or parsed.
* **Fail Safe / Do Nothing**: If inference encounters a timeout, exception, or malformed score, the decision evaluates to `None` and the system does nothing.
* **Model Preloading**: The model is loaded once at startup and pre-warmed with a health-check inference before market hours.

---

## 5. Upstox Integration

Upstox APIs provide authoritative market and instrument data:
* **Upstox Developer Portal**: [https://upstox.com/developer/api-documentation/](https://upstox.com/developer/api-documentation/)
* **Option Contracts API**: [GET /v2/option/contract](https://upstox.com/developer/api-documentation/#tag/Options)
* **Market Data Feed V3**: WebSocket streaming with Protobuf encoding and automatic dictionary decoding via `MarketDataStreamerV3`.
* **Lot Size Verification**: Retrieves actual lot sizes directly from broker metadata (e.g. 65 or 75) and verifies against `expected_lot_size` in config. Mismatches trigger a safe abort.

---

## 6. Paper-Trading Disclaimer

> [!CAUTION]
> **PAPER TRADING ONLY — EXPERIMENTAL RESEARCH SYSTEM**
> 
> * FinLaya is strictly a **simulation and research tool**.
> * There is **NO code path** in this repository that submits live financial orders to any exchange or broker.
> * All order execution is simulated locally by `PaperBroker` matching against real-time bid/ask quotes and LTP.
> * Model confidence scores must **NOT** be interpreted as guaranteed win rates or financial advice.
> * Do not use this software for live capital trading.

---

## 7. Installation & uv Setup

FinLaya uses [`uv`](https://github.com/astral-sh/uv) for fast, deterministic Python virtual environments and dependency management.

### Prerequisites
* Windows 10/11, macOS, or Linux
* Python 3.12 (supported: `>=3.11, <3.13`)
* `uv` installed (`pip install uv` or via standalone installer)

### Setup Commands
```bash
# 1. Clone or navigate to the repository
cd FinLaya

# 2. Create the virtual environment (.venv)
uv venv

# 3. Synchronize dependencies and lockfile
uv sync --extra dev
```

---

## 8. Environment Variables

Copy the example environment template to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your Upstox API credentials:
```bash
# Obtain from https://upstox.com/developer/api-documentation/
UPSTOX_ACCESS_TOKEN=your_upstox_access_token_here
UPSTOX_API_KEY=your_upstox_api_key_here
UPSTOX_API_SECRET=your_upstox_api_secret_here

# Optional: custom Hugging Face model cache
# HF_HOME=
```

> [!IMPORTANT]
> The `.env` file is excluded in `.gitignore`. Secrets and authorization tokens are automatically redacted by the structured logger and are never committed to version control.

---

## 9. Model Download

Pre-cache the official Laya weights locally before running live sessions:
```bash
uv run python scripts/download_model.py
```
Or via CLI:
```bash
uv run finlaya download-model
```

---

## 10. Configuration

All strategy parameters are declared in [`config/config.yaml`](file:///E:/Development/PlayGround/FinLaya/config/config.yaml):

```yaml
project:
  name: FinLaya
  timezone: Asia/Kolkata

trading:
  start_time: "09:27:00"
  force_exit_time: "15:13:00"
  lots: 1
  expected_lot_size: 65
  enforce_expected_lot_size: true
  strike_step: 50
  lot_size_source: "broker"

strategy:
  decision_interval_seconds: 0.5
  confidence_threshold: 0.60

market_data:
  candle_interval: "1minute"
  historical_candles: 6
  max_staleness_seconds: 2.0

laya:
  model: "convaiinnovations/laya"
  device: "auto"
  confidence_threshold: 0.60

paper_trading:
  enabled: true
  price_fallback: "ltp"

database:
  path: "data/finlaya.db"

logging:
  level: "INFO"
  directory: "data/logs"
```

---

## 11. How to Start FinLaya (Trading Bot)

FinLaya runs as a deterministic, observable quantitative trading process in **Terminal 1**.

### Step 1: Pre-Session Validation
Verify your virtual environment, dependencies, directories, and configuration:
```bash
uv run finlaya validate
```

### Step 2: Download & Cache Model Weights
Download the official open-source Laya weights (`convaiinnovations/laya`) locally into memory/cache:
```bash
uv run finlaya download-model
```

### Step 3: Upstox Connectivity & Option Chain Discovery
Verify that your `UPSTOX_ACCESS_TOKEN` is active, the exchange is open, and option contracts are resolvable:
```bash
uv run finlaya check-upstox
```

### Step 4: Launch the Live Paper-Trading Session
```bash
uv run finlaya run
```
* **Trading Start**: `09:27:00 Asia/Kolkata`
* **Forced Exit**: `15:13:00 Asia/Kolkata`
* Terminal 1 will stream structured live logs with sub-millisecond precision.

#### Available Bot Options:
* `uv run finlaya run --config-path <path>`: Custom configuration file (default: `config/config.yaml`).
* `uv run finlaya run --use-mock-laya`: Runs using `MockDecisionModel` instead of neural weights (ideal for local testing).

---

## 12. How to Start the Real-Time Dashboard

FinLaya includes an independent, desktop-first real-time trading dashboard built with **FastAPI**, **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS v4**.

The dashboard runs independently in **Terminal 2** and communicates with the trading bot over zero-latency local loopback UDP (`127.0.0.1:8766`).

### Start the Dashboard Server:
In a separate terminal window:
```bash
uv run finlaya-dashboard
```
Open your browser and navigate to:
```
http://127.0.0.1:8765
```

### Available Dashboard Flags:
| Flag | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--port` | `-p` | HTTP & WebSocket port to listen on | `8765` |
| `--host` | `-h` | Host network interface to bind | `127.0.0.1` |
| `--mock` | | Launch with synthetic real-time event generator (`MOCK DATA`) | `false` |
| `--production` | | Serve pre-compiled React frontend bundle | `false` |
| `--db-path` | | Path to SQLite paper-trading database | `data/finlaya.db` |

---

## 13. The Two-Terminal Workflow

The standard operational workflow runs FinLaya across two independent terminals:

### Terminal 1 — Trading Bot:
```bash
uv run finlaya run
```
* Shows live structured trading logs:
  ```text
  09:27:00 INFO  FinLaya paper-trading system starting...
  09:27:00 INFO  NIFTY spot: 23456.25 -> Selected Strike: 23450
  09:27:00 INFO  CE: NIFTY26OCT23450CE, PE: NIFTY26OCT23450PE
  09:27:00 INFO  Laya decision loop started (0.5s interval)
  09:27:00 INFO  Laya Decision: BUY (conf=0.7420, latency=18.4ms)
  09:27:00 INFO  Paper order #1 FILLED: BUY 65x NIFTY26OCT23450CE @ 151.20
  09:27:00 INFO  Position: LONG_CE
  ```

### Terminal 2 — Real-Time Dashboard:
```bash
uv run finlaya-dashboard
```
* Serves the real-time observability terminal at `http://127.0.0.1:8765`.
* Displays live NIFTY ticks, CE/PE quotes, Laya decision confidence, position status, P&L curve, and execution log.
* If the bot stops or crashes, the dashboard detects heartbeat loss after 3 seconds and displays `BOT OFFLINE (Last heartbeat: Xs ago)`.

---

## 14. Offline Simulation & Mock Modes

You can run and test both the bot and dashboard offline outside market hours without an Upstox access token:

### Option A: Standalone Mock Dashboard
Run the dashboard with synthetic real-time market data and simulated Laya decisions:
```bash
uv run finlaya-dashboard --mock
```
* Instantly generates live NIFTY ticks wandering around 23,450, simulated CE & PE option depth, Laya decisions every 0.5s, position changes, and live P&L curve.
* A high-visibility `MOCK DATA` badge is displayed in the status bar.

### Option B: Offline Bot Simulation Script
Run the scripted 6-tick end-to-end simulation against `data/finlaya_dev.db`:
```bash
uv run python scripts/run_simulation.py
```
* If `uv run finlaya-dashboard` is open in Terminal 2, it will automatically receive live simulation telemetry via UDP loopback!

---

## 15. Inspecting Research Telemetry

FinLaya captures detailed telemetry in SQLite (`data/finlaya.db`) for quantitative analysis.

Run the inspection utility:
```bash
uv run finlaya inspect-db
```
Or inspect a development database:
```bash
uv run finlaya inspect-db --db-path data/finlaya_dev.db
```
Or use the standalone quantitative analysis script:
```bash
uv run python scripts/inspect_database.py --db data/finlaya_dev.db
```

### Sample Output:
```text
=== FinLaya Database: data/finlaya_dev.db ===
Total Trading Sessions: 1

=== Quantitative Telemetry: Session #1 (2026-09-29) ===
+--------------------------------+-------------------+
| Research Metric                | Result            |
|--------------------------------+-------------------|
| Total Decisions Generated      | 5                 |
| BUY Decisions                  | 2                 |
| SELL Decisions                 | 1                 |
| HOLD Decisions                 | 2                 |
| Average Model Confidence       | 73.00%            |
| Direction Switches (Reversals) | 1                 |
| Avg Inference Latency          | 15.00 ms          |
| Min / Max Latency              | 15.0 ms / 15.0 ms |
| Total Orders Submitted         | 4                 |
| Filled Orders                  | 4                 |
| Average Simulated Slippage     | 0.50 pts          |
| Max Simulated Slippage         | 0.50 pts          |
| Final Realized P&L             | +1170.00          |
+--------------------------------+-------------------+
```

---

## 16. Database Schema

The SQLite database (`data/finlaya.db`) contains six core tables with indexes:
* `trading_sessions`: Session dates, start/end timestamps, spot at start, fixed strike, expiry, CE/PE keys, lot sizes, and final status.
* `market_snapshots`: Exact state snapshot used for each Laya decision (NIFTY spot, CE/PE quotes, depth, volumes, OI).
* `laya_decisions`: Session ID, timestamp, prior position, question options JSON, chosen action, confidence, accepted flag, complete state JSON, and inference latency in milliseconds.
* `orders`: Order ID, session ID, instrument, side (BUY/SELL), quantity, order type, requested price, fill price, status (FILLED/REJECTED/CANCELLED), and pricing source.
* `positions`: Timestamped position updates, instrument, side (`FLAT`, `LONG_CE`, `LONG_PE`), entry price, exit price, realized P&L, and unrealized P&L.
* `events`: System lifecycle events, component names, log levels, messages, and metadata.

---

## 17. Testing Suite

FinLaya has an extensive automated test suite covering unit behaviors, state machines, atomic transitions, and end-to-end simulations with 100% pass rate:

```bash
uv run pytest tests -v
```

### Coverage:
* `test_strike_selector.py`: Strike rounding (half-up) and immutable session strike locks.
* `test_expiry_check.py`: Expiry extraction, fail-closed behavior on expiry days, and target expiry selection.
* `test_lot_size.py`: Broker metadata vs expected lot size enforcement.
* `test_laya_schemas.py`: Schema validation, confidence boundaries, question builders, and error fallbacks.
* `test_state_machine.py`: Every valid and invalid state transition for `FLAT`, `LONG_CE`, and `LONG_PE`.
* `test_indicators.py`: Calculation of SMA, EMA, RSI, MACD, ATR, VWAP, and Bollinger Bands with null fallbacks.
* `test_paper_broker.py`: Simulated fills (ask for BUY, bid for SELL, LTP fallback) and P&L tracking.
* `test_trading_clock.py`: IST session phases and schedules.
* `test_risk_engine.py`: Single-lot and no-pyramiding constraints.
* `test_atomic_transitions.py`: Asynchronous two-phase switching (`LONG_CE -> FLAT -> LONG_PE` and vice versa).
* `test_end_to_end_simulation.py`: Full mock session lifecycle with complete SQLite persistence.

---

## 18. Official Resources & References

* **Laya GitHub**: [https://github.com/NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)
* **Laya Hugging Face**: [https://huggingface.co/convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya)
* **Upstox Developer API**: [https://upstox.com/developer/api-documentation/](https://upstox.com/developer/api-documentation/)
* **Upstox Option Contracts API**: [https://upstox.com/developer/api-documentation/#tag/Options](https://upstox.com/developer/api-documentation/#tag/Options)
* **Upstox Market Data Feed V3**: [https://upstox.com/developer/api-documentation/#tag/Websocket](https://upstox.com/developer/api-documentation/#tag/Websocket)
* **Astral uv Package Manager**: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
