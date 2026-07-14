# Configuration

Configuration is environment-variable based.

Recommended profiles:

- `.env.fixture.example`
- `.env.local.example`
- `.env.paper.example`
- `.env.github-actions.example`
- `.env.render.example`

Important rules:

- `TRADING_MODE` should remain `paper`.
- `DATA_MODE=fixture` is deterministic and offline for demos.
- `DATA_MODE=coinbase` uses free public OHLCV candles without API keys.
- Telegram credentials are optional.
- Coinalyze is optional and only improves OI change data.
- Invalid numbers, booleans, modes, and timeframes should fail at startup after
  the configuration-validation phase is merged.

Do not commit real API keys or Telegram credentials.
