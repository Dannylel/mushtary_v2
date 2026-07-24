"""
Intra-document retrieval for the SoW Extractor.

Problem it fixes: the extractor previously trimmed long documents to head(9k)+tail(3k),
silently dropping the middle — so any field defined on pages in the middle of a long RFP
was lost. This module instead chunks the WHOLE document, embeds it, and keeps the chunks
most relevant to the fields we want to fill, reassembled in original reading order.

This is RAG over the single uploaded document (an ephemeral, in-memory index) — it needs
NO pre-collected corpus, which is why it can ship before any training/example data exists.

Fail-safe: on any error (embedding server down, model not pulled, etc.) it falls back to
the exact original head+tail truncation, so behavior is never worse than before.
"""
from __future__ import annotations

import logging

from .chunking import chunk_text
from .store import VectorStore

logger = logging.getLogger(__name__)

# Aspect queries — one per group of TenderBuyerForm fields the extractor must populate.
# Retrieving against all of these gathers the chunks that mention each kind of fact.
_FIELD_QUERIES = [
    "tender title, buyer name, and organization description",
    "project objective, background, and purpose",
    "scope of work and detailed requirements",
    "deliverables and expected outputs",
    "project timeline, milestones, and key dates",
    "roles and responsibilities of buyer and vendor",
    "budget, estimated value, pricing, and payment terms",
    "eligibility criteria and required vendor qualifications",
    "required documents and certifications",
    "evaluation criteria and how proposals are scored",
    "submission deadline, method, and proposal format",
    "category, sector, and type of procurement",
]


def _head_tail_truncation(text: str, max_chars: int) -> str:
    """The original fallback behavior: keep the beginning and the end."""
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.75)
    tail = max_chars - head
    return text[:head] + "\n...[truncated]...\n" + text[-tail:]


def build_focused_sow_text(raw_text: str, max_chars: int = 12000) -> str:
    """Return a focused subset of a long document, biased toward fillable fields.

    Short documents (<= max_chars) are returned unchanged — no embedding cost incurred.
    """
    text = raw_text or ""
    if len(text) <= max_chars:
        return text

    try:
        chunks = chunk_text(text)
        if not chunks:
            return _head_tail_truncation(text, max_chars)

        store = VectorStore()
        # Remember original order so we can reassemble the kept chunks coherently.
        store.add_texts(chunks, metadata={})
        order_of = {chunk: i for i, chunk in enumerate(chunks)}

        # Pull a few top chunks per aspect query; union them (a chunk may serve several).
        per_query = max(2, (max_chars // len(chunks)) if chunks else 2)
        selected: dict[int, str] = {}
        for q in _FIELD_QUERIES:
            for hit in store.search(q, k=3, min_score=0.0):
                idx = order_of.get(hit.text)
                if idx is not None:
                    selected[idx] = hit.text

        if not selected:
            return _head_tail_truncation(text, max_chars)

        # Reassemble in reading order, filling up to the character budget.
        kept: list[str] = []
        total = 0
        for idx in sorted(selected):
            piece = selected[idx]
            if total + len(piece) > max_chars and kept:
                break
            kept.append(piece)
            total += len(piece)

        return "\n\n...\n\n".join(kept)
    except Exception as e:
        # Any failure (no embed model, server down, etc.) -> original safe behavior.
        logger.warning("SoW focused retrieval failed (%s); using head+tail truncation.", type(e).__name__)
        return _head_tail_truncation(text, max_chars)
