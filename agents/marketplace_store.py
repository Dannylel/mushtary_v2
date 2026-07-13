"""Durable SQLite storage for demo tender drafts and published tenders."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from agents.artifact_store import DB_PATH


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketplace_tenders (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, buyer_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_json TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_marketplace_tenders_status ON marketplace_tenders(status, created_at DESC)")
    conn.commit()
    return conn


def save_tender(tender_id: str, status: str, buyer_id: str | None, payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO marketplace_tenders (id, status, buyer_id, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status, buyer_id=excluded.buyer_id,
              updated_at=excluded.updated_at, payload_json=excluded.payload_json
        """, (tender_id, status, buyer_id, now, now, json.dumps(payload, ensure_ascii=False, default=str)))
        conn.commit()
    finally:
        conn.close()


def list_tenders(*, status: str | None = None, buyer_id: str | None = None) -> list[dict[str, Any]]:
    clauses, values = [], []
    if status:
        clauses.append("status = ?"); values.append(status)
    if buyer_id:
        clauses.append("buyer_id = ?"); values.append(buyer_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    conn = _connect()
    try:
        rows = conn.execute(f"SELECT * FROM marketplace_tenders{where} ORDER BY created_at DESC", values).fetchall()
    finally:
        conn.close()
    output = []
    for row in rows:
        data = json.loads(row["payload_json"])
        data.setdefault("id", row["id"])
        data.setdefault("status", row["status"])
        data.setdefault("created_at", row["created_at"])
        output.append(data)
    return output


def get_tender(tender_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM marketplace_tenders WHERE id = ?", (tender_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    data = json.loads(row["payload_json"])
    data.setdefault("id", row["id"]); data.setdefault("status", row["status"]); data.setdefault("created_at", row["created_at"])
    return data
