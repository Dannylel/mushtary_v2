from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── INPUT ──────────────────────────────────────────────────────────────────────

class DocumentMeta(BaseModel):
    """Metadata only — raw file content never reaches the LLM."""
    doc_type: Literal[
        "commercial_registration",
        "vat_certificate",
        "brand_registration",
        "saudization_certificate",
        "iso_certificate",
        "other",
    ]
    filename: str
    size_bytes: int
    uploaded_at: datetime


class VendorValidationInput(BaseModel):
    vendor_id: str
    cr_number: str = Field(..., pattern=r"^7\d{9}$")  # Saudi CR: starts with 7, 10 digits
    legal_name_ar: str
    legal_name_en: str
    selected_categories: list[str]
    documents: list[DocumentMeta]
    is_revalidation: bool = False   # True when triggered by a profile edit


# ── TOOL RESULT SCHEMAS ────────────────────────────────────────────────────────
# These represent what each stub (and later real integration) returns.

class CRLookupResult(BaseModel):
    """Result from Amaly E-magazine CR lookup (stub for now)."""
    found: bool
    cr_number: str
    registered_name_ar: str = ""
    registered_name_en: str = ""
    status: Literal["active", "expired", "not_found", "unknown"] = "unknown"
    registered_activities: list[str] = []
    issue_date: str = ""
    expiry_date: str = ""
    source: str = "amaly_stub"     # swap to "wathq" post-MVP


class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    matched_vendor_id: str | None = None
    match_reason: str | None = None  # "same_cr" | "similar_name"


class CategoryAlignmentResult(BaseModel):
    alignment: Literal["approved", "limited", "rejected"]
    approved_categories: list[str] = []
    rejected_categories: list[str] = []
    notes: str = ""


class DocumentCompletenessResult(BaseModel):
    complete: bool
    missing: list[str] = []
    present: list[str] = []


# ── OUTPUT ─────────────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    outcome: Literal["AUTO_VALIDATED", "NEEDS_CORRECTION", "FLAGGED_FOR_REVIEW"]
    cr_status: Literal["active", "expired", "not_found", "unknown"]
    name_match: bool
    name_match_confidence: float = Field(ge=0.0, le=1.0)
    category_alignment: Literal["approved", "limited", "rejected"]
    is_duplicate: bool
    missing_documents: list[str]
    flags: list[str]            # machine-readable issue tags
    vendor_message: str         # displayed to vendor if NEEDS_CORRECTION
    admin_note: str             # displayed to Platform Admin if FLAGGED_FOR_REVIEW
    trace_id: str
    checked_at: datetime


# Safe fallback used when LLM output fails guardrail validation
VALIDATION_FALLBACK = ValidationResult(
    outcome="FLAGGED_FOR_REVIEW",
    cr_status="unknown",
    name_match=False,
    name_match_confidence=0.0,
    category_alignment="rejected",
    is_duplicate=False,
    missing_documents=[],
    flags=["guardrail_failure"],
    vendor_message="Your registration is under manual review. We will contact you shortly.",
    admin_note="AI validation failed schema guardrails — manual review required.",
    trace_id="fallback",
    checked_at=datetime.utcnow(),
)
