"""
RAG (retrieval-augmented generation) package — local-first, fail-safe.

Two consumers today:
  - Tender Drafting   -> TenderKnowledgeBase (persistent corpus of approved tenders /
                          clause library / procurement rules). See knowledge_base.py.
  - SoW Extractor     -> build_focused_sow_text (intra-document retrieval; no corpus
                          needed). See sow_retrieval.py.

Everything degrades to a safe no-op when the corpus is empty or the embedding server is
unreachable, so importing/using this package never breaks the existing pipeline.
"""
from .chunking import chunk_text
from .knowledge_base import TenderKnowledgeBase, get_tender_kb
from .schemas import Chunk, RetrievedChunk
from .sow_retrieval import build_focused_sow_text
from .store import VectorStore

__all__ = [
    "Chunk",
    "RetrievedChunk",
    "VectorStore",
    "TenderKnowledgeBase",
    "get_tender_kb",
    "build_focused_sow_text",
    "chunk_text",
]
