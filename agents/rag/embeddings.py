"""
Local embeddings via the same OpenAI-compatible endpoint used for generation (Ollama).

Reuses agents.llm_config.make_client so the provider/base_url/api_key live in ONE place.
Returns L2-normalized float32 vectors, so a dot product between any two vectors is their
cosine similarity (this is what the vector store relies on).

Embedding failures here RAISE (so indexing a corpus fails loudly and you know to
`ollama pull` the model). Retrieval-time callers are expected to wrap calls and degrade
gracefully — see knowledge_base.py and sow_retrieval.py.
"""
from __future__ import annotations

import logging

import numpy as np
from tqdm import tqdm

from agents.llm_config import make_client

from .config import get_embed_model

logger = logging.getLogger(__name__)

# Ollama embedding endpoints are happiest with modest batches; keep requests small.
_BATCH_SIZE = 32


def _normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row so dot products equal cosine similarity. Zero rows stay zero."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # avoid divide-by-zero for empty/degenerate vectors
    return (matrix / norms).astype(np.float32)


def embed_texts(texts: list[str], show_progress: bool = False) -> np.ndarray:
    """Embed many texts. Returns an (N, D) normalized float32 array.

    Used at index time (corpus build) and inside intra-document retrieval.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    client = make_client()
    model = get_embed_model()

    vectors: list[list[float]] = []
    batches = range(0, len(texts), _BATCH_SIZE)
    iterator = (
        tqdm(batches, desc="Embedding", unit="batch") if show_progress else batches
    )
    for start in iterator:
        batch = texts[start : start + _BATCH_SIZE]
        resp = client.embeddings.create(model=model, input=batch)
        # OpenAI-compatible response preserves input order in resp.data.
        vectors.extend(item.embedding for item in resp.data)

    return _normalize(np.array(vectors, dtype=np.float32))


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string. Returns a 1-D normalized float32 vector."""
    matrix = embed_texts([text])
    return matrix[0] if matrix.shape[0] else np.zeros((0,), dtype=np.float32)
