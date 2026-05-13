from __future__ import annotations

import os
import unittest

from coach_miranda_miner.config import Settings


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["COINALYZE_API_KEY"] = ""
        os.environ["COINALAYZE_API_KEY"] = ""

    def tearDown(self) -> None:
        os.environ.pop("COINALYZE_API_KEY", None)
        os.environ.pop("COINALAYZE_API_KEY", None)

    def test_coinalyze_key_uses_canonical_name(self) -> None:
        os.environ["COINALYZE_API_KEY"] = "canonical-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "canonical-key")

    def test_coinalyze_key_accepts_common_misspelling(self) -> None:
        os.environ["COINALAYZE_API_KEY"] = "misspelled-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "misspelled-key")


if __name__ == "__main__":
    unittest.main()
