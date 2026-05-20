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

    def test_setup_score_calibration_groups_recent_scores(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "journal.sqlite3"
            journal = Journal(str(db_path))
            journal.record_setup_score(
                symbol="BTC/USD",
                setup="tabo",
                signal="watch",
                rank=1,
                score=80.0,
                confidence=0.75,
                approved=False,
                volume_24h_usd=1_000_000_000,
                oi_change_24h_pct=12.0,
                relative_volume=1.5,
            )
            journal.record_setup_score(
                symbol="ETH/USD",
                setup="tabo",
                signal="watch",
                rank=2,
                score=60.0,
                confidence=0.65,
                approved=False,
                volume_24h_usd=500_000_000,
                oi_change_24h_pct=6.0,
                relative_volume=1.2,
            )

            rows = journal.setup_calibration()

            self.assertEqual(rows[0]["setup"], "tabo")
            self.assertEqual(rows[0]["signal"], "watch")
            self.assertEqual(rows[0]["count"], 2)
            self.assertEqual(rows[0]["avg_score"], 70.0)

    def test_signal_outcome_seed_can_be_updated_and_summarized(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "journal.sqlite3"
            journal = Journal(str(db_path))
            journal.record_signal_outcome_seed(
                symbol="BTC/USD",
                exchange_id="coinbase",
                route_symbol="BTC/USD",
                setup="tabo",
                signal="enter",
                direction="long",
                grade="A",
                entry=100.0,
                stop_loss=98.0,
                target=104.0,
                score=80.0,
                confidence=0.8,
                horizon_hours=4,
            )

            pending = journal.pending_signal_outcomes()
            self.assertEqual(len(pending), 1)

            journal.update_signal_outcome(pending[0]["id"], "target", 4.0, "target")
            rows = journal.recent_signal_outcomes()
            summary = journal.outcome_summary()

            self.assertEqual(rows[0]["status"], "target")
            self.assertEqual(summary[0]["setup"], "tabo")
            self.assertEqual(summary[0]["win_rate"], 1.0)

    def test_signal_outcome_seed_deduplicates_pending_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "journal.sqlite3"
            journal = Journal(str(db_path))
            for _ in range(2):
                journal.record_signal_outcome_seed(
                    symbol="BTC/USD",
                    exchange_id="coinbase",
                    route_symbol="BTC/USD",
                    setup="tabo",
                    signal="watch",
                    direction="long",
                    grade="B",
                    entry=100.0,
                    stop_loss=98.0,
                    target=104.0,
                    score=70.0,
                    confidence=0.72,
                    horizon_hours=1,
                )

            self.assertEqual(len(journal.pending_signal_outcomes()), 1)

    def test_active_setup_lifecycle_records_and_finds_watch(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "journal.sqlite3"
            journal = Journal(str(db_path))
            journal.record_active_setup(
                symbol="BTC/USD",
                setup="tabo",
                direction="long",
                status="watch",
                grade="B",
                entry=100.0,
                stop_loss=98.0,
                target=104.0,
                score=70.0,
                confidence=0.72,
                ttl_minutes=240,
            )

            self.assertTrue(journal.active_watch_exists("BTC/USD", "tabo", "long"))
            rows = journal.recent_active_setups()
            self.assertEqual(rows[0]["status"], "watch")


if __name__ == "__main__":
    unittest.main()
