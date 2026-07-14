# Limitations

- Backtests are not yet sufficient to approve live trading.
- Fixture data is synthetic and should never be interpreted as market evidence.
- CoinPaprika mode uses live prices but local candle scaffolding.
- Hosted environments can block public exchange endpoints.
- The dashboard is improved only in the UI foundation branch; deeper component
  decomposition is still needed.
- Journal schema migration versioning is still future work.
- Risk management is not yet portfolio-aware.
- Telegram callbacks must not be allowed to place live trades.
- Live trading remains disabled.
