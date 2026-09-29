# AGENT.MD — FinLaya System Rules & Developer Guidelines

> **Notice to AI Agents & Developers**:
> This document is the authoritative operating guide for FinLaya. Whenever you modify, debug, or extend this codebase, you **must** adhere strictly to the rules, invariants, and architectural constraints documented here. Update this file whenever new system capabilities or architectural changes are introduced.

---

## 1. Core Mission & Scope

**FinLaya** is an experimental quantitative **paper-trading research system** that uses the open-source **Laya decision model** running locally to generate directional decisions for NIFTY options from live market state.

### Absolute Safety Rules:
1. **PAPER TRADING ONLY**: There must NEVER be any code path that submits live financial orders to any broker or exchange. The execution interface (`PaperBroker`) must only simulate fills locally.
2. **NO HOSTED LLMs / NO PROSE**: FinLaya uses Laya strictly as a local typed choice decision engine. Never introduce external LLM API calls (OpenAI, Anthropic, Gemini, etc.), hosted inference services, or natural language prompt parsing.
3. **FAIL CLOSED**: If market status is closed, expiry cannot be resolved, broker lot size mismatches configuration, or market data is stale, the system **MUST abort or do nothing**. It must never guess or fabricate data.

---

## 2. Environment & Tooling Standards

* **Package Manager**: Use `uv` exclusively.
  * Virtual environment path: `.venv/`
  * Setup commands:
    ```bash
    uv venv
    uv sync --extra dev
    ```
  * Running commands: Always prefix with `uv run` (e.g. `uv run finlaya validate`, `uv run pytest tests -v`).
  * Never use `pip install`, `python -m venv`, `conda`, or `poetry`.
* **Python Version**: Supported Python is `>=3.11, <3.13` (current target: `3.12.7`).
* **Cross-Platform Console Encoding**:
  * On Windows, PowerShell and `cmd.exe` often use code page `cp1252`.
  * **Rule**: Never print raw unicode glyphs like `✔` (`\u2714`) or `✖` in terminal scripts. Always use ASCII indicators like `[OK]`, `[X]`, `[PASS]`, `[FAIL]`, or `[!]`.

---

## 3. Database Environment Separation

> [!IMPORTANT]
> **Strict Separation of Production vs Development/Test Databases**:
> * `data/finlaya.db`: The **production** paper-trading database. It must ONLY be written to when running the actual paper trading bot in live market hours. **Never run unit tests or offline simulations against `data/finlaya.db`**.
> * `data/finlaya_dev.db`: Used for offline developmental simulations (e.g. `scripts/run_simulation.py`).
> * `data/finlaya_test.db` or temporary directories (`tempfile.TemporaryDirectory`): Used for unit and integration testing.
> * All SQLite database files (`data/*.db`, `data/*.db-wal`, `data/*.db-shm`) are excluded from Git in `.gitignore`.

---

## 4. Quantitative Strategy & Market Invariants

