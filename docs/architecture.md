# Coach Miranda Miner System Architecture

Coach Miranda Miner is a crypto signal and execution assistant. The system keeps
deterministic market math in code and uses AI only where visual/contextual
judgment is valuable.

## Core Principle

The backend owns facts, risk, math, routing, persistence, and execution. The AI
does not fetch data, invent prices, or bypass risk rules. The AI reads prepared
chart images and structured context, then returns a schema-validated trade thesis.

## Recommended Tooling

| Layer | Recommended Tool | Purpose |
| --- | --- | --- |
| Backend | Python 3.12+ | Async orchestration, data processing, execution services |
| Exchange abstraction | CCXT | OHLCV, markets, public/private exchange methods |
| Exchange-specific data | Binance/Bybit/OKX official APIs | Open interest, funding, derivatives details not always normalized |
| Dataframes | Polars or Pandas | Indicator calculations and candle transforms |
| Indicators | pandas-ta or custom vetted math | RSI, MACD, ATR, volume filters |
| Chart rendering | Plotly/Kaleido or Matplotlib/mplfinance | Deterministic chart images for vision analysis |
| Analysis | Deterministic Python rules by default | Setup classification, prison-break state, trade thesis |
| Schema validation | Pydantic | Validate model output before alerts/execution |
| Storage | SQLite first, Postgres later | Decisions, candles, fills, audits |
| Scheduling | APScheduler or async service loop | 15-minute discovery and analysis cycles |
| Alerts | Telegram Bot API | Human-readable setup alerts and execution links |
| Live execution | Separate broker service | Isolated, permissioned order placement |

## Current Implementation Modes

The current codebase supports two data modes:

- `DATA_MODE=fixture`: offline synthetic data for development and tests.
- `DATA_MODE=live`: public exchange data through CCXT.

The current codebase supports two analyzer modes:

- `ANALYZER_MODE=rule`: deterministic free analyzer.
- `ANALYZER_MODE=openai`: optional paid vision analyzer using chart images and
  strict JSON schema output.

The free default is `ANALYZER_MODE=rule` plus `DISCOVERY_MODE=exchange`.
CoinMarketCap, CryptoPanic, and OpenAI are optional extras. Telegram is optional
and free.

## Free Rule Analyzer

The rule analyzer detects:

- `bounce`: rejection near a support zone with at least 3 wick touches.
- `apex_squeeze`: range compression followed by breakout behavior.
- `transition_play`: RSI recovery plus bullish MACD context.
- `tabo`: trend continuation after breakout context.
- `none`: no clean setup.

Validation blocks execution unless:

- signal is `enter`
- risk/reward meets the configured minimum
- confidence meets the configured minimum
- long stops are below entry and long targets are above entry
- stop distance is not excessive versus ATR
- BTC regime allows longs

The 15m prison-break state is calculated from recent candles:

- `wait`: price remains inside consolidation.
- `watch`: first candle closes outside the pattern.
- `enter`: follow-through outside the pattern.
- `reject`: breakout fails back into the pattern.

## Backtesting

The free backtester now includes:

- fees
- slippage
- ATR-based stops
- R-multiple targets
- win rate
- profit factor
- expectancy
- max drawdown

## Pipeline

### 1. Discovery

Runs every 15 minutes.

- Fetch top crypto assets by market cap.
- Exclude stablecoins and low-liquidity instruments.
- Keep majors automatically.
- Scan remaining instruments for:
  - 24h open-interest expansion
  - 24h volume expansion
  - spread and liquidity quality
  - exchange availability

### 2. Gatekeepers

Hard-coded risk filters run before AI analysis.

- BTC market regime kill-switch.
- Stablecoin depeg filter.
- Exchange maintenance or symbol-disabled filter.
- Liquidity floor.
- Max spread filter.
- News veto pre-check for severe bearish events.

### 3. Intelligence Gathering

Runs concurrently per candidate.

- Fetch candles for `1d`, `4h`, `1h`, and `15m`.
- Fetch open interest, funding, and volume.
- Calculate indicators:
  - RSI
  - MACD
  - ATR
  - moving averages
  - relative volume
  - wick rejection metrics
- Fetch macro and coin-specific news.
- Render four chart images with the same visual style every time.

### 4. AI Vision Analysis

The AI receives:

- chart images
- indicator values
- support/resistance candidates from code
- news summary
- market regime
- allowed setup definitions
- required output schema

Allowed setups:

- `bounce`
- `apex_squeeze`
- `transition_play`
- `tabo`
- `none`

The AI must classify the setup, explain evidence, and return one of:

- `wait`
- `watch`
- `enter`
- `reject`

### 5. Validation

Code validates the AI response before alerting.

- JSON schema passes.
- Entry, stop, and targets are numeric.
- Risk/reward meets minimum threshold.
- Stop distance is realistic versus ATR.
- Entry state is not `enter` unless the 15m confirmation rule passes.
- Fundamental veto cannot be overridden by bullish chart structure.

### 6. Alerts And Execution

Default behavior is alert-only or paper-trading.

Live execution must be a separate mode with:

- explicit config flag
- exchange API key permissions limited to trading only
- max position limits
- daily loss limit
- kill switch
- full journal logging

## Prison Break Logic

The 15m chart controls entry timing.

| State | Meaning | Action |
| --- | --- | --- |
| Prison | Price is still inside consolidation | `wait` |
| Prison Break | Candle closes outside the pattern | `watch` |
| Confirmation | Follow-through or clean retest occurs | `enter` |
| Failed Break | Candle re-enters the pattern | `reject` |

## Structured AI Output

Every AI response should validate against a schema similar to:

```json
{
  "symbol": "BTC/USDT",
  "setup": "apex_squeeze",
  "signal": "watch",
  "direction": "long",
  "confidence": 0.72,
  "entry": 65000.0,
  "stop_loss": 63500.0,
  "targets": [67000.0, 69000.0],
  "risk_reward": 1.8,
  "invalidation_reason": null,
  "evidence": [
    "1h trendline has at least 3 touches",
    "15m candle closed above consolidation",
    "volume expanded on breakout"
  ],
  "news_veto": false
}
```

## Build Order

1. Replace the current simple scaffold with typed domain models.
2. Add exchange/data adapters.
3. Add deterministic indicator and gatekeeper filters.
4. Add chart rendering.
5. Add structured AI analyzer interface.
6. Add Telegram alerts.
7. Add paper trading.
8. Add backtests and replay mode.
9. Add live execution only after paper results are stable.
