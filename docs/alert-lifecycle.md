# Alert Lifecycle

The current alert system supports:

- Telegram alerts.
- Signal thresholds.
- Minimum alert grades.
- Alert cooldowns.
- Separate scalp and intraday budgets.
- Active setup tracking.
- Outcome refreshes.

Target lifecycle states:

- `DISCOVERED`
- `WAIT`
- `WATCH`
- `CONFIRMED`
- `ENTER`
- `INVALIDATED`
- `EXPIRED`
- `TARGET_HIT`
- `STOPPED`
- `MANUALLY_DISMISSED`

Stable setup identity should use:

```text
symbol + strategy + direction + timeframe + setup start time + strategy version
```

Entry price alone should not identify a setup because it can shift between scans.
