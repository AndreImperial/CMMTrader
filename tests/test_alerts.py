from __future__ import annotations

import unittest

from coach_miranda_miner.alerts import AlertFormatter
from coach_miranda_miner.models import (
    Asset,
    Candidate,
    Setup,
    SignalState,
    TradeThesis,
    ValidationResult,
)


class AlertFormatterTests(unittest.TestCase):
    def test_alert_includes_grade_and_volume(self) -> None:
        candidate = Candidate(
            asset=Asset(symbol="BTC/USDT", base="BTC"),
            exchange_id="binance",
            route_symbol="BTC/USDT",
            reason="test",
            volume_24h_usd=1_500_000_000,
        )
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.WATCH,
            direction="long",
            confidence=0.72,
            entry=100.0,
            stop_loss=98.0,
            targets=[104.0],
            risk_reward=2.0,
        )
        alert = AlertFormatter().format(
            candidate,
            thesis,
            ValidationResult(approved=False, reasons=["Signal is watch."]),
        )
        self.assertIn("Grade: B", alert)
        self.assertIn("24h volume: $1.50B", alert)


if __name__ == "__main__":
    unittest.main()

