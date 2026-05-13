from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from coach_miranda_miner.journal import Journal


class JournalAlertTests(unittest.TestCase):
    def test_alert_cooldown_records_recent_alert(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "journal.sqlite3"
            journal = Journal(str(db_path))

            self.assertFalse(
                journal.alert_sent_recently("BTC/USD", "tabo", "watch", 60)
            )
            journal.record_alert("BTC/USD", "tabo", "watch", "hello")
            self.assertTrue(
                journal.alert_sent_recently("BTC/USD", "tabo", "watch", 60)
            )
            self.assertFalse(
                journal.alert_sent_recently("ETH/USD", "tabo", "watch", 60)
            )


if __name__ == "__main__":
    unittest.main()
