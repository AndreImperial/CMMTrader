# Repository Audit

Date: 2026-07-14
Branch: `agent/repository-audit`

## Scope

This audit covers the current `CMMTrader` repository as cloned locally. It is a
read-only behavioral audit: no trading logic, strategy thresholds, alert rules,
or runtime defaults were changed.

## Inventory

- Tracked files: 55
- Python files: 42
- Test files: 14
- GitHub Actions workflows: 1
- Documented SQLite tables created by `Journal`: 8
- Primary app entry points:
  - `app.py`
  - `python -m coach_miranda_miner`
  - `Start Coach Miranda Miner.bat`
  - `dashboard.bat`
  - `quick_scan.bat`
  - `start.ps1`
- Largest project files:

| Lines | File |
| ---: | --- |
| 1284 | `coach_miranda_miner/coach.py` |
| 1225 | `coach_miranda_miner/dashboard.py` |
| 797 | `coach_miranda_miner/journal.py` |
| 721 | `coach_miranda_miner/analyzer.py` |
| 701 | `coach_miranda_miner/exchanges.py` |
| 505 | `coach_miranda_miner/backtest.py` |
| 473 | `coach_miranda_miner/scalper.py` |
| 332 | `coach_miranda_miner/oi.py` |
| 168 | `coach_miranda_miner/config.py` |

## Baseline Results

The first raw run from a fresh clone failed because dependencies were not
installed. After creating a local `.venv` and installing `requirements.txt`, the
baseline was:

| Check | Result |
| --- | --- |
| Python version | 3.11.9 |
| `python -m unittest discover` | Pass, 40 tests |
| `python -m coach_miranda_miner doctor` | Pass |
| `DATA_MODE=fixture python -m coach_miranda_miner scan` | Pass |
| `DATA_MODE=fixture python -m coach_miranda_miner scalp` | Pass |
| `DATA_MODE=fixture python -m coach_miranda_miner oi` | Pass with external-provider warnings |
| `python -m coach_miranda_miner telegram-test` | Pass, reports Telegram not configured |
| `DATA_MODE=fixture python -m coach_miranda_miner backtest --symbol BTC/USD --timeframe 1h` | Pass, 1 sample trade |
| Dashboard import smoke test | Pass |
| `streamlit run app.py --server.headless true --server.port 8502` | Starts successfully |

## Findings

### Critical: Backtest Evidence Is Too Thin For Strategy Claims

- Component: backtesting
- Evidence: fixture backtest returned one BTC/USDT 1h trade with 100% win rate,
  99.00 profit factor, and 0.66% return.
- Impact: a one-trade backtest is not meaningful evidence and can make the
  strategy look validated when it is not.
- Recommended correction: build a stronger backtesting standard with fixed
  historical fixtures, next-bar execution rules, cost sensitivity, trade-count
  warnings, out-of-sample reporting, and explicit validation policy.
- Suggested phase: Phase 6.

### High: Configuration Parsing Is Fragile

- Component: `coach_miranda_miner/config.py`
- Evidence: `Settings.from_env()` directly calls `int()` and `float()` across
  many environment variables, and accepts string modes without enum validation.
- Impact: malformed environment values can crash startup; unsupported modes can
  flow deeper into runtime before failing.
- Recommended correction: introduce grouped typed settings, enum validation,
  bounded numeric fields, and a richer doctor command.
- Suggested phase: Phase 3.

### High: Fixture Mode Still Uses External OI Providers

- Component: `coach_miranda_miner/oi.py`, `CoachMirandaMiner.high_oi_watchlist`
- Evidence: `DATA_MODE=fixture python -m coach_miranda_miner oi` attempted OKX
  and Binance derivatives requests before falling back to volume-only rows.
- Impact: fixture mode is not fully offline or deterministic for OI workflows.
  Tests and demos may depend on network behavior.
- Recommended correction: route fixture mode through deterministic OI fixtures,
  and label volume-only fallbacks separately from true OI results.
