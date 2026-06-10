"""
VendorValidationAgent — local LLM (Ollama via LangChain, see agents/llm_config.py)

Agentic tool-use loop:
  1. Send vendor registration data + system prompt to the local model
  2. The model calls tools (CR lookup, duplicate check, category alignment, doc completeness)
  3. We execute each tool locally and return results
  4. The model reasons over all results and returns structured ValidationResult JSON
  5. Guardrails validate the JSON — fallback applied if invalid
  6. AIArtifact built and returned for DB persistence
"""
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.base import AIArtifact, BaseAgent
from agents.guardrails import safe_parse
from agents.llm_config import make_chat_model

from .prompts import PROMPT_NAME, PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from .schemas import (
    VALIDATION_FALLBACK,
    DocumentMeta,
    ValidationResult,
    VendorValidationInput,
)
from .stubs import (
    check_document_completeness,
    check_duplicate_vendor,
    lookup_cr_amaly,
    validate_category_alignment,
)

logger = logging.getLogger(__name__)

# ── Tool definitions (OpenAI format) ──────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_cr_amaly",
            "description": (
                "Look up a Saudi CR number in the Amaly registry. "
                "Returns registered legal name, CR status, and business activities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_number": {"type": "string", "description": "10-digit Saudi CR number starting with 7"},
                },
                "required": ["cr_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_duplicate_vendor",
            "description": "Check if a vendor with the same CR number or similar name already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_number": {"type": "string"},
                    "legal_name_en": {"type": "string"},
                },
                "required": ["cr_number", "legal_name_en"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_category_alignment",
            "description": "Check if the vendor's selected categories match their CR-registered activities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_activities": {"type": "array", "items": {"type": "string"}},
                    "selected_categories": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cr_activities", "selected_categories"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_document_completeness",
            "description": "Check whether all required documents have been uploaded.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uploaded_doc_types": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["uploaded_doc_types"],
            },
        },
    },
]


def _dispatch_tool(name: str, args: dict, documents: list[DocumentMeta]) -> str:
    if name == "lookup_cr_amaly":
        result = lookup_cr_amaly(args["cr_number"])
    elif name == "check_duplicate_vendor":
        result = check_duplicate_vendor(args["cr_number"], args["legal_name_en"])
    elif name == "validate_category_alignment":
        result = validate_category_alignment(args["cr_activities"], args["selected_categories"])
    elif name == "check_document_completeness":
        doc_metas = [d for d in documents if d.doc_type in args["uploaded_doc_types"]]
        result = check_document_completeness(doc_metas)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return result.model_dump_json()


class VendorValidationAgent(BaseAgent):
    artifact_type = "VENDOR_VALIDATION"
    max_tool_rounds = 6

    def __init__(self, api_key: str | None = None):
        # Native LangChain: bind the OpenAI-format tool schemas to the local chat model.
        self._model = make_chat_model(temperature=0.1, max_tokens=1024).bind_tools(TOOLS)

    def run(self, payload: VendorValidationInput) -> AIArtifact:
        trace_id = self.new_trace_id()
        logger.info("VendorValidationAgent started", extra={"trace_id": trace_id, "vendor_id": payload.vendor_id})

        input_snapshot = self.sanitize_input(payload.model_dump(mode="json"))
        doc_types = [doc.doc_type for doc in payload.documents]

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_message(
                cr_number=payload.cr_number,
                legal_name_ar=payload.legal_name_ar,
                legal_name_en=payload.legal_name_en,
                selected_categories=payload.selected_categories,
                doc_types=doc_types,
            )),
        ]

        total_input_tokens = 0
        total_output_tokens = 0
        final_text: str | None = None

        # ── Agentic tool-use loop (LangChain bind_tools) ───────────────────
        for round_num in range(self.max_tool_rounds):
            logger.debug("Tool-use loop round %d", round_num + 1, extra={"trace_id": trace_id})

            ai_msg = self._model.invoke(messages)

            usage = getattr(ai_msg, "usage_metadata", None) or {}
            total_input_tokens += usage.get("input_tokens", 0) if usage else 0
            total_output_tokens += usage.get("output_tokens", 0) if usage else 0

            tool_calls = getattr(ai_msg, "tool_calls", None)

            if not tool_calls:
                final_text = ai_msg.content
                break

            # Append the assistant turn (carrying the tool-call requests)
            messages.append(ai_msg)

            # Execute each tool locally and append its result
            for tc in tool_calls:
                result = _dispatch_tool(tc["name"], tc.get("args") or {}, payload.documents)
                logger.debug("Tool executed", extra={"tool": tc["name"], "trace_id": trace_id})
                messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

        else:
            logger.warning("Tool-use loop hit max rounds — flagging for review", extra={"trace_id": trace_id})
            final_text = None

        validated = self._parse_output(final_text, trace_id)

        artifact = self.build_artifact(
            trace_id=trace_id,
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
            input_snapshot=input_snapshot,
            output=validated.model_dump(mode="json"),
            usage={"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            vendor_id=payload.vendor_id,
        )

        logger.info("VendorValidationAgent complete", extra={"trace_id": trace_id, "outcome": validated.outcome})
        return artifact

    def _parse_output(self, raw_text: str | None, trace_id: str) -> ValidationResult:
        if not raw_text:
            return VALIDATION_FALLBACK.model_copy(update={"trace_id": trace_id})

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            raw_dict = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return VALIDATION_FALLBACK.model_copy(update={"trace_id": trace_id})

        raw_dict["trace_id"] = trace_id
        raw_dict["checked_at"] = datetime.now(timezone.utc).isoformat()

        fallback = VALIDATION_FALLBACK.model_copy(update={"trace_id": trace_id})
        return safe_parse(raw_dict, ValidationResult, fallback, trace_id)
