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
PDF_TEMPLATES = {
    "premium_bw": "Premium B/W",
    "modern_bw": "Modern B/W",
}
DEFAULT_TEMPLATE = "premium_bw"
SAUDI_GREEN = (0, 108, 53)
SAUDI_GREEN_DARK = (0, 83, 85)
SAUDI_GREEN_MID = (42, 139, 86)
SAUDI_GREEN_LIGHT = (202, 229, 216)
SAUDI_GREEN_PALE = (246, 251, 248)
SAUDI_GREEN_SOFT = (232, 244, 238)


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


def normalize_template(template: str | None) -> str:
    return template if template in PDF_TEMPLATES else DEFAULT_TEMPLATE


def _font(pdf: FPDF) -> str:
    return "Times" if getattr(pdf, "template", DEFAULT_TEMPLATE) == "premium_bw" else PDF_FONT


def _is_modern(pdf: FPDF) -> bool:
    return getattr(pdf, "template", DEFAULT_TEMPLATE) == "modern_bw"


def _draw_ai_draft_watermark(pdf: FPDF):
    if not _is_modern(pdf):
        return

    x = pdf.l_margin
    y = 7
    w = 42
    h = 6.2
    pdf.set_fill_color(*SAUDI_GREEN_PALE)
    pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
    pdf.set_line_width(0.12)
    pdf.rect(x, y, w, h, style="DF")
    pdf.set_xy(x + 2, y + 1.4)
    pdf.set_text_color(*SAUDI_GREEN_DARK)
    pdf.set_font(_font(pdf), "B", 6.4)
    pdf.cell(w - 4, 3.2, _safe_text("AI GENERATED DRAFT"), align="L")


def _dedupe_key(text: Any) -> str:
    safe = " ".join(_safe_text(text).lower().split())
    return safe.strip(" .:;-")


def _content_seen(pdf: FPDF, text: Any) -> bool:
    key = _dedupe_key(text)
    if len(key) < 36:
        return False

    seen = getattr(pdf, "_seen_content", None)
    if seen is None:
        seen = set()
        setattr(pdf, "_seen_content", seen)

    if key in seen:
        return True

    seen.add(key)
    return False


def _is_placeholder_text(value: Any) -> bool:
    text = _dedupe_key(value)
    return text in {"", "-", "n/a", "none", "not required", "not specified"}


def _write_para_subsection(pdf: FPDF, title: str, text: Any):
    if _is_placeholder_text(text):
        return

    _write_subsection(pdf, title)
    _write_para(pdf, text)


def _formal_submission_method(value: Any) -> str:
    text = _safe_text(value).strip()
    if not text:
        return "All proposals must be submitted through the buyer-approved submission channel."

    normalized = text.lower()
    if "mushtarry" in normalized and ("only" in normalized or "platform" in normalized):
        return "All proposals must be submitted through the Mushtarry platform. Submissions outside the platform are not accepted unless expressly approved by the Buyer-Admin."

    return text


def _formal_file_naming(value: Any, proposal_type: str) -> str:
    text = _safe_text(value).strip()
    if not text:
        return f"Each {proposal_type.lower()} file must include the proposal type, bidder legal name, tender reference, and tender title."

    normalized = text.replace("_", " ")
    normalized = normalized.replace("[Bidder Name]", "<Bidder Legal Name>")
    normalized = normalized.replace("[Tender Reference]", "<Tender Reference>")
    normalized = normalized.replace(".pdf", " PDF")
    return (
        f"{proposal_type} naming format: {normalized}. Replace placeholders with the bidder legal name "
        f"and official tender reference before uploading the {proposal_type.lower()} file."
    )


def _tender_data_value(label: str, value: Any) -> str:
    text = _safe_text(value).strip()
    normalized = _dedupe_key(text)

    if label == "Submission Method":
        return _formal_submission_method(text)

    if normalized == "to be confirmed":
        return f"{label} will be confirmed by the Buyer-Admin."

    if normalized == "not required":
        return f"No {label.lower()} is required for this tender."

    if normalized in {"", "-", "n/a", "not specified"}:
        return f"{label} has not been specified."

    return text


def _cover_date(metadata: dict, tender_data_sheet: dict, intelligence: dict) -> str:
    candidates = [
        metadata.get("issue_date"),
        tender_data_sheet.get("issue_date"),
        intelligence.get("generated_at"),
    ]
    for candidate in candidates:
        text = _safe_text(candidate).strip()
        if not text or _dedupe_key(text) in {"to be confirmed", "not specified", "n/a"}:
            continue
        return text[:10].replace("-", " / ")
    return datetime.now(timezone.utc).strftime("%Y / %m / %d")


def _draw_architecture_background(pdf: FPDF):
    pdf.set_fill_color(0, 76, 65)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    pdf.set_fill_color(0, 58, 52)
    pdf.rect(0, 0, pdf.w * 0.42, pdf.h, style="F")
    pdf.rect(pdf.w * 0.70, 0, pdf.w * 0.30, pdf.h, style="F")

    pdf.set_draw_color(0, 118, 98)
    pdf.set_line_width(0.35)
    for offset in range(-110, 260, 13):
        pdf.line(offset, pdf.h, offset + 132, 0)

    pdf.set_draw_color(21, 143, 114)
    pdf.set_line_width(0.18)
    for x in [18, 31, 44, 57, 151, 164, 177, 190]:
        pdf.line(x, 0, x + 20, pdf.h)
    for y in range(25, 285, 17):
        pdf.line(0, y, pdf.w, y - 22)

    pdf.set_draw_color(0, 46, 42)
    pdf.set_line_width(1.1)
    pdf.line(18, 0, 134, pdf.h)
    pdf.line(86, 0, 196, pdf.h)
    pdf.line(128, 0, 62, pdf.h)


def _cover_info_row(pdf: FPDF, label: str, value: Any, x: float, y: float, w: float):
    pdf.set_xy(x, y)
    pdf.set_text_color(245, 255, 250)
    pdf.set_font(_font(pdf), "", 8.6)
    pdf.cell(w, 4.2, _safe_text(f"{label}: {value}"), align="R")
    pdf.set_draw_color(60, 190, 105)
    pdf.set_line_width(0.35)
    pdf.line(x, y + 6.2, x + w, y + 6.2)


def _draw_simple_icon(pdf: FPDF, x: float, y: float, kind: int, scale: float = 1.0):
    s = 6 * scale
    pdf.set_draw_color(86, 196, 83)
    pdf.set_line_width(0.35)
    if kind % 5 == 0:
        pdf.rect(x, y, s, s * 0.82)
        pdf.line(x, y + s * 0.25, x + s, y + s * 0.25)
        pdf.line(x + s * 0.25, y - 1, x + s * 0.25, y + 1.6)
        pdf.line(x + s * 0.75, y - 1, x + s * 0.75, y + 1.6)
    elif kind % 5 == 1:
        pdf.rect(x + 1, y, s * 0.72, s)
        pdf.line(x + 2.4, y + 2, x + s * 0.6, y + 2)
        pdf.line(x + 2.4, y + 4, x + s * 0.6, y + 4)
    elif kind % 5 == 2:
        pdf.line(x, y + s, x + s, y)
        pdf.line(x + 1.5, y, x + s, y + s - 1.5)
        pdf.line(x + 1, y + s - 1, x + s - 1, y + 1)
    elif kind % 5 == 3:
        pdf.rect(x + 1, y + 2, s * 0.75, s * 0.65)
        pdf.line(x, y + 2, x + s * 0.5, y)
        pdf.line(x + s, y + 2, x + s * 0.5, y)
    else:
        pdf.ellipse(x + 1, y, s * 0.65, s * 0.65)
        pdf.line(x + s * 0.5, y + s * 0.65, x + s * 0.5, y + s)
        pdf.line(x + 1, y + s, x + s - 1, y + s)


