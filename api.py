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

def _format_date(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            yyyy, mm, dd = text.split("-")
            return f"{dd}/{mm}/{yyyy}"
    except Exception:
        pass
    return text


def _apply_form_overrides(form, overrides: dict | None):
    if not overrides:
        return form

    data = form.model_dump(mode="json")
    simple_fields = [
        "tender_title", "tender_id", "buyer_name", "buyer_description",
        "category", "subcategory", "tender_type", "procurement_method",
        "location", "project_objective", "scope_of_work",
        "technical_requirements", "methodology_requirements",
        "estimated_value_sar", "budget_range", "payment_terms",
        "proposal_validity_days", "bid_security_required",
        "bid_security_amount_or_percentage", "performance_bond_required",
        "performance_bond_percentage", "performance_bond_validity",
        "retention_percentage", "liquidated_damages_applicable", "liquidated_damages_rate",
        "minimum_years_experience", "minimum_similar_projects",
        "minimum_project_value_sar", "required_sector_license",
        "blacklist_declaration_required", "local_presence_required",
        "saudization_required", "confidentiality_required", "onsite_required",
        "evaluation_model", "technical_weight", "financial_weight",
        "minimum_score", "submission_method", "proposal_format",
        "contract_duration", "warranty_duration", "language_requirements",
    ]
    for field in simple_fields:
        if field in overrides and overrides[field] not in (None, ""):
            data[field] = overrides[field]

    for field in ["issue_date", "clarification_deadline", "submission_deadline", "opening_date", "site_visit_date"]:
        if field in overrides:
            formatted = _format_date(overrides.get(field))
            if formatted:
                if field == "submission_deadline" and overrides.get("submission_time"):
                    formatted = f"{formatted} @ {overrides['submission_time']} KSA Time"
                data[field] = formatted

    if "site_visit_required" in overrides:
        data["site_visit_required"] = bool(overrides["site_visit_required"])
        if not data["site_visit_required"]:
            data["site_visit_date"] = None

    if "submission_controls" in overrides and isinstance(overrides["submission_controls"], dict):
        controls = dict(data.get("submission_controls") or {})
        controls.update({k: v for k, v in overrides["submission_controls"].items() if v not in (None, "")})
        data["submission_controls"] = controls

    list_fields = [
        "deliverables", "timeline", "roles_and_responsibilities",
        "eligibility_criteria", "required_certifications", "required_documents",
        "mandatory_documents", "conditional_documents", "optional_documents",
        "sector_specific_documents", "prestige_documents", "evaluation_criteria",
        "mandatory_disqualification_criteria", "technical_evaluation_parameters",
        "financial_evaluation_parameters",
    ]
    for field in list_fields:
        if field in overrides and isinstance(overrides[field], list):
            data[field] = overrides[field]

    from agents.buyer_form import TenderBuyerForm
    return TenderBuyerForm.model_validate(data)


def _job_full_draft(seed: str | None, sow_path: str | None, sow_text: str | None = None, template: str | None = None, form_overrides: dict | None = None) -> dict:
    """Run the full LangGraph pipeline and render the PDF. Returns artifact + file ids."""
    from agents.graph.modes import run_mode
    from pdf_renderer import build_pdf, normalize_template

    if form_overrides:
        if sow_text:
            form = run_mode("extract", sow_text=sow_text)
        elif sow_path:
            form = run_mode("extract", sow_path=sow_path)
        else:
            form = run_mode("form", seed=seed)
        form = _apply_form_overrides(form, form_overrides)
        state = run_mode("full", form=form, seed=seed)
    elif sow_text:
        state = run_mode("full", sow_text=sow_text, seed=seed)
    elif sow_path:
        state = run_mode("full", sow_path=sow_path)
    else:
        state = run_mode("full", seed=seed)

    artifact = state.get("artifact") if isinstance(state, dict) else None
    if not artifact:
        raise RuntimeError("Pipeline returned no artifact")

    fid = uuid.uuid4().hex[:12]
    template = normalize_template(template)
    pdf_path = OUTPUTS / f"tender_{fid}_{template}.pdf"
    default_pdf_path = OUTPUTS / f"tender_{fid}.pdf"
    json_path = OUTPUTS / f"tender_{fid}.json"
    import json as _json
    json_path.write_text(_json.dumps(artifact, indent=2, ensure_ascii=False, default=str),
                         encoding="utf-8")
    build_pdf(artifact, pdf_path, template=template)
    build_pdf(artifact, default_pdf_path, template=template)

    return {"artifact": artifact, "file_id": fid, "template": template}


def _job_form(seed: str | None) -> dict:
    from agents.graph.modes import run_mode
    form = run_mode("form", seed=seed)
    return {"form": form.model_dump(mode="json")}


def _job_extract(sow_path: str) -> dict:
    from agents.graph.modes import run_mode
    form = run_mode("extract", sow_path=sow_path)
    return {"form": form.model_dump(mode="json")}


def _job_sow_review(project_name: str, scope_text: str) -> dict:
    from agents.sow_review import SoWReviewAgent

    review = SoWReviewAgent().run(project_name=project_name, scope_text=scope_text)
    return {"review": review.model_dump(mode="json")}


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


def _append_unique(target: dict, key: str, values: list[str]) -> None:
    current = target.get(key)
    if not isinstance(current, list):
        current = []
    seen = {str(item).strip().lower() for item in current if str(item).strip()}
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in seen:
            current.append(text)
            seen.add(text.lower())
    target[key] = current


def _committee_agent(committee: dict, name: str) -> dict:
    agents = committee.get("agents") or []
    return next((a for a in agents if str(a.get("agent_name", "")).lower() == name.lower()), {})


def _job_improve_tender(artifact: dict, file_id: str | None = None, template: str | None = None) -> dict:
    """Patch the existing tender artifact using AI Tender Committee feedback."""
    from pdf_renderer import build_pdf, normalize_template

    if not isinstance(artifact, dict) or not isinstance(artifact.get("output"), dict):
        raise RuntimeError("Improve tender requires an artifact with an output object")

    import json as _json

    edited = _json.loads(_json.dumps(artifact, ensure_ascii=False, default=str))
    output = edited["output"]
    intelligence = output.get("tender_intelligence") or {}
    committee = intelligence.get("ai_tender_committee") or {}
    priorities = committee.get("improvement_priorities") or intelligence.get("missing_or_weak_requirements") or []
    if not committee and not priorities:
        raise RuntimeError("No AI Committee feedback is available on this tender")

    scope = output.setdefault("scope_of_work", {})
    evaluation = output.setdefault("evaluation_criteria", {})
    proposal_format = output.setdefault("proposal_format", {})
    payment = output.setdefault("payment_terms", {})
    terms = output.setdefault("general_terms", {})
    instructions = output.setdefault("instructions_to_bidders", {})
    award = output.setdefault("award_and_contract", {})
    deliverables = output.setdefault("deliverables", {})
    timeline = output.setdefault("timeline", {})

    technical_agent = _committee_agent(committee, "Technical Agent")
    commercial_agent = _committee_agent(committee, "Commercial Agent")
    compliance_agent = _committee_agent(committee, "Compliance Agent")
    delivery_agent = _committee_agent(committee, "Delivery Agent")
    risk_agent = _committee_agent(committee, "Risk Agent")

    _append_unique(scope, "general_requirements", [
        "Vendors shall provide measurable acceptance criteria for each major workstream.",
        "Vendors shall identify assumptions, exclusions, dependencies, and buyer inputs required for delivery.",
        technical_agent.get("recommendation", ""),
    ])
    _append_unique(evaluation, "technical_parameters", [
        "Completeness and measurability of the proposed technical solution.",
        "Quality of implementation methodology, testing approach, and acceptance plan.",
        "Strength of project team experience and support model.",
        technical_agent.get("recommendation", ""),
    ])

    commercial_proposal = proposal_format.setdefault("commercial_proposal", {})
    _append_unique(commercial_proposal, "pricing_requirements", [
        "Provide a detailed price breakdown by deliverable, phase, and optional item.",
        "State VAT treatment, currency, assumptions, exclusions, and validity period.",
        commercial_agent.get("recommendation", ""),
    ])
    _append_unique(evaluation, "financial_parameters", [
        "Total cost clarity and completeness of commercial breakdown.",
        "Commercial assumptions, exclusions, and payment milestone alignment.",
        commercial_agent.get("recommendation", ""),
    ])
    _append_unique(payment, "invoice_requirements", [
        "Invoices shall reference accepted deliverables and include signed acceptance evidence.",
        "Payment claims shall match the approved commercial breakdown and milestone plan.",
    ])

    _append_unique(terms, "compliance_requirements", [
        "Bidders shall submit all mandatory documents in valid, readable, and current form.",
        "The Buyer may reject incomplete, expired, inconsistent, or non-compliant submissions.",
        compliance_agent.get("recommendation", ""),
    ])
    _append_unique(evaluation, "mandatory_criteria", [
        {"criterion": "Submission of all mandatory eligibility and document requirements."},
        {"criterion": "Compliance with submission format, deadline, and platform controls."},
        {"criterion": "No unresolved conflict of interest or prohibited conduct declaration."},
    ])
    _append_unique(award, "vendor_document_rules", [
        "Mandatory documents are pass/fail requirements unless the Buyer-Admin expressly waives a non-material defect.",
        compliance_agent.get("recommendation", ""),
    ])

    _append_unique(deliverables, "reporting_requirements", [
        "Weekly status reporting covering progress, risks, blockers, decisions, and upcoming milestones.",
        "Final handover report confirming deliverable acceptance, open issues, and support transition.",
        delivery_agent.get("recommendation", ""),
    ])
    _append_unique(deliverables, "work_order_process", [
        "Each work package shall define scope, owner, due date, acceptance criteria, and approval workflow.",
    ])
    _append_unique(timeline, "project_phases", [
        "Kickoff and requirements confirmation",
        "Detailed design and implementation planning",
        "Execution, testing, acceptance, and handover",
        delivery_agent.get("recommendation", ""),
    ])

    _append_unique(instructions, "submission_rules", [
        "Bidders shall raise clarification questions before the clarification deadline through the approved channel.",
        "Bidders shall clearly list deviations, assumptions, and exclusions in their proposals.",
        risk_agent.get("recommendation", ""),
    ])
    if instructions.get("clarifications_process"):
        instructions["clarifications_process"] = (
            str(instructions["clarifications_process"]).rstrip()
            + " All bidder questions, buyer responses, and addenda shall be controlled through the approved clarification process and shared consistently with eligible bidders."
        )

    output["ai_committee_edit_applied"] = {
        "applied": True,
        "source": "AI Tender Committee",
        "final_score": committee.get("final_score"),
        "priorities": priorities,
        "edited_at": datetime.now(timezone.utc).isoformat(),
    }

    fid = file_id or uuid.uuid4().hex[:12]
    template = normalize_template(template)
    json_path = OUTPUTS / f"tender_{fid}.json"
    pdf_path = OUTPUTS / f"tender_{fid}_{template}.pdf"
    default_pdf_path = OUTPUTS / f"tender_{fid}.pdf"
    json_path.write_text(_json.dumps(edited, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    build_pdf(edited, pdf_path, template=template)
    build_pdf(edited, default_pdf_path, template=template)
    return {"artifact": edited, "file_id": fid, "template": template, "edited": True}


# ── Request models for synchronous endpoints ─────────────────────────────────────

class SeedReq(BaseModel):
    seed: str | None = None
    template: str | None = None
    form_overrides: dict[str, Any] | None = None


class GuidedDraftReq(BaseModel):
    project_name: str
    scope_text: str
    template: str | None = None
    form_overrides: dict[str, Any] | None = None


class SowReviewReq(BaseModel):
    project_name: str = ""
    scope_text: str


class ValidateReq(BaseModel):
    vendor_id: str = "VND-DEMO-001"
    cr_number: str
    legal_name_ar: str
    legal_name_en: str
    selected_categories: list[str] = []
    document_types: list[str] = []   # doc_type strings; converted to DocumentMeta below


class ImproveTenderReq(BaseModel):
    artifact: dict
    file_id: str | None = None
    template: str | None = None


# ── API: job-launching endpoints ─────────────────────────────────────────────────

@app.post("/api/jobs/draft")
def start_draft(req: SeedReq):
    job = _new_job("draft")
    _run_async(job, _job_full_draft, req.seed or None, None, None, req.template, req.form_overrides)
    return {"job_id": job.id}


@app.post("/api/jobs/draft-guided")
def start_guided_draft(req: GuidedDraftReq):
    scope_text = (
        f"Project Name: {req.project_name.strip()}\n\n"
        f"Scope of Work:\n{req.scope_text.strip()}"
    )
    job = _new_job("guided draft")
    _run_async(job, _job_full_draft, req.project_name.strip() or None, None, scope_text, req.template, req.form_overrides)
    return {"job_id": job.id}


@app.post("/api/jobs/sow-review")
def start_sow_review(req: SowReviewReq):
    job = _new_job("sow review")
    _run_async(job, _job_sow_review, req.project_name, req.scope_text)
    return {"job_id": job.id}


@app.post("/api/jobs/draft-sow")
async def start_draft_sow(file: UploadFile = File(...), template: str | None = Form(None), form_overrides: str | None = Form(None)):
    path = UPLOADS / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path.write_bytes(await file.read())
    overrides = None
    if form_overrides:
        import json as _json
        overrides = _json.loads(form_overrides)
    job = _new_job("draft")
    _run_async(job, _job_full_draft, None, str(path), None, template, overrides)
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


@app.post("/api/jobs/improve-tender")
def start_improve_tender(req: ImproveTenderReq):
    job = _new_job("improve tender")
    _run_async(job, _job_improve_tender, req.artifact, req.file_id, req.template)
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
def download(file_id: str, kind: str, template: str | None = None):
    from pdf_renderer import build_pdf, normalize_template

    ext = "pdf" if kind == "pdf" else "json"
    path = OUTPUTS / f"tender_{file_id}.{ext}"
    if ext == "pdf" and template:
        template = normalize_template(template)
        path = OUTPUTS / f"tender_{file_id}_{template}.pdf"
        if not path.exists():
            json_path = OUTPUTS / f"tender_{file_id}.json"
            if json_path.exists():
                import json as _json
                artifact = _json.loads(json_path.read_text(encoding="utf-8"))
                build_pdf(artifact, path, template=template)
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
