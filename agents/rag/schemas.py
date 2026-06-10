"""
RAG Pydantic v2 schemas.

Keeping chunks and retrieval hits as validated models (rather than loose dicts) matches the
project rule that every data unit moving between components is a Pydantic model.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """One indexable unit of text plus arbitrary provenance metadata.

    metadata is free-form so different corpora can tag what matters to them, e.g.
    {"source": "etimad_law.pdf", "authority": "law", "category": "IT", "approved": true}.
    Retrieval and prompt-formatting only rely on a few optional conventional keys
    (source, authority, category) and ignore the rest.
    """

    text: str
    metadata: dict = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """A chunk returned by a search, with its similarity score (cosine, 0..1)."""

    text: str
    metadata: dict = Field(default_factory=dict)
    score: float
