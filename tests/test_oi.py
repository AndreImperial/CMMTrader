from __future__ import annotations

import unittest

from coach_miranda_miner.oi import OpenInterestScanner


class FakeTicker:
    def __init__(self, last: float, quote_volume: float) -> None:
        self.last = last
        self.quote_volume = quote_volume


class FakeRouter:
    def fetch_ticker(self, exchange_id: str, symbol: str) -> FakeTicker:
        values = {
            "BTC/USD": FakeTicker(100.0, 1_000_000),
            "ETH/USD": FakeTicker(10.0, 500_000),
        }
        return values[symbol]


class OIScannerTests(unittest.TestCase):
    def test_volume_only_fallback_is_sorted(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["ETH", "BTC"])
        rows = scanner._volume_only_fallback()
        self.assertEqual(rows[0].symbol, "BTC/USD")
        self.assertEqual(rows[0].status, "Volume only; OI unavailable")
        self.assertIsNone(rows[0].open_interest_usd)


if __name__ == "__main__":
    unittest.main()

