"""
Prompts for SoWExtractorAgent.
System prompt text lives in `agents/prompts/sow_extractor_system.md` (one prompt per file).
"""
from agents.prompts import load_prompt

PROMPT_NAME = "sow_extract_v1"
PROMPT_VERSION = "1.2.0"

SYSTEM_PROMPT = load_prompt("sow_extractor_system")


def build_user_message(raw_text: str, hint_category: str | None = None) -> str:
    hint = f"\nCategory hint (if not clear from document): {hint_category}" if hint_category else ""
    return f"""\
Please extract structured tender information from the following document text.{hint}

DOCUMENT TEXT:
{raw_text}
"""
