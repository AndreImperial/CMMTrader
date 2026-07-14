# Strategy Documentation Index

The deterministic analyzer currently recognizes these setup families:

- Bounce
- Apex Squeeze
- Transition Play
- TABO
- Prison Break timing states
- ALMA/EMA/CCI scalp

Each strategy still needs a full timestamp-level audit before being considered
validated. In particular, every strategy must prove:

- Signals use only candles available at the signal timestamp.
- ENTER decisions do not use future indicator values.
- Support and resistance windows do not include future bars.
- Multi-timeframe candles are aligned to the correct close time.
- Long and short variants have documented asymmetries.
- Backtests enter on a documented executable candle.

Until those checks are complete, strategy output should be treated as scanner
research and manual review material.