### A. Fixed Near-the-Money Strike Selection
* At session open (`09:27:00 Asia/Kolkata`), fetch NIFTY spot price.
* Round to nearest 50-point strike using standard **round half-up**:
  ```python
  strike = int(math.floor(spot / step + 0.5) * step)
  ```
  *(Do not use Python's built-in `round()`, which rounds half to even and causes asymmetric rounding on odd multiples).*
* **Rule**: The selected strike is **immutable for the session**. Dynamic strike rolling is prohibited.

### B. Dynamic Expiry Verification
* Query Upstox option contracts metadata for underlying `NSE_INDEX|Nifty 50`.
* Extract all active expiry dates.
* **Expiry Day Rule**: If today in `Asia/Kolkata` is an authoritative expiry date, log `NIFTY_EXPIRY_DAY` and **abort immediately without trading**.
* Select the earliest future expiry strictly $> \text{today}$. If none exists, fail closed.

### C. Lot Size Verification
* Retrieve the actual broker contract `lot_size` from Upstox metadata.
* Compare with `expected_lot_size` (default `65`).
* If `enforce_expected_lot_size` is true and broker lot size $\neq$ expected lot size, log `LotSizeMismatchError` and **abort immediately**.

### D. Single-Lot Position Constraint
* Exactly one configured lot is traded.
* Permitted strategy states: `FLAT`, `LONG_CE`, `LONG_PE`.
* Never allow simultaneous CE and PE positions.
* No short selling, no options writing, no naked options, no multi-leg spreads, no averaging down, and no pyramiding.

### E. Timezone & Market Hours
* All timestamps and schedules **must explicitly use `ZoneInfo("Asia/Kolkata")`**.
* Never rely on the machine's naive local timezone.
* Trading start: `09:27:00 IST`.
* Forced exit: `15:13:00 IST`. At or after 15:13, cancel pending orders, close open positions, verify `FLAT`, and mark session completed.

---

## 5. Laya Decision Model Guidelines

### A. Model Specifications
* Official Hugging Face model: `convaiinnovations/laya`.
* Non-autoregressive typed choice classification in a single forward pass (~10–30ms).
* Load the model **once at startup** and warm up with a test health-check inference. Never reload every 0.5s.

### B. Typed Choice Prompts
* **When FLAT**: Criteria options are strictly `BUY` and `SELL`. (`HOLD` must NOT be offered).
* **When Active (LONG_CE / LONG_PE)**: Criteria options are `BUY`, `SELL`, and `HOLD`.

### C. Decision Schema & Confidence Threshold
```python
class LayaDecision(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float  # 0.0 <= confidence <= 1.0
```
* Threshold rule: `confidence >= threshold` (default `0.60`).
* Record confidence exactly as returned without mathematical transformation.
* **Fail Safe / Do Nothing**: On malformed output, timeout, or exception, evaluate to `None` and do nothing. Never guess.

---

## 6. Execution Simulation & Order Manager

### A. Fill Logic
* Paper orders must have explicit states: `PENDING`, `FILLED`, `CANCELLED`, `REJECTED`. Only `FILLED` changes strategy position.
* `BUY` orders fill at current `ask` (fallback to `ltp` if configured).
* `SELL` orders fill at current `bid` (fallback to `ltp` if configured).
* Simulated slippage against snapshot LTP and fill latency must be recorded.

### B. Atomic Position Transitions
Switching between option legs (`LONG_CE -> LONG_PE` or `LONG_PE -> LONG_CE`) is a two-phase operation protected by `asyncio.Lock()`:
1. Acquire strategy lock (suppress Laya calls and concurrent ticks).
2. Submit exit order for existing leg.
3. Wait for confirmed paper fill.
4. Verify existing quantity is 0 and intermediate position is `FLAT`.
5. Submit entry order for target leg.
6. Wait for confirmed paper fill.
7. Verify target quantity matches configured lot size and position is updated.
8. Release strategy lock.

---

## 7. Persistence & Observability

### SQLite Schema (`finlaya.db` / `finlaya_dev.db`)
* `trading_sessions`: Session metadata, fixed strike, expiry, lot size, status.
* `market_snapshots`: Exact live snapshot used for each Laya decision.
* `laya_decisions`: Prior position, question JSON, action, confidence, accepted flag, complete state JSON, inference latency in ms.
* `orders`: Order ID, session ID, instrument, side, quantity, requested price, fill price, status, pricing source.
* `positions`: Position changes, side, entry price, exit price, realized and unrealized P&L.
* `events`: System lifecycle logs with levels and metadata.

### Logging Rules
* Write structured logs to console (`stdout`) and rotating logs in `data/logs/finlaya_YYYYMMDD.log` and `.jsonl`.
* **Redaction**: Never log access tokens, API keys, or authorization headers. All matching regex patterns must be replaced with `[REDACTED]`.

---

## 8. Common Developer Workflows

### Run Test Suite
```bash
uv run pytest tests -v
```
All 39 unit and integration tests must pass.

### Run Environment Verification
```bash
uv run python scripts/verify_environment.py
```

### Validate Configuration & Setup
```bash
uv run finlaya validate
```

### Download / Verify Laya Model Weights
```bash
uv run python scripts/download_model.py
# or
uv run finlaya download-model
```

### Run Offline Development Simulation
```bash
uv run python scripts/run_simulation.py --db data/finlaya_dev.db
```

### Inspect Database Telemetry
```bash
# Production DB
uv run finlaya inspect-db
# Development / Simulation DB
uv run finlaya inspect-db --db-path data/finlaya_dev.db
# Standalone quantitative research script
uv run python scripts/inspect_database.py --db data/finlaya_dev.db
```

---

## 9. Extending FinLaya

When adding features in future work:
1. **Replay Market Data Provider**: Implement the `MarketDataProvider` protocol to feed historical ticks or 1m candle replays without modifying the strategy core.
2. **Additional Indicators**: Add mathematical functions to [`src/finlaya/market/indicators.py`](file:///E:/Development/PlayGround/FinLaya/src/finlaya/market/indicators.py). Ensure they return `None` when insufficient candles exist.
3. **Strategy Invariants**: Do NOT introduce stop-loss, take-profit, trailing stops, dynamic strike rolling, or options selling unless explicitly requested as a new experimental strategy branch.
4. **Always update `agent.md`** whenever modifying workflows, protocols, or database schemas.
