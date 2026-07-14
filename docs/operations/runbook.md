# Operations Runbook

## Health Check

```powershell
python -m coach_miranda_miner doctor
```

## Fixture Scan

```powershell
$env:DATA_MODE="fixture"
python -m coach_miranda_miner scan
```

## Scalp Scan

```powershell
python -m coach_miranda_miner scalp
```

## OI Watchlist

```powershell
python -m coach_miranda_miner oi
```

## Backtest

```powershell
python -m coach_miranda_miner backtest --symbol BTC/USD --timeframe 1h
```

## Dashboard

```powershell
streamlit run app.py
```

## Telegram Test

```powershell
python -m coach_miranda_miner telegram-test
```

If Telegram is not configured, the command should report the missing token/chat
ID instead of failing.

## SQLite Recovery

1. Stop scheduled workers.
2. Copy the current SQLite file.
3. Restore a known-good backup.
4. Run `doctor`.
5. Run one fixture scan before enabling scheduled alerts.
