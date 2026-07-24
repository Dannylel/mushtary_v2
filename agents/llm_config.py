"""
Central LLM configuration — single source of truth for provider, model, and credentials.

Local-first: defaults point at a local Ollama server exposing the OpenAI-compatible API.
Everything is overridable via environment variables (loaded from .env), so switching
models or pointing at a remote endpoint never requires touching agent code.

Environment variables (all optional — sensible local defaults applied):
    LLM_BASE_URL   OpenAI-compatible endpoint. Default: http://localhost:11434/v1 (Ollama)
    LLM_MODEL      Model id/tag served by that endpoint. Default: qwen2.5:7b-instruct-q4_K_M
    LLM_API_KEY    API key. Local servers ignore it, but the openai SDK needs a non-empty
                   string. Default: "ollama".

Local-only by decision (2026-06-10): remote-provider key fallbacks (OPENAI_API_KEY,
gemini_API, OPENROUTER_API_KEY) were removed. To target a remote OpenAI-compatible
endpoint later, set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY explicitly.
"""
import json
import os
import re
import threading
import time

from agents.observability import emit, sha256_text, span

# ── Local defaults (Ollama) ────────────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
DEFAULT_API_KEY = "ollama"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-3.5-flash"


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(maximum, max(minimum, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


_LLM_CONCURRENCY = _bounded_int_env("LLM_MAX_CONCURRENCY", 4, 1, 32)
_LLM_SEMAPHORE = threading.BoundedSemaphore(_LLM_CONCURRENCY)
_CIRCUIT_LOCK = threading.Lock()
_CIRCUIT_FAILURES = 0
_CIRCUIT_OPEN_UNTIL = 0.0


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


def get_timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "120")))
    except ValueError:
        return 120.0


def get_max_retries() -> int:
    return _bounded_int_env("LLM_MAX_RETRIES", 2, 0, 5)


def _circuit_before_call() -> None:
    with _CIRCUIT_LOCK:
        if time.monotonic() < _CIRCUIT_OPEN_UNTIL:
            emit("ai.circuit.open", level="WARNING")
            raise RuntimeError("LLM circuit breaker is open; retry after the cooldown")


def _circuit_record(success: bool) -> None:
    global _CIRCUIT_FAILURES, _CIRCUIT_OPEN_UNTIL
    threshold = _bounded_int_env("LLM_CIRCUIT_FAILURE_THRESHOLD", 5, 1, 20)
    try:
        cooldown = max(1.0, float(os.getenv("LLM_CIRCUIT_COOLDOWN_SECONDS", "60")))
    except ValueError:
        cooldown = 60.0
    with _CIRCUIT_LOCK:
        if success:
            _CIRCUIT_FAILURES = 0
            _CIRCUIT_OPEN_UNTIL = 0.0
            return
        _CIRCUIT_FAILURES += 1
        if _CIRCUIT_FAILURES >= threshold:
            _CIRCUIT_OPEN_UNTIL = time.monotonic() + cooldown
            emit(
                "ai.circuit.opened",
                level="WARNING",
                failure_count=_CIRCUIT_FAILURES,
                cooldown_seconds=cooldown,
            )


def make_client(api_key: str | None = None):
    """Build a raw OpenAI-compatible client pointed at the configured endpoint.

    Retained for any code path that wants the bare SDK; the LangChain layer below is
    the primary interface used by the agents and the LangGraph pipeline.
    """
    from openai import OpenAI

    return OpenAI(
        base_url=get_base_url(),
        api_key=api_key or get_api_key(),
        timeout=get_timeout_seconds(),
        max_retries=get_max_retries(),
    )


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
                # Never place raw generated content in the shared operational feed.
                # The UI only needs a progress heartbeat.
                activity.publish("token", "")
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
            activity.publish("end", "stopped with an error; use the job trace for details")

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
        timeout=get_timeout_seconds(),
        max_retries=get_max_retries(),
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
    disable_thinking = get_provider() == "ollama" and get_model().lower().startswith("qwen3")
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
            # Qwen3 reasoning can consume a local generation budget and leave truncated
            # JSON. These agents need the final auditable structure, not a long think trace.
            if disable_thinking and not content.lstrip().startswith("/no_think"):
                content = "/no_think\n" + content
            out.append(HumanMessage(content=content))
    return out


def invoke_bounded(model, messages):
    """Invoke a pre-bound/tool-capable model under the shared reliability controls."""
    _circuit_before_call()
    acquired = _LLM_SEMAPHORE.acquire(timeout=get_timeout_seconds())
    if not acquired:
        raise TimeoutError("Timed out waiting for an available LLM concurrency slot")
    try:
        response = model.invoke(messages)
    except Exception:
        _circuit_record(False)
        raise
    else:
        _circuit_record(True)
        return response
    finally:
        _LLM_SEMAPHORE.release()


