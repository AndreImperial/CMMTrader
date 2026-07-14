# Current Architecture

Date: 2026-07-14

## Runtime Shape

The repository is a Python 3.11 Streamlit and CLI application. The current
public-data default is `DATA_MODE=coinbase`, `DISCOVERY_MODE=exchange`,
`ANALYZER_MODE=rule`, and `TRADING_MODE=paper`.

```text
app.py
└── coach_miranda_miner.dashboard

python -m coach_miranda_miner
└── coach_miranda_miner.__main__
    └── CoachMirandaMiner
```

## Main Components

| Component | Current role |
| --- | --- |
| `config.py` | Loads environment variables into one `Settings` dataclass. |
| `__main__.py` | CLI parser and command dispatcher. |
| `coach.py` | Central orchestration for scans, alerts, backtests, doctor output, and OI. |
| `exchanges.py` | Exchange routing and fixture/live market access. |
| `data.py` | Candle fetching helpers. |
| `discovery.py` | Candidate discovery and ranking. |
| `market_cap.py` | Static and CoinMarketCap-backed market-cap discovery. |
| `oi.py` | Open-interest and volume watchlist data. |
| `news.py` | Empty and CryptoPanic news providers. |
| `indicators.py` | RSI and moving-average helpers. |
| `analyzer.py` | Rule-based setup classification. |
| `scalper.py` | ALMA/EMA/CCI scalp scan logic. |
| `validator.py` | Thesis validation and risk/reward checks. |
| `risk.py` | Position sizing and paper risk controls. |
| `broker.py` | Paper broker behavior. |
| `journal.py` | SQLite persistence for decisions, fills, alerts, outcomes, active setups, and samples. |
| `alerts.py` | Alert formatting. |
| `telegram.py` | Telegram Bot API delivery. |
| `backtest.py` | Lightweight strategy replay/backtest harness. |
| `dashboard.py` | Streamlit UI, scans, charts, controls, summaries, and state handling. |

## Data Flow

```text
Settings
  -> CoachMirandaMiner
    -> discovery / exchange routers
    -> candle and ticker data
    -> indicators and rule analyzer
    -> validator and risk checks
    -> journal persistence
    -> alert formatter / Telegram
    -> CLI output or Streamlit dashboard
```

## Persistence

`Journal` creates these SQLite tables:

- `decisions`
- `fills`
- `ai_theses`
- `telegram_alerts`
- `setup_scores`
- `signal_outcomes`
- `active_setups`
- `candle_samples`

The schema is created directly from application code. There is no dedicated
migration system yet.

## Deployment

- Local Windows launchers: `Start Coach Miranda Miner.bat`, `dashboard.bat`,
  `quick_scan.bat`, `start.ps1`
- Render Blueprint: `render.yaml`
- Scheduled alerts: `.github/workflows/persistent-alerts.yml`

## Architecture Gaps

- Configuration, domain models, services, repositories, providers, and UI are
  not yet cleanly separated.
- `coach.py` is the main orchestration hub and is responsible for too many
  runtime concerns.
- `dashboard.py` mixes presentation, commands, data shaping, and workflow logic.
- Strategy functions are mostly deterministic, but timestamp and closed-candle
  guarantees need dedicated regression tests.
- Data provider fallback behavior exists, but the normalized data-quality
  contract is not yet explicit.
