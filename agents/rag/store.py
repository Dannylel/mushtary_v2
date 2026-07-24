"""
VectorStore — a dependency-light flat (brute-force) cosine-similarity index.

Why flat numpy instead of FAISS/Chroma:
  - Zero native-build pain on Windows; numpy is already a transitive dep.
  - The tender knowledge base is small (hundreds–low thousands of chunks). Brute-force
    cosine over that is sub-millisecond; an ANN index would be premature optimization.
Swap this class for a FAISS/Chroma-backed one later without touching callers — the public
surface (add / search / save / load / __len__) is all the rest of the package depends on.

Persistence layout (one directory per store):
    <dir>/vectors.npy     float32 (N, D) normalized embeddings
    <dir>/chunks.jsonl    one JSON object per line: {"text": ..., "metadata": {...}}
"""
from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .embeddings import embed_query, embed_texts
from .schemas import Chunk, RetrievedChunk

logger = logging.getLogger(__name__)

_VECTORS_FILE = "vectors.npy"
_CHUNKS_FILE = "chunks.jsonl"
_MANIFEST_FILE = "manifest.json"


class VectorStore:
    """In-memory vector store with optional disk persistence."""

    def __init__(self) -> None:
        self._vectors: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self._chunks: list[Chunk] = []
        self.manifest: dict = {}

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def is_empty(self) -> bool:
        return len(self._chunks) == 0

    # ── Writing ────────────────────────────────────────────────────────────────
    def add(self, chunks: list[Chunk], show_progress: bool = False) -> None:
        """Embed and append chunks. No-op for an empty list."""
        if not chunks:
            return
        new_vectors = embed_texts([c.text for c in chunks], show_progress=show_progress)

        if self._vectors.shape[0] == 0:
            self._vectors = new_vectors
        else:
            # Dimensions must match across appends (same embedding model throughout).
            if new_vectors.shape[1] != self._vectors.shape[1]:
                raise ValueError(
                    f"Embedding dim mismatch: store has {self._vectors.shape[1]}, "
                    f"new chunks have {new_vectors.shape[1]}. Did the embed model change?"
                )
            self._vectors = np.vstack([self._vectors, new_vectors])
        self._chunks.extend(chunks)

    def add_texts(self, texts: list[str], metadata: dict | None = None,
                  show_progress: bool = False) -> None:
        """Convenience: wrap raw strings as Chunks sharing one metadata dict."""
        meta = metadata or {}
        self.add([Chunk(text=t, metadata=dict(meta)) for t in texts],
                 show_progress=show_progress)

    # ── Reading ────────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 4, min_score: float = 0.0) -> list[RetrievedChunk]:
        """Return up to k chunks most similar to the query, filtered by min_score.

        Vectors are normalized, so a plain dot product is cosine similarity.
        """
        if self.is_empty or not (query or "").strip():
            return []

        q = embed_query(query)
        if q.shape[0] != self._vectors.shape[1]:
            # Query embedding dim disagrees with the index (model changed) — fail safe.
            logger.warning("Query/index embedding dim mismatch; returning no matches.")
            return []

        scores = self._vectors @ q  # (N,) cosine similarities
        # argsort descending, then take the first k above threshold.
        order = np.argsort(-scores)
        out: list[RetrievedChunk] = []
        for idx in order[:k]:
            score = float(scores[idx])
            if score < min_score:
                break  # sorted descending — nothing after this clears the bar either
            chunk = self._chunks[idx]
            out.append(RetrievedChunk(text=chunk.text, metadata=chunk.metadata, score=score))
        return out

    # ── Persistence ──────────────────────────────────────────────────────────────
    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / _VECTORS_FILE, self._vectors)
        with (directory / _CHUNKS_FILE).open("w", encoding="utf-8") as f:
            for chunk in self._chunks:
                f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")
        from .config import get_embed_model
        corpus_hash = hashlib.sha256(
            "\n".join(chunk.text for chunk in self._chunks).encode("utf-8")
        ).hexdigest()
        self.manifest = {
            "schema_version": 1,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": get_embed_model(),
            "chunk_count": len(self._chunks),
            "vector_dimension": int(self._vectors.shape[1]) if self._vectors.ndim == 2 and self._vectors.size else 0,
            "corpus_sha256": corpus_hash,
        }
        (directory / _MANIFEST_FILE).write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Saved vector store (%d chunks) to %s", len(self._chunks), directory)

    @classmethod
    def load(cls, directory: str | Path) -> "VectorStore":
        """Load a store from disk. A missing/empty directory yields an empty store."""
        directory = Path(directory)
        store = cls()
        vec_path = directory / _VECTORS_FILE
        chunk_path = directory / _CHUNKS_FILE
        if not vec_path.exists() or not chunk_path.exists():
            return store  # graceful: corpus not built yet

        store._vectors = np.load(vec_path).astype(np.float32)
        with chunk_path.open("r", encoding="utf-8") as f:
            store._chunks = [Chunk(**json.loads(line)) for line in f if line.strip()]
        manifest_path = directory / _MANIFEST_FILE
        if manifest_path.exists():
            store.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return store
