# Market Data

CMMTrader uses multiple public-data paths:

- Fixture synthetic candles.
- Coinbase public OHLCV candles.
- CoinPaprika live prices with local candle scaffolding.
- CoinGecko public market data.
- Yahoo Finance chart data.
- Direct exchange APIs through CCXT.
- Optional Coinalyze open-interest history.

Market-data work added in the phase branches introduces candle quality checks
for:

- Missing columns.
- Invalid timestamps.
- Duplicate candle timestamps.
- Out-of-order candles.
- Missing intervals.
- Invalid OHLC values.
- Negative volume.
- Too few candles.
- Stale latest candle warnings.

Fixture OI is synthetic and offline after the market-data phase is merged.
