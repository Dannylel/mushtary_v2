"""
Tender PDF renderer — turns an assembled TenderDraft (or its AIArtifact) into the
branded RFP PDF. Extracted from the legacy main.py so both entry points (run.py and
main.py) share one renderer.

Pure presentation: no LLM calls, no agent logic. Accepts a dict, a Pydantic model,
or a full AIArtifact (it unwraps .output automatically).
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT_PDF = Path("outputs") / "tender_draft.pdf"
DEFAULT_LOGO_PATH = Path("assets") / "buyer_logo.png"
PDF_FONT = "Helvetica"


def _register_fonts(pdf: FPDF):
    """Use a modern Windows font when available; fall back to FPDF core fonts."""
    global PDF_FONT

    fonts_dir = Path("C:/Windows/Fonts")
    regular = fonts_dir / "calibri.ttf"
    bold = fonts_dir / "calibrib.ttf"
    italic = fonts_dir / "calibrii.ttf"

    if not regular.exists() or not bold.exists():
        PDF_FONT = "Helvetica"
        return

    try:
        pdf.add_font("DocFont", "", str(regular))
        pdf.add_font("DocFont", "B", str(bold))
        if italic.exists():
            pdf.add_font("DocFont", "I", str(italic))
        PDF_FONT = "DocFont"
    except Exception:
        PDF_FONT = "Helvetica"

def _safe_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2192": "->",
        "\u2022": "-",
        "\u00a0": " ",
        "\u2705": "[OK]",
        "\u274c": "[X]",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.encode("latin-1", errors="replace").decode("latin-1")


def _as_dict(obj: Any) -> dict:
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")

    if hasattr(obj, "dict"):
        return obj.dict()

    return {}


def _as_list(value: Any) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")

    if hasattr(obj, "dict"):
        return obj.dict()

    return obj


def _unwrap_draft(draft: Any) -> dict:
    raw = _to_jsonable(draft)

    if isinstance(raw, dict) and isinstance(raw.get("output"), dict):
        payload = raw["output"]

        if "trace_id" not in payload and raw.get("trace_id"):
            payload["trace_id"] = raw.get("trace_id")

        return payload

    return raw if isinstance(raw, dict) else {}


def _format_percent(value: Any) -> str:
    if value is None or value == "":
        return ""

    try:
        number = float(value)
        if number.is_integer():
            return f"{int(number)}%"
        return f"{number}%"
    except (TypeError, ValueError):
        text = str(value)
        return text if text.endswith("%") else f"{text}%"


def _initials(name: str) -> str:
    words = [word for word in _safe_text(name).replace("&", " ").split() if word]
    initials = "".join(word[0].upper() for word in words[:2])
    return initials or "BE"


def _logo_path(metadata: dict, tender_data_sheet: dict) -> Path | None:
    candidates = [
        metadata.get("buyer_logo_path"),
        tender_data_sheet.get("buyer_logo_path"),
        DEFAULT_LOGO_PATH,
    ]

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path

    return None


class TenderPDF(FPDF):
    def __init__(self, doc_title: str = "", tender_ref: str = "", status: str = "DRAFT - Pending Buyer Approval"):
        super().__init__()
        self.doc_title = doc_title
        self.tender_ref = tender_ref
        self.status = status

    def header(self):
        if self.page_no() == 1:
            return

        self.set_y(8)
        self.set_text_color(30, 30, 30)
        self.set_draw_color(205, 205, 205)
        self.set_line_width(0.15)
        self.set_x(self.l_margin)
        self.set_font(PDF_FONT, "B", 7.5)
        self.cell(62, 4, _safe_text(self.tender_ref or "Tender Reference"), align="L")
        self.set_font(PDF_FONT, "", 7.5)
        self.cell(0, 4, _safe_text("Formal Tender Package"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        self.set_x(self.l_margin)
        self.set_font(PDF_FONT, "", 6.8)
        self.set_text_color(85, 85, 85)
        self.cell(0, 3.5, _safe_text(self.status), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        self.line(self.l_margin, self.get_y() + 1.2, self.w - self.r_margin, self.get_y() + 1.2)
        self.ln(7)
        self.set_x(self.l_margin)

    def footer(self):
        if self.page_no() == 1:
            return

        self.set_y(-16)
        self.set_x(self.l_margin)
        self.set_draw_color(205, 205, 205)
        self.set_line_width(0.15)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        self.set_text_color(70, 70, 70)
        self.set_font(PDF_FONT, "", 7)
        self.cell(68, 4, _safe_text("Confidential - Buyer controlled tender document"), align="L")
        self.cell(0, 4, _safe_text(f"Page {self.page_no()}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        self.set_x(self.l_margin)
        self.set_font(PDF_FONT, "", 6.5)
        self.set_text_color(95, 95, 95)
        self.cell(0, 4, _safe_text("Generated by Mushtarry AI - Draft pending Buyer-Admin approval before publication"), align="C")
        self.set_text_color(0, 0, 0)


def _ensure_space(pdf: TenderPDF, min_height: float = 18):
    if pdf.get_y() + min_height > pdf.page_break_trigger:
        pdf.add_page()
        pdf.set_x(pdf.l_margin)


def _write_section(pdf: TenderPDF, title: str):
    _ensure_space(pdf, 16)
    pdf.set_x(pdf.l_margin)
    pdf.ln(5)
    pdf.set_x(pdf.l_margin)
    pdf.set_draw_color(185, 185, 185)
    pdf.set_line_width(0.18)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font(PDF_FONT, "B", 13)
    pdf.multi_cell(0, 7.2, _safe_text(title))
    pdf.line(pdf.l_margin, pdf.get_y() + 0.5, pdf.w - pdf.r_margin, pdf.get_y() + 0.5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.ln(4)


def _write_subsection(pdf: TenderPDF, title: str):
    _ensure_space(pdf, 12)
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(35, 35, 35)
    pdf.set_font(PDF_FONT, "B", 10)
    pdf.multi_cell(0, 5.5, _safe_text(title))
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)


def _write_para(pdf: TenderPDF, text: Any):
    if not text:
        return

    _ensure_space(pdf, 10)
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(PDF_FONT, "", 9.5)
    pdf.multi_cell(0, 5.2, _safe_text(text))
    pdf.set_x(pdf.l_margin)
    pdf.ln(1.5)
    pdf.set_text_color(0, 0, 0)


def _write_bullets(pdf: TenderPDF, items: list[Any]):
    pdf.set_font(PDF_FONT, "", 9.4)

    for item in _as_list(items):
        if not item:
            continue

        _ensure_space(pdf, 8)
        pdf.set_x(pdf.l_margin)
        pdf.cell(4, 5, "-", align="L")
        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(0, 5, _safe_text(item))

    pdf.set_x(pdf.l_margin)
    pdf.ln(1)


def _write_key_value_table(pdf: TenderPDF, rows: list[tuple[str, Any]]):
    left_w = 56
    right_w = pdf.w - pdf.l_margin - pdf.r_margin - left_w

    for key, value in rows:
        if value is None:
            value = ""

        key_text = _safe_text(key)
        value_text = _safe_text(value)
        key_lines = max(1, len(key_text) // 32 + 1)
        value_lines = max(1, len(value_text) // 82 + 1)
        row_h = max(7, min(28, max(key_lines, value_lines) * 4.2 + 4))

        _ensure_space(pdf, row_h + 2)
        pdf.set_x(pdf.l_margin)

        x = pdf.get_x()
        y = pdf.get_y()

        pdf.set_draw_color(220, 220, 220)
        pdf.set_line_width(0.12)
        pdf.line(x, y, x + left_w + right_w, y)
        pdf.line(x, y + row_h, x + left_w + right_w, y + row_h)

        pdf.set_xy(x + 2, y + 2)
        pdf.set_text_color(80, 80, 80)
        pdf.set_font(PDF_FONT, "B", 9)
        pdf.multi_cell(left_w - 4, 4.2, key_text)

        pdf.set_xy(x + left_w + 2, y + 2)
        pdf.set_text_color(25, 25, 25)
        pdf.set_font(PDF_FONT, "", 9)
        pdf.multi_cell(right_w - 4, 4.2, value_text)

        pdf.set_y(y + row_h)
        pdf.set_x(pdf.l_margin)

    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)


def _write_notice_box(pdf: TenderPDF, title: str, text: str, *, fill=(255, 255, 255), border=(0, 0, 0)):
    if not text:
        return

    _ensure_space(pdf, 26)
    x = pdf.l_margin
    y = pdf.get_y()
    w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(195, 195, 195)
    pdf.set_line_width(0.18)
    pdf.line(x, y, x + w, y)
    pdf.line(x, y + 22, x + w, y + 22)
    pdf.set_draw_color(35, 35, 35)
    pdf.set_line_width(0.55)
    pdf.line(x, y, x, y + 22)
    pdf.set_xy(x + 5, y + 3)
    pdf.set_text_color(25, 25, 25)
    pdf.set_font(PDF_FONT, "B", 9)
    pdf.multi_cell(w - 10, 4.6, _safe_text(title))
    pdf.set_x(x + 5)
    pdf.set_text_color(55, 55, 55)
    pdf.set_font(PDF_FONT, "", 8.5)
    pdf.multi_cell(w - 10, 4.3, _safe_text(text))
    pdf.set_y(y + 26)
    pdf.set_text_color(0, 0, 0)


def _write_process_figure(pdf: TenderPDF, title: str, steps: list[str]):
    steps = [s for s in steps if s]
    if not steps:
        return

    _ensure_space(pdf, 42)
    _write_subsection(pdf, title)
    x0 = pdf.l_margin
    y = pdf.get_y() + 5
    total_w = pdf.w - pdf.l_margin - pdf.r_margin
    node_r = 4.2
    usable_w = total_w - node_r * 2
    step_gap = usable_w / max(1, len(steps) - 1) if len(steps) > 1 else 0
    line_y = y + node_r
    pdf.set_draw_color(185, 185, 185)
    pdf.set_line_width(0.35)
    if len(steps) > 1:
        pdf.line(x0 + node_r, line_y, x0 + total_w - node_r, line_y)

    for i, step in enumerate(steps):
        cx = x0 + node_r + (i * step_gap if len(steps) > 1 else usable_w / 2)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(40, 40, 40)
        pdf.ellipse(cx - node_r, y, node_r * 2, node_r * 2)
        pdf.set_xy(cx - node_r, y + 1.3)
        pdf.set_font(PDF_FONT, "B", 7)
        pdf.set_text_color(25, 25, 25)
        pdf.cell(node_r * 2, 3.5, str(i + 1), align="C")
        label_w = min(38, total_w / len(steps) - 2)
        label_x = max(x0, min(cx - label_w / 2, x0 + total_w - label_w))
        pdf.set_xy(label_x, y + 11)
        pdf.set_font(PDF_FONT, "", 7.2)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(label_w, 3.4, _safe_text(step), align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + 25)
    pdf.set_x(pdf.l_margin)


def _write_matrix_table(pdf: TenderPDF, title: str, headers: list[str], rows: list[list[Any]]):
    if not rows:
        return

    _write_subsection(pdf, title)
    col_count = max(1, len(headers))
    total_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = total_w / col_count
    row_h = 8.5

    _ensure_space(pdf, row_h * (len(rows) + 2))
    pdf.set_draw_color(210, 210, 210)
    pdf.set_line_width(0.12)
    pdf.set_font(PDF_FONT, "B", 8)
    y = pdf.get_y()
    x = pdf.l_margin

    pdf.set_fill_color(245, 245, 245)
    pdf.rect(x, y, total_w, row_h, style="F")
    pdf.line(x, y, x + total_w, y)
    pdf.line(x, y + row_h, x + total_w, y + row_h)
    for idx, header in enumerate(headers):
        pdf.set_xy(x + idx * col_w + 1.5, y + 2)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(col_w - 3, 3.5, _safe_text(header), align="C")

    y += row_h
    pdf.set_font(PDF_FONT, "", 8)
    pdf.set_text_color(30, 30, 30)
    for row in rows:
        _ensure_space(pdf, row_h + 2)
        x = pdf.l_margin
        pdf.line(x, y + row_h, x + total_w, y + row_h)
        for idx in range(col_count):
            value = row[idx] if idx < len(row) else ""
            pdf.set_xy(x + idx * col_w + 1.5, y + 2)
            pdf.multi_cell(col_w - 3, 3.5, _safe_text(value), align="C")
        y += row_h
        pdf.set_y(y)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _write_document_control_page(pdf: TenderPDF, d: dict, metadata: dict, tender_data_sheet: dict, intelligence: dict):
    generated_at = intelligence.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf.add_page()
    _write_section(pdf, "Document Control")
    _write_key_value_table(
        pdf,
        [
            ("Document Type", "Request for Proposal (RFP) / Tender Package"),
            ("Tender Title", metadata.get("title") or tender_data_sheet.get("tender_title", "")),
            ("Tender Reference", metadata.get("tender_id") or tender_data_sheet.get("tender_reference", "")),
            ("Buyer Entity", metadata.get("buyer_entity") or tender_data_sheet.get("buyer_entity", "")),
            ("Version", "1.0"),
            ("Generated Date", generated_at),
            ("Trace ID", d.get("trace_id", "")),
            ("Document Status", intelligence.get("document_status") or "Draft - Pending Buyer Approval"),
            ("Publication Status", "Not Published"),
        ],
    )

    _write_subsection(pdf, "Approval and Publication Control")
    _write_notice_box(
        pdf,
        "Buyer-Admin Approval Required",
        "This tender package was generated by Mushtarry AI for buyer review. It is not approved, issued, or published until the authorized Buyer-Admin completes the approval block and changes the document status to Approved / Published.",
    )
    _write_process_figure(
        pdf,
        "Document Lifecycle",
        ["AI Draft", "Buyer Review", "Buyer-Admin Approval", "Official Publication"],
    )

    _write_subsection(pdf, "Confidentiality and Use")
    _write_para(
        pdf,
        "This document is confidential and intended only for authorized buyer review and controlled tender publication. Vendors may rely on this document only after the Buyer-Admin approval and official publication through the approved channel.",
    )

    _write_subsection(pdf, "Document Status Definitions")
    _write_key_value_table(
        pdf,
        [
            ("Draft", "Generated by Mushtarry AI and pending Buyer-Admin review. Not valid for issue to market."),
            ("Approved", "Reviewed and accepted by the Buyer-Admin. Ready for controlled publication."),
            ("Published", "Officially issued to vendors through the approved publication channel."),
        ],
    )


def _write_document_table(pdf: TenderPDF, title: str, docs: list[Any]):
    if not docs:
        return

    _write_subsection(pdf, title)

    for doc in docs:
        d = _as_dict(doc)

        _ensure_space(pdf, 14)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(PDF_FONT, "B", 10)
        pdf.multi_cell(0, 5.5, _safe_text(f"- {d.get('name', '')}"))

        detail_parts = []

        if d.get("category"):
            detail_parts.append(f"Category: {d.get('category')}")

        if d.get("applicability"):
            detail_parts.append(f"Applicability: {d.get('applicability')}")

        if d.get("issuing_authority"):
            detail_parts.append(f"Issuing Authority: {d.get('issuing_authority')}")

        if d.get("notes"):
            detail_parts.append(f"Notes: {d.get('notes')}")

        if detail_parts:
            _ensure_space(pdf, 10)
            pdf.set_x(pdf.l_margin)
            pdf.set_font(PDF_FONT, "", 9)
            pdf.multi_cell(0, 5, _safe_text("  " + " | ".join(detail_parts)))

    pdf.set_x(pdf.l_margin)
    pdf.ln(1)


def _write_cover_page(pdf: TenderPDF, d: dict, metadata: dict, tender_data_sheet: dict, intelligence: dict):
    status = "DRAFT - PENDING BUYER APPROVAL"
    generated_at = intelligence.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    buyer_name = metadata.get("buyer_entity") or tender_data_sheet.get("buyer_entity") or "Buyer Entity"
    tender_title = metadata.get("title") or tender_data_sheet.get("tender_title") or "Tender Draft"
    logo_path = _logo_path(metadata, tender_data_sheet)

    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    left = 22
    right = pdf.w - 22
    width = right - left

    pdf.set_draw_color(25, 25, 25)
    pdf.set_line_width(0.35)
    pdf.line(left, 20, right, 20)
    pdf.set_draw_color(215, 215, 215)
    pdf.set_line_width(0.15)
    pdf.line(left, 23, right, 23)

    pdf.set_xy(left, 30)
    if logo_path:
        pdf.image(str(logo_path), x=left, y=27, w=28)
    else:
        pdf.set_draw_color(40, 40, 40)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(left, 30, 22, 22)
        pdf.set_xy(left, 36.5)
        pdf.set_font(PDF_FONT, "B", 12)
        pdf.set_text_color(25, 25, 25)
        pdf.cell(22, 7, _safe_text(_initials(buyer_name)), align="C")

    pdf.set_xy(left + 34, 30)
    pdf.set_text_color(25, 25, 25)
    pdf.set_font(PDF_FONT, "B", 12.5)
    pdf.multi_cell(width - 77, 6, _safe_text(buyer_name))
    pdf.set_x(left + 34)
    pdf.set_font(PDF_FONT, "", 8.8)
    pdf.set_text_color(85, 85, 85)
    pdf.multi_cell(width - 77, 4.6, _safe_text("Formal tender document prepared for Buyer-Admin review."))

    pdf.set_xy(right - 42, 31)
    pdf.set_draw_color(55, 55, 55)
    pdf.set_line_width(0.18)
    pdf.rect(right - 42, 31, 42, 13)
    pdf.set_xy(right - 40, 33)
    pdf.set_font(PDF_FONT, "B", 7.2)
    pdf.set_text_color(35, 35, 35)
    pdf.multi_cell(38, 3.6, _safe_text(status), align="C")

    pdf.set_xy(left, 82)
    pdf.set_font(PDF_FONT, "", 9)
    pdf.set_text_color(85, 85, 85)
    pdf.cell(0, 5, _safe_text("Request for Proposal (RFP)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(left)
    pdf.set_font(PDF_FONT, "B", 24)
    pdf.set_text_color(15, 15, 15)
    pdf.multi_cell(width, 10, _safe_text(tender_title))
    pdf.ln(2)
    pdf.set_x(left)
    pdf.set_font(PDF_FONT, "", 10)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(width, 5.5, _safe_text("Professional tender package generated by Mushtarry AI. Not valid for market issue until Buyer-Admin approval."))

    pdf.ln(9)
    pdf.set_draw_color(35, 35, 35)
    pdf.set_line_width(0.28)
    pdf.line(left, pdf.get_y(), left + 48, pdf.get_y())
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.12)
    pdf.line(left + 52, pdf.get_y(), right, pdf.get_y())
    pdf.ln(9)

    _write_key_value_table(
        pdf,
        [
            ("Tender Reference Number", metadata.get("tender_id") or tender_data_sheet.get("tender_reference", "")),
            ("Issue Date", metadata.get("issue_date") or tender_data_sheet.get("issue_date", "")),
            ("Submission Deadline", tender_data_sheet.get("submission_deadline", "")),
            ("Document Version", "Version 1.0 - AI Draft"),
            ("Generated Date", generated_at),
            ("Trace ID", d.get("trace_id", "")),
            ("Document Status", "Draft / Not Published"),
        ],
    )

    pdf.set_y(238)
    pdf.set_x(left)
    pdf.set_draw_color(210, 210, 210)
    pdf.set_line_width(0.15)
    pdf.line(left, pdf.get_y() - 4, right, pdf.get_y() - 4)
    pdf.set_font(PDF_FONT, "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5, _safe_text("Confidentiality Notice"))
    pdf.set_x(left)
    pdf.set_font(PDF_FONT, "", 8.5)
    pdf.set_text_color(65, 65, 65)
    pdf.multi_cell(
        width,
        5,
        _safe_text(
            "This document is confidential and intended only for authorized buyer review. "
            "It was generated by Mushtarry AI and cannot be issued, published, or used for award "
            "until approved by the Buyer-Admin."
        ),
    )
    pdf.set_text_color(0, 0, 0)


def _write_toc(pdf: TenderPDF):
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.set_font(PDF_FONT, "B", 16)
    pdf.multi_cell(0, 9, _safe_text("Table of Contents"), align="C")
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)

    _write_bullets(
        pdf,
        [
            "Document Control",
            "1. Tender Data Sheet",
            "2. Introduction",
            "3. Instructions to Bidders",
            "4. Award and Contract",
            "5. Eligibility and Vendor Document Requirements",
            "6. Proposal Submission Requirements",
            "7. Project Overview",
            "8. Objectives",
            "9. Scope of Work",
            "10. Deliverables",
            "11. Timeline",
            "12. Team Requirements",
            "13. General Terms and Conditions",
            "14. Confidentiality",
            "15. Technical and Financial Evaluation Methodology",
            "16. Payment Terms",
            "17. Annexures",
            "18. Buyer Approval",
        ],
    )


def build_pdf(draft: Any, output_path: Path = OUTPUT_PDF):
    d = _unwrap_draft(draft)

    metadata = d.get("metadata", {})
    tender_data_sheet = d.get("tender_data_sheet", {})
    introduction = d.get("introduction", {})
    instructions = d.get("instructions_to_bidders", {})
    award = d.get("award_and_contract", {})
    proposal_format = d.get("proposal_format", {})
    overview = d.get("project_overview", {})
    objectives = d.get("objectives", {})
    scope = d.get("scope_of_work", {})
    deliverables = d.get("deliverables", {})
    timeline = d.get("timeline", {})
    team = d.get("team_requirements", {})
    terms = d.get("general_terms", {})
    evaluation = d.get("evaluation_criteria", {})
    payment = d.get("payment_terms", {})
    annexures = d.get("annexures", [])
    intelligence = d.get("tender_intelligence", {})

    pdf = TenderPDF(
        doc_title=metadata.get("title", ""),
        tender_ref=metadata.get("tender_id") or tender_data_sheet.get("tender_reference", ""),
    )
    _register_fonts(pdf)
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    _write_cover_page(pdf, d, metadata, tender_data_sheet, intelligence)

    _write_document_control_page(pdf, d, metadata, tender_data_sheet, intelligence)
    _write_toc(pdf)

    pdf.add_page()

    _write_section(pdf, "1. Tender Data Sheet")
    _write_key_value_table(
        pdf,
        [
            ("Tender Title", tender_data_sheet.get("tender_title", "")),
            ("Tender Reference", tender_data_sheet.get("tender_reference", "")),
            ("Buyer Entity", tender_data_sheet.get("buyer_entity", "")),
            ("Procurement Category", tender_data_sheet.get("procurement_category", "")),
            ("Tender Type", tender_data_sheet.get("tender_type", "")),
            ("Procurement Method", tender_data_sheet.get("procurement_method", "")),
            ("Submission Method", tender_data_sheet.get("submission_method", "")),
            ("Issue Date", tender_data_sheet.get("issue_date", "")),
            ("Site Visit", tender_data_sheet.get("site_visit", "")),
            ("Clarification Deadline", tender_data_sheet.get("clarification_deadline", "")),
            ("Submission Deadline", tender_data_sheet.get("submission_deadline", "")),
            ("Opening Date", tender_data_sheet.get("opening_date", "")),
            ("Proposal Validity", tender_data_sheet.get("proposal_validity", "")),
            ("Bid Security", tender_data_sheet.get("bid_security", "")),
            ("Performance Bond", tender_data_sheet.get("performance_bond", "")),
            ("Contract Duration", tender_data_sheet.get("contract_duration", "")),
            ("Warranty Duration", tender_data_sheet.get("warranty_duration", "")),
            ("Language", tender_data_sheet.get("language", "")),
            ("Evaluation Model", tender_data_sheet.get("evaluation_model", "")),
            ("Minimum Technical Score", tender_data_sheet.get("minimum_technical_score", "")),
        ],
    )

    _write_section(pdf, "2. Introduction")
    _write_subsection(pdf, "About the Organisation")
    _write_para(pdf, introduction.get("about_organization", ""))
    _write_subsection(pdf, "Background")
    _write_para(pdf, introduction.get("background", ""))
    _write_subsection(pdf, "Purpose of this RFP")
    _write_para(pdf, introduction.get("purpose_of_rfp", ""))

    _write_section(pdf, "3. Instructions to Bidders")
    _write_subsection(pdf, "3.1 Submission Rules")
    _write_bullets(pdf, instructions.get("submission_rules", []))

    timetable = instructions.get("timetable", {})
    _write_subsection(pdf, "3.2 Timetable")
    _write_key_value_table(
        pdf,
        [
            ("RFP Issue Date", timetable.get("issue_date", "")),
            ("Clarifications Deadline", timetable.get("clarifications_deadline", "")),
            ("Proposal Submission Deadline", timetable.get("submission_deadline", "")),
        ],
    )

    _write_subsection(pdf, "3.3 Clarifications Process")
    _write_para(pdf, instructions.get("clarifications_process", ""))

    _write_subsection(pdf, "3.4 Proposal Validity")
    _write_para(
        pdf,
        f"Proposals must remain valid for {instructions.get('proposal_validity_days', 90)} days from the closing date.",
    )

    _write_subsection(pdf, "3.5 Confidentiality")
    _write_para(pdf, instructions.get("confidentiality_statement", ""))

    _write_subsection(pdf, "3.6 Conflict of Interest")
    _write_para(pdf, instructions.get("conflict_of_interest_policy", ""))

    _write_subsection(pdf, "3.7 Cancellation Rights")
    _write_para(pdf, instructions.get("cancellation_rights", ""))

    submission_controls = instructions.get("submission_controls") or {}

    if submission_controls:
        _ensure_space(pdf, 95)

        _write_subsection(pdf, "3.8 Platform Submission Controls")
        _write_key_value_table(
            pdf,
            [
                (
                    "Platform Submission Only",
                    "Yes" if submission_controls.get("platform_submission_only") else "No",
                ),
                (
                    "Separate Technical / Commercial",
                    "Yes" if submission_controls.get("separate_technical_commercial") else "No",
                ),
                ("Technical File Format", submission_controls.get("technical_file_format", "")),
                ("Commercial File Format", submission_controls.get("commercial_file_format", "")),
                ("Maximum File Size", f"{submission_controls.get('max_file_size_mb', '')} MB"),
                (
                    "Resubmission Before Deadline",
                    "Yes" if submission_controls.get("resubmission_allowed_before_deadline") else "No",
                ),
                (
                    "Submission Lock After Deadline",
                    "Yes" if submission_controls.get("lock_after_deadline") else "No",
                ),
                (
                    "Late Submission Allowed",
                    "Yes" if submission_controls.get("late_submission_allowed") else "No",
                ),
                (
                    "Completeness Check Required",
                    "Yes" if submission_controls.get("completeness_check_required") else "No",
                ),
                (
                    "Official Timestamp",
                    "Mushtarry platform timestamp is official"
                    if submission_controls.get("timestamp_is_official")
                    else "Not specified",
                ),
            ],
        )
        _write_bullets(pdf, submission_controls.get("rules", []))

    pdf.add_page()

    _write_section(pdf, "4. Award and Contract")
    _write_subsection(pdf, "4.1 Evaluation Process")
    _write_para(pdf, award.get("evaluation_process", ""))
    _write_subsection(pdf, "4.2 Negotiation Policy")
    _write_para(pdf, award.get("negotiation_policy", ""))
    _write_subsection(pdf, "4.3 Award Rules")
    _write_para(pdf, award.get("award_rules", ""))
    _write_subsection(pdf, "4.4 Bid Security")
    _write_para(pdf, award.get("bid_security", ""))
    _write_subsection(pdf, "4.5 Performance Bond")
    _write_para(pdf, award.get("performance_bond_text", ""))
    _write_subsection(pdf, "4.6 Saudization Requirements")
    _write_para(pdf, award.get("saudization_requirements", ""))

    _write_section(pdf, "5. Eligibility and Vendor Document Requirements")
    _write_notice_box(
        pdf,
        "Eligibility Requirement",
        "Bidders must satisfy the eligibility and document requirements in this section. The Buyer may reject incomplete, expired, unreadable, inconsistent, or non-compliant submissions in accordance with the tender rules and Buyer-Admin approval controls.",
    )
    _write_subsection(pdf, "5.1 Document Governance Rules")
    _write_bullets(pdf, award.get("vendor_document_rules", []))
    _write_subsection(pdf, "5.2 Documents Required for this Tender")
    _write_bullets(pdf, award.get("statutory_documents_required", []))
    _write_document_table(pdf, "5.3 Mandatory Documents", award.get("mandatory_documents", []))
    _write_document_table(pdf, "5.4 Mandatory-if-Applicable / Conditional Documents", award.get("conditional_documents", []))
    _write_document_table(pdf, "5.5 IT Sector-Specific Documents", award.get("sector_specific_documents", []))
    _write_document_table(pdf, "5.6 Optional Capability and Credibility Documents", award.get("optional_documents", []))

    pdf.add_page()

    _write_section(pdf, "6. Proposal Submission Requirements")
    _write_notice_box(
        pdf,
        "Submission Requirement",
        "Technical and commercial proposals must be prepared, separated, signed, stamped, and submitted according to this section. The Mushtarry platform record and timestamp constitute the official submission record unless the Buyer-Admin expressly approves another channel.",
    )
    _write_process_figure(
        pdf,
        "Proposal Submission Flow",
        ["Prepare Proposals", "Upload to Mushtarry", "Completeness Check", "Deadline Lock"],
    )
    _write_para(pdf, proposal_format.get("submission_method", ""))

    technical_proposal = proposal_format.get("technical_proposal", {})
    commercial_proposal = proposal_format.get("commercial_proposal", {})

    _write_subsection(pdf, "6.1 Technical Proposal")
    _write_key_value_table(
        pdf,
        [("File Naming Convention", technical_proposal.get("file_naming_convention", ""))],
    )
    _write_bullets(pdf, technical_proposal.get("required_sections", []))

    _write_subsection(pdf, "6.2 Commercial Proposal")
    _write_key_value_table(
        pdf,
        [
            ("File Naming Convention", commercial_proposal.get("file_naming_convention", "")),
            ("Accepted Currencies", ", ".join(commercial_proposal.get("accepted_currencies", ["SAR"]))),
        ],
    )
    _write_bullets(pdf, commercial_proposal.get("pricing_requirements", []))

    _write_section(pdf, "7. Project Overview")
    _write_subsection(pdf, "Project Introduction")
    _write_para(pdf, overview.get("project_introduction", ""))
    _write_subsection(pdf, "Background")
    _write_para(pdf, overview.get("background", ""))
    _write_subsection(pdf, "Context")
    _write_para(pdf, overview.get("context", ""))

    _write_section(pdf, "8. Objectives")
    _write_subsection(pdf, "Business Goals")
    _write_bullets(pdf, objectives.get("business_goals", []))
    _write_subsection(pdf, "Expected Outcomes")
    _write_bullets(pdf, objectives.get("expected_outcomes", []))
    _write_subsection(pdf, "Key Performance Indicators")
    _write_bullets(pdf, objectives.get("kpis", []))

    pdf.add_page()

    _write_section(pdf, "9. Scope of Work")
    for category in scope.get("categories", []):
        c = _as_dict(category)
        _write_subsection(pdf, c.get("name", "Work Category"))
        _write_para(pdf, c.get("description", ""))
        _write_bullets(pdf, c.get("requirements", []))

    _write_subsection(pdf, "Execution Phases")
    for phase in scope.get("phases", []):
        p = _as_dict(phase)
        _write_subsection(pdf, p.get("phase", "Phase"))
        _write_bullets(pdf, p.get("activities", []))

    _write_subsection(pdf, "General Requirements")
    _write_bullets(pdf, scope.get("general_requirements", []))

    pdf.add_page()

    _write_section(pdf, "10. Deliverables")
    _write_subsection(pdf, "10.1 Work Order Process")
    _write_bullets(pdf, deliverables.get("work_order_process", []))

    _write_subsection(pdf, "10.2 Required Deliverables")
    for item in deliverables.get("deliverables", []):
        it = _as_dict(item)

        _ensure_space(pdf, 14)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(PDF_FONT, "B", 10)
        pdf.multi_cell(0, 5.5, _safe_text(it.get("name", "")))

        pdf.set_x(pdf.l_margin)
        pdf.set_font(PDF_FONT, "", 9)

        if it.get("format"):
            _ensure_space(pdf, 8)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _safe_text(f"Format: {it.get('format')}"))

        if it.get("deadline_note"):
            _ensure_space(pdf, 8)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _safe_text(f"Deadline: {it.get('deadline_note')}"))

        _write_para(pdf, it.get("description", ""))

    _write_subsection(pdf, "10.3 Approval Process")
    _write_para(pdf, deliverables.get("approval_process", ""))

    _write_subsection(pdf, "10.4 Reporting Requirements")
    _write_bullets(pdf, deliverables.get("reporting_requirements", []))

    _write_subsection(pdf, "10.5 Escalation Matrix")
    for tier in deliverables.get("escalation_tiers", []):
        t = _as_dict(tier)
        _write_key_value_table(
            pdf,
            [
                ("Level", t.get("level", "")),
                ("Trigger Delay", t.get("trigger_delay", "")),
                ("Contact Role", t.get("contact_role", "")),
            ],
        )

    _write_section(pdf, "11. Timeline")
    _write_para(pdf, timeline.get("total_duration", ""))

    _write_subsection(pdf, "Project Phases")
    _write_bullets(pdf, timeline.get("project_phases", []))

    _write_subsection(pdf, "Key Milestones")
    for milestone in timeline.get("milestones", []):
        m = _as_dict(milestone)
        _write_key_value_table(
            pdf,
            [
                ("Phase", m.get("phase", "")),
                ("Milestone", m.get("milestone", "")),
                ("Target Date", m.get("target_date", "")),
            ],
        )

    pdf.add_page()

    _write_section(pdf, "12. Team Requirements")
    for role in team.get("roles", []):
        r = _as_dict(role)
        _write_subsection(pdf, r.get("position", "Role"))
        _write_para(pdf, f"Responsibilities: {r.get('responsibilities', '')}")
        _write_para(pdf, f"Minimum Experience: {r.get('minimum_experience', '')}")

    _write_subsection(pdf, "Saudization")
    _write_para(pdf, team.get("saudization_note", ""))

    _write_section(pdf, "13. General Terms and Conditions")
    _write_subsection(pdf, "13.1 Legal Terms")
    _write_bullets(pdf, terms.get("legal_terms", []))
    _write_subsection(pdf, "13.2 Compliance Requirements")
    _write_bullets(pdf, terms.get("compliance_requirements", []))
    _write_subsection(pdf, "13.3 Language Requirements")
    _write_para(pdf, terms.get("language_requirements", ""))
    _write_subsection(pdf, "13.4 Equipment and Logistics")
    _write_para(pdf, terms.get("equipment_and_logistics", ""))

    _write_section(pdf, "14. Confidentiality")
    _write_para(pdf, d.get("confidentiality", ""))

    pdf.add_page()

    _write_section(pdf, "15. Technical and Financial Evaluation Methodology")
    _write_notice_box(
        pdf,
        "Evaluation Governance",
        "Evaluation will be conducted against the Buyer-approved mandatory, technical, and financial requirements. Any Mushtarry AI recommendation is advisory only; the Buyer-Admin retains final decision authority for qualification, award, rejection, and publication.",
    )
    _write_process_figure(
        pdf,
        "Evaluation Workflow",
        ["Mandatory Compliance", "Technical Review", "Financial Review", "Buyer Approval"],
    )
    _write_key_value_table(
        pdf,
        [
            ("Evaluation Model", evaluation.get("evaluation_model", "")),
            ("Technical Evaluation", _format_percent(evaluation.get("technical_weight", ""))),
            ("Financial Evaluation", _format_percent(evaluation.get("financial_weight", ""))),
            ("Minimum Technical Score", _format_percent(evaluation.get("minimum_technical_score", ""))),
            ("Award Basis", evaluation.get("award_basis", "")),
        ],
    )

    _write_subsection(pdf, "15.1 Mandatory Pass/Fail Criteria")
    for criterion in evaluation.get("mandatory_criteria", []):
        c = _as_dict(criterion)
        _write_bullets(pdf, [c.get("criterion", criterion)])

    _write_subsection(pdf, "15.2 Technical Evaluation Parameters")
    _write_bullets(pdf, evaluation.get("technical_parameters", []))

    _write_subsection(pdf, "15.3 Financial Evaluation Parameters")
    _write_bullets(pdf, evaluation.get("financial_parameters", []))

    _write_subsection(pdf, "15.4 AI-Assisted Recommendation Note")
    _write_para(
        pdf,
        "Mushtarry may assist the buyer by summarizing proposals, checking mandatory compliance, "
        "comparing technical and commercial alignment, reviewing vendor document status, considering "
        "category-specific vendor reputation indicators, delivery reliability, rating history, completed "
        "contract history, compliance signals, and AI risk indicators, and preparing a ranked recommendation "
        "against buyer-approved criteria. AI output is advisory only and cannot publish, reject, award, "
        "or finalize any tender decision. Final award requires buyer approval.",
    )

    _write_section(pdf, "16. Payment Terms")
    _write_subsection(pdf, "16.1 Payment Basis")
    _write_para(pdf, payment.get("payment_basis", ""))
    _write_subsection(pdf, "16.2 Invoice Requirements")
    _write_bullets(pdf, payment.get("invoice_requirements", []))
    _write_subsection(pdf, "16.3 Payment Timeline")
    _write_para(pdf, payment.get("payment_timeline", ""))

    _write_section(pdf, "17. Annexures")
    _write_bullets(pdf, annexures)

    pdf.add_page()

    _write_section(pdf, "18. Buyer Approval")
    _write_para(pdf, "PENDING BUYER APPROVAL - This tender cannot be published until approved by the authorized Buyer-Admin.")
    _write_key_value_table(
        pdf,
        [
            ("Document Version", "Version 1.0 - AI Draft"),
            ("Document Status", "Draft / Pending Buyer Approval"),
            ("Generated Date", intelligence.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
            ("Trace ID", d.get("trace_id", "")),
            ("Publication Control", "Publication, award, rejection, and vendor notification remain blocked until Buyer-Admin approval."),
        ],
    )
    _write_matrix_table(
        pdf,
        "Approval Control Matrix",
        ["Control", "Status", "Owner"],
        [
            ["AI Generated Draft", "Complete", "Mushtarry AI"],
            ["Buyer Review", "Pending", "Buyer Admin"],
            ["Approval to Publish", "Pending", "Buyer Admin"],
            ["Official Publication", "Blocked", "Buyer Admin"],
        ],
    )
    pdf.ln(8)
    _write_key_value_table(
        pdf,
        [
            ("Reviewed & Approved By", ""),
            ("Role", "Buyer-Admin"),
            ("Date", ""),
        ],
    )

    _ensure_space(pdf, 42)
    pdf.set_x(pdf.l_margin)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_fill_color(255, 255, 255)
    box_w = (pdf.w - pdf.l_margin - pdf.r_margin - 10) / 2
    y = pdf.get_y()
    pdf.set_line_width(0.15)
    pdf.line(pdf.l_margin, y, pdf.l_margin + box_w, y)
    pdf.line(pdf.l_margin + box_w + 10, y, pdf.l_margin + box_w * 2 + 10, y)
    pdf.line(pdf.l_margin, y + 24, pdf.l_margin + box_w, y + 24)
    pdf.line(pdf.l_margin + box_w + 10, y + 24, pdf.l_margin + box_w * 2 + 10, y + 24)
    pdf.set_xy(pdf.l_margin, y + 9)
    pdf.set_font(PDF_FONT, "B", 9)
    pdf.set_text_color(45, 45, 45)
    pdf.cell(box_w, 6, _safe_text("Signature"), align="C")
    pdf.set_xy(pdf.l_margin + box_w + 10, y + 9)
    pdf.cell(box_w, 6, _safe_text("Official Stamp"), align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.output(str(output_path))
