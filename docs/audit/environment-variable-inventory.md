# Environment Variable Inventory

Date: 2026-07-14

Source: `coach_miranda_miner/config.py`, `.env.example`, `README.md`,
`render.yaml`, and `.github/workflows/persistent-alerts.yml`.

## Runtime Modes

- `TRADING_MODE`
- `DATA_MODE`
- `ANALYZER_MODE`
- `DISCOVERY_MODE`

## Optional API Keys

- `OPENAI_MODEL`
- `COINMARKETCAP_API_KEY`
- `CRYPTOPANIC_API_KEY`
- `COINALYZE_API_KEY`
- `COINALAYZE_API_KEY`
- `COINGLASS_API_KEY`

## Market Data And Discovery

- `EXCHANGE_IDS`
- `EXCHANGE_ID`
- `SYMBOL`
- `QUOTE_CURRENCY`
- `TIMEFRAME`
- `TIMEFRAMES`
- `CANDLE_LIMIT`
- `DISCOVERY_LIMIT`
- `DISCOVERY_POOL_LIMIT`
- `PREFILTER_LIMIT`
- `DEEP_SCAN_LIMIT`
- `SCAN_WORKERS`
- `FETCH_TIMEOUT_SECONDS`
- `PREFILTER_CANDLE_LIMIT`
- `MIN_MARKET_CAP_USD`

## Dashboard And Scheduling

- `AUTO_SCAN_ENABLED`
- `AUTO_SCAN_INTERVAL_SECONDS`
- `SCAN_INTERVAL_SECONDS`
- `RENDER_CHARTS`
- `CHART_DIR`
- `DASHBOARD_URL`

## Indicators And Strategy

- `SHORT_MA`
- `LONG_MA`
- `RSI_PERIOD`
- `RSI_BUY_MAX`
- `RSI_SELL_MIN`
- `MIN_CONFIDENCE`
- `MIN_RISK_REWARD`
- `MAX_STOP_ATR_MULTIPLE`
- `MAX_ATR_PCT`

## Risk And Paper Trading

- `STARTING_CASH`
- `MAX_POSITION_USD`
- `MAX_DAILY_LOSS_USD`
- `BTC_KILL_SWITCH_DROP_PCT`
- `MIN_VOLUME_24H_USD`

## Backtesting

- `BACKTEST_FEE_BPS`
- `BACKTEST_SLIPPAGE_BPS`
- `BACKTEST_STOP_ATR_MULTIPLE`
- `BACKTEST_TARGET_R_MULTIPLE`
- `BACKTEST_LIMIT`

## Persistence

- `JOURNAL_DB`

## Telegram Alerts

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_MIN_SIGNAL`
- `MIN_ALERT_GRADE`
- `REQUIRE_WATCH_BEFORE_ENTER`
- `ACTIVE_SETUP_TTL_MINUTES`
- `ALERT_COOLDOWN_MINUTES`
- `MAX_ALERTS_PER_SCAN`

## Scalper

- `MAX_SCALP_ALERTS_PER_SCAN`
- `SCALP_SCAN_LIMIT`
- `SCALP_UNIVERSE_LIMIT`
- `SCALP_CANDLE_LIMIT`
- `SCALP_MIN_VOLUME_24H_USD`
- `SCALP_ALERT_COOLDOWN_MINUTES`
- `SCALP_MIN_ATR_PCT`
- `SCALP_MAX_ATR_PCT`
- `SCALP_CROSS_FRESH_BARS`

## Open Interest

- `OI_BASES`
- `OI_LIMIT`

## Audit Notes

- The current settings object contains more than 60 fields.
- Numeric parsing currently happens directly in `Settings.from_env()`.
- Modes and thresholds should be validated before services are constructed.
- `.env.example`, Render, GitHub Actions, README, and code should be reconciled
  during the configuration redesign.
