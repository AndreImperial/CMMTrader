# Current State

CMMTrader is currently a paper-mode crypto scanner, backtesting harness,
Telegram alerting tool, and Streamlit dashboard.

It supports:

- Fixture-mode deterministic demos.
- Free public-data modes including Coinbase, CoinPaprika, CoinGecko, Yahoo, and
  direct exchange APIs.
- Intraday setup scanning.
- ALMA/EMA/CCI scalp scanning.
- Open-interest and volume watchlists.
- SQLite journaling.
- Telegram alerts.
- Streamlit dashboard operation.
- Basic backtests and walk-forward checks.

It does not support live order execution, and live trading should remain
disabled.

## Phase Branches Pushed

- `agent/repository-audit`
- `agent/tooling-foundation`
- `agent/configuration-redesign`
- `agent/market-data-integrity`
- `agent/strategy-backtest-risk-validation`
- `agent/ui-architecture-foundation`
- `agent/documentation-release-readiness`

Open and merge these in order to reduce conflict risk.
