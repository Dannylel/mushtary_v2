"""
Activity feed — a process-wide, thread-safe event stream of what the agents are doing.

Purpose: let the demo UI show live "the model is now writing X" output. Agents publish
events (LLM tokens, lifecycle messages); the API exposes them via GET /api/activity?since=N
and the frontend polls while a job runs.

Design notes:
  - Ring buffer (bounded) of {id, ts, kind, label, text}; ids increase monotonically so a
    client can poll with `since` and never miss or duplicate events.
  - kind: "token" (streamed model text), "info" (lifecycle/log lines), "start"/"end"
    (LLM call boundaries).
  - Labels are thread-local: an agent sets its label right before calling the model, and
    the streaming callback (which fires on the same thread) reads it. The drafting section
    agents each run in their own worker thread, so parallel sections stream side by side
    under their own names.
  - Single-process only by design — matches the demo API (threads, no Celery).
"""
from __future__ import annotations

import itertools
import threading
import time
from collections import deque

from agents.observability import current_context

_MAX_EVENTS = 8000  # plenty for one long pipeline run; old events fall off the front

_lock = threading.Lock()
_events: deque[dict] = deque(maxlen=_MAX_EVENTS)
_next_id = itertools.count(1)
_label = threading.local()


def set_label(label: str) -> None:
    """Tag the current thread; subsequent token events from it carry this label."""
    _label.value = label


def get_label() -> str:
    return getattr(_label, "value", "LLM")


def publish(kind: str, text: str, label: str | None = None) -> None:
    """Append one event to the feed. Cheap; safe to call from any thread."""
    context = current_context()
    event = {
        "id": next(_next_id),
        "ts": time.time(),
        "kind": kind,
        "label": label if label is not None else get_label(),
        "text": text,
        "job_id": context.job_id,
        "trace_id": context.trace_id,
        "actor_id": context.actor_id,
        "tenant_id": context.tenant_id,
    }
    with _lock:
        _events.append(event)


def get_since(
    since_id: int = 0,
    limit: int = 500,
    *,
    job_id: str | None = None,
    trace_id: str | None = None,
) -> tuple[list[dict], int]:
    """Return events for one authorized execution scope; never expose the global feed."""
    with _lock:
        if job_id:
            out = [e for e in _events if e["id"] > since_id and e["job_id"] == job_id]
        elif trace_id:
            out = [e for e in _events if e["id"] > since_id and e["trace_id"] == trace_id]
        else:
            out = []
        last = _events[-1]["id"] if _events else since_id
    return out[:limit], last
