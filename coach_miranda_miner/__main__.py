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
    subparsers.add_parser("scalp", help="Run one ALMA/EMA/CCI scalp scan")
    subparsers.add_parser("doctor", help="Check configuration and free-mode status")
    subparsers.add_parser("oi", help="Show high open-interest and volume watchlist")
    price = subparsers.add_parser("price", help="Fetch one live/updating price")
    price.add_argument("--symbol", default=None)
    alerts = subparsers.add_parser("alerts", help="Run Telegram alert scans forever")
    alerts.add_argument("--interval", type=int, default=None)
    loop = subparsers.add_parser("loop", help="Run scans forever on a fixed interval")
    loop.add_argument("--interval", type=int, default=None)
    backtest = subparsers.add_parser("backtest", help="Run a strategy backtest")
    backtest.add_argument("--symbol", default=None)
    backtest.add_argument("--timeframe", default=None)
    backtest.add_argument("--strategy", choices=["miranda", "ma", "scalp"], default="miranda")
    backtest.add_argument("--side", choices=["both", "long", "short"], default="both")
    batch = subparsers.add_parser("backtest-batch", help="Backtest the current top universe")
    batch.add_argument("--limit", type=int, default=None)
    batch.add_argument("--timeframe", default="15m")
    batch.add_argument("--strategy", choices=["miranda", "ma", "scalp"], default="miranda")
    batch.add_argument("--side", choices=["both", "long", "short"], default="both")
    walk = subparsers.add_parser("walk-forward", help="Run train/test walk-forward validation")
    walk.add_argument("--symbol", default=None)
    walk.add_argument("--timeframe", default=None)
    walk.add_argument("--strategy", choices=["miranda", "ma", "scalp"], default="miranda")
    walk.add_argument("--side", choices=["both", "long", "short"], default="both")
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
    if args.command == "scalp":
        summary, results = coach.scan_scalps()
        for warning in summary.warnings[:5]:
            print(f"Warning: {warning}")
        for result in results:
            print(
                f"{result.candidate.route_symbol} | {result.thesis.signal.value.upper()} "
                f"{result.thesis.direction.upper()} | confidence {result.thesis.confidence:.2f} | "
                f"score {result.score.score:.1f} | entry {result.thesis.entry or 0:.6g}"
            )
    if args.command == "backtest":
        print(coach.backtest(args.symbol, args.timeframe, args.strategy, args.side).format())
    if args.command == "backtest-batch":
        rows = coach.batch_backtest(args.limit, args.timeframe, args.strategy, args.side)
        for row in rows:
            print(
                f"{row['symbol']} | trades {row['trades']} | win {row['win_rate']:.1%} | "
                f"return {row['return_pct']:.2f}% | expectancy {row['expectancy_pct']:.2f}% | "
                f"PF {row['profit_factor']:.2f} | L/S {row['long_trades']}/{row['short_trades']} | "
                f"best setup {row.get('best_setup') or 'n/a'}"
            )
    if args.command == "walk-forward":
        result = coach.walk_forward_backtest(args.symbol, args.timeframe, args.strategy, args.side)
        print(f"Walk-forward {result['symbol']} {result['timeframe']}")
        print(
            f"Train: trades {result['train'].trades} | expectancy "
            f"{result['train_expectancy_pct']:.2f}% | return {result['train'].total_return_pct:.2f}%"
        )
        print(
            f"Test: trades {result['test'].trades} | expectancy "
            f"{result['test_expectancy_pct']:.2f}% | return {result['test'].total_return_pct:.2f}%"
        )
        print(f"Expectancy degradation: {result['degradation_pct']:.2f}%")
    if args.command == "doctor":
        print(coach.doctor())
    if args.command == "oi":
        rows, warnings = coach.high_oi_watchlist()
        for warning in warnings[:5]:
            print(f"Warning: {warning}")
        for row in rows:
            oi = f"{row.open_interest_usd:,.0f}" if row.open_interest_usd is not None else "n/a"
            oi_change = (
                f"{row.open_interest_change_24h_pct:.2f}%"
                if row.open_interest_change_24h_pct is not None
                else "n/a"
            )
            volume = f"{row.volume_24h_usd:,.0f}" if row.volume_24h_usd is not None else "n/a"
            print(
                f"{row.symbol} | {row.source} | OI USD: {oi} | "
                f"OI 24h: {oi_change} | 24h Volume: {volume} | {row.status}"
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
