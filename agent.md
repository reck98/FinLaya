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

### F. Upstox API v2 Integration Standards
* **API Version Argument**: Upstox REST endpoints such as `MarketQuoteApi.get_full_market_quote(symbol, api_version)` and `MarketQuoteApi.ltp(symbol, api_version)` require an explicit `api_version="2.0"` positional argument.
* **OpenAPI Model Response Parsing**: Response items returned in `resp.data` are instances of SDK OpenAPI models (e.g. `MarketQuoteSymbol` or `MarketQuoteSymbolLtp`). These objects do not provide a `.get()` method. Access attributes via `hasattr(item, "last_price")`, `.to_dict()`, or dictionary fallbacks.
* **LTP Fallback**: If full market quotes return empty or unparsable data, always fallback to `quote_api.ltp(symbol, api_version="2.0")` before raising an error.

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
* **Threshold Rule**: `confidence > threshold` (default `0.50`, strictly greater than threshold; $\le 0.50$ is rejected).
* **Softmax Choice Probabilities**: In Laya RL responses, calibrated policy confidence is often near zero, while `probabilities` contains the actual softmax choice distribution across criteria (e.g. `BUY: 0.4878, SELL: 0.5122`) and `answer_confidence` (`0.5122`). `LayaDecisionModel` extracts the choice probability as decision confidence. Signals are accepted only when `confidence > 0.50` (or configured threshold).
* **Historical Candle Seeding**: At session start, `UpstoxInstrumentService.fetch_historical_candles` seeds `CandleEngine` with 60 completed 1-minute candles (using `HistoryApi.get_intra_day_candle_data` and falling back to prior trading day's 1-minute data via `HistoryApi.get_historical_candle_data1`). This guarantees that all 15 technical indicators (`sma5/10/20`, `ema5/9/20`, `rsi14`, `macd/signal/hist`, `atr14`, `vwap`, `bb_upper/mid/lower`) calculate cleanly with zero nulls right from the first decision tick.
* **Fail Safe / Do Nothing**: On malformed output, timeout, or exception, evaluate to `None` and do nothing. Never guess.

### D. Verbose Inference Inspection (`log_full_inference`)
* When `laya.log_full_inference: true` in `config/config.yaml`, FinLaya renders a formatted ASCII panel in Terminal 1 for every decision cycle.
* Displays:
  1. Full market state snapshot (spot, quotes, spreads, OHLC, indicators).
  2. Deterministic typed choice questions and criteria dictionary.
  3. Raw Laya model response (choice, softmax choice probabilities, confidence, answer confidence, token usage).
  4. Decision evaluation outcome, latency, and FSM transition result.

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

### C. Graceful Shutdown (`Ctrl+C` / `SIGINT`)
* When terminated manually, `strategy.shutdown(reason="USER_INTERRUPT")`:
  1. Sets `_running = False` to break decision loop.
  2. Cancels pending paper orders and closes open positions to `FLAT`.
  3. Updates session status in SQLite database to `STOPPED` with current IST timestamp.
  4. Emits `status="STOPPED"` heartbeat on telemetry broadcaster.
  5. Cleanly disconnects Upstox WebSocket feeds and exits with code 0 without unhandled tracebacks.

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
* **Colored Console Formatter**: Terminal logs use distinct ANSI colors for components (`[strategy]`, `[state_machine]`, `[upstox_market_data]`), log levels (`[INFO]`, `[WARNING]`, `[ERROR]`), and event badges.
* **Visual Bifurcation**: Automatically prepends a blank newline space before each `[LAYA_INFERENCE]` decision cycle on console.
* **Disk Logs**: Writes clean, non-colored structured logs to `data/logs/finlaya_YYYYMMDD.log` and structured `.jsonl`.
* **Redaction**: Never log access tokens, API keys, or authorization headers. All matching regex patterns must be replaced with `[REDACTED]`.

---

## 8. Common Developer Workflows

### Run Test Suite
```bash
uv run pytest tests -v
```
All 53 unit and integration tests must pass.

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

---

## 10. Installed Agent Skills

The repository includes project-scoped skills installed via `npx skills` into `.agents/skills/`:

### A. Emil Kowalski Motion & UI Engineering Suite (`emilkowalski/skill`)
* `animate`: Decisions and implementations for fluid web motion, springs, and interactive transitions.
* `animate-expo`: React Native and Expo animation engine using Reanimated and Gesture Handler.
* `animation-vocabulary`: Reverse lookup glossary for motion design terminology.
* `apple-design`: Apple interface guidelines, fluid gestures, momentum, translucency, and spatial consistency.
* `ask-sonner`: Integration guide and troubleshooting for the Sonner toast notification library.
* `emil-design-eng`: UI polish, component feel, and micro-interactions philosophy.
* `find-animation-opportunities`: Audit codebase for static UI elements that benefit from motion.
* `improve-animations`: Motion critique and prioritization audit for existing animations.
* `mobile-native`: Web-to-native mobile polish (touch highlights, 100vh bugs, gesture handling).
* `pick-ui-library`: Evaluates and selects component libraries based on stack requirements.
* `prototype`: Rapid interactive prototyping patterns.
* `review-animations`: Code review checklist for physics, interruptibility, and 60fps execution.
* `write-swift`: Swift 6 concurrency, value types, and modern Swift best practices.

### B. Taste Skill Suite (`Leonxlnx/taste-skill`)
* `brandkit`: High-end brand guidelines, logo systems, and visual identity boards.
* `design-taste-frontend` & `v1`: Anti-slop frontend engineering for landing pages, web apps, and dashboards.
* `full-output-enforcement`: Overrides truncation behavior for complete, unabridged code generation.
* `gpt-taste`: Advanced UX/UI and GSAP motion engineering.
* `high-end-visual-design`: Premium typography, spacing, depth, and layout standards.
* `image-to-code`: Translates UI mockups and visual designs into clean frontend code.
* `imagegen-frontend-mobile`: Generates mobile screen concepts and app flows.
* `imagegen-frontend-web`: Generates section-by-section web design references.
* `industrial-brutalist-ui`: Swiss typographic print fused with military terminal aesthetics.
* `minimalist-ui`: Editorial layouts, warm monochrome palettes, typographic contrast, and bento grids.
* `redesign-existing-projects`: Upgrades existing user interfaces to premium standards without breaking functionality.
* `stitch-design-taste`: Semantic design system standards for Google Stitch.

### Managing Skills:
* Restore skills from lockfile: `npx skills experimental_install`
* Add additional skills: `npx skills add <owner>/<repo> -y`
* List installed skills: `npx skills list`
* Update skills: `npx skills update`

---

## 11. FinLaya Real-Time Trading Dashboard

FinLaya includes an independent, desktop-first real-time trading dashboard built with **FastAPI**, **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS v4**.

### A. Key Invariants & Safety
1. **STRICTLY READ-ONLY**: The dashboard does NOT have buy/sell/close buttons or endpoints. It cannot modify positions, submit orders, or call Laya directly.
2. **ZERO IMPACT ON 0.5s LOOP**: The bot communicates with the dashboard using non-blocking local UDP loopback (`127.0.0.1:8766`). Telemetry emissions take $< 0.01\text{ms}$. If the dashboard is not running or crashes, packets drop silently without delay.
3. **HEARTBEAT & LIVENESS**: The bot writes `data/runtime/heartbeat.json` and emits `heartbeat` events. If no heartbeat arrives for $> 3.0\text{s}$, the dashboard displays `BOT OFFLINE (Last heartbeat: Xs ago)`.

### B. Two-Terminal Workflow
* **Terminal 1 (FinLaya Bot)**:
  ```bash
  uv run finlaya run
  ```
  *(Continues standard structured terminal logging without interference).*
* **Terminal 2 (FinLaya Dashboard)**:
  ```bash
  uv run finlaya-dashboard
  ```
  *(Launches FastAPI server and serves the React dashboard on `http://127.0.0.1:8765`).*

### C. Available CLI Commands & Flags
* **Bot Commands**:
  * `uv run finlaya validate`: Validates `.env`, directories, and config.
  * `uv run finlaya download-model`: Caches Laya neural weights locally and runs startup warmup.
  * `uv run finlaya check-upstox`: Validates Upstox connectivity, spot quote, and option chain discovery.
  * `uv run finlaya run`: Starts the paper trading session (09:27 - 15:13 IST).
  * `uv run finlaya run --use-mock-laya`: Runs using `MockDecisionModel` instead of neural weights.
  * `uv run finlaya inspect-db`: Displays session summary and quantitative metrics.
* **Dashboard Commands**:
  * `uv run finlaya-dashboard`: Starts the server on default port `8765`.
  * `uv run finlaya-dashboard --port 8080`: Runs on custom port.
  * `uv run finlaya-dashboard --mock`: Starts in standalone mock simulation mode (`MOCK DATA`).
  * `uv run finlaya-dashboard --db-path data/finlaya_dev.db`: Points dashboard to dev database.

### D. Synthetic Simulation & Mock Mode
To develop, visually test, or demonstrate the dashboard without running the live trading bot or connecting to Upstox:
```bash
uv run finlaya-dashboard --mock
```
This activates `MockEventGenerator`, which streams realistic NIFTY ticks, option quotes, Laya decisions every 0.5s, position changes, and P&L curves. A prominent `MOCK DATA` badge is displayed in the status bar.

### E. Frontend Development & Build Commands
* Directory: `frontend/`
* Dev Server with Vite proxy:
  ```bash
  cd frontend
  npm run dev
  ```
* Production Build:
  ```bash
  cd frontend
  npm run build
  ```
  Built assets reside in `frontend/dist` and must be copied to `src/finlaya/dashboard/static` for self-contained serving.

### F. Testing the Dashboard
Run all backend dashboard and IPC unit tests:
```bash
uv run pytest tests/unit/test_dashboard_backend.py -v
```
