from __future__ import annotations

import os
import unittest

from coach_miranda_miner.config import Settings


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["COINALYZE_API_KEY"] = ""
        os.environ["COINALAYZE_API_KEY"] = ""
        for name in [
            "PREFILTER_LIMIT",
            "DISCOVERY_LIMIT",
            "DEEP_SCAN_LIMIT",
            "SCAN_WORKERS",
            "FETCH_TIMEOUT_SECONDS",
            "PREFILTER_CANDLE_LIMIT",
            "AUTO_SCAN_ENABLED",
            "AUTO_SCAN_INTERVAL_SECONDS",
            "SCAN_INTERVAL_SECONDS",
            "TELEGRAM_MIN_SIGNAL",
            "MIN_ALERT_GRADE",
            "BACKTEST_LIMIT",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "SCALP_SCAN_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "SCALP_MIN_VOLUME_24H_USD",
        ]:
            os.environ.pop(name, None)
        os.environ["DISCOVERY_LIMIT"] = "100"

    def tearDown(self) -> None:
        for name in [
            "COINALYZE_API_KEY",
            "COINALAYZE_API_KEY",
            "PREFILTER_LIMIT",
            "DISCOVERY_LIMIT",
            "DEEP_SCAN_LIMIT",
            "SCAN_WORKERS",
            "FETCH_TIMEOUT_SECONDS",
            "PREFILTER_CANDLE_LIMIT",
            "AUTO_SCAN_ENABLED",
            "AUTO_SCAN_INTERVAL_SECONDS",
            "SCAN_INTERVAL_SECONDS",
            "TELEGRAM_MIN_SIGNAL",
            "MIN_ALERT_GRADE",
            "BACKTEST_LIMIT",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "SCALP_SCAN_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "SCALP_MIN_VOLUME_24H_USD",
        ]:
            os.environ.pop(name, None)

    def test_coinalyze_key_uses_canonical_name(self) -> None:
        os.environ["COINALYZE_API_KEY"] = "canonical-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "canonical-key")

    def test_coinalyze_key_accepts_common_misspelling(self) -> None:
        os.environ["COINALAYZE_API_KEY"] = "misspelled-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "misspelled-key")

    def test_alert_upgrade_defaults(self) -> None:
        settings = Settings.from_env()

        self.assertEqual(settings.prefilter_limit, 100)
        self.assertEqual(settings.deep_scan_limit, 20)
        self.assertEqual(settings.scan_workers, 8)
        self.assertEqual(settings.fetch_timeout_seconds, 20)
        self.assertEqual(settings.prefilter_candle_limit, 40)
        self.assertTrue(settings.auto_scan_enabled)
        self.assertEqual(settings.auto_scan_interval_seconds, settings.scan_interval_seconds)
        self.assertEqual(settings.telegram_min_signal, "watch")
        self.assertEqual(settings.min_alert_grade, "B")
        self.assertEqual(settings.backtest_limit, 25)
        self.assertFalse(settings.require_watch_before_enter)
        self.assertEqual(settings.active_setup_ttl_minutes, 240)
        self.assertEqual(settings.max_atr_pct, 8)
        self.assertEqual(settings.scalp_scan_limit, 20)
        self.assertEqual(settings.scalp_candle_limit, 240)
        self.assertEqual(settings.scalp_min_volume_24h_usd, 25_000_000)


if __name__ == "__main__":
    unittest.main()
