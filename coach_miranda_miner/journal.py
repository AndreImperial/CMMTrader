from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3


class Journal:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    reason TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    risk_reason TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    notional_usd REAL NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_theses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    approved INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )

    def record_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        price: float,
        reason: str,
        approved: bool,
        risk_reason: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    created_at, symbol, action, confidence, price, reason, approved, risk_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    action,
                    confidence,
                    price,
                    reason,
                    int(approved),
                    risk_reason,
                ),
            )

    def record_fill(
        self,
        action: str,
        quantity: float,
        price: float,
        notional_usd: float,
        message: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fills (
                    created_at, action, quantity, price, notional_usd, message
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    action,
                    quantity,
                    price,
                    notional_usd,
                    message,
                ),
            )

    def record_thesis(
        self,
        symbol: str,
        setup: str,
        signal: str,
        direction: str,
        confidence: float,
        approved: bool,
        payload_json: str,
        validation_json: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_theses (
                    created_at, symbol, setup, signal, direction, confidence,
                    approved, payload_json, validation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    setup,
                    signal,
                    direction,
                    confidence,
                    int(approved),
                    payload_json,
                    validation_json,
                ),
            )

    def recent_theses(self, limit: int = 25) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, symbol, setup, signal, direction, confidence,
                       approved, payload_json, validation_json
                FROM ai_theses
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            results.append(
                {
                    "created_at": row[0],
                    "symbol": row[1],
                    "setup": row[2],
                    "signal": row[3],
                    "direction": row[4],
                    "confidence": row[5],
                    "approved": bool(row[6]),
                    "payload": json.loads(row[7]),
                    "validation": json.loads(row[8]),
                }
            )
        return results

    def alert_sent_recently(
        self,
        symbol: str,
        setup: str,
        signal: str,
        cooldown_minutes: int,
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM telegram_alerts
                WHERE symbol = ? AND setup = ? AND signal = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol, setup, signal),
            ).fetchone()
        if row is None:
            return False
        created_at = datetime.fromisoformat(row[0])
        elapsed = datetime.now(timezone.utc) - created_at
        return elapsed.total_seconds() < cooldown_minutes * 60

    def record_alert(self, symbol: str, setup: str, signal: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_alerts (created_at, symbol, setup, signal, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    setup,
                    signal,
                    message,
                ),
            )

    def recent_alerts(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, symbol, setup, signal, message
                FROM telegram_alerts
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "symbol": row[1],
                "setup": row[2],
                "signal": row[3],
                "message": row[4],
            }
            for row in rows
        ]
