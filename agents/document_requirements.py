"""Agent-assisted vendor document applicability assessment for the MVP.

It is advisory: hard activation decisions remain with the validation policy and a
human reviewer until issuer, expiry, and identity checks are connected to real services.
"""
from __future__ import annotations

import json
import re
from typing import Any

from agents.llm_config import chat_json_text
from agents.prompts import GLOBAL_QUALITY_STANDARD


BASE_REQUIRED = {"commercial_registration"}


def assess_document_requirements(*, categories: list[str], document_types: list[str]) -> dict[str, Any]:
    fallback = {
        "mode": "deterministic_fallback",
        "required_now": sorted(BASE_REQUIRED),
        "conditional": ["vat_certificate", "saudization_certificate", "brand_registration"],
        "missing_required": sorted(BASE_REQUIRED - set(document_types)),
        "review_flags": ["Demo document metadata only; issuer, expiry, and legal-name checks require verified integrations."],
    }
    system = GLOBAL_QUALITY_STANDARD + """
You are the Vendor Document Applicability Agent for Saudi procurement. Based only on selected
categories and uploaded document TYPES, identify which document types are immediately required,
which are conditional, and what a human must verify. Do not claim a certificate is authentic,
valid, current, or legally sufficient. Return only JSON:
{"required_now":["..."],"conditional":["..."],"review_flags":["..."]}."""
    try:
        raw = chat_json_text(
            [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"categories": categories, "uploaded_document_types": document_types})}],
            temperature=0.0, max_tokens=700,
        )
        match = re.search(r"\{.*\}", raw or "", re.S)
        data = json.loads(match.group(0)) if match else {}
        if not isinstance(data, dict):
            return fallback
        required = [str(v) for v in data.get("required_now", []) if str(v)]
        conditional = [str(v) for v in data.get("conditional", []) if str(v)]
        return {
            "mode": "agent",
            "required_now": sorted(set(required) | BASE_REQUIRED),
            "conditional": sorted(set(conditional)),
            "missing_required": sorted((set(required) | BASE_REQUIRED) - set(document_types)),
            "review_flags": [str(v) for v in data.get("review_flags", []) if str(v)],
        }
    except Exception:
        return fallback
