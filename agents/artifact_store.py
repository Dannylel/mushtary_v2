"""Small SQLite audit store for AI artifacts and buyer decisions.

The MVP deliberately keeps marketplace state in memory, but AI outputs and approvals
need durable, reviewable records. SQLite provides that without adding a service.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mushtary.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_artifacts (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            type TEXT NOT NULL,
            vendor_id TEXT,
            tender_id TEXT,
            proposal_id TEXT,
            actor_id TEXT,
            status TEXT NOT NULL,
            prompt_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            model_used TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            provider TEXT NOT NULL DEFAULT 'unknown',
            result_mode TEXT NOT NULL DEFAULT 'AI_SUCCESS',
            prompt_sha256 TEXT NOT NULL DEFAULT '',
            parent_artifact_id TEXT,
            revision_number INTEGER NOT NULL DEFAULT 1,
            input_snapshot_json TEXT NOT NULL,
            output_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_at TEXT,
            approved_by TEXT,
            approval_note TEXT
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_artifacts)")}
    if "proposal_id" not in columns:
        conn.execute("ALTER TABLE ai_artifacts ADD COLUMN proposal_id TEXT")
    migrations = {
        "provider": "TEXT NOT NULL DEFAULT 'unknown'",
        "result_mode": "TEXT NOT NULL DEFAULT 'AI_SUCCESS'",
        "prompt_sha256": "TEXT NOT NULL DEFAULT ''",
        "parent_artifact_id": "TEXT",
        "revision_number": "INTEGER NOT NULL DEFAULT 1",
    }
    for column, declaration in migrations.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE ai_artifacts ADD COLUMN {column} {declaration}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_tender ON ai_artifacts(tender_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_vendor ON ai_artifacts(vendor_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_trace ON ai_artifacts(trace_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_parent ON ai_artifacts(parent_artifact_id, revision_number)")
    conn.commit()
    return conn


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Insert one immutable AIArtifact and return the durable stored form."""
    now = _now()
    data = dict(artifact)
    created_at = str(data.get("created_at") or now)
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO ai_artifacts (
                id, trace_id, type, vendor_id, tender_id, proposal_id, actor_id, status,
                prompt_name, prompt_version, model_used, input_tokens, output_tokens,
                provider, result_mode, prompt_sha256, parent_artifact_id, revision_number,
                input_snapshot_json, output_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
        """, (
            data["id"], data["trace_id"], data["type"], data.get("vendor_id"),
            data.get("tender_id"), data.get("proposal_id"), data.get("actor_id"), data.get("status", "DRAFT"),
            data["prompt_name"], data["prompt_version"], data["model_used"],
            data.get("input_tokens", 0), data.get("output_tokens", 0),
            data.get("provider", "unknown"), data.get("result_mode", "AI_SUCCESS"),
            data.get("prompt_sha256", ""), data.get("parent_artifact_id"),
            data.get("revision_number", 1),
            json.dumps(data.get("input_snapshot") or {}, ensure_ascii=False, default=str),
            json.dumps(data.get("output") or {}, ensure_ascii=False, default=str),
            created_at, now,
        ))
        conn.commit()
    finally:
        conn.close()
    return get_artifact(data["id"]) or data


def _row_to_artifact(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["input_snapshot"] = json.loads(data.pop("input_snapshot_json"))
    data["output"] = json.loads(data.pop("output_json"))
    return data


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM ai_artifacts WHERE id = ?", (artifact_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_artifact(row) if row else None


def list_artifacts(
    *,
    tender_id: str | None = None,
    vendor_id: str | None = None,
    actor_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses, values = [], []
    if tender_id:
        clauses.append("tender_id = ?")
        values.append(tender_id)
    if vendor_id:
        clauses.append("vendor_id = ?")
        values.append(vendor_id)
    if actor_id:
        clauses.append("actor_id = ?")
        values.append(actor_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    conn = _connect()
    try:
        rows = conn.execute(f"SELECT * FROM ai_artifacts{where} ORDER BY created_at DESC LIMIT ?", (*values, limit)).fetchall()
    finally:
        conn.close()
    return [_row_to_artifact(row) for row in rows]


def get_latest_artifact(*, tender_id: str, vendor_id: str, proposal_id: str, artifact_type: str) -> dict[str, Any] | None:
    """Return the current assessment for one specific submitted proposal, if already run."""
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT * FROM ai_artifacts
            WHERE tender_id = ? AND vendor_id = ? AND proposal_id = ? AND type = ?
            ORDER BY created_at DESC LIMIT 1
        """, (tender_id, vendor_id, proposal_id, artifact_type)).fetchone()
    finally:
        conn.close()
    return _row_to_artifact(row) if row else None


def approve_artifact(artifact_id: str, *, buyer_id: str, note: str | None = None) -> dict[str, Any] | None:
    """Atomically approve a draft owned by this buyer. Already-final artifacts are immutable."""
    conn = _connect()
    try:
        updated = conn.execute("""
            UPDATE ai_artifacts
            SET status = 'APPROVED', approved_at = ?, approved_by = ?, approval_note = ?, updated_at = ?
            WHERE id = ? AND status = 'DRAFT' AND (actor_id IS NULL OR actor_id = ?)
        """, (_now(), buyer_id, note, _now(), artifact_id, buyer_id)).rowcount
        conn.commit()
    finally:
        conn.close()
    return get_artifact(artifact_id) if updated else None
