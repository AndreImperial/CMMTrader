# Command Matrix

Date: 2026-07-14

Commands were run after creating a local `.venv` and installing
`requirements.txt`.

| Command | Mode | Result | Notes |
| --- | --- | --- | --- |
| `python -m unittest discover` | local venv | Pass | 40 tests in about 2.5 seconds. |
| `python -m coach_miranda_miner doctor` | default | Pass | Reports Coinbase data mode, exchange discovery, rule analyzer, charts enabled, Telegram not configured. |
| `python -m coach_miranda_miner scan` | `DATA_MODE=fixture` | Pass | Produced deterministic WATCH LONG rows for fixture universe. |
| `python -m coach_miranda_miner scalp` | `DATA_MODE=fixture` | Pass | Produced WATCH LONG scalp rows; warned Coinalyze key unavailable. |
| `python -m coach_miranda_miner oi` | `DATA_MODE=fixture` | Pass with warnings | Still attempted external OI providers, then returned Coinbase volume-only fallback rows. |
| `python -m coach_miranda_miner telegram-test` | default | Pass | Correctly reported Telegram is not configured. |
| `python -m coach_miranda_miner backtest --symbol BTC/USD --timeframe 1h` | `DATA_MODE=fixture` | Pass | Returned one BTC/USDT trade; useful smoke test but not strategy evidence. |
| `python -c "from coach_miranda_miner.dashboard import main"` | default | Pass | Dashboard import smoke test passed. |
| `streamlit run app.py --server.headless true --server.port 8502` | default | Pass | Server started and advertised local URL `http://localhost:8502`. |

## Not Run

- Long-running `alerts` and `loop` commands were not left running during audit.
- Real Telegram delivery was not tested because credentials are not configured.
- Real exchange scans were not exhaustively tested because external endpoints
  can be region-blocked or rate-limited and should not be required for baseline
  CI.
