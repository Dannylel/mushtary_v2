"""
Prompts for VendorValidationAgent.
The system prompt text lives in `agents/prompts/vendor_validation_system.md`
(one prompt per file). Bump PROMPT_VERSION when that file changes.
"""
from agents.prompts import load_prompt

PROMPT_NAME = "vendor_validation_v1"
PROMPT_VERSION = "1.1.0"

SYSTEM_PROMPT = load_prompt("vendor_validation_system")


def build_user_message(
    cr_number: str,
    legal_name_ar: str,
    legal_name_en: str,
    selected_categories: list[str],
    doc_types: list[str],
) -> str:
    return f"""\
Please validate the following vendor registration:

CR Number: {cr_number}
Legal Name (Arabic): {legal_name_ar}
Legal Name (English): {legal_name_en}
Selected Categories: {', '.join(selected_categories)}
Uploaded Document Types: {', '.join(doc_types) if doc_types else 'none'}

Use all four tools, then return the validation JSON.
"""
