"""
Mushtary demo API — a thin FastAPI layer over the existing agents so the web UI can
exercise the whole pipeline locally. NOT the production app (no auth, no DB); it's a
demo/testing surface.

Long-running agent calls (full drafting takes minutes on a local 7B model) run in
background threads via a tiny in-memory job manager; the frontend polls for completion.
Fast calls (knowledge-base search, metadata) are synchronous.

Run:
    python api.py            # then open http://localhost:8000
    # or: python -m uvicorn api:app --port 8000
"""
from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(override=True)

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
UPLOADS = OUTPUTS / "uploads"
OUTPUTS.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="Mushtary Demo API", version="1.0.0")

# ── Activity feed: bridge agents' log lines into the live console ───────────────
from agents import activity  # noqa: E402  (after dotenv so config is loaded)
import logging


class _ActivityLogHandler(logging.Handler):
    """Forward agents.* INFO logs into the activity feed as narrator lines."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            activity.publish("info", record.getMessage(), label=record.name.split(".")[-1])
        except Exception:  # the feed must never break logging
            pass


_agents_logger = logging.getLogger("agents")
_agents_logger.setLevel(logging.INFO)
_agents_logger.addHandler(_ActivityLogHandler())


# ── Tiny in-memory job manager ──────────────────────────────────────────────────
# A job is one agent/pipeline run. Status flows PENDING -> RUNNING -> SUCCESS|FAILURE.
class Job(BaseModel):
    id: str
    kind: str
    status: str = "PENDING"
    created_at: str
    finished_at: str | None = None
    result: Any = None
    error: str | None = None


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def _new_job(kind: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind,
              created_at=datetime.now(timezone.utc).isoformat())
    with _LOCK:
        _JOBS[job.id] = job
    return job


def _run_async(job: Job, fn, *args, **kwargs) -> None:
    """Execute fn(*args) in a daemon thread, recording result/error on the job."""
    def _target():
        with _LOCK:
            _JOBS[job.id].status = "RUNNING"
        activity.publish("info", f"Job started: {job.kind}", label="job")
        try:
            result = fn(*args, **kwargs)
            with _LOCK:
                _JOBS[job.id].status = "SUCCESS"
                _JOBS[job.id].result = result
                _JOBS[job.id].finished_at = datetime.now(timezone.utc).isoformat()
            activity.publish("info", f"Job finished: {job.kind}", label="job")
        except Exception as e:  # surface the failure to the UI rather than dying silently
            with _LOCK:
                _JOBS[job.id].status = "FAILURE"
                _JOBS[job.id].error = f"{type(e).__name__}: {e}"
                _JOBS[job.id].finished_at = datetime.now(timezone.utc).isoformat()
            activity.publish("info", f"Job FAILED: {job.kind} — {e}", label="job")
            traceback.print_exc()

    threading.Thread(target=_target, daemon=True).start()


# ── Job worker functions (run inside the background thread) ──────────────────────

def _job_full_draft(seed: str | None, sow_path: str | None) -> dict:
    """Run the full LangGraph pipeline and render the PDF. Returns artifact + file ids."""
    from agents.graph.modes import run_mode
    from pdf_renderer import build_pdf

    if sow_path:
        state = run_mode("full", sow_path=sow_path)
    else:
        state = run_mode("full", seed=seed)

    artifact = state.get("artifact") if isinstance(state, dict) else None
    if not artifact:
        raise RuntimeError("Pipeline returned no artifact")

    fid = uuid.uuid4().hex[:12]
    pdf_path = OUTPUTS / f"tender_{fid}.pdf"
    json_path = OUTPUTS / f"tender_{fid}.json"
    import json as _json
    json_path.write_text(_json.dumps(artifact, indent=2, ensure_ascii=False, default=str),
                         encoding="utf-8")
    build_pdf(artifact, pdf_path)

    return {"artifact": artifact, "file_id": fid}


def _job_form(seed: str | None) -> dict:
    from agents.graph.modes import run_mode
    form = run_mode("form", seed=seed)
    return {"form": form.model_dump(mode="json")}


def _job_extract(sow_path: str) -> dict:
    from agents.graph.modes import run_mode
    form = run_mode("extract", sow_path=sow_path)
    return {"form": form.model_dump(mode="json")}


def _job_validate(payload: dict) -> dict:
    from agents.vendor_validation.agent import VendorValidationAgent
    from agents.vendor_validation.schemas import VendorValidationInput

    data = VendorValidationInput.model_validate(payload)
    artifact = VendorValidationAgent().run(data)
    return {"artifact": artifact.model_dump(mode="json")}


def _job_evaluate() -> dict:
    """Score every vendor in the bundled sample (in isolation), then rank. Reuses the
    builder helpers from the demo script so the input shapes stay in one place."""
    import json as _json
    from agents.evaluation.agent import EvaluationRankerAgent
    from agents.evaluation.schemas import (
        RankingInput, VendorScoringInput, VendorScore, DisqualificationResult,
        FitScoreBreakdown, CriterionScore,
    )
    from agents.samples.run_demo import build_policy, build_criteria, build_vri, build_submission

    samples = ROOT / "agents" / "samples"
    tender = _json.loads((samples / "it_infrastructure_tender.json").read_text(encoding="utf-8"))
    subs = _json.loads((samples / "vendor_submissions.json").read_text(encoding="utf-8"))

    policy = build_policy(tender)
    criteria = build_criteria(tender)
    agent = EvaluationRankerAgent()

    scores_json = []
    score_objects = []
    for vd in subs["submissions"]:
        payload = VendorScoringInput(
            tender_id=tender["tender_id"],
            tender_category=tender["subcategory"],
            criteria=criteria,
            submission=build_submission(vd["submission"]),
            vri=build_vri(vd["vri"]),
            policy=policy,
            market_avg_price_sar=tender.get("market_avg_price_sar"),
        )
        s = agent.run(payload).output
        s["vendor_name"] = vd["vendor_name"]  # carry name for display only
        scores_json.append(s)
        score_objects.append(VendorScore(
            vendor_id=s["vendor_id"], submission_id=s["submission_id"],
            disqualification=DisqualificationResult(**s["disqualification"]),
            scores_by_criterion=[CriterionScore(**c) for c in s["scores_by_criterion"]],
            fit_score_breakdown=FitScoreBreakdown(**s["fit_score_breakdown"]),
            weighted_total=s["weighted_total"], risk_level=s["risk_level"],
            overall_reasoning=s["overall_reasoning"],
            missing_requirements=s["missing_requirements"], trace_id=s["trace_id"],
        ))

    ranking = agent.rank(RankingInput(
        tender_id=tender["tender_id"], policy=policy, vendor_scores=score_objects,
    )).output

    # Map vendor_id -> display name so the ranked list can show names.
    names = {vd["submission"]["vendor_id"]: vd["vendor_name"] for vd in subs["submissions"]}
    return {
        "tender_title": tender.get("title", tender["tender_id"]),
        "scores": scores_json,
        "ranking": ranking,
        "vendor_names": names,
    }


# ── Request models for synchronous endpoints ─────────────────────────────────────

class SeedReq(BaseModel):
    seed: str | None = None


class ValidateReq(BaseModel):
    vendor_id: str = "VND-DEMO-001"
    cr_number: str
    legal_name_ar: str
    legal_name_en: str
    selected_categories: list[str] = []
    document_types: list[str] = []   # doc_type strings; converted to DocumentMeta below


# ── API: job-launching endpoints ─────────────────────────────────────────────────

@app.post("/api/jobs/draft")
def start_draft(req: SeedReq):
    job = _new_job("draft")
    _run_async(job, _job_full_draft, req.seed or None, None)
    return {"job_id": job.id}


@app.post("/api/jobs/draft-sow")
async def start_draft_sow(file: UploadFile = File(...)):
    path = UPLOADS / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path.write_bytes(await file.read())
    job = _new_job("draft")
    _run_async(job, _job_full_draft, None, str(path))
    return {"job_id": job.id}


@app.post("/api/jobs/form")
def start_form(req: SeedReq):
    job = _new_job("form")
    _run_async(job, _job_form, req.seed or None)
    return {"job_id": job.id}


@app.post("/api/jobs/extract")
async def start_extract(file: UploadFile = File(...)):
    path = UPLOADS / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path.write_bytes(await file.read())
    job = _new_job("extract")
    _run_async(job, _job_extract, str(path))
    return {"job_id": job.id}


@app.post("/api/jobs/validate")
def start_validate(req: ValidateReq):
    now = datetime.now(timezone.utc).isoformat()
    documents = [
        {"doc_type": dt, "filename": f"{dt}.pdf", "size_bytes": 1024, "uploaded_at": now}
        for dt in req.document_types
    ]
    payload = {
        "vendor_id": req.vendor_id,
        "cr_number": req.cr_number,
        "legal_name_ar": req.legal_name_ar,
        "legal_name_en": req.legal_name_en,
        "selected_categories": req.selected_categories,
        "documents": documents,
    }
    job = _new_job("validate")
    _run_async(job, _job_validate, payload)
    return {"job_id": job.id}


@app.post("/api/jobs/evaluate")
def start_evaluate():
    job = _new_job("evaluate")
    _run_async(job, _job_evaluate)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.model_dump()


# ── API: synchronous endpoints ───────────────────────────────────────────────────

@app.get("/api/meta")
def meta():
    from agents.llm_config import get_model, get_base_url
    from agents.rag.config import get_embed_model
    from agents.categories import CATEGORIES
    from agents.rag.knowledge_base import get_tender_kb

    kb = get_tender_kb()
    # _store is internal; len() reflects indexed chunk count for the UI stat.
    try:
        kb_count = len(kb._store)
    except Exception:
        kb_count = 0
    return {
        "model": get_model(),
        "embed_model": get_embed_model(),
        "base_url": get_base_url(),
        "categories": CATEGORIES,
        "kb_available": kb.available,
        "kb_count": kb_count,
    }


@app.get("/api/activity")
def get_activity(since: int = 0):
    """Live feed of agent activity (streamed model text + lifecycle lines).

    The frontend polls this while a job runs to show what the model is writing.
    """
    events, last = activity.get_since(since)
    return {"events": events, "last_id": last}


@app.get("/api/kb/search")
def kb_search(q: str, k: int = 5):
    from agents.rag.knowledge_base import get_tender_kb

    hits = get_tender_kb().retrieve(q, k=k, min_score=0.0)
    return {
        "query": q,
        "hits": [
            {"score": round(h.score, 3),
             "source": h.metadata.get("source", "?"),
             "authority": h.metadata.get("authority", "?"),
             "text": h.text}
            for h in hits
        ],
    }


@app.get("/api/download/{file_id}/{kind}")
def download(file_id: str, kind: str):
    ext = "pdf" if kind == "pdf" else "json"
    path = OUTPUTS / f"tender_{file_id}.{ext}"
    if not path.exists():
        raise HTTPException(404, "file not found")
    media = "application/pdf" if ext == "pdf" else "application/json"
    return FileResponse(path, media_type=media, filename=path.name)


# ── Static frontend (mounted last so /api/* wins) ────────────────────────────────
FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    print("Mushtary demo UI -> http://localhost:8000")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
