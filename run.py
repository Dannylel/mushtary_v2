"""
Mushtarry — unified runner.

Default ("full") runs the LangGraph tender-creation pipeline end to end with NO user
input: the AI invents the buyer brief, four section agents draft in parallel, and the
result is written to JSON + PDF (status: DRAFT, pending buyer approval).

Any single agent can be run alone via --mode.

Examples
--------
  python run.py                              # autonomous draft tender (AI fills everything)
  python run.py --seed "hospital MRI supply" # autonomous draft, steered by a topic
  python run.py --mode form --seed "solar farm O&M"     # just synthesise a buyer form
  python run.py --mode full --form my_form.json         # draft from a provided form
  python run.py --mode extract --sow some_rfp.pdf       # SOW/RFP document -> buyer form
  python run.py --mode scope --seed "school catering"   # one drafting section alone
  python run.py --mode score --input vendor_scoring.json
  python run.py --mode rank  --input ranking_input.json
  python run.py --mode validate --input vendor.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agents.buyer_form import TenderBuyerForm
from agents.graph.modes import MODES, run_mode


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    return obj


def _load_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save_json(obj: Any, path: Path) -> None:
    path.write_text(
        json.dumps(_to_jsonable(obj), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Saved: {path.resolve()}")


def main() -> None:
    # Windows consoles default to cp1252 and choke on Arabic/Unicode output.
    try:
        import sys

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description="Mushtarry agent runner")
    parser.add_argument("--mode", default="full", choices=MODES, help="which agent / pipeline to run")
    parser.add_argument("--seed", default=None, help="topic/category hint for autonomous form generation")
    parser.add_argument("--form", default=None, help="path to a TenderBuyerForm JSON file")
    parser.add_argument("--sow", default=None, help="path to a SOW/RFP document (.pdf) or text (.txt)")
    parser.add_argument("--input", default=None, help="path to a JSON payload (validate/score/rank modes)")
    parser.add_argument("--out-json", default="outputs/tender_draft.json", help="output JSON path (full mode)")
    parser.add_argument("--out-pdf", default="outputs/tender_draft.pdf", help="output PDF path (full mode)")
    args = parser.parse_args()

    Path("outputs").mkdir(parents=True, exist_ok=True)

    # Resolve optional inputs
    form = None
    if args.form:
        form = TenderBuyerForm.model_validate(_load_json(args.form))

    sow_text = sow_path = None
    if args.sow:
        if args.sow.lower().endswith(".pdf"):
            sow_path = args.sow
        else:
            sow_text = Path(args.sow).read_text(encoding="utf-8")

    payload = _load_json(args.input)

    print(f"Running mode: {args.mode}")
    result = run_mode(
        args.mode,
        seed=args.seed,
        form=form,
        sow_text=sow_text,
        sow_path=sow_path,
        payload=payload,
    )

    # ── Render per mode ─────────────────────────────────────────────────────────
    if args.mode == "full":
        artifact = result.get("artifact") if isinstance(result, dict) else _to_jsonable(result)
        draft_payload = artifact.get("output", {}) if isinstance(artifact, dict) else {}
        title = draft_payload.get("metadata", {}).get("title", "Tender Draft")
        print(f"Title: {title}")

        _save_json(artifact, Path(args.out_json))

        try:
            from pdf_renderer import build_pdf

            build_pdf(artifact, Path(args.out_pdf))
            print(f"Saved: {Path(args.out_pdf).resolve()}")
        except Exception as e:  # PDF rendering is best-effort
            print(f"(PDF rendering skipped: {e})")
        return

    # All single-agent modes just emit their structured output as JSON.
    out_path = Path("outputs") / f"{args.mode}_output.json"
    _save_json(result, out_path)
    print(json.dumps(_to_jsonable(result), indent=2, ensure_ascii=False, default=str)[:1500])


if __name__ == "__main__":
    main()
