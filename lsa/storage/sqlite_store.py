#!/usr/bin/env python3
"""SQLite-backed local persistent event store for LSA.

Provides durable persistence for ingested agent events, sessions, and alerts.
Zero external dependencies (stdlib sqlite3).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteEventStore:
    def __init__(self, db_path: Path | str = ".intent-guard/lsa_events.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    organization_name TEXT NOT NULL DEFAULT 'default',
                    agent_source TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    target TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON session_events(session_id)")
            conn.commit()

    def store_event(
        self,
        session_id: str,
        agent_source: str,
        tool_name: str,
        target: str | None,
        payload: dict[str, Any],
        organization_name: str = "default",
    ) -> int:
        """Persist event to database. Returns inserted row ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO session_events (session_id, organization_name, agent_source, tool_name, target, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, organization_name, agent_source, tool_name, target or "", json.dumps(payload)),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_events_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve persisted events for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_events WHERE session_id = ? ORDER BY id ASC", (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "agent_source": row["agent_source"],
                    "tool_name": row["tool_name"],
                    "target": row["target"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def is_healthy(self) -> bool:
        """Verify database connectivity."""
        try:
            with self._get_connection() as conn:
                conn.execute("SELECT 1")
                return True
        except Exception:
            return False
