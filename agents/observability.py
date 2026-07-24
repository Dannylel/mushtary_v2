"""Trace context and privacy-safe structured events for the AI runtime."""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mushtary.db"
logger = logging.getLogger("agents.observability")
_prune_lock = threading.Lock()
_pruned_paths: set[str] = set()

_SENSITIVE_KEY = re.compile(
    r"(password|secret|token|api.?key|authorization|cookie|otp|cr_number|"
    r"legal_name|email|phone|raw|content|prompt|response|proposal|scope|error.?message)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TraceContext:
    request_id: str = ""
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    job_id: str = ""
    tenant_id: str = ""
    actor_id: str = ""
    tender_id: str = ""
    vendor_id: str = ""
    agent: str = ""


_context: contextvars.ContextVar[TraceContext] = contextvars.ContextVar(
    "mushtary_trace_context", default=TraceContext()
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def current_context() -> TraceContext:
    return _context.get()


def ensure_trace(**updates: str | None) -> TraceContext:
    current = current_context()
    clean = {key: value for key, value in updates.items() if value is not None}
    if not current.request_id:
        clean.setdefault("request_id", new_id("req"))
    if not current.trace_id:
        clean.setdefault("trace_id", new_id("trace"))
    result = replace(current, **clean)
    _context.set(result)
    return result


@contextmanager
def bind_context(**updates: str | None) -> Iterator[TraceContext]:
    current = current_context()
    clean = {key: value for key, value in updates.items() if value is not None}
    token = _context.set(replace(current, **clean))
    try:
        yield current_context()
    finally:
        _context.reset(token)


@contextmanager
def span(name: str, **updates: str | None) -> Iterator[TraceContext]:
    parent = ensure_trace()
    span_id = new_id("span")
    started = time.perf_counter()
    with bind_context(
        parent_span_id=parent.span_id,
        span_id=span_id,
        agent=name,
        **updates,
    ) as ctx:
        emit("ai.span.started", agent=name)
        try:
            yield ctx
        except Exception as exc:
            emit(
                "ai.span.failed",
                level="ERROR",
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
            )
            raise
        else:
            emit(
                "ai.span.completed",
                duration_ms=round((time.perf_counter() - started) * 1000),
            )


def sha256_text(value: str | bytes | None) -> str:
    raw = value if isinstance(value, bytes) else (value or "").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def redact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return a bounded, recursively redacted value suitable for operational logs."""
    if depth > 5:
        return "[MAX_DEPTH]"
    safe_metric_key = key.lower().endswith(("_tokens", "_sha256"))
    if _SENSITIVE_KEY.search(key) and not safe_metric_key:
        text = json.dumps(value, ensure_ascii=False, default=str)
        return {"redacted": True, "sha256": sha256_text(text), "length": len(text)}
    if isinstance(value, dict):
        return {str(k): redact(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, key=key, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str) and len(value) > 500:
        return {"sha256": sha256_text(value), "length": len(value)}
    return value


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            event TEXT NOT NULL,
            request_id TEXT,
            trace_id TEXT,
            span_id TEXT,
            parent_span_id TEXT,
            job_id TEXT,
            tenant_id TEXT,
            actor_id TEXT,
            tender_id TEXT,
            vendor_id TEXT,
            agent TEXT,
            details_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_events_trace ON ai_events(trace_id, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_events_job ON ai_events(job_id, id)")
    path_key = str(DB_PATH.resolve())
    with _prune_lock:
        if path_key not in _pruned_paths:
            try:
                days = max(1, int(os.getenv("AI_EVENT_RETENTION_DAYS", "30")))
            except ValueError:
                days = 30
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conn.execute("DELETE FROM ai_events WHERE timestamp < ?", (cutoff,))
            _pruned_paths.add(path_key)
    conn.commit()
    return conn


def emit(event: str, *, level: str = "INFO", **details: Any) -> None:
    """Persist one privacy-safe event. Observability must never break the AI workflow."""
    ctx = ensure_trace()
    safe_details = redact(details)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "event": event,
        **asdict(ctx),
        "details": safe_details,
    }
    try:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO ai_events (
                    timestamp, level, event, request_id, trace_id, span_id,
                    parent_span_id, job_id, tenant_id, actor_id, tender_id,
                    vendor_id, agent, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["timestamp"], record["level"], event, ctx.request_id,
                    ctx.trace_id, ctx.span_id, ctx.parent_span_id, ctx.job_id,
                    ctx.tenant_id, ctx.actor_id, ctx.tender_id, ctx.vendor_id,
                    ctx.agent, json.dumps(safe_details, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.debug("Could not persist AI observability event", exc_info=True)


def list_events(
    *,
    trace_id: str | None = None,
    job_id: str | None = None,
    actor_id: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    if not trace_id and not job_id:
        raise ValueError("trace_id or job_id is required")
    field, value = ("trace_id", trace_id) if trace_id else ("job_id", job_id)
    actor_clause = " AND actor_id = ?" if actor_id else ""
    values: list[Any] = [value]
    if actor_id:
        values.append(actor_id)
    values.append(min(max(limit, 1), 2000))
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT * FROM ai_events WHERE {field} = ?{actor_clause} ORDER BY id LIMIT ?",
            values,
        ).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json"))
        out.append(item)
    return out


def trace_usage(trace_id: str) -> dict[str, int]:
    """Aggregate completed model-call usage for an artifact trace."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT details_json FROM ai_events WHERE trace_id = ? AND event = 'ai.call.completed'",
            (trace_id,),
        ).fetchall()
    finally:
        conn.close()
    input_tokens = output_tokens = 0
    for (raw,) in rows:
        details = json.loads(raw)
        input_tokens += int(details.get("input_tokens") or 0)
        output_tokens += int(details.get("output_tokens") or 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def trace_result_mode(trace_id: str) -> str:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT event, details_json FROM ai_events WHERE trace_id = ?",
            (trace_id,),
        ).fetchall()
    finally:
        conn.close()
    modes = []
    for event, raw in rows:
        details = json.loads(raw)
        if event == "ai.fallback.applied":
            return "PARTIAL_SUCCESS"
        if details.get("result_mode"):
            modes.append(details["result_mode"])
    return "AI_REPAIRED" if "AI_REPAIRED" in modes else "AI_SUCCESS"