def chat_text(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> str | None:
    """Invoke the chat model on OpenAI-style messages and return the text content."""
    text, _ = chat_with_usage(messages, temperature=temperature, max_tokens=max_tokens)
    return text


def _json_object_from_text(raw: str | None) -> dict | None:
    """Extract one JSON object from common local-model wrappers."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1] if len(parts) > 1 else text
        text = re.sub(r"^json\s*", "", text.strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def repair_json_text(raw: str | None, output_contract: str, max_tokens: int | None = None) -> str | None:
    """Repair an already-produced JSON response without re-running its business workflow."""
    parsed = _json_object_from_text(raw)
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False)
    repaired, _ = chat_with_usage(
        [
            {"role": "system", "content": "You are a strict JSON repair service. Return one valid JSON object only; do not add facts or explanations."},
            {"role": "user", "content": "OUTPUT CONTRACT:\n" + output_contract + "\n\nMALFORMED RESPONSE:\n" + str(raw or "") + "\n\nReturn repaired JSON only."},
        ],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    parsed = _json_object_from_text(repaired)
    emit(
        "ai.json_repair.completed" if parsed is not None else "ai.json_repair.failed",
        level="INFO" if parsed is not None else "WARNING",
        result_mode="AI_REPAIRED" if parsed is not None else "DETERMINISTIC_FALLBACK",
    )
    return json.dumps(parsed, ensure_ascii=False) if parsed is not None else raw


def chat_json_with_usage(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> tuple[str | None, dict, bool]:
    """Return JSON text, repairing one malformed local-model response when necessary.

    The original instructions already contain the output schema. The repair turn only
    restores valid JSON and must not add facts or change the requested contract.
    """
    raw, usage = chat_with_usage(messages, temperature=temperature, max_tokens=max_tokens)
    parsed = _json_object_from_text(raw)
    if parsed is not None:
        usage["result_mode"] = "AI_SUCCESS"
        return json.dumps(parsed, ensure_ascii=False), usage, False

    original_contract = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    repair_messages = [
        {
            "role": "system",
            "content": (
                "You are a strict JSON repair service. Return one valid JSON object only. "
                "Do not add facts, explanations, markdown, or fields not required by the original contract."
            ),
        },
        {
            "role": "user",
            "content": (
                "ORIGINAL OUTPUT CONTRACT:\n" + original_contract +
                "\n\nMALFORMED MODEL RESPONSE:\n" + str(raw or "") +
                "\n\nRepair it into the required JSON object only."
            ),
        },
    ]
    repaired, repair_usage = chat_with_usage(repair_messages, temperature=0.0, max_tokens=max_tokens)
    parsed = _json_object_from_text(repaired)
    combined_usage = {
        "input_tokens": usage.get("input_tokens", 0) + repair_usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0) + repair_usage.get("output_tokens", 0),
        "prompt_sha256": usage.get("prompt_sha256", ""),
        "result_mode": "AI_REPAIRED" if parsed is not None else "DETERMINISTIC_FALLBACK",
    }
    emit(
        "ai.json_repair.completed" if parsed is not None else "ai.json_repair.failed",
        level="INFO" if parsed is not None else "WARNING",
        result_mode=combined_usage["result_mode"],
    )
    return (json.dumps(parsed, ensure_ascii=False) if parsed is not None else raw, combined_usage, True)


def chat_json_text(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> str | None:
    """JSON-oriented variant of chat_text with one automatic repair attempt."""
    text, _, _ = chat_json_with_usage(messages, temperature=temperature, max_tokens=max_tokens)
    return text


def chat_with_usage(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> tuple[str | None, dict]:
    """Like chat_text but also returns {input_tokens, output_tokens} for cost tracking."""
    model = make_chat_model(temperature=temperature, max_tokens=max_tokens)
    prompt_fingerprint = sha256_text(
        json.dumps(messages, ensure_ascii=False, sort_keys=True, default=str)
    )
    started = time.perf_counter()
    with span("llm_call"):
        _circuit_before_call()
        emit(
            "ai.call.started",
            provider=get_provider(),
            model=get_model(),
            prompt_sha256=prompt_fingerprint,
            message_count=len(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=get_timeout_seconds(),
        )
        acquired = _LLM_SEMAPHORE.acquire(timeout=get_timeout_seconds())
        if not acquired:
            emit("ai.call.failed", level="ERROR", error_type="ConcurrencyTimeout")
            raise TimeoutError("Timed out waiting for an available LLM concurrency slot")
        try:
            response = model.invoke(_to_lc_messages(messages))
        except Exception as exc:
            _circuit_record(False)
            emit(
                "ai.call.failed",
                level="ERROR",
                provider=get_provider(),
                model=get_model(),
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
            )
            raise
        finally:
            _LLM_SEMAPHORE.release()
        usage = getattr(response, "usage_metadata", None) or {}
        _circuit_record(True)
        result_usage = {
            "input_tokens": usage.get("input_tokens", 0) if usage else 0,
            "output_tokens": usage.get("output_tokens", 0) if usage else 0,
            "prompt_sha256": prompt_fingerprint,
            "result_mode": "AI_SUCCESS",
        }
        emit(
            "ai.call.completed",
            provider=get_provider(),
            model=get_model(),
            duration_ms=round((time.perf_counter() - started) * 1000),
            **result_usage,
        )
        return getattr(response, "content", None), result_usage
