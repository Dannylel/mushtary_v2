"""
Central LLM configuration — single source of truth for provider, model, and credentials.

Local-first: defaults point at a local Ollama server exposing the OpenAI-compatible API.
Everything is overridable via environment variables (loaded from .env), so switching
models or pointing at a remote endpoint never requires touching agent code.

Environment variables (all optional — sensible local defaults applied):
    LLM_BASE_URL   OpenAI-compatible endpoint. Default: http://localhost:11434/v1 (Ollama)
    LLM_MODEL      Model id/tag served by that endpoint. Default: qwen3:4b
    LLM_API_KEY    API key. Local servers ignore it, but the openai SDK needs a non-empty
                   string. Default: "ollama".

Local-only by decision (2026-06-10): remote-provider key fallbacks (OPENAI_API_KEY,
gemini_API, OPENROUTER_API_KEY) were removed. To target a remote OpenAI-compatible
endpoint later, set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY explicitly.
"""
import os

# ── Local defaults (Ollama) ────────────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3:4b"
DEFAULT_API_KEY = "ollama"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-3.5-flash"


def get_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()


def get_base_url() -> str:
    if get_provider() == "gemini":
        return os.getenv("GEMINI_BASE_URL") or GEMINI_BASE_URL
    return os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL


def get_model() -> str:
    if get_provider() == "gemini":
        return os.getenv("GEMINI_MODEL") or GEMINI_MODEL
    return os.getenv("LLM_MODEL") or DEFAULT_MODEL


def get_api_key() -> str:
    if get_provider() == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY in .env or the environment.")
        return key
    # Local Ollama ignores the key, but the SDK needs a non-empty placeholder.
    return os.getenv("LLM_API_KEY") or DEFAULT_API_KEY


def make_client(api_key: str | None = None):
    """Build a raw OpenAI-compatible client pointed at the configured endpoint.

    Retained for any code path that wants the bare SDK; the LangChain layer below is
    the primary interface used by the agents and the LangGraph pipeline.
    """
    from openai import OpenAI

    return OpenAI(base_url=get_base_url(), api_key=api_key or get_api_key())


# ── LangChain layer (native) ───────────────────────────────────────────────────
# All agents and the LangGraph pipeline talk to the model through these helpers so
# the provider/model is defined in exactly one place.

def _make_activity_callback():
    """Build a LangChain callback that mirrors streamed tokens into the activity feed.

    Tokens are coalesced into ~80-char chunks (or up to a newline) before publishing so the
    feed stays small while still feeling live. The callback runs on the calling thread, so
    the thread-local agent label set via activity.set_label() is attached automatically.
    Defined inside a factory so langchain_core is only imported when actually used.
    """
    from langchain_core.callbacks import BaseCallbackHandler

    from agents import activity

    class _ActivityStreamCallback(BaseCallbackHandler):
        def __init__(self):
            self._buf: list[str] = []
            self._buf_len = 0

        def _flush(self):
            if self._buf:
                activity.publish("token", "".join(self._buf))
                self._buf, self._buf_len = [], 0

        def on_chat_model_start(self, serialized, messages, **kwargs):
            activity.publish("start", "thinking...")

        def on_llm_new_token(self, token: str, **kwargs):
            if not token:
                return
            self._buf.append(token)
            self._buf_len += len(token)
            if self._buf_len >= 80 or token.endswith("\n"):
                self._flush()

        def on_llm_end(self, response, **kwargs):
            self._flush()
            activity.publish("end", "done")

        def on_llm_error(self, error, **kwargs):
            self._flush()
            activity.publish("end", f"error: {error}")

    return _ActivityStreamCallback()


def make_chat_model(temperature: float = 0.4, max_tokens: int | None = None,
                    stream_activity: bool = True, **kwargs):
    """LangChain ChatOpenAI bound to the configured local (Ollama) endpoint.

    stream_activity: stream tokens and mirror them into agents.activity so the demo UI
    can show live model output. Disable for tool-calling loops (vendor validation) where
    streamed tool-call deltas are unreliable on some local servers.
    """
    from langchain_openai import ChatOpenAI

    callbacks = kwargs.pop("callbacks", None) or []
    streaming = False
    if get_provider() == "gemini":
        stream_activity = False
    if stream_activity:
        callbacks = [*callbacks, _make_activity_callback()]
        streaming = True

    if streaming:
        # Ask the server to attach usage to the final stream chunk so token counts survive.
        kwargs.setdefault("stream_usage", True)

    return ChatOpenAI(
        base_url=get_base_url(),
        api_key=get_api_key(),
        model=get_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        callbacks=callbacks or None,
        **kwargs,
    )


def _to_lc_messages(messages: list[dict]):
    """Convert OpenAI-style role dicts into LangChain message objects."""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "tool":
            out.append(ToolMessage(content=content, tool_call_id=m.get("tool_call_id", "")))
        else:
            out.append(HumanMessage(content=content))
    return out


def chat_text(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> str | None:
    """Invoke the chat model on OpenAI-style messages and return the text content."""
    text, _ = chat_with_usage(messages, temperature=temperature, max_tokens=max_tokens)
    return text


def chat_with_usage(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> tuple[str | None, dict]:
    """Like chat_text but also returns {input_tokens, output_tokens} for cost tracking."""
    model = make_chat_model(temperature=temperature, max_tokens=max_tokens)
    response = model.invoke(_to_lc_messages(messages))
    usage = getattr(response, "usage_metadata", None) or {}
    return (
        getattr(response, "content", None),
        {
            "input_tokens": usage.get("input_tokens", 0) if usage else 0,
            "output_tokens": usage.get("output_tokens", 0) if usage else 0,
        },
    )
