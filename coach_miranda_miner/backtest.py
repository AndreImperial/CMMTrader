from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import atr, moving_average, rsi


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    profit_factor: float
    expectancy_pct: float
    average_win_pct: float
    average_loss_pct: float

    def format(self) -> str:
        return (
            f"Backtest {self.symbol} {self.timeframe}\n"
            f"Trades: {self.trades} | Wins: {self.wins} | Losses: {self.losses}\n"
            f"Win rate: {self.win_rate:.2%}\n"
            f"Total return: {self.total_return_pct:.2f}%\n"
            f"Max drawdown: {self.max_drawdown_pct:.2f}%\n"
            f"Profit factor: {self.profit_factor:.2f}\n"
            f"Expectancy: {self.expectancy_pct:.2f}% per trade\n"
            f"Avg win/loss: {self.average_win_pct:.2f}% / {self.average_loss_pct:.2f}%"
        )


class MovingAverageBacktester:
    def __init__(
        self,
        short_ma: int,
        long_ma: int,
        rsi_period: int,
        rsi_buy_max: float,
        fee_bps: float,
        slippage_bps: float,
        stop_atr_multiple: float,
        target_r_multiple: float,
    ) -> None:
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.rsi_period = rsi_period
        self.rsi_buy_max = rsi_buy_max
        self.fee_rate = fee_bps / 10_000
        self.slippage_rate = slippage_bps / 10_000
        self.stop_atr_multiple = stop_atr_multiple
        self.target_r_multiple = target_r_multiple

    def run(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> BacktestResult:
        frame = candles.copy()
        frame["short_ma"] = moving_average(frame["close"], self.short_ma)
        frame["long_ma"] = moving_average(frame["close"], self.long_ma)
        frame["rsi"] = rsi(frame["close"], self.rsi_period)
        frame["atr"] = atr(frame, 14)

        in_position = False
        entry_price = 0.0
        stop_price = 0.0
        target_price = 0.0
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        wins = 0
        losses = 0
        returns: list[float] = []

        for row in frame.itertuples(index=False):
            if (
                pd.isna(row.short_ma)
                or pd.isna(row.long_ma)
                or pd.isna(row.rsi)
                or pd.isna(row.atr)
            ):
                continue

            if not in_position and row.short_ma > row.long_ma and row.rsi <= self.rsi_buy_max:
                in_position = True
                entry_price = float(row.close) * (1 + self.slippage_rate)
                risk = float(row.atr) * self.stop_atr_multiple
                stop_price = entry_price - risk
                target_price = entry_price + (risk * self.target_r_multiple)
                continue

            if in_position:
                exit_price = None
                if float(row.low) <= stop_price:
                    exit_price = stop_price * (1 - self.slippage_rate)
                elif float(row.high) >= target_price:
                    exit_price = target_price * (1 - self.slippage_rate)
                elif row.short_ma < row.long_ma:
                    exit_price = float(row.close) * (1 - self.slippage_rate)

                if exit_price is None:
                    peak = max(peak, equity)
                    drawdown = (peak - equity) / peak
                    max_drawdown = max(max_drawdown, drawdown)
                    continue

                trade_return = ((exit_price - entry_price) / entry_price) - (self.fee_rate * 2)
                equity *= max(0.0, 1 + trade_return)
                returns.append(trade_return)
                if trade_return > 0:
                    wins += 1
                else:
                    losses += 1
                peak = max(peak, equity)
                drawdown = (peak - equity) / peak
                max_drawdown = max(max_drawdown, drawdown)
                in_position = False

        trades = wins + losses
        win_rate = wins / trades if trades else 0.0
        gross_profit = sum(value for value in returns if value > 0)
        gross_loss = abs(sum(value for value in returns if value < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.0 if gross_profit > 0 else 0.0
        average_win = gross_profit / wins if wins else 0.0
        average_loss = gross_loss / losses if losses else 0.0
        expectancy = sum(returns) / trades if trades else 0.0
        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_return_pct=(equity - 1) * 100,
            max_drawdown_pct=max_drawdown * 100,
            profit_factor=float(profit_factor),
            expectancy_pct=expectancy * 100,
            average_win_pct=average_win * 100,
            average_loss_pct=average_loss * 100,
        )
