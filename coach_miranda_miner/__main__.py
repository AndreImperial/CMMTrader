from __future__ import annotations

import argparse
import time

from .coach import CoachMirandaMiner
from .config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coach_miranda_miner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run one paper-trading decision cycle")
    subparsers.add_parser("scan", help="Run one multi-asset signal scan")
    subparsers.add_parser("doctor", help="Check configuration and free-mode status")
    subparsers.add_parser("oi", help="Show high open-interest and volume watchlist")
    price = subparsers.add_parser("price", help="Fetch one live/updating price")
    price.add_argument("--symbol", default=None)
    alerts = subparsers.add_parser("alerts", help="Run Telegram alert scans forever")
    alerts.add_argument("--interval", type=int, default=None)
    loop = subparsers.add_parser("loop", help="Run scans forever on a fixed interval")
    loop.add_argument("--interval", type=int, default=None)
    backtest = subparsers.add_parser("backtest", help="Run a simple MA/RSI backtest")
    backtest.add_argument("--symbol", default=None)
    backtest.add_argument("--timeframe", default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    settings = Settings.from_env()
    coach = CoachMirandaMiner(settings)

    if args.command == "run":
        result = coach.run_once()
        print(result)
    if args.command == "scan":
        for index, message in enumerate(coach.scan(), start=1):
            if index > 1:
                print("\n" + ("-" * 72) + "\n")
            print(message)
    if args.command == "backtest":
        print(coach.backtest(args.symbol, args.timeframe).format())
    if args.command == "doctor":
        print(coach.doctor())
    if args.command == "oi":
        rows, warnings = coach.high_oi_watchlist()
        for warning in warnings[:5]:
            print(f"Warning: {warning}")
        for row in rows:
            oi = f"{row.open_interest_usd:,.0f}" if row.open_interest_usd is not None else "n/a"
            volume = f"{row.volume_24h_usd:,.0f}" if row.volume_24h_usd is not None else "n/a"
            print(
                f"{row.symbol} | {row.source} | OI USD: {oi} | "
                f"24h Volume: {volume} | {row.status}"
            )
    if args.command == "price":
        print(coach.price(args.symbol))
    if args.command == "alerts":
        interval = args.interval or settings.scan_interval_seconds
        while True:
            print(coach.scan_for_alerts())
            print(f"\nNext alert scan in {interval} seconds.")
            time.sleep(interval)
    if args.command == "loop":
        interval = args.interval or settings.scan_interval_seconds
        while True:
            for index, message in enumerate(coach.scan(), start=1):
                if index > 1:
                    print("\n" + ("-" * 72) + "\n")
                print(message)
            print(f"\nNext scan in {interval} seconds.")
            time.sleep(interval)


if __name__ == "__main__":
    main()
