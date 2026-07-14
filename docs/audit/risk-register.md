# Risk Register

Date: 2026-07-14

| Severity | Risk | Evidence | Impact | Next action |
| --- | --- | --- | --- | --- |
| Critical | Backtest results can look meaningful with too few trades. | Fixture BTC 1h backtest returned only 1 trade. | False confidence in strategy quality. | Add validation policy, minimum trade warnings, and stronger fixtures. |
| High | Invalid environment values can crash startup. | `Settings.from_env()` directly casts many env vars. | Hosted jobs or dashboard can fail at boot. | Add typed grouped configuration and validation. |
| High | Fixture mode is not fully offline for OI. | `DATA_MODE=fixture` OI command attempted OKX/Binance calls. | Tests and demos can be network-dependent. | Add fixture OI provider path. |
| High | Large modules concentrate business and UI logic. | `coach.py` 1284 lines, `dashboard.py` 1225 lines. | Higher regression risk and harder review. | Refactor after test coverage is expanded. |
| High | Documentation does not fully match runtime. | Architecture lists only `fixture` and `live`; config supports more modes. | Operator confusion. | Add current-state and configuration docs. |
| Medium | Dependency installs are not reproducible. | Minimum-only `requirements.txt` resolved to future major versions. | CI or deploy behavior can drift. | Add constraints/lock strategy. |
| Medium | Journal schema has no versioned migrations. | Tables are created inline with `CREATE TABLE IF NOT EXISTS`. | Future schema changes can be unsafe. | Add migration table and versioned migrations. |
| Medium | Test suite is green but not yet safety-complete. | 40 tests pass, no coverage baseline. | Critical trading assumptions may remain untested. | Add layered tests and coverage reporting. |
| Medium | Dashboard UI is difficult to evolve safely. | One large Streamlit module owns many workflows. | UX fixes risk behavior changes. | Introduce view models and page modules. |
| Low | Telegram is optional but unconfigured locally. | `telegram-test` reports missing credentials. | Expected in local audit; limits delivery testing. | Add mocked Telegram integration tests. |

## Live Trading Status

Live execution should remain disabled. The repository is suitable for continued
paper-mode and alert-mode improvement only until data quality, backtesting,
risk, alert lifecycle, and operations controls are substantially stronger.
