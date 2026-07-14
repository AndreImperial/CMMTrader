# Backtesting Validation Policy

Backtests in this project are research evidence, not profitability guarantees.
A backtest may be useful for debugging execution assumptions while still being
too weak to approve a strategy.

## Minimum Evidence Before Calling A Strategy Validated

- At least 30 closed trades for a smoke validation, and more for production use.
- Separate in-sample and out-of-sample periods.
- Explicit next-bar or market-at-close execution policy.
- Documented stop-versus-target collision handling.
- Fees and slippage enabled.
- Result breakdown by symbol, timeframe, setup, direction, and market regime.
- No single symbol or single month should explain most of the result.
- Performance should survive reasonable fee and slippage sensitivity.
- Paper-trading results should be compared against backtest expectations.

## Current Status

The current backtester is useful for repeatable regression checks and rough
strategy comparison. It is not yet sufficient to approve live trading.

Backtest output now warns when:

- Trade count is below the validation threshold.
- No losing trades are observed.
- No winning trades are observed.

These warnings are intentionally conservative. A clean-looking result with one
trade is a smoke test, not evidence of edge.
