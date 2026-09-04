#!/usr/bin/env python3
"""SQLite-backed local persistent event store for LSA.

Provides durable persistence for ingested agent events, sessions, and alerts.
Zero external dependencies (stdlib sqlite3).
"""
from __future__ import annotations

import hashlib
import json
import secrets
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

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Secure SHA-256 hash of API key for storage."""
        return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()

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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_org_session ON session_events(organization_name, session_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_hash TEXT PRIMARY KEY,
                    organization_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    key_prefix TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_name)")

            # Ensure role column exists if upgrading table
            try:
                conn.execute("ALTER TABLE api_keys ADD COLUMN role TEXT NOT NULL DEFAULT 'member'")
            except Exception:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_policies (
                    organization_name TEXT PRIMARY KEY,
                    version INTEGER DEFAULT 1,
                    policy_yaml TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_api_key(self, organization_name: str, raw_key: str | None = None, role: str = "member") -> str:
        """Create and store a hashed API key for an organization with role ('admin' or 'member'). Returns the raw API key."""
        if not raw_key:
            raw_key = f"lsa_{secrets.token_urlsafe(24)}"
        khash = self.hash_key(raw_key)
        prefix = raw_key[:8] if len(raw_key) >= 8 else raw_key
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (key_hash, organization_name, role, key_prefix, revoked)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(key_hash) DO UPDATE SET organization_name = excluded.organization_name, role = excluded.role, revoked = 0
                """,
                (khash, organization_name, role, prefix),
            )
            conn.commit()
        return raw_key

    def revoke_api_key(self, raw_key: str) -> bool:
        """Mark an API key as revoked."""
        khash = self.hash_key(raw_key)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE api_keys SET revoked = 1 WHERE key_hash = ?", (khash,))
            conn.commit()
            return cur.rowcount > 0

    def lookup_key(self, raw_key: str) -> dict[str, Any] | None:
        """Look up API key metadata by raw key. Returns None if invalid or revoked."""
        if not raw_key:
            return None
        khash = self.hash_key(raw_key)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT organization_name, role, created_at, revoked FROM api_keys WHERE key_hash = ?",
                (khash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "organization_name": row["organization_name"],
                "role": row["role"] if "role" in row.keys() else "member",
                "created_at": row["created_at"],
                "revoked": bool(row["revoked"]),
            }

    def set_org_policy(self, organization_name: str, policy_yaml: str, version: int = 1) -> None:
        """Persist or update policy-as-code for an organization."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO org_policies (organization_name, version, policy_yaml, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(organization_name) DO UPDATE SET
                    version = excluded.version,
                    policy_yaml = excluded.policy_yaml,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (organization_name, version, policy_yaml),
            )
            conn.commit()

    def get_org_policy(self, organization_name: str) -> dict[str, Any] | None:
        """Retrieve policy-as-code for an organization."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT organization_name, version, policy_yaml, updated_at FROM org_policies WHERE organization_name = ?",
                (organization_name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "organization_name": row["organization_name"],
                "version": row["version"],
                "policy_yaml": row["policy_yaml"],
                "updated_at": row["updated_at"],
            }

    def store_event(
        self,
        session_id: str,
        agent_source: str,
        tool_name: str,
        target: str | None,
        payload: dict[str, Any],
        organization_name: str = "default",
    ) -> int:
        """Persist event to database scoped strictly to an organization. Returns inserted row ID."""
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

    def get_events_for_session(
        self, session_id: str, organization_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve persisted events for a session, optionally scoped to an organization."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if organization_name:
                cursor.execute(
                    "SELECT * FROM session_events WHERE session_id = ? AND organization_name = ? ORDER BY id ASC",
                    (session_id, organization_name),
                )
            else:
                cursor.execute("SELECT * FROM session_events WHERE session_id = ? ORDER BY id ASC", (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "organization_name": row["organization_name"],
                    "agent_source": row["agent_source"],
                    "tool_name": row["tool_name"],
                    "target": row["target"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def get_recent_events(
        self, limit: int = 50, organization_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve most recent persisted events, optionally scoped to an organization."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if organization_name:
                cursor.execute(
                    "SELECT * FROM session_events WHERE organization_name = ? ORDER BY id DESC LIMIT ?",
                    (organization_name, limit),
                )
            else:
                cursor.execute("SELECT * FROM session_events ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "organization_name": row["organization_name"],
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
