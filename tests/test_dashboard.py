from __future__ import annotations

import unittest

from coach_miranda_miner.dashboard import TRADINGVIEW_HEIGHT, _tradingview_widget


class DashboardTests(unittest.TestCase):
    def test_tradingview_widget_uses_fixed_height(self) -> None:
        html = _tradingview_widget("BTC/USD", "1h")

        self.assertIn(f'"height": {TRADINGVIEW_HEIGHT}', html)
        self.assertIn('"width": "100%"', html)
        self.assertNotIn('"autosize": true', html)


if __name__ == "__main__":
    unittest.main()
