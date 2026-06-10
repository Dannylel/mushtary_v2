"""
LEGACY entry point — drafts a tender from the hardcoded IT-infrastructure test form
using the ThreadPoolExecutor orchestrator, then writes JSON + PDF to outputs/.

The primary entry point is run.py (LangGraph pipeline, all modes). This file remains
for the original demo flow only. The PDF renderer lives in pdf_renderer.py; the test
form lives in agents/samples/test_form.py.
"""
import json
from pathlib import Path

from dotenv import load_dotenv

from agents.samples.test_form import build_test_form
from agents.tender_drafting.agent import TenderDrafterAgent
from agents.tender_drafting.schemas import TenderDraftInput
from pdf_renderer import _to_jsonable, _unwrap_draft, build_pdf

OUTPUT_DIR = Path("outputs")
OUTPUT_JSON = OUTPUT_DIR / "tender_draft.json"
OUTPUT_PDF = OUTPUT_DIR / "tender_draft.pdf"


def main():
    # Local-first: agents resolve the model from agents/llm_config.py (Ollama default);
    # .env can override LLM_BASE_URL / LLM_MODEL / LLM_API_KEY.
    load_dotenv(override=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    form = build_test_form()
    print(f"Generating tender draft for: {form.tender_title}")

    draft = TenderDrafterAgent().run(TenderDraftInput(buyer_id="test-buyer-001", form=form))
    draft_payload = _unwrap_draft(draft)

    title = (
        draft_payload.get("metadata", {}).get("title")
        or draft_payload.get("title")
        or form.tender_title
    )
    print(f"Title: {title}")

    print("\nSaving JSON...")
    OUTPUT_JSON.write_text(
        json.dumps(_to_jsonable(draft), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Saved: {OUTPUT_JSON.resolve()}")

    print("\nBuilding PDF...")
    build_pdf(draft, OUTPUT_PDF)
    print(f"Saved: {OUTPUT_PDF.resolve()}")


if __name__ == "__main__":
    main()
