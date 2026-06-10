"""
Text chunking — split a long document into overlapping, embeddable pieces.

Strategy: pack whole paragraphs (split on blank lines) up to a character budget, then start
a new chunk. A small tail overlap is carried into the next chunk so a fact sitting on a
paragraph boundary is not split away from its context. Character-based (not token-based) on
purpose: it has zero dependencies and is good enough for retrieval granularity.
"""
from __future__ import annotations

import re

# ~1200 chars ≈ a few paragraphs ≈ a coherent retrieval unit for a small local model's window.
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_OVERLAP = 150

# Split on one-or-more blank lines so we keep paragraphs intact where possible.
_PARA_SPLIT = re.compile(r"\n\s*\n")


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Return a list of overlapping text chunks. Empty input yields an empty list."""
    text = (text or "").strip()
    if not text:
        return []

    # First pass: paragraph units. Any single paragraph longer than chunk_size is
    # hard-split below so it never blocks packing.
    paragraphs: list[str] = []
    for para in _PARA_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            paragraphs.append(para)
        else:
            # Hard-split an oversized paragraph into chunk_size windows.
            for i in range(0, len(para), chunk_size):
                paragraphs.append(para[i : i + chunk_size])

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= chunk_size:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            # Carry a tail overlap so boundary context is not lost.
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail}\n\n{para}" if tail else para

    if current:
        chunks.append(current)

    return chunks
