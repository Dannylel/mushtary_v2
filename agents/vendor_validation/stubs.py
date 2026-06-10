"""
STUBS — replace each function with a real integration once available.
See agents/README.md for what each stub needs to become.

Each stub is clearly marked with:
    # STUB: <what replaces this>
"""
import logging

from .schemas import (
    CRLookupResult,
    CategoryAlignmentResult,
    DocumentCompletenessResult,
    DuplicateCheckResult,
    DocumentMeta,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# STUB 1 — Amaly E-magazine CR lookup
# Replace with: real HTTP scrape or API call to Amaly / WATHQ
# Blocker: we need the URL, auth method, and sample response (see README)
# ---------------------------------------------------------------------------

AMALY_MOCK_DB: dict[str, dict] = {
    "7000000001": {
        "registered_name_ar": "شركة النماذج للتجارة",
        "registered_name_en": "Sample Trading Company",
        "status": "active",
        "registered_activities": ["General Trading", "Information Technology", "Consulting"],
        "issue_date": "2019-03-15",
        "expiry_date": "2026-03-14",
    },
    "7000000002": {
        "registered_name_ar": "مؤسسة الاختبار",
        "registered_name_en": "Test Establishment",
        "status": "expired",
        "registered_activities": ["Retail", "Food Distribution"],
        "issue_date": "2018-01-01",
        "expiry_date": "2023-01-01",
    },
}


def lookup_cr_amaly(cr_number: str) -> CRLookupResult:  # STUB: Amaly / WATHQ API
    logger.info("[STUB] lookup_cr_amaly called", extra={"cr_number": cr_number})
    record = AMALY_MOCK_DB.get(cr_number)
    if not record:
        return CRLookupResult(found=False, cr_number=cr_number, status="not_found")
    return CRLookupResult(
        found=True,
        cr_number=cr_number,
        registered_name_ar=record["registered_name_ar"],
        registered_name_en=record["registered_name_en"],
        status=record["status"],
        registered_activities=record["registered_activities"],
        issue_date=record["issue_date"],
        expiry_date=record["expiry_date"],
    )


# ---------------------------------------------------------------------------
# STUB 2 — Duplicate vendor detection
# Replace with: DB query against vendors table on cr_number + fuzzy name match
# Blocker: need duplicate detection rules confirmed (see README)
# ---------------------------------------------------------------------------

def check_duplicate_vendor(cr_number: str, legal_name_en: str) -> DuplicateCheckResult:  # STUB: DB query
    logger.info("[STUB] check_duplicate_vendor called", extra={"cr_number": cr_number})
    # Always returns no duplicate in stub — real impl queries the DB
    return DuplicateCheckResult(is_duplicate=False)


# ---------------------------------------------------------------------------
# STUB 3 — Category vs CR activity alignment
# Replace with: mapping table of platform categories → allowed CR activity keywords
# Blocker: need full platform category taxonomy (see README)
# ---------------------------------------------------------------------------

CATEGORY_ACTIVITY_MAP: dict[str, list[str]] = {
    # platform category → CR activity keywords that are acceptable
    "Information Technology": ["information technology", "software", "it", "technology", "digital"],
    "General Trading": ["general trading", "trading", "commerce", "import", "export"],
    "Consulting": ["consulting", "advisory", "management consulting"],
    "Manufacturing": ["manufacturing", "production", "fabrication", "industrial"],
    "Retail": ["retail", "distribution", "wholesale"],
    # TODO: expand once full taxonomy is provided
}


def validate_category_alignment(
    cr_activities: list[str],
    selected_categories: list[str],
) -> CategoryAlignmentResult:  # STUB: expand with full taxonomy
    logger.info("[STUB] validate_category_alignment called")

    activities_lower = [a.lower() for a in cr_activities]
    approved, rejected = [], []

    for cat in selected_categories:
        keywords = CATEGORY_ACTIVITY_MAP.get(cat, [])
        matched = any(kw in act for act in activities_lower for kw in keywords)
        if matched:
            approved.append(cat)
        else:
            rejected.append(cat)

    if rejected and approved:
        alignment = "limited"
    elif rejected and not approved:
        alignment = "rejected"
    else:
        alignment = "approved"

    return CategoryAlignmentResult(
        alignment=alignment,
        approved_categories=approved,
        rejected_categories=rejected,
        notes="Stub mapping — expand once full taxonomy provided.",
    )


# ---------------------------------------------------------------------------
# STUB 4 — Document completeness check
# Replace with: configurable required-docs rules per vendor type / category
# Blocker: need required documents list confirmed (see README)
# ---------------------------------------------------------------------------

REQUIRED_DOCS: list[str] = [
    "commercial_registration",
    # TODO: add vat_certificate, saudization_certificate once confirmed mandatory
]


def check_document_completeness(documents: list[DocumentMeta]) -> DocumentCompletenessResult:  # STUB
    logger.info("[STUB] check_document_completeness called")
    present = [doc.doc_type for doc in documents]
    missing = [req for req in REQUIRED_DOCS if req not in present]
    return DocumentCompletenessResult(
        complete=len(missing) == 0,
        missing=missing,
        present=present,
    )
