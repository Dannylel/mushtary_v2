"""
RAG configuration — single source of truth for the embedding model and retrieval knobs.

Mirrors agents/llm_config.py: the embedding endpoint is the SAME local OpenAI-compatible
server (Ollama) used for generation, so there is nothing extra to run. Only the model id
differs (a dedicated embedding model, not a chat model).

Environment variables (all optional — sensible local defaults applied):
    RAG_EMBED_MODEL   Embedding model served by the local endpoint.
                      Default: qwen3-embedding:0.6b (already pulled in the mushtary env).
                      Alternatives, e.g. nomic-embed-text, just need `ollama pull <name>`
                      and RAG_EMBED_MODEL set to that tag. IMPORTANT: if you change the
                      embed model after building an index, rebuild it — vectors from
                      different models are not comparable (the store guards dim mismatch).
    RAG_TOP_K         Default number of chunks returned by a search. Default: 4
    RAG_MIN_SCORE     Minimum cosine similarity for a chunk to be returned. Default: 0.30
                      (below this a match is usually noise; keeps weak hits out of prompts)

The base URL and API key are intentionally reused from agents.llm_config so the provider
lives in exactly one place across the whole project.
"""
import os

# Default local embedding model. qwen3-embedding:0.6b is already pulled in the mushtary
# Ollama env, so RAG works out of the box with no extra download.
DEFAULT_EMBED_MODEL = "qwen3-embedding:0.6b"
DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.30


def get_embed_model() -> str:
    return os.getenv("RAG_EMBED_MODEL") or DEFAULT_EMBED_MODEL


def get_top_k() -> int:
    # Guard against a malformed env value rather than crashing the pipeline.
    try:
        return int(os.getenv("RAG_TOP_K") or DEFAULT_TOP_K)
    except ValueError:
        return DEFAULT_TOP_K


def get_min_score() -> float:
    try:
        return float(os.getenv("RAG_MIN_SCORE") or DEFAULT_MIN_SCORE)
    except ValueError:
        return DEFAULT_MIN_SCORE
