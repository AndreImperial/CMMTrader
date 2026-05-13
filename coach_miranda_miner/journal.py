from __future__ import annotations

from datetime import datetime, timezone
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
