"""
Platform tender references — TND-ID-0001 format.

Tender references are assigned by the platform, never invented by the model: every
generated/extracted tender gets the next sequential "TND-ID-NNNN". The counter persists
in outputs/.tender_seq so references stay unique across runs. (When a real DB arrives,
this becomes a sequence/identity column; the format is the contract.)
"""
from __future__ import annotations

import threading
from pathlib import Path

_PREFIX = "TND-ID-"
_SEQ_FILE = Path(__file__).parent.parent / "outputs" / ".tender_seq"
_lock = threading.Lock()


def next_tender_id() -> str:
    """Return the next sequential platform tender reference, e.g. 'TND-ID-0007'."""
    with _lock:
        try:
            current = int(_SEQ_FILE.read_text().strip())
        except (FileNotFoundError, ValueError):
            current = 0
        current += 1
        _SEQ_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEQ_FILE.write_text(str(current), encoding="utf-8")
    return f"{_PREFIX}{current:04d}"