def _write_thank_you_page(pdf: FPDF):
    if not _is_modern(pdf):
        return

    pdf.add_page()
    pdf.full_bleed_pages.add(pdf.page_no())
    _draw_architecture_background(pdf)

    for row in range(8):
        for col in range(3):
            _draw_simple_icon(pdf, 126 + col * 20, 18 + row * 20, row + col, 1.15)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font(_font(pdf), "B", 33)
    pdf.set_xy(22, 92)
    pdf.cell(82, 14, _safe_text("Thank You"))
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.6)
    pdf.line(22, 111, 82, 111)

    pdf.set_font(_font(pdf), "", 10.5)
    pdf.set_xy(22, 178)
    contact = [
        "Building 5328, 2nd floor",
        "Anas Ibn Malik Rd, Al Malqa",
        "Riyadh 13525 - 7516",
        "Kingdom of Saudi Arabia",
        "Phone: +966 11 200 6306",
        "Email: info@sca.sa",
    ]
    for line in contact:
        pdf.cell(0, 5, _safe_text(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_x(22)

    pdf.set_xy(22, 223)
    pdf.set_font(_font(pdf), "B", 18)
    pdf.cell(0, 8, _safe_text("sca.sa"))

    pdf.set_xy(22, 258)
    pdf.set_font(_font(pdf), "B", 23)
    pdf.cell(0, 10, _safe_text("SCA"))
    pdf.set_font(_font(pdf), "", 10)
    pdf.set_xy(22, 270)
    pdf.multi_cell(92, 5, _safe_text("Saudi Contractors Authority"))
    pdf.set_text_color(0, 0, 0)


def _split_numbered_title(title: str) -> tuple[str, str]:
    safe = _safe_text(title).strip()
    number, sep, rest = safe.partition(". ")

    if sep and number.replace(".", "").isdigit():
        return number, rest

    return "", safe


def _estimate_lines(text: str, chars_per_line: int) -> int:
    if not text:
        return 1

    lines = 0
    for paragraph in _safe_text(text).splitlines() or [""]:
        lines += max(1, len(paragraph) // max(1, chars_per_line) + 1)

    return lines


class TenderPDF(FPDF):
    def __init__(
        self,
        doc_title: str = "",
        tender_ref: str = "",
        status: str = "DRAFT - Pending Buyer Approval",
        template: str | None = None,
    ):
        super().__init__()
        self.doc_title = doc_title
        self.tender_ref = tender_ref
        self.status = status
        self.template = normalize_template(template)
        self._seen_content = set()
        self.full_bleed_pages = set()

    def header(self):
        if self.page_no() == 1:
            return
        if self.page_no() in self.full_bleed_pages:
            return

        _draw_ai_draft_watermark(self)

        right = self.w - self.r_margin
        logo_y = 10
        mark_size = 12
        mark_x = right - 40

        self.set_y(logo_y)
        self.set_draw_color(*(SAUDI_GREEN_LIGHT if _is_modern(self) else (150, 150, 150)))
        self.set_fill_color(255, 255, 255)
        self.set_line_width(0.18)
        self.ellipse(mark_x, logo_y, mark_size, mark_size)
        self.set_draw_color(*SAUDI_GREEN)
        self.line(mark_x + 3.2, logo_y + 6.2, mark_x + mark_size - 3.2, logo_y + 6.2)
        self.line(mark_x + 6.2, logo_y + 3.2, mark_x + 6.2, logo_y + mark_size - 3.2)
        self.set_xy(mark_x + 2.6, logo_y + 4.3)
        self.set_text_color(*(SAUDI_GREEN_DARK if _is_modern(self) else (35, 35, 35)))
        self.set_font(PDF_FONT, "B", 4.8)
        self.cell(mark_size - 5.2, 3.2, _safe_text("EP"), align="C")

        self.set_xy(mark_x + mark_size + 3, logo_y + 1.2)
        self.set_font(PDF_FONT, "B", 7.2)
        self.set_text_color(*(SAUDI_GREEN_DARK if _is_modern(self) else (38, 38, 38)))
        self.cell(25, 4, _safe_text("EVOLVED"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(mark_x + mark_size + 3)
        self.set_font(PDF_FONT, "", 4.8)
        self.set_text_color(*(SAUDI_GREEN_MID if _is_modern(self) else (105, 105, 105)))
        self.cell(25, 3.2, _safe_text("PROCUREMENT"), align="L")

        self.set_draw_color(*(SAUDI_GREEN_LIGHT if _is_modern(self) else (35, 35, 35)))
        self.set_line_width(0.55)
        self.line(self.l_margin, 27, right, 27)
        self.set_draw_color(*SAUDI_GREEN)
        self.set_line_width(0.55)
        self.line(self.l_margin, 27, self.l_margin + 32, 27)
        self.set_y(31)
        self.set_x(self.l_margin)

    def footer(self):
        if self.page_no() == 1:
            return
        if self.page_no() in self.full_bleed_pages:
            return

        line_y = self.h - 20
        footer_y = self.h - 14.6
        right = self.w - self.r_margin

        self.set_y(line_y)
        self.set_x(self.l_margin)
        self.set_draw_color(*(SAUDI_GREEN_LIGHT if _is_modern(self) else (205, 205, 205)))
        self.set_line_width(0.15)
        self.line(self.l_margin, line_y, right, line_y)

        self.set_xy(self.l_margin, footer_y + 1.4)
        self.set_text_color(*SAUDI_GREEN_DARK)
        self.set_font(PDF_FONT, "", 7.3)
        self.cell(0, 4, _safe_text("(c) 2024 Saudi Contractors Authority. All Rights Reserved."), align="L")

        page_text = str(self.page_no())
        suffix = " | P a g e"
        self.set_font(PDF_FONT, "B", 12)
        page_w = self.get_string_width(page_text)
        self.set_font(PDF_FONT, "", 10)
        suffix_w = self.get_string_width(suffix)
        x = right - page_w - suffix_w
        self.set_xy(x, footer_y)
        self.set_text_color(*(SAUDI_GREEN_DARK if _is_modern(self) else (15, 15, 15)))
        self.set_font(PDF_FONT, "B", 12)
        self.cell(page_w, 6, page_text)
        self.set_font(PDF_FONT, "", 10)
        self.set_text_color(*(SAUDI_GREEN_MID if _is_modern(self) else (135, 135, 135)))
        self.cell(suffix_w, 6, suffix)
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
    if not _is_modern(pdf):
        pdf.set_draw_color(35, 35, 35)
        pdf.set_line_width(0.35)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2.2)
        pdf.set_text_color(15, 15, 15)
        pdf.set_font(_font(pdf), "B", 14.5)
        pdf.multi_cell(0, 7, _safe_text(title.upper()))
        pdf.set_draw_color(*SAUDI_GREEN)
        pdf.set_line_width(0.6)
        pdf.line(pdf.l_margin, pdf.get_y() + 0.4, pdf.l_margin + 22, pdf.get_y() + 0.4)
        pdf.set_draw_color(45, 45, 45)
        pdf.set_line_width(0.22)
        pdf.line(pdf.l_margin, pdf.get_y() + 1.2, pdf.w - pdf.r_margin, pdf.get_y() + 1.2)
        pdf.ln(5)
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
        return

    number, label = _split_numbered_title(title)
    x = pdf.l_margin
    y = pdf.get_y()
    w = pdf.w - pdf.l_margin - pdf.r_margin
    block_w = 17 if number else 5
    title_x = x + block_w + 4
    title_w = w - block_w - 4
    label_lines = _estimate_lines(label, 54)
    band_h = max(14, min(25, label_lines * 5.8 + 6))

    _ensure_space(pdf, band_h + 5)
    y = pdf.get_y()
    pdf.set_fill_color(*SAUDI_GREEN_PALE)
    pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
    pdf.set_line_width(0.12)
    pdf.rect(x, y, w, band_h, style="DF")
    pdf.set_fill_color(*SAUDI_GREEN)
    pdf.rect(x, y, 3, band_h, style="F")

    if number:
        pdf.set_xy(x + 4.5, y + 3.8)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.set_font(_font(pdf), "B", 14)
        pdf.cell(block_w - 5, 5.6, _safe_text(number), align="L")

    pdf.set_xy(title_x, y + 3.2)
    pdf.set_text_color(*SAUDI_GREEN_DARK)
    pdf.set_font(_font(pdf), "B", 12.2)
    pdf.multi_cell(title_w, 5.8, _safe_text(label.upper()))
    pdf.set_y(y + band_h + 3)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)


def _write_subsection(pdf: TenderPDF, title: str):
    _ensure_space(pdf, 12)
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(35, 35, 35)
    if not _is_modern(pdf):
        pdf.set_font(_font(pdf), "B", 11)
        y = pdf.get_y() + 1.4
        pdf.set_draw_color(*SAUDI_GREEN)
        pdf.set_line_width(0.45)
        pdf.line(pdf.l_margin, y, pdf.l_margin + 4, y)
        pdf.set_x(pdf.l_margin + 7)
        pdf.multi_cell(0, 5.8, _safe_text(title))
        pdf.set_draw_color(170, 170, 170)
        pdf.set_line_width(0.12)
        pdf.line(pdf.l_margin, pdf.get_y() + 0.2, pdf.l_margin + 52, pdf.get_y() + 0.2)
        pdf.ln(2.2)
    else:
        x = pdf.l_margin
        y = pdf.get_y()
        w = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.set_fill_color(*SAUDI_GREEN_PALE)
        pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
        pdf.set_line_width(0.12)
        pdf.rect(x, y, w, 8.8, style="DF")
        pdf.set_fill_color(*SAUDI_GREEN)
        pdf.rect(x, y, 1.6, 8.8, style="F")
        pdf.set_xy(x + 5, y + 2)
        pdf.set_font(_font(pdf), "B", 9.4)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.multi_cell(w - 10, 4.5, _safe_text(title))
        pdf.set_y(max(pdf.get_y(), y + 10.5))
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)


def _write_para(pdf: TenderPDF, text: Any):
    if not text:
        return
    if _content_seen(pdf, text):
        return

    _ensure_space(pdf, 10)
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(_font(pdf), "", 10.2 if pdf.template == "premium_bw" else 9.5)
    pdf.multi_cell(0, 5.6 if pdf.template == "premium_bw" else 5.2, _safe_text(text))
    pdf.set_x(pdf.l_margin)
    pdf.ln(1.5)
    pdf.set_text_color(0, 0, 0)


def _write_bullets(pdf: TenderPDF, items: list[Any]):
    pdf.set_font(_font(pdf), "", 10 if pdf.template == "premium_bw" else 9.4)

    for item in _as_list(items):
        if not item:
            continue
        if _content_seen(pdf, item):
            continue

        _ensure_space(pdf, 8)
        pdf.set_x(pdf.l_margin)
        if _is_modern(pdf):
            y = pdf.get_y() + 1.9
            pdf.set_fill_color(*SAUDI_GREEN)
            pdf.rect(pdf.l_margin + 1, y, 1.8, 1.8, style="F")
            pdf.set_x(pdf.l_margin + 7)
            pdf.set_text_color(24, 52, 38)
            pdf.multi_cell(0, 5, _safe_text(item))
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.cell(4, 5.2, "o", align="L")
            pdf.set_x(pdf.l_margin + 6)
            pdf.multi_cell(0, 5.2, _safe_text(item))

    pdf.set_x(pdf.l_margin)
    pdf.ln(1)


def _has_renderable_items(pdf: TenderPDF, items: list[Any]) -> bool:
    seen = getattr(pdf, "_seen_content", set())
    for item in _as_list(items):
        if not item:
            continue
        key = _dedupe_key(item)
        if len(key) < 36 or key not in seen:
            return True
    return False


def _write_bullet_subsection(pdf: TenderPDF, title: str, items: list[Any]):
    if not _has_renderable_items(pdf, items):
        return

    _write_subsection(pdf, title)
    _write_bullets(pdf, items)


def _write_key_value_table(pdf: TenderPDF, rows: list[tuple[str, Any]]):
    classic = not _is_modern(pdf)
    left_w = 62 if classic else 56
    right_w = pdf.w - pdf.l_margin - pdf.r_margin - left_w

    for key, value in rows:
        if value is None:
            value = ""

        key_text = _safe_text(key)
        value_text = _safe_text(value)

        if not classic:
            w = pdf.w - pdf.l_margin - pdf.r_margin
            left_w = 54
            right_w = w - left_w
            key_lines = _estimate_lines(key_text, 28)
            value_lines = _estimate_lines(value_text, 74)
            row_h = max(10.8, min(38, max(key_lines, value_lines) * 4.2 + 4.8))

            _ensure_space(pdf, row_h + 2)
            x = pdf.l_margin
            y = pdf.get_y()

            pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
            pdf.set_line_width(0.14)
            pdf.set_fill_color(*SAUDI_GREEN_SOFT)
            pdf.rect(x, y, left_w, row_h, style="DF")
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x + left_w, y, right_w, row_h, style="DF")
            pdf.set_fill_color(*SAUDI_GREEN)
            pdf.rect(x, y, 1.7, row_h, style="F")

            pdf.set_xy(x + 4.5, y + 2.4)
            pdf.set_text_color(*SAUDI_GREEN_DARK)
            pdf.set_font(_font(pdf), "B", 8)
            pdf.multi_cell(left_w - 7, 3.8, key_text.upper())

            pdf.set_xy(x + left_w + 3.5, y + 2.4)
            pdf.set_text_color(24, 52, 38)
            pdf.set_font(_font(pdf), "", 9.1)
            pdf.multi_cell(right_w - 7, 4.2, value_text or "-")

            pdf.set_y(y + row_h)
            pdf.set_x(pdf.l_margin)
            continue

        key_lines = max(1, len(key_text) // 30 + 1)
        value_lines = max(1, len(value_text) // 76 + 1)
        line_h = 4.5
        row_h = max(8.5, min(32, max(key_lines, value_lines) * line_h + 4))

        _ensure_space(pdf, row_h + 2)
        pdf.set_x(pdf.l_margin)

        x = pdf.get_x()
        y = pdf.get_y()

        pdf.set_fill_color(242, 242, 242)
        pdf.set_draw_color(80, 80, 80)
        pdf.set_line_width(0.18)
        pdf.rect(x, y, left_w, row_h, style="DF")
        pdf.rect(x + left_w, y, right_w, row_h)
        pdf.set_draw_color(*SAUDI_GREEN)
        pdf.set_line_width(0.42)
        pdf.line(x, y, x, y + row_h)

        pdf.set_xy(x + 2, y + 2)
        pdf.set_text_color(35, 35, 35)
        pdf.set_font(_font(pdf), "B", 9.5)
        pdf.multi_cell(left_w - 4, line_h, key_text)

        pdf.set_xy(x + left_w + 2, y + 2)
        pdf.set_text_color(25, 25, 25)
        pdf.set_font(_font(pdf), "", 9.5)
        pdf.multi_cell(right_w - 4, line_h, value_text)

        pdf.set_y(y + row_h)
        pdf.set_x(pdf.l_margin)

    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)


def _write_compact_key_value_table(pdf: TenderPDF, rows: list[tuple[str, Any]]):
    if not rows:
        return

    if not _is_modern(pdf):
        _write_key_value_table(pdf, rows)
        return

    w = pdf.w - pdf.l_margin - pdf.r_margin
    left_w = 51
    right_w = w - left_w

    for key, value in rows:
        key_text = _safe_text(key)
        value_text = _safe_text(value)
        key_lines = _estimate_lines(key_text, 28)
        value_lines = _estimate_lines(value_text, 70)
        row_h = max(7.6, min(17.5, max(key_lines, value_lines) * 3.25 + 3.1))

        _ensure_space(pdf, row_h + 1)
        x = pdf.l_margin
        y = pdf.get_y()

        pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
        pdf.set_line_width(0.1)
        pdf.set_fill_color(*SAUDI_GREEN_SOFT)
        pdf.rect(x, y, left_w, row_h, style="DF")
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x + left_w, y, right_w, row_h, style="DF")
        pdf.set_fill_color(*SAUDI_GREEN)
        pdf.rect(x, y, 1.5, row_h, style="F")

        pdf.set_xy(x + 4, y + 1.7)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.set_font(_font(pdf), "B", 6.8)
        pdf.multi_cell(left_w - 6, 3.1, key_text.upper())

        pdf.set_xy(x + left_w + 3.2, y + 1.7)
        pdf.set_text_color(24, 52, 38)
        pdf.set_font(_font(pdf), "", 7.4)
        pdf.multi_cell(right_w - 6.2, 3.35, value_text or "-")

        pdf.set_y(y + row_h)
        pdf.set_x(pdf.l_margin)

    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.ln(1.5)


def _write_payment_schedule_tables(pdf: TenderPDF, rows: list[dict]):
    if not rows:
        return

    _write_subsection(pdf, "4.4.2 Payment Schedule")
    for index, row in enumerate(rows, start=1):
        milestone = row.get("milestone", f"Payment Milestone {index}")
        _write_subsection(pdf, f"4.4.2.{index} {milestone}")
        _write_key_value_table(
            pdf,
            [
                ("Payment Trigger", row.get("payment_trigger", "")),
                ("Supporting Evidence", row.get("supporting_evidence", "")),
                ("Invoice Timing", row.get("invoice_timing", "")),
                ("Amount / Basis", row.get("payment_percentage_or_amount", "")),
            ],
        )


def _write_notice_box(pdf: TenderPDF, title: str, text: str, *, fill=(255, 255, 255), border=(0, 0, 0)):
    if not text:
        return

    if _is_modern(pdf):
        w = pdf.w - pdf.l_margin - pdf.r_margin
        text_lines = _estimate_lines(text, 92)
        title_h = 8.8
        body_h = max(8, min(30, text_lines * 4.3 + 2))
        _ensure_space(pdf, title_h + body_h + 5)
        x = pdf.l_margin
        y = pdf.get_y()

        pdf.set_fill_color(*SAUDI_GREEN_PALE)
        pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
        pdf.set_line_width(0.12)
        pdf.rect(x, y, w, title_h, style="DF")
        pdf.set_fill_color(*SAUDI_GREEN)
        pdf.rect(x, y, 1.8, title_h, style="F")
        pdf.set_xy(x + 5, y + 2)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.set_font(_font(pdf), "B", 9.0)
        pdf.multi_cell(w - 10, 4.5, _safe_text(title))
        pdf.set_xy(x, y + title_h + 2)
        pdf.set_text_color(35, 75, 54)
        pdf.set_font(_font(pdf), "", 8.6)
        pdf.multi_cell(w, 4.3, _safe_text(text))
        pdf.set_y(y + title_h + body_h + 4)
        pdf.set_text_color(0, 0, 0)
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
    pdf.set_draw_color(*SAUDI_GREEN)
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

    if _is_modern(pdf):
        _ensure_space(pdf, 58)
        _write_subsection(pdf, title)
        x = pdf.l_margin
        y = pdf.get_y() + 2
        w = pdf.w - pdf.l_margin - pdf.r_margin
        step_h = 13

        for i, step in enumerate(steps):
            _ensure_space(pdf, step_h + 3)
            y = pdf.get_y()
            pdf.set_fill_color(*SAUDI_GREEN_PALE)
            pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
            pdf.set_line_width(0.12)
            pdf.rect(x + 10, y, w - 10, step_h, style="DF")
            pdf.set_fill_color(*SAUDI_GREEN)
            pdf.ellipse(x, y + 2, 7, 7, style="F")
            pdf.set_xy(x, y + 3)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font(_font(pdf), "B", 7)
            pdf.cell(7, 3.5, str(i + 1), align="C")
            pdf.set_xy(x + 14, y + 3)
            pdf.set_text_color(35, 75, 54)
            pdf.set_font(_font(pdf), "", 8.3)
            pdf.multi_cell(w - 18, 4, _safe_text(step))
            pdf.set_y(y + step_h + 2)

        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
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
        pdf.set_draw_color(*SAUDI_GREEN)
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
    classic = not _is_modern(pdf)
    row_h = 9.2 if classic else 8.5

    _ensure_space(pdf, row_h * (len(rows) + 2))
    pdf.set_draw_color(70, 70, 70) if classic else pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
    pdf.set_line_width(0.18 if classic else 0.14)
    pdf.set_font(_font(pdf), "B", 8.6 if classic else 8.2)
    y = pdf.get_y()
    x = pdf.l_margin

    pdf.set_fill_color(236, 236, 236) if classic else pdf.set_fill_color(*SAUDI_GREEN)
    pdf.rect(x, y, total_w, row_h, style="DF" if classic else "F")
    if not classic:
        pdf.set_fill_color(*SAUDI_GREEN)
        pdf.rect(x, y, 2, row_h, style="F")
    for idx, header in enumerate(headers):
        if classic:
            pdf.line(x + idx * col_w, y, x + idx * col_w, y + row_h)
        pdf.set_xy(x + idx * col_w + 1.5, y + 2)
        pdf.set_text_color(25, 25, 25) if classic else pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(col_w - 3, 3.8 if classic else 3.5, _safe_text(header), align="C")
    if classic:
        pdf.line(x + total_w, y, x + total_w, y + row_h)
    else:
        pdf.line(x, y, x + total_w, y)
        pdf.line(x, y + row_h, x + total_w, y + row_h)

    y += row_h
    pdf.set_font(_font(pdf), "", 8.4 if classic else 8)
    pdf.set_text_color(30, 30, 30)
    for row_i, row in enumerate(rows):
        _ensure_space(pdf, row_h + 2)
        x = pdf.l_margin
        if classic:
            pdf.rect(x, y, total_w, row_h)
        else:
            if row_i % 2 == 0:
                pdf.set_fill_color(*SAUDI_GREEN_PALE)
                pdf.rect(x, y, total_w, row_h, style="F")
            pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
            pdf.line(x, y + row_h, x + total_w, y + row_h)
        for idx in range(col_count):
            value = row[idx] if idx < len(row) else ""
            if classic:
                pdf.line(x + idx * col_w, y, x + idx * col_w, y + row_h)
            pdf.set_xy(x + idx * col_w + 1.5, y + 2)
            pdf.multi_cell(col_w - 3, 3.8 if classic else 3.5, _safe_text(value), align="C")
        if classic:
            pdf.line(x + total_w, y, x + total_w, y + row_h)
        y += row_h
        pdf.set_y(y)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _write_document_control_page(pdf: TenderPDF, d: dict, metadata: dict, tender_data_sheet: dict, intelligence: dict):
    pdf.add_page()
    _write_section(pdf, "1.2 Document Control")
    _write_subsection(pdf, "1.2.1 Approval and Publication Control")
    _write_notice_box(
        pdf,
        "Buyer-Admin Approval Required",
        "This tender package was generated by Mushtarry AI for buyer review. It is not approved, issued, or published until the authorized Buyer-Admin completes the approval block and changes the document status to Approved / Published.",
    )
    _write_subsection(pdf, "1.2.2 Confidentiality and Use")
    _write_para(
        pdf,
        "This document is confidential and intended only for authorized buyer review and controlled tender publication. Vendors may rely on this document only after the Buyer-Admin approval and official publication through the approved channel.",
    )


def _write_tender_data_sheet_page(pdf: TenderPDF, tender_data_sheet: dict):
    pdf.add_page()
    _write_section(pdf, "Section 1: Document Governance")
    _write_subsection(pdf, "1.1 Tender Data Sheet")
    _write_compact_key_value_table(
        pdf,
        [
            ("Tender Title", _tender_data_value("Tender Title", tender_data_sheet.get("tender_title", ""))),
            ("Tender Reference", _tender_data_value("Tender Reference", tender_data_sheet.get("tender_reference", ""))),
            ("Buyer Entity", _tender_data_value("Buyer Entity", tender_data_sheet.get("buyer_entity", ""))),
            ("Procurement Category", _tender_data_value("Procurement Category", tender_data_sheet.get("procurement_category", ""))),
            ("Tender Type", _tender_data_value("Tender Type", tender_data_sheet.get("tender_type", ""))),
            ("Procurement Method", _tender_data_value("Procurement Method", tender_data_sheet.get("procurement_method", ""))),
            ("Submission Method", _tender_data_value("Submission Method", tender_data_sheet.get("submission_method", ""))),
            ("Issue Date", _tender_data_value("Issue Date", tender_data_sheet.get("issue_date", ""))),
            ("Site Visit", _tender_data_value("Site Visit", tender_data_sheet.get("site_visit", ""))),
            ("Clarification Deadline", _tender_data_value("Clarification Deadline", tender_data_sheet.get("clarification_deadline", ""))),
            ("Submission Deadline", _tender_data_value("Submission Deadline", tender_data_sheet.get("submission_deadline", ""))),
            ("Opening Date", _tender_data_value("Opening Date", tender_data_sheet.get("opening_date", ""))),
            ("Proposal Validity", _tender_data_value("Proposal Validity", tender_data_sheet.get("proposal_validity", ""))),
            ("Bid Security", _tender_data_value("Bid Security", tender_data_sheet.get("bid_security", ""))),
            ("Performance Bond", _tender_data_value("Performance Bond", tender_data_sheet.get("performance_bond", ""))),
            ("Contract Duration", _tender_data_value("Contract Duration", tender_data_sheet.get("contract_duration", ""))),
            ("Warranty Duration", _tender_data_value("Warranty Duration", tender_data_sheet.get("warranty_duration", ""))),
            ("Language", _tender_data_value("Language", tender_data_sheet.get("language", ""))),
            ("Evaluation Model", _tender_data_value("Evaluation Model", tender_data_sheet.get("evaluation_model", ""))),
            ("Minimum Technical Score", _tender_data_value("Minimum Technical Score", tender_data_sheet.get("minimum_technical_score", ""))),
        ],
    )


def _write_document_table(pdf: TenderPDF, title: str, docs: list[Any]):
    if not docs:
        return

    _write_subsection(pdf, title)

    if _is_modern(pdf):
        w = pdf.w - pdf.l_margin - pdf.r_margin

        for i, doc in enumerate(docs, start=1):
            d = _as_dict(doc)
            detail_parts = []

            if d.get("category"):
                detail_parts.append(f"Category: {d.get('category')}")

            if d.get("applicability"):
                detail_parts.append(f"Applicability: {d.get('applicability')}")

            if d.get("issuing_authority"):
                detail_parts.append(f"Issuing Authority: {d.get('issuing_authority')}")

            if d.get("notes"):
                detail_parts.append(f"Notes: {d.get('notes')}")

            details = " | ".join(detail_parts)
            name = _safe_text(d.get("name", ""))
            title_h = max(8.8, min(18, _estimate_lines(name, 74) * 4.2 + 4.5))
            details_h = max(0, min(22, _estimate_lines(details, 92) * 4 + 1)) if details else 0
            row_h = title_h + details_h + (2 if details else 0)
            _ensure_space(pdf, row_h + 3)
            x = pdf.l_margin
            y = pdf.get_y()

            pdf.set_fill_color(*SAUDI_GREEN_PALE)
            pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
            pdf.set_line_width(0.12)
            pdf.rect(x, y, w, title_h, style="DF")
            pdf.set_fill_color(*SAUDI_GREEN)
            pdf.rect(x, y, 1.8, title_h, style="F")
            pdf.set_xy(x + 5, y + 2.2)
            pdf.set_text_color(*SAUDI_GREEN_MID)
            pdf.set_font(_font(pdf), "B", 7.6)
            pdf.cell(8, 3.8, f"{i:02d}", align="L")

            pdf.set_xy(x + 14, y + 2.2)
            pdf.set_text_color(*SAUDI_GREEN_DARK)
            pdf.set_font(_font(pdf), "B", 9.2)
            pdf.multi_cell(w - 18, 4.3, name)

            if details:
                pdf.set_xy(x, y + title_h + 2)
                pdf.set_text_color(35, 75, 54)
                pdf.set_font(_font(pdf), "", 8.2)
                pdf.multi_cell(w, 4, _safe_text(details))

            pdf.set_y(y + row_h + 2.5)

        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
        pdf.ln(1)
        return

    for doc in docs:
        d = _as_dict(doc)

        _ensure_space(pdf, 14)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(_font(pdf), "B", 10.5 if pdf.template == "premium_bw" else 10)
        prefix = "Document: " if pdf.template == "premium_bw" else "- "
        pdf.multi_cell(0, 5.7 if pdf.template == "premium_bw" else 5.5, _safe_text(f"{prefix}{d.get('name', '')}"))

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
            pdf.set_font(_font(pdf), "", 9.4 if pdf.template == "premium_bw" else 9)
            pdf.multi_cell(0, 5.2 if pdf.template == "premium_bw" else 5, _safe_text("  " + " | ".join(detail_parts)))

    pdf.set_x(pdf.l_margin)
    pdf.ln(1)


def _write_deliverable_item(pdf: TenderPDF, item: dict, index: int):
    name = item.get("name", "")
    fmt = item.get("format", "")
    deadline = item.get("deadline_note", "")
    description = item.get("description", "")

    if _is_modern(pdf):
        w = pdf.w - pdf.l_margin - pdf.r_margin
        meta = " | ".join(part for part in [f"Format: {fmt}" if fmt else "", f"Deadline: {deadline}" if deadline else ""] if part)
        title_h = max(8.8, min(18, _estimate_lines(name, 72) * 4.3 + 4.5))
        meta_h = max(0, min(10, _estimate_lines(meta, 90) * 3.8 + 1)) if meta else 0
        desc_h = max(0, min(28, _estimate_lines(description, 92) * 4 + 1)) if description else 0
        row_h = title_h + meta_h + desc_h + (4 if meta or description else 0)
        _ensure_space(pdf, row_h + 4)
        x = pdf.l_margin
        y = pdf.get_y()

        pdf.set_fill_color(*SAUDI_GREEN_PALE)
        pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
        pdf.set_line_width(0.12)
        pdf.rect(x, y, w, title_h, style="DF")
        pdf.set_fill_color(*SAUDI_GREEN)
        pdf.rect(x, y, 1.8, title_h, style="F")
        pdf.set_xy(x + 5, y + 2.3)
        pdf.set_text_color(*SAUDI_GREEN_MID)
        pdf.set_font(_font(pdf), "B", 7.8)
        pdf.cell(10, 3.8, f"{index:02d}", align="L")

        pdf.set_xy(x + 16, y + 2.2)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.set_font(_font(pdf), "B", 9.2)
        pdf.multi_cell(w - 20, 4.3, _safe_text(name))

        body_y = y + title_h + 2
        if meta:
            pdf.set_xy(x, body_y)
            pdf.set_text_color(*SAUDI_GREEN_DARK)
            pdf.set_font(_font(pdf), "B", 8)
            pdf.multi_cell(w, 3.8, _safe_text(meta))
            body_y = pdf.get_y() + 0.5

        if description:
            pdf.set_xy(x, body_y)
            pdf.set_text_color(35, 75, 54)
            pdf.set_font(_font(pdf), "", 8.5)
            pdf.multi_cell(w, 4, _safe_text(description))

        pdf.set_y(y + row_h + 3)
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
        return

    _ensure_space(pdf, 14)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(PDF_FONT, "B", 10)
    pdf.multi_cell(0, 5.5, _safe_text(name))

    pdf.set_x(pdf.l_margin)
    pdf.set_font(PDF_FONT, "", 9)

    if fmt:
        _ensure_space(pdf, 8)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, _safe_text(f"Format: {fmt}"))

    if deadline:
        _ensure_space(pdf, 8)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, _safe_text(f"Deadline: {deadline}"))

    _write_para(pdf, description)


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

    if pdf.template == "modern_bw":
        _draw_architecture_background(pdf)
        _draw_ai_draft_watermark(pdf)

        ref = metadata.get("tender_id") or tender_data_sheet.get("tender_reference", "")
        issue_date = _cover_date(metadata, tender_data_sheet, intelligence)

        pdf.set_xy(18, 25)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(_font(pdf), "B", 18)
        pdf.multi_cell(174, 8.5, _safe_text(f"Project Name: {tender_title}"), align="R")

        info_x = 78
        info_w = 111
        info_y = 174
        _cover_info_row(pdf, "Request Number", ref or "Tender reference pending", info_x, info_y, info_w)
        _cover_info_row(pdf, "Version Number", "1.0", info_x, info_y + 15, info_w)
        _cover_info_row(pdf, "Issue Date", issue_date, info_x, info_y + 30, info_w)
        _cover_info_row(pdf, "Publisher", "Procurement Department", info_x, info_y + 45, info_w)
        _cover_info_row(pdf, "Copyright", "Saudi Contractors Authority", info_x, info_y + 60, info_w)

        pdf.set_xy(18, 262)
        pdf.set_font(_font(pdf), "", 8.2)
        pdf.set_text_color(221, 244, 234)
        pdf.multi_cell(
            82,
            4.5,
            _safe_text("AI-generated draft for Buyer-Admin review. Not valid for market issue until approved."),
        )
        pdf.set_text_color(0, 0, 0)
        return

    pdf.set_font(_font(pdf), "", 10)
    pdf.set_draw_color(25, 25, 25)
    pdf.set_line_width(0.35)
    pdf.line(left, 20, right, 20)
    pdf.set_draw_color(*SAUDI_GREEN)
    pdf.set_line_width(0.15)
    pdf.line(left, 23, right, 23)
    pdf.set_fill_color(*SAUDI_GREEN)
    pdf.rect(left, 23.8, 22, 1.3, style="F")

    pdf.set_xy(left, 30)
    if logo_path:
        pdf.image(str(logo_path), x=left, y=27, w=28)
    else:
        pdf.set_draw_color(40, 40, 40)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(left, 30, 22, 22)
        pdf.set_xy(left, 36.5)
        pdf.set_font(_font(pdf), "B", 12)
        pdf.set_text_color(25, 25, 25)
        pdf.cell(22, 7, _safe_text(_initials(buyer_name)), align="C")

    pdf.set_xy(left + 34, 30)
    pdf.set_text_color(25, 25, 25)
    pdf.set_font(_font(pdf), "B", 13.5)
    pdf.multi_cell(width - 77, 6, _safe_text(buyer_name))
    pdf.set_x(left + 34)
    pdf.set_font(_font(pdf), "", 9.2)
    pdf.set_text_color(85, 85, 85)
    pdf.multi_cell(width - 77, 4.6, _safe_text("Formal tender document prepared for Buyer-Admin review."))

    pdf.set_xy(right - 42, 31)
    pdf.set_draw_color(55, 55, 55)
    pdf.set_line_width(0.18)
    pdf.rect(right - 42, 31, 42, 13)
    pdf.set_xy(right - 40, 33)
    pdf.set_font(_font(pdf), "B", 7.2)
    pdf.set_text_color(35, 35, 35)
    pdf.multi_cell(38, 3.6, _safe_text(status), align="C")

    pdf.set_xy(left, 82)
    pdf.set_font(_font(pdf), "", 9.5)
    pdf.set_text_color(85, 85, 85)
    pdf.cell(0, 5, _safe_text("Request for Proposal (RFP)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(left)
    pdf.set_font(_font(pdf), "B", 26)
    pdf.set_text_color(15, 15, 15)
    pdf.multi_cell(width, 10, _safe_text(tender_title))
    pdf.ln(2)
    pdf.set_x(left)
    pdf.set_font(_font(pdf), "", 10.5)
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
    pdf.set_font(_font(pdf), "B", 9.5)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5, _safe_text("Confidentiality Notice"))
    pdf.set_x(left)
    pdf.set_font(_font(pdf), "", 9)
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

    if _is_modern(pdf):
        groups = [
            (
                "Document Governance",
                [
                    "Tender Data Sheet",
                    "Document Control",
                    "Introduction",
                    "Instructions to Bidders",
                    "Award and Contract",
                ],
            ),
            (
                "Bidder Requirements",
                [
                    "Eligibility and Vendor Document Requirements",
                    "Proposal Submission Requirements",
                ],
            ),
            (
                "Project Requirements",
                [
                    "Project Overview",
                    "Objectives",
                    "Scope of Work",
                    "Deliverables",
                    "Timeline",
                    "Team Requirements",
                ],
            ),
            (
                "Commercial, Legal, and Approval",
                [
                    "General Terms and Conditions",
                    "Confidentiality",
                    "Technical and Financial Evaluation Methodology",
                    "Payment Terms",
                    "Annexures",
                    "Buyer Approval",
                ],
            ),
        ]
        x = pdf.l_margin
        y = pdf.get_y() + 2
        w = pdf.w - pdf.l_margin - pdf.r_margin

        pdf.set_xy(x, y)
        pdf.set_font(_font(pdf), "B", 18)
        pdf.set_text_color(*SAUDI_GREEN_DARK)
        pdf.multi_cell(w, 8, _safe_text("Table of Contents"))
        pdf.set_draw_color(*SAUDI_GREEN)
        pdf.set_line_width(0.8)
        pdf.line(x, pdf.get_y() + 1, x + 28, pdf.get_y() + 1)
        pdf.ln(8)

        for group_index, (group_title, items) in enumerate(groups, start=1):
            _ensure_space(pdf, 15 + len(items) * 7.5)
            group_y = pdf.get_y()
            pdf.set_fill_color(*SAUDI_GREEN_SOFT)
            pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
            pdf.set_line_width(0.12)
            pdf.rect(x, group_y, w, 8.8, style="DF")
            pdf.set_fill_color(*SAUDI_GREEN)
            pdf.rect(x, group_y, 2.2, 8.8, style="F")
            pdf.set_xy(x + 5, group_y + 2.2)
            pdf.set_text_color(*SAUDI_GREEN_DARK)
            pdf.set_font(_font(pdf), "B", 9.2)
            pdf.cell(w - 10, 4, _safe_text(f"Section {group_index}: {group_title}"))
            pdf.set_y(group_y + 8.5)

            for item_index, item in enumerate(items, start=1):
                row_y = pdf.get_y()
                pdf.set_draw_color(*SAUDI_GREEN_LIGHT)
                pdf.set_line_width(0.08)
                pdf.line(x + 9, row_y + 7.2, x + w, row_y + 7.2)
                pdf.set_xy(x + 12, row_y + 2)
                pdf.set_text_color(*SAUDI_GREEN_MID)
                pdf.set_font(_font(pdf), "B", 8.4)
                pdf.cell(13, 3.8, _safe_text(f"{group_index}.{item_index}"))
                pdf.set_xy(x + 29, row_y + 2)
                pdf.set_text_color(24, 52, 38)
                pdf.set_font(_font(pdf), "", 8.8)
                pdf.cell(w - 32, 3.8, _safe_text(item))
                pdf.set_y(row_y + 7.4)

            pdf.ln(3.5)

        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
        return

    pdf.set_x(pdf.l_margin)
    pdf.set_font(_font(pdf), "B", 17 if pdf.template == "premium_bw" else 16)
    title = "TABLE OF CONTENTS" if pdf.template == "premium_bw" else "Table of Contents"
    pdf.multi_cell(0, 9, _safe_text(title), align="L" if pdf.template == "premium_bw" else "C")
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


def build_pdf(draft: Any, output_path: Path = OUTPUT_PDF, template: str | None = None):
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
        template=template,
    )
    _register_fonts(pdf)
    if pdf.template == "premium_bw":
        pdf.set_margins(20, 20, 20)
        pdf.set_auto_page_break(auto=True, margin=18)
    else:
        pdf.set_margins(18, 18, 18)
        pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    _write_cover_page(pdf, d, metadata, tender_data_sheet, intelligence)

    _write_tender_data_sheet_page(pdf, tender_data_sheet)
    _write_document_control_page(pdf, d, metadata, tender_data_sheet, intelligence)
    _write_toc(pdf)

    pdf.add_page()

    _write_section(pdf, "1.3 Introduction")
    _write_subsection(pdf, "1.3.1 About the Organisation")
    _write_para(pdf, introduction.get("about_organization", ""))
    _write_subsection(pdf, "1.3.2 Background")
    _write_para(pdf, introduction.get("background", ""))
    _write_subsection(pdf, "1.3.3 Purpose of this RFP")
    _write_para(pdf, introduction.get("purpose_of_rfp", ""))

    _write_section(pdf, "1.4 Instructions to Bidders")
    _write_bullet_subsection(pdf, "1.4.1 Submission Rules", instructions.get("submission_rules", []))

    timetable = instructions.get("timetable", {})
    _write_subsection(pdf, "1.4.2 Timetable")
    _write_key_value_table(
        pdf,
        [
            ("RFP Issue Date", timetable.get("issue_date", "")),
            ("Clarifications Deadline", timetable.get("clarifications_deadline", "")),
            ("Proposal Submission Deadline", timetable.get("submission_deadline", "")),
        ],
    )

    _write_subsection(pdf, "1.4.3 Clarifications Process")
    _write_para(pdf, instructions.get("clarifications_process", ""))

    _write_subsection(pdf, "1.4.4 Proposal Validity")
    _write_para(
        pdf,
        f"Proposals must remain valid for {instructions.get('proposal_validity_days', 90)} days from the closing date.",
    )

    _write_subsection(pdf, "1.4.5 Confidentiality")
    _write_para(pdf, instructions.get("confidentiality_statement", ""))

    _write_subsection(pdf, "1.4.6 Conflict of Interest")
    _write_para(pdf, instructions.get("conflict_of_interest_policy", ""))

    _write_subsection(pdf, "1.4.7 Cancellation Rights")
    _write_para(pdf, instructions.get("cancellation_rights", ""))

    submission_controls = instructions.get("submission_controls") or {}

    if submission_controls:
        _ensure_space(pdf, 95)

        _write_subsection(pdf, "1.4.8 Platform Submission Controls")
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

    _write_section(pdf, "1.5 Award and Contract")
    _write_para_subsection(pdf, "1.5.1 Evaluation Process", award.get("evaluation_process", ""))
    _write_para_subsection(pdf, "1.5.2 Negotiation Policy", award.get("negotiation_policy", ""))
    _write_para_subsection(pdf, "1.5.3 Award Rules", award.get("award_rules", ""))
    _write_para_subsection(pdf, "1.5.4 Bid Security", award.get("bid_security", ""))
    _write_para_subsection(pdf, "1.5.5 Performance Bond", award.get("performance_bond_text", ""))
    _write_para_subsection(pdf, "1.5.6 Saudization Requirements", award.get("saudization_requirements", ""))

    _write_section(pdf, "Section 2: Bidder Requirements")
    _write_subsection(pdf, "2.1 Eligibility and Vendor Document Requirements")
    _write_notice_box(
        pdf,
        "Eligibility Requirement",
        "Bidders must satisfy the eligibility and document requirements in this section. The Buyer may reject incomplete, expired, unreadable, inconsistent, or non-compliant submissions in accordance with the tender rules and Buyer-Admin approval controls.",
    )
    _write_bullet_subsection(pdf, "2.1.1 Document Governance Rules", award.get("vendor_document_rules", []))
    _write_bullet_subsection(pdf, "2.1.2 Documents Required for this Tender", award.get("statutory_documents_required", []))
    _write_document_table(pdf, "2.1.3 Mandatory Documents", award.get("mandatory_documents", []))
    _write_document_table(pdf, "2.1.4 Mandatory-if-Applicable / Conditional Documents", award.get("conditional_documents", []))
    _write_document_table(pdf, "2.1.5 IT Sector-Specific Documents", award.get("sector_specific_documents", []))
    _write_document_table(pdf, "2.1.6 Optional Capability and Credibility Documents", award.get("optional_documents", []))

    pdf.add_page()

    _write_section(pdf, "2.2 Proposal Submission Requirements")
    _write_notice_box(
        pdf,
        "Submission Requirement",
        "Technical and commercial proposals must be prepared, separated, signed, stamped, and submitted according to this section. The Mushtarry platform record and timestamp constitute the official submission record unless the Buyer-Admin expressly approves another channel.",
    )
    _write_key_value_table(
        pdf,
        [("Submission Channel", _formal_submission_method(proposal_format.get("submission_method", "")))],
    )

    technical_proposal = proposal_format.get("technical_proposal", {})
    commercial_proposal = proposal_format.get("commercial_proposal", {})

    _write_subsection(pdf, "2.2.1 Technical Proposal")
    _write_key_value_table(
        pdf,
        [("File Naming Standard", _formal_file_naming(technical_proposal.get("file_naming_convention", ""), "Technical Proposal"))],
    )
    _write_bullets(pdf, technical_proposal.get("required_sections", []))

    _write_subsection(pdf, "2.2.2 Commercial Proposal")
    _write_key_value_table(
        pdf,
        [
            ("File Naming Standard", _formal_file_naming(commercial_proposal.get("file_naming_convention", ""), "Commercial Proposal")),
            ("Accepted Currencies", ", ".join(commercial_proposal.get("accepted_currencies", ["SAR"]))),
        ],
    )
    _write_bullets(pdf, commercial_proposal.get("pricing_requirements", []))

    _write_section(pdf, "Section 3: Project Requirements")
    _write_subsection(pdf, "3.1 Project Overview")
    _write_subsection(pdf, "3.1.1 Project Introduction")
    _write_para(pdf, overview.get("project_introduction", ""))
    _write_subsection(pdf, "3.1.2 Background")
    _write_para(pdf, overview.get("background", ""))
    _write_subsection(pdf, "3.1.3 Context")
    _write_para(pdf, overview.get("context", ""))

    _write_subsection(pdf, "3.2 Objectives")
    _write_bullet_subsection(pdf, "3.2.1 Business Goals", objectives.get("business_goals", []))
    _write_bullet_subsection(pdf, "3.2.2 Expected Outcomes", objectives.get("expected_outcomes", []))
    _write_bullet_subsection(pdf, "3.2.3 Key Performance Indicators", objectives.get("kpis", []))

    _write_section(pdf, "3.3 Scope of Work")
    scope_categories = scope.get("categories", [])
    for index, category in enumerate(scope_categories, start=1):
        c = _as_dict(category)
        _write_subsection(pdf, f"3.3.{index} {c.get('name', 'Work Category')}")
        _write_para(pdf, c.get("description", ""))
        _write_bullets(pdf, c.get("requirements", []))

    next_scope_section = len(scope_categories) + 1
    scope_phases = scope.get("phases", [])
    if scope_phases:
        _write_subsection(pdf, f"3.3.{next_scope_section} Execution Phases")
        for phase_index, phase in enumerate(scope_phases, start=1):
            p = _as_dict(phase)
            _write_subsection(pdf, f"3.3.{next_scope_section}.{phase_index} {p.get('phase', 'Phase')}")
            _write_bullets(pdf, p.get("activities", []))
        next_scope_section += 1

    _write_bullet_subsection(pdf, f"3.3.{next_scope_section} General Requirements", scope.get("general_requirements", []))

    pdf.add_page()

    _write_section(pdf, "3.4 Deliverables")
    _write_bullet_subsection(pdf, "3.4.1 Work Order Process", deliverables.get("work_order_process", []))

    _write_subsection(pdf, "3.4.2 Required Deliverables")
    for index, item in enumerate(deliverables.get("deliverables", []), start=1):
        it = _as_dict(item)
        _write_deliverable_item(pdf, it, index)

    _write_subsection(pdf, "3.4.3 Approval Process")
    _write_para(pdf, deliverables.get("approval_process", ""))

    _write_bullet_subsection(pdf, "3.4.4 Reporting Requirements", deliverables.get("reporting_requirements", []))

    _write_subsection(pdf, "3.4.5 Escalation Matrix")
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

    _write_section(pdf, "3.5 Timeline")
    _write_para(pdf, timeline.get("total_duration", ""))

    _write_bullet_subsection(pdf, "3.5.1 Project Phases", timeline.get("project_phases", []))

    _write_subsection(pdf, "3.5.2 Key Milestones")
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

    _write_section(pdf, "3.6 Team Requirements")
    team_roles = team.get("roles", [])
    for role_index, role in enumerate(team_roles, start=1):
        r = _as_dict(role)
        _write_subsection(pdf, f"3.6.{role_index} {r.get('position', 'Role')}")
        _write_para(pdf, f"Responsibilities: {r.get('responsibilities', '')}")
        _write_para(pdf, f"Minimum Experience: {r.get('minimum_experience', '')}")

    _write_subsection(pdf, f"3.6.{len(team_roles) + 1} Saudization")
    _write_para(pdf, team.get("saudization_note", ""))

    _write_section(pdf, "Section 4: Commercial, Legal, and Approval")
    _write_subsection(pdf, "4.1 General Terms and Conditions")
    _write_bullet_subsection(pdf, "4.1.1 Legal Terms", terms.get("legal_terms", []))
    _write_bullet_subsection(pdf, "4.1.2 Compliance Requirements", terms.get("compliance_requirements", []))
    _write_subsection(pdf, "4.1.3 Language Requirements")
    _write_para(pdf, terms.get("language_requirements", ""))
    _write_subsection(pdf, "4.1.4 Equipment and Logistics")
    _write_para(pdf, terms.get("equipment_and_logistics", ""))

    _write_section(pdf, "4.2 Confidentiality")
    _write_para(pdf, d.get("confidentiality", ""))

    pdf.add_page()

    _write_section(pdf, "4.3 Technical and Financial Evaluation Methodology")
    _write_notice_box(
        pdf,
        "Evaluation Governance",
        "Evaluation will be conducted against the Buyer-approved mandatory, technical, and financial requirements. Any Mushtarry AI recommendation is advisory only; the Buyer-Admin retains final decision authority for qualification, award, rejection, and publication.",
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

    _write_subsection(pdf, "4.3.1 Mandatory Pass/Fail Criteria")
    for criterion in evaluation.get("mandatory_criteria", []):
        c = _as_dict(criterion)
        _write_bullets(pdf, [c.get("criterion", criterion)])

    _write_bullet_subsection(pdf, "4.3.2 Technical Evaluation Parameters", evaluation.get("technical_parameters", []))

    _write_bullet_subsection(pdf, "4.3.3 Financial Evaluation Parameters", evaluation.get("financial_parameters", []))

    _write_subsection(pdf, "4.3.4 AI-Assisted Recommendation Note")
    _write_para(
        pdf,
        "Mushtarry may assist the buyer by summarizing proposals, checking mandatory compliance, "
        "comparing technical and commercial alignment, reviewing vendor document status, considering "
        "category-specific vendor reputation indicators, delivery reliability, rating history, completed "
        "contract history, compliance signals, and AI risk indicators, and preparing a ranked recommendation "
        "against buyer-approved criteria. AI output is advisory only and cannot publish, reject, award, "
        "or finalize any tender decision. Final award requires buyer approval.",
    )

    _write_section(pdf, "4.4 Payment Terms")
    _write_subsection(pdf, "4.4.1 Payment Basis")
    _write_para(pdf, payment.get("payment_basis", ""))

    payment_schedule = []
    for item in payment.get("payment_schedule", []) or []:
        row = _as_dict(item)
        if row:
            payment_schedule.append(row)
    if payment_schedule:
        _write_payment_schedule_tables(pdf, payment_schedule)

    _write_bullet_subsection(pdf, "4.4.3 Invoice Requirements", payment.get("invoice_requirements", []))
    _write_bullet_subsection(pdf, "4.4.4 Payment Controls", payment.get("payment_controls", []))

    _write_para_subsection(pdf, "4.4.5 Tax and Currency", payment.get("tax_and_currency", ""))
    _write_para_subsection(pdf, "4.4.6 Retention, Withholding, and Set-Off", payment.get("withholding_retention", ""))
    _write_subsection(pdf, "4.4.7 Payment Timeline")
    _write_para(pdf, payment.get("payment_timeline", ""))

    _write_section(pdf, "4.5 Annexures")
    _write_bullets(pdf, annexures)

    pdf.add_page()

    _write_section(pdf, "4.6 Buyer Approval")
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
    pdf.set_draw_color(*(SAUDI_GREEN_LIGHT if _is_modern(pdf) else (150, 150, 150)))
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
    pdf.set_text_color(*(SAUDI_GREEN_DARK if _is_modern(pdf) else (45, 45, 45)))
    pdf.cell(box_w, 6, _safe_text("Signature"), align="C")
    pdf.set_xy(pdf.l_margin + box_w + 10, y + 9)
    pdf.cell(box_w, 6, _safe_text("Official Stamp"), align="C")
    pdf.set_text_color(0, 0, 0)

    _write_thank_you_page(pdf)

    pdf.output(str(output_path))
