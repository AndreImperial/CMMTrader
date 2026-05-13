# Coach Miranda Miner System

Coach Miranda Miner System is a crypto trading assistant scaffold. It is
designed to start in paper-trading mode, mine market signals, apply risk
controls, and log every decision with a clear reason.

The target architecture is documented in
[`docs/architecture.md`](docs/architecture.md).

The main build is free-first. It does not require OpenAI, CoinMarketCap,
CryptoPanic, or paid data feeds.

## What It Does

- Discovers routed crypto candidates from free public exchange tickers.
- Optionally pulls ranked assets from CoinMarketCap if you choose to add a key.
- Applies BTC regime and liquidity gatekeepers.
- Builds multi-timeframe intelligence packs.
- Optionally includes CryptoPanic headlines.
- Calculates RSI, MACD, ATR, and relative volume.
- Renders local chart images.
- Detects Bounce, Apex Squeeze, Transition Play, TABO, and Prison Break states
  with deterministic Python rules.
- Optionally sends Telegram alerts.
- Records decisions, theses, and paper fills to SQLite.

## Safety Defaults

This project does not place live trades by default. The default mode is:

```text
TRADING_MODE=paper
```

Do not add real API keys or enable live trading until the strategy has been
backtested and monitored in paper mode.

## Quick Start

Easiest option on Windows:

1. Double-click `Start Coach Miranda Miner.bat`.
2. Choose `Open web dashboard`.

You can also double-click `dashboard.bat` to open the browser platform directly.
It runs at:

```text
http://127.0.0.1:8502
```

For a one-click scan, double-click `quick_scan.bat`.

The menu can:

- run a health check
- open the web dashboard
- run one scan
- run a BTC backtest
- run the 15-minute loop
- switch between offline demo data and live free exchange data
- open the settings file

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m coach_miranda_miner scan
python -m coach_miranda_miner backtest --symbol BTC/USDT --timeframe 1h
python -m coach_miranda_miner loop --interval 900
python -m coach_miranda_miner doctor
python -m unittest discover
```

`DATA_MODE=fixture` is the default development mode. It uses deterministic
offline market data so the pipeline works even when exchange APIs are blocked or
unreachable.

To try live public exchange data, set this in `.env`:

```text
DATA_MODE=live
```

The default free updating mode is:

```text
DATA_MODE=paprika
DISCOVERY_MODE=exchange
ANALYZER_MODE=rule
```

If exchange domains work on your machine, you can also try direct exchange data:

```text
DATA_MODE=live
```

`paprika` mode uses updated free CoinPaprika prices and local intraday candle
scaffolding. If you want to try other free public sources:

```text
DATA_MODE=yahoo
DATA_MODE=coingecko
```

If internet is unavailable, use offline demo data:

```text
DATA_MODE=fixture
```

To enable free Telegram alerts, set:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

OpenAI, CoinMarketCap, and CryptoPanic are optional extras only. The core system
does not need them.

## Render Hosting

This repo includes `render.yaml` for Render Blueprint deployment.

Default hosted mode:

```text
DATA_MODE=paprika
ANALYZER_MODE=rule
TRADING_MODE=paper
```

Render start command:

```text
streamlit run coach_miranda_miner/dashboard.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

## Quality Controls

The free analyzer and validator use these safety knobs:

```text
MIN_CONFIDENCE=0.6
MIN_RISK_REWARD=1.5
MAX_STOP_ATR_MULTIPLE=3
BTC_KILL_SWITCH_DROP_PCT=3
MIN_VOLUME_24H_USD=50000000
```

The backtester includes basic trading friction:

```text
BACKTEST_FEE_BPS=10
BACKTEST_SLIPPAGE_BPS=5
BACKTEST_STOP_ATR_MULTIPLE=1.5
BACKTEST_TARGET_R_MULTIPLE=2
```

## Project Layout

```text
coach_miranda_miner/
  __main__.py          CLI entrypoint
  config.py            Environment/config loading
  data.py              Exchange candle fetching
  exchanges.py         Live and fixture exchange routers
  discovery.py         Candidate discovery
  gatekeepers.py       BTC regime and liquidity filters
  intelligence.py      Multi-timeframe indicator packs
  charts.py            Deterministic chart image rendering
  analyzer.py          Analyzer interface and rule-based placeholder
  validator.py         Thesis safety validation
  alerts.py            Alert formatting
  prompts.py           Optional AI prompt and schema contract
  backtest.py          Lightweight replay/backtest harness
  market_cap.py        Static and CoinMarketCap discovery providers
  news.py              Empty and CryptoPanic news providers
  telegram.py          Telegram alert sender
  indicators.py        RSI and moving averages
  miner.py             Signal mining logic
  risk.py              Risk controls
  broker.py            Paper broker
  journal.py           SQLite trade/decision journal
  coach.py             Orchestrates the system
```

## Next Steps

1. Add public open-interest adapters for Binance, Bybit, and OKX.
2. Add a small local dashboard.
3. Add strategy tests against saved candle fixtures.
4. Only then consider live execution.