- Suggested phase: Phase 4 or Phase 11.

### High: Core Responsibilities Are Concentrated In Large Modules

- Component: `coach.py`, `dashboard.py`, `journal.py`, `analyzer.py`,
  `exchanges.py`
- Evidence: the two largest files exceed 1,200 lines each. `coach.py` combines
  orchestration, scan lifecycle, alert behavior, journaling decisions, and
  command-facing formatting. `dashboard.py` combines UI, settings, scan actions,
  charts, state, and presentation.
- Impact: changes are harder to test and review; UI changes can accidentally
  touch business logic.
- Recommended correction: extract services, view models, UI components, and
  repositories incrementally after behavior is covered by tests.
- Suggested phase: Phase 9 and Phase 12.

### High: Documentation Drift

- Component: `README.md`, `docs/architecture.md`
- Evidence: architecture says the current code supports only `fixture` and
  `live` data modes, while README and config include `coinbase`, `paprika`,
  `yahoo`, and `coingecko`.
- Impact: operators can follow stale instructions or misunderstand what is
  implemented versus aspirational.
- Recommended correction: split docs into current-state, setup, configuration,
  architecture, strategy, backtesting, alert lifecycle, deployment, and
  operations pages.
- Suggested phase: Phase 13.

### Medium: Dependency Versions Are Not Reproducible

- Component: `requirements.txt`
- Evidence: dependencies are minimum-only ranges such as `pandas>=2.2.0` and
  `streamlit>=1.36.0`. On 2026-07-14 this resolved to `pandas 3.0.3` and
  `streamlit 1.59.2`.
- Impact: future installs can pull behavior-changing versions without a repo
  change.
- Recommended correction: add `pyproject.toml`, dev dependencies, constraints or
  lock files, and CI checks.
- Suggested phase: Phase 2.

### Medium: Test Suite Is Green But Narrow

- Component: `tests/`
- Evidence: 40 tests pass. Coverage is concentrated on current unit behaviors,
  alert thresholds, scalper cases, validator behavior, and journal alert logic.
  Coverage tooling is not configured.
- Impact: green tests do not yet prove data integrity, backtest realism,
  concurrency, provider fallback correctness, or UI regressions.
- Recommended correction: add layered tests and coverage baselines for data,
  strategy timestamps, risk, backtesting, persistence, and dashboard view models.
- Suggested phase: Phase 10.

### Medium: Journal Schema Is Useful But Migration-Lite

- Component: `coach_miranda_miner/journal.py`
- Evidence: eight tables are created with `CREATE TABLE IF NOT EXISTS`; schema
  changes appear embedded in repository code rather than versioned migrations.
- Impact: future schema evolution can become risky for long-running hosted
  journals and GitHub Actions cache restoration.
- Recommended correction: add migration versioning and explicit setup/alert
  lifecycle event tables.
- Suggested phase: Phase 8.

### Medium: Dashboard Boots But Needs UX Redesign

- Component: `coach_miranda_miner/dashboard.py`
- Evidence: Streamlit starts successfully, but the file is 1,225 lines and mixes
  navigation, settings, scans, cards, charts, history, OI, backtesting, and
  status rendering.
- Impact: the UI is difficult to maintain and likely hard for an operator to
  scan quickly during market movement.
- Recommended correction: create a trading-operations information architecture,
  reusable components, and page modules.
- Suggested phase: Phase 12.

## Recommended PR 2 Scope

The next reviewable pull request should be the tooling foundation:

1. Add `pyproject.toml` with project metadata and tool configuration.
2. Add dev dependencies for `pytest`, `pytest-cov`, `ruff`, `pyright` or
   `mypy`, `bandit`, and `pip-audit`.
3. Add a constraints strategy so installs do not float unpredictably.
4. Add `.editorconfig` and optional pre-commit config.
5. Add CI that runs import smoke checks, tests, lint, and security scans.
6. Do not change trading behavior in this PR.
