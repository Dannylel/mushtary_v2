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
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
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


@app.middleware("http")
async def utf8_responses(request: Request, call_next):
    """Make browser/API text encoding explicit for Arabic and English demo content."""
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if (content_type.startswith("text/") or "application/json" in content_type) and "charset=" not in content_type.lower():
        response.headers["content-type"] = f"{content_type}; charset=utf-8"
    # This local demo is edited frequently during rehearsals. Never let an old
    # JavaScript/CSS bundle leave the buyer form with a mismatched click handler.
    if request.url.path in {"/", "/index.html", "/app.js", "/styles.css"}:
        response.headers["cache-control"] = "no-store"
    return response

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
if not any(isinstance(handler, _ActivityLogHandler) for handler in _agents_logger.handlers):
    _agents_logger.addHandler(_ActivityLogHandler())


# ── Tiny in-memory job manager ──────────────────────────────────────────────────
# A job is one agent/pipeline run. Status flows PENDING -> RUNNING -> SUCCESS|FAILURE|CANCELLED.
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
_TENDERS: dict[str, dict[str, Any]] = {}
_PENDING_TENDERS: dict[str, dict[str, Any]] = {}
_PROPOSALS: dict[str, dict[str, Any]] = {}
DEMO_BUYER_ID = "BUY-020"  # Taif Events Bureau
DEMO_VENDOR_ID = "VND-001"  # Alpha Tech Solutions


def _save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Persist an AIArtifact in the local audit store before returning it to the UI."""
    from agents.artifact_store import save_artifact

    return save_artifact(artifact)


def _new_job(kind: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind,
              created_at=datetime.now(timezone.utc).isoformat())
    with _LOCK:
        _JOBS[job.id] = job
    return job


def _run_async(job: Job, fn, *args, **kwargs) -> None:
    """Execute fn(*args) in a daemon thread, respecting cancellation at safe boundaries."""
    def _target():
        with _LOCK:
            if _JOBS[job.id].status == "CANCELLED":
                return
            _JOBS[job.id].status = "RUNNING"
        activity.publish("info", f"Job started: {job.kind}", label="job")
        try:
            result = fn(*args, **kwargs)
            with _LOCK:
                if _JOBS[job.id].status == "CANCELLED":
                    activity.publish("info", f"Job cancelled: {job.kind}", label="job")
                    return
                _JOBS[job.id].status = "SUCCESS"
                _JOBS[job.id].result = result
                _JOBS[job.id].finished_at = datetime.now(timezone.utc).isoformat()
            activity.publish("info", f"Job finished: {job.kind}", label="job")
        except Exception as e:  # surface the failure to the UI rather than dying silently
            with _LOCK:
                if _JOBS[job.id].status == "CANCELLED":
                    activity.publish("info", f"Job cancelled: {job.kind}", label="job")
                    return
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


def _buyer_for_tender(buyer_id: str | None, buyer_name: str | None = None) -> dict[str, Any]:
    from agents.reputation import get_buyer, list_buyers

    if buyer_id:
        buyer = get_buyer(buyer_id)
        if buyer:
            return buyer
    buyers = list_buyers()
    if buyer_name:
        match = next((b for b in buyers if b["name"].lower() == buyer_name.lower()), None)
        if match:
            return match
    return buyers[0]


def _shortlist_payload_from_form(form: dict[str, Any]) -> dict[str, Any]:
    certs = form.get("required_certifications") or []
    normalized_certs = [
        item if isinstance(item, str) else item.get("name", "")
        for item in certs
    ]
    return {
        "category": form.get("category") or "Information Technology",
        "subcategory": form.get("subcategory") or "IT Infrastructure & Data Centers",
        "estimated_value_sar": form.get("estimated_value_sar") or 1_500_000,
        "timeline_days": _duration_days(form.get("contract_duration")) or 90,
        "required_certifications": [c for c in normalized_certs if c] or ["ISO 27001"],
        "minimum_years_experience": form.get("minimum_years_experience") or 5,
        "minimum_similar_projects": form.get("minimum_similar_projects") or 3,
        "local_presence_required": bool(form.get("local_presence_required", True)),
        "required_sector_license": form.get("required_sector_license") or None,
    }


def _duration_days(value: Any) -> int | None:
    if value in (None, ""):
        return None
    import re

    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _published_tender_view(tender: dict[str, Any], include_artifact: bool = False) -> dict[str, Any]:
    view = {k: v for k, v in tender.items() if include_artifact or k != "artifact"}
    view["proposal_count"] = sum(1 for p in _PROPOSALS.values() if p["tender_id"] == tender["id"])
    return view


def _save_marketplace_tender(tender_id: str, status: str, buyer_id: str | None, payload: dict[str, Any]) -> None:
    from agents.marketplace_store import save_tender
    save_tender(tender_id, status, buyer_id, payload)


def _load_marketplace_tenders(status: str | None = None, buyer_id: str | None = None) -> list[dict[str, Any]]:
    from agents.marketplace_store import list_tenders
    return list_tenders(status=status, buyer_id=buyer_id)


def _publish_tender_artifact(
    artifact: dict[str, Any],
    file_id: str,
    template: str,
    buyer_id: str | None = None,
) -> dict[str, Any]:
    from agents.reputation import shortlist_vendors

    form = artifact.get("input_snapshot") or {}
    output = artifact.get("output") or {}
    meta = output.get("metadata") or {}
    data_sheet = output.get("tender_data_sheet") or {}
    buyer = _buyer_for_tender(buyer_id, form.get("buyer_name") or data_sheet.get("buyer_entity"))
    payload = _shortlist_payload_from_form(form)
    shortlist = shortlist_vendors(payload)
    tender_id = file_id
    tender = {
        "id": tender_id,
        "file_id": file_id,
        "template": template,
        "status": "published",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "buyer_id": buyer["account_id"],
        "buyer": buyer,
        "title": meta.get("title") or form.get("tender_title") or data_sheet.get("tender_title") or "Untitled Tender",
        "reference": meta.get("tender_id") or form.get("tender_id") or data_sheet.get("tender_reference") or tender_id,
        "category": form.get("category") or payload["category"],
        "subcategory": form.get("subcategory") or payload["subcategory"],
        "location": form.get("location") or data_sheet.get("location") or buyer.get("city"),
        "submission_deadline": form.get("submission_deadline") or data_sheet.get("submission_deadline"),
        "estimated_value_sar": form.get("estimated_value_sar"),
        "budget_range": form.get("budget_range"),
        "scope_of_work": form.get("scope_of_work") or "",
        "required_certifications": payload["required_certifications"],
        "minimum_years_experience": payload["minimum_years_experience"],
        "minimum_similar_projects": payload["minimum_similar_projects"],
        "evaluation_model": form.get("evaluation_model") or data_sheet.get("evaluation_model"),
        "shortlist": shortlist,
        "human_in_the_loop": "AI recommends only. Buyer controls final approval and award.",
        "artifact": artifact,
    }
    with _LOCK:
        _TENDERS[tender_id] = tender
    _save_marketplace_tender(tender_id, "published", buyer["account_id"], tender)
    return _published_tender_view(tender)


def _proposal_comparison_for_tender(tender: dict[str, Any]) -> dict[str, Any]:
    from agents.reputation import get_vendor
    from agents.vendor_committee import run_vendor_committee
    from agents.vendor_committee.graph import PROMPT_NAME, PROMPT_VERSION
    from agents.base import AIArtifact
    from agents.llm_config import get_model
    from agents.artifact_store import get_latest_artifact

    proposals = [p for p in _PROPOSALS.values() if p["tender_id"] == tender["id"]]
    scored = {}
    for bucket in (tender.get("shortlist", {}).get("buckets") or {}).values():
        for vendor in bucket:
            scored[vendor["vendor_id"]] = vendor
    ranked = []
    for proposal in proposals:
        vendor = get_vendor(proposal["vendor_id"]) or {}
        score = dict(scored.get(proposal["vendor_id"]) or {})
        if not score:
            score = {
                "vendor_id": proposal["vendor_id"],
                "vendor_name": vendor.get("name") or proposal["vendor_id"],
                "vri": vendor.get("vri", {}).get("category_specific"),
                "vri_level": vendor.get("vri", {}).get("level", "Under Review"),
                "ai_recommendation_score": 58,
                "fit_score": 58,
                "risk_score": 62,
                "probability_of_success": 61,
                "compliance_status": "Buyer Review Required",
                "risk_level": "Medium",
                "committee": {"final_score": 58, "agents": []},
                "why_selected": ["Submitted proposal requires manual buyer review because it was not pre-shortlisted."],
            }
        price = proposal.get("price_sar")
        estimate = tender.get("estimated_value_sar")
        if price and estimate:
            ratio = price / estimate
            if ratio < 0.7:
                score["risk_level"] = "High"
                score["risk_score"] = min(score.get("risk_score") or 60, 55)
                score["why_selected"] = (score.get("why_selected") or []) + ["Commercial proposal is unusually low compared with the tender estimate."]
            elif ratio <= 1.05:
                score["ai_recommendation_score"] = min(100, round((score.get("ai_recommendation_score") or 0) + 2, 1))
        tender_context = {
            "title": tender.get("title"),
            "category": tender.get("category"),
            "subcategory": tender.get("subcategory"),
            "estimated_value_sar": estimate,
            "budget_range": tender.get("budget_range"),
            "submission_deadline": tender.get("submission_deadline"),
            "minimum_years_experience": tender.get("minimum_years_experience"),
            "minimum_similar_projects": tender.get("minimum_similar_projects"),
            "required_certifications": tender.get("required_certifications") or [],
            "scope_of_work": (tender.get("artifact") or {}).get("output", {}).get("scope_of_work", {}),
        }
        baseline_committee = dict(score.get("committee") or {"final_score": score.get("ai_recommendation_score", 58), "agents": []})
        stored_artifact = get_latest_artifact(
            tender_id=tender["id"], vendor_id=proposal["vendor_id"], proposal_id=proposal["id"],
            artifact_type="VENDOR_TENDER_COMMITTEE",
        )
        committee = stored_artifact["output"] if stored_artifact else run_vendor_committee(
            tender=tender_context, vendor=vendor, proposal=proposal, baseline=baseline_committee,
        )
        score["committee"] = committee
        score["committee_source"] = "deterministic_fallback" if committee.get("fallback_used") else "llm"
        score["deterministic_recommendation_score"] = score.get("ai_recommendation_score")
        score["ai_recommendation_score"] = committee["final_score"]
        score["why_selected"] = (score.get("why_selected") or []) + [committee["final_recommendation"]]
        if not stored_artifact:
            committee_artifact = AIArtifact(
                id=uuid.uuid4().hex,
                trace_id=f"trace_{uuid.uuid4().hex}",
                type="VENDOR_TENDER_COMMITTEE",
                vendor_id=proposal["vendor_id"],
                tender_id=tender["id"],
                actor_id=tender.get("buyer_id"),
                prompt_name=PROMPT_NAME,
                prompt_version=PROMPT_VERSION,
                input_snapshot={
                    "tender_requirements": tender_context,
                    "vendor_profile": vendor,
                    "submitted_proposal": proposal,
                    "deterministic_baseline": baseline_committee,
                },
                output=committee,
                model_used=get_model(),
            )
            committee_artifact_data = committee_artifact.model_dump(mode="json")
            committee_artifact_data["proposal_id"] = proposal["id"]
            stored_artifact = _save_artifact(committee_artifact_data)
        score["committee_artifact_id"] = stored_artifact["id"]
        score["committee_approval_status"] = stored_artifact["status"]
        score["proposal"] = proposal
        score["vendor"] = vendor
        ranked.append(score)
    ranked.sort(key=lambda item: item.get("ai_recommendation_score") or 0, reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return {
        "tender": _published_tender_view(tender),
        "submitted_vendor_count": len(ranked),
        "recommended_vendor": ranked[0] if ranked else None,
        "ranking": ranked,
        "human_in_the_loop": "AI recommends only. Buyer controls final approval and award.",
    }


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


def _job_full_draft(
    seed: str | None,
    sow_path: str | None,
    sow_text: str | None = None,
    template: str | None = None,
    form_overrides: dict | None = None,
    buyer_id: str | None = None,
) -> dict:
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

    artifact["actor_id"] = buyer_id or artifact.get("actor_id")
    consistency = state.get("consistency_report") if isinstance(state, dict) else None
    if consistency:
        artifact.setdefault("output", {})["consistency_report"] = consistency
    _save_artifact(artifact)

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
    # Drafts remain private until the Buyer-Admin explicitly approves publication.
    with _LOCK:
        pending = {
            "artifact": artifact, "file_id": fid, "template": template, "buyer_id": buyer_id,
        }
        _PENDING_TENDERS[artifact["id"]] = pending
    _save_marketplace_tender(artifact["id"], "draft", buyer_id, pending)
    return {
        "artifact": artifact, "file_id": fid, "template": template,
        "publication_status": "PENDING_BUYER_APPROVAL",
        "human_in_the_loop": "This draft is private. Buyer-Admin approval is required before vendors can view it.",
    }


def _job_form(seed: str | None) -> dict:
    from agents.graph.modes import run_mode
    form = run_mode("form", seed=seed)
    return {"form": form.model_dump(mode="json")}


def _job_populate_optional_sections(project_name: str, scope_text: str, form_overrides: dict | None = None) -> dict:
    """Derive editable optional fields without generating or publishing a tender."""
    from agents.sow_extractor import SoWExtractorAgent

    source = f"Project Name: {project_name.strip()}\n\nScope of Work:\n{scope_text.strip()}"
    form = SoWExtractorAgent().extract_from_text(source)
    return {"form": _apply_form_overrides(form, form_overrides).model_dump(mode="json")}


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
    stored = _save_artifact(artifact.model_dump(mode="json"))
    return {"artifact": stored}


def _job_evaluate() -> dict:
    """Score every vendor in the bundled sample (in isolation), then rank. Reuses the
    builder helpers from the demo script so the input shapes stay in one place."""
    import json as _json
    from agents.evaluation.graph import run_evaluation_graph

    samples = ROOT / "agents" / "samples"
    tender = _json.loads((samples / "it_infrastructure_tender.json").read_text(encoding="utf-8"))
    subs = _json.loads((samples / "vendor_submissions.json").read_text(encoding="utf-8"))

    state = run_evaluation_graph(tender, subs["submissions"])
    for artifact in state["score_artifacts"]:
        _save_artifact(artifact)
    _save_artifact(state["ranking_artifact"])
    return {
        "tender_title": tender.get("title", tender["tender_id"]),
        "scores": state["scores"], "ranking": state["ranking"],
        "vendor_names": state["vendor_names"],
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


def _job_improve_tender(artifact: dict, file_id: str | None = None, template: str | None = None, review_prompt: str | None = None) -> dict:
    """Patch the existing tender artifact using AI Tender Committee feedback."""
    from pdf_renderer import build_pdf, normalize_template

    if not isinstance(artifact, dict) or not isinstance(artifact.get("output"), dict):
        raise RuntimeError("Improve tender requires an artifact with an output object")

    import json as _json

    edited = _json.loads(_json.dumps(artifact, ensure_ascii=False, default=str))
    output = edited["output"]
    if review_prompt:
        try:
            from agents.llm_config import chat_json_text
            from agents.tender_drafting.schemas import TenderDraft
            import re
            current_draft = {key: output[key] for key in TenderDraft.model_fields if key in output}
            raw = chat_json_text(
                [{"role": "system", "content": "You are the Mushtarry Tender Revision Agent. Revise the supplied existing tender using the committee instruction. Preserve buyer facts. Do not invent dates, amounts, percentages, or legal requirements. Return only JSON matching the existing tender schema."}, {"role": "user", "content": _json.dumps({"review_instruction": review_prompt, "existing_tender": current_draft}, ensure_ascii=False)}],
                temperature=0.1, max_tokens=6000,
            )
            match = re.search(r"\{.*\}", raw or "", re.S)
            if match:
                output.update(TenderDraft.model_validate(_json.loads(match.group(0))).model_dump(mode="json"))
                output["ai_revision"] = {"mode": "agent", "instruction": review_prompt}
        except Exception:
            output["ai_revision"] = {"mode": "rule_based_fallback", "instruction": review_prompt}
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
    buyer_id: str | None = None


class GuidedDraftReq(BaseModel):
    project_name: str
    scope_text: str
    template: str | None = None
    form_overrides: dict[str, Any] | None = None
    buyer_id: str | None = None


class SowReviewReq(BaseModel):
    project_name: str = ""
    scope_text: str


class PopulateOptionalReq(BaseModel):
    project_name: str = ""
    scope_text: str
    form_overrides: dict[str, Any] | None = None


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
    review_prompt: str | None = None


class VendorShortlistReq(BaseModel):
    category: str | None = None
    subcategory: str | None = None
    estimated_value_sar: float | None = None
    timeline_days: int | None = None
    required_certifications: list[str] = []
    minimum_years_experience: int | None = None
    minimum_similar_projects: int | None = None
    local_presence_required: bool = True
    required_sector_license: str | None = None


class RandomSessionReq(BaseModel):
    role: str


class AccountSessionReq(BaseModel):
    role: str
    account_id: str


class ProposalReq(BaseModel):
    vendor_id: str
    price_sar: float | None = None
    timeline_days: int | None = None
    technical_summary: str = ""
    commercial_summary: str = ""


class ArtifactApprovalReq(BaseModel):
    buyer_id: str
    note: str | None = None


# ── API: job-launching endpoints ─────────────────────────────────────────────────

@app.post("/api/jobs/draft")
def start_draft(req: SeedReq):
    job = _new_job("draft")
    _run_async(job, _job_full_draft, req.seed or None, None, None, req.template, req.form_overrides, req.buyer_id)
    return {"job_id": job.id}


@app.post("/api/jobs/draft-guided")
def start_guided_draft(req: GuidedDraftReq):
    scope_text = (
        f"Project Name: {req.project_name.strip()}\n\n"
        f"Scope of Work:\n{req.scope_text.strip()}"
    )
    job = _new_job("guided draft")
    _run_async(job, _job_full_draft, req.project_name.strip() or None, None, scope_text, req.template, req.form_overrides, req.buyer_id)
    return {"job_id": job.id}


@app.post("/api/jobs/sow-review")
def start_sow_review(req: SowReviewReq):
    job = _new_job("sow review")
    _run_async(job, _job_sow_review, req.project_name, req.scope_text)
    return {"job_id": job.id}


@app.post("/api/jobs/draft-sow")
async def start_draft_sow(
    file: UploadFile = File(...),
    template: str | None = Form(None),
    form_overrides: str | None = Form(None),
    buyer_id: str | None = Form(None),
):
    path = UPLOADS / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path.write_bytes(await file.read())
    overrides = None
    if form_overrides:
        import json as _json
        overrides = _json.loads(form_overrides)
    job = _new_job("draft")
    _run_async(job, _job_full_draft, None, str(path), None, template, overrides, buyer_id)
    return {"job_id": job.id}


@app.post("/api/jobs/populate-optional-sections")
def start_populate_optional_sections(req: PopulateOptionalReq):
    if not req.scope_text.strip():
        raise HTTPException(422, "Scope of Work is required to populate optional sections")
    job = _new_job("populate optional sections")
    _run_async(job, _job_populate_optional_sections, req.project_name, req.scope_text, req.form_overrides)
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
    _run_async(job, _job_improve_tender, req.artifact, req.file_id, req.template, req.review_prompt)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.model_dump()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancel a queued/running demo job and discard any late result safely."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job.status in {"SUCCESS", "FAILURE", "CANCELLED"}:
            return job.model_dump()
        job.status = "CANCELLED"
        job.error = "Stopped by user"
        job.finished_at = datetime.now(timezone.utc).isoformat()
    activity.publish("info", f"Stop requested for job: {job.kind}", label="job")
    return job.model_dump()


@app.post("/api/jobs/cancel-all")
def cancel_all_jobs():
    """Stop every queued/running demo job from the UI's global stop control."""
    cancelled = []
    with _LOCK:
        for job in _JOBS.values():
            if job.status not in {"PENDING", "RUNNING"}:
                continue
            job.status = "CANCELLED"
            job.error = "Stopped by user"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            cancelled.append({"id": job.id, "kind": job.kind})
    if cancelled:
        activity.publish("info", f"Stopped {len(cancelled)} running job(s)", label="job")
    return {"cancelled": cancelled}


@app.get("/api/artifacts")
def artifacts(tender_id: str | None = None, vendor_id: str | None = None, limit: int = 100):
    """Buyer audit view for persisted model outputs and decision history."""
    from agents.artifact_store import list_artifacts

    return {"artifacts": list_artifacts(tender_id=tender_id, vendor_id=vendor_id, limit=min(max(limit, 1), 500))}


@app.get("/api/artifacts/{artifact_id}")
def artifact_detail(artifact_id: str):
    from agents.artifact_store import get_artifact

    artifact = get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(404, "artifact not found")
    return {"artifact": artifact}


@app.post("/api/artifacts/{artifact_id}/approve")
def approve_artifact(artifact_id: str, req: ArtifactApprovalReq):
    """Record a buyer's approval without allowing AI to approve itself."""
    from agents.artifact_store import approve_artifact as approve_stored_artifact

    artifact = approve_stored_artifact(artifact_id, buyer_id=req.buyer_id, note=req.note)
    if not artifact:
        raise HTTPException(404, "artifact not found")
    published_tender = None
    with _LOCK:
        pending = _PENDING_TENDERS.pop(artifact_id, None)
    if not pending:
        from agents.marketplace_store import get_tender
        restored = get_tender(artifact_id)
        if restored and restored.get("status") == "draft":
            pending = restored
    if pending:
        if pending.get("buyer_id") and pending["buyer_id"] != req.buyer_id:
            with _LOCK:
                _PENDING_TENDERS[artifact_id] = pending
            raise HTTPException(403, "Only the draft's Buyer-Admin can publish it")
        consistency = (pending.get("artifact", {}).get("output", {}) or {}).get("consistency_report", {})
        if consistency.get("status") == "BLOCKED":
            with _LOCK:
                _PENDING_TENDERS[artifact_id] = pending
            raise HTTPException(409, "Publication is blocked until high-severity consistency findings are resolved")
        published_tender = _publish_tender_artifact(
            pending["artifact"], pending["file_id"], pending["template"], req.buyer_id,
        )
        # The durable published record (keyed by file id) replaces the private
        # draft entry, preventing duplicate/conflicting tender states in history.
        from agents.marketplace_store import delete_tender
        delete_tender(artifact_id)
    return {
        "artifact": artifact,
        "published_tender": published_tender,
        "human_in_the_loop": "Buyer approval was recorded. Approved drafts are now visible to vendors; contract award remains a separate buyer-controlled action.",
    }


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


@app.post("/api/session/random")
def random_session(req: RandomSessionReq):
    from agents.reputation import list_buyers, list_vendors

    role = req.role.strip().lower()
    if role not in {"buyer", "vendor"}:
        raise HTTPException(400, "role must be buyer or vendor")
    account = get_buyer(DEMO_BUYER_ID) if role == "buyer" else get_vendor(DEMO_VENDOR_ID)
    return {"session": _demo_session(role, account, "fixed_demo_account")}


def _demo_session(role: str, account: dict[str, Any], mode: str) -> dict[str, Any]:
    session = {
        "role": role,
        "account": account,
        "signed_in_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }
    if role == "buyer":
        session["current_tender_id"] = f"TND-{account['account_id'].replace('BUY-', 'BUY')}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    return session


@app.post("/api/session/account")
def account_session(req: AccountSessionReq):
    """Choose a fixed demo account for repeatable buyer/vendor testing."""
    from agents.reputation import get_buyer, get_vendor

    role = req.role.strip().lower()
    if role not in {"buyer", "vendor"}:
        raise HTTPException(400, "role must be buyer or vendor")
    fixed_account_id = DEMO_BUYER_ID if role == "buyer" else DEMO_VENDOR_ID
    if req.account_id != fixed_account_id:
        raise HTTPException(403, f"This demo is pinned to {fixed_account_id} for repeatable workflows")
    account = get_buyer(fixed_account_id) if role == "buyer" else get_vendor(fixed_account_id)
    if not account:
        raise HTTPException(404, f"{role} account not found")
    return {"session": _demo_session(role, account, "selected_demo_account")}


@app.post("/api/demo/reset")
def reset_demo_state():
    """Clear volatile demo jobs, tenders, and proposals without deleting the audit trail."""
    with _LOCK:
        counts = {"jobs": len(_JOBS), "tenders": len(_TENDERS), "pending_tenders": len(_PENDING_TENDERS), "proposals": len(_PROPOSALS)}
        _JOBS.clear()
        _TENDERS.clear()
        _PENDING_TENDERS.clear()
        _PROPOSALS.clear()
    return {
        "cleared": counts,
        "audit_trail": "preserved",
        "message": "Demo state reset. Saved drafts, published tenders, AI artifacts, and approval records were retained.",
    }


@app.get("/api/tenders/feed")
def tender_feed(vendor_id: str | None = None):
    persisted = _load_marketplace_tenders(status="published")
    with _LOCK:
        for tender in persisted:
            _TENDERS[tender["id"]] = tender
    tenders = [_published_tender_view(t) for t in persisted]
    tenders.sort(key=lambda item: item["created_at"], reverse=True)
    if vendor_id:
        for tender in tenders:
            ranked = tender.get("shortlist", {}).get("top_three") or []
            tender["recommended_to_current_vendor"] = any(v.get("vendor_id") == vendor_id for v in ranked)
            tender["current_vendor_rank"] = next((v.get("rank") for v in ranked if v.get("vendor_id") == vendor_id), None)
            tender["current_vendor_proposal"] = next(
                (p for p in _PROPOSALS.values() if p["tender_id"] == tender["id"] and p["vendor_id"] == vendor_id),
                None,
            )
            # Buyer-only decision support: vendors may learn whether they are invited / a
            # suggested match, but never see their own committee dossier or competing
            # vendor profiles, scores, rankings, or recommendations.
            tender.pop("shortlist", None)
    return {"tenders": tenders}


@app.get("/api/tenders/saved")
def saved_tenders(buyer_id: str | None = None):
    """Buyer-visible drafted tender register, including publication and vendor activity."""
    records = _load_marketplace_tenders(buyer_id=buyer_id)
    items = []
    for record in records:
        artifact = record.get("artifact") or {}
        output = artifact.get("output") or {}
        form = artifact.get("input_snapshot") or {}
        tender_id = record.get("id")
        persisted_activity = record.get("proposal_activity") or []
        live_activity = [proposal for proposal in _PROPOSALS.values() if proposal.get("tender_id") == tender_id]
        activity_by_id = {item.get("id"): item for item in persisted_activity if item.get("id")}
        activity_by_id.update({item.get("id"): item for item in live_activity if item.get("id")})
        submissions = sorted(activity_by_id.values(), key=lambda item: item.get("submitted_at") or "", reverse=True)
        shortlist = record.get("shortlist") or {}
        shortlist_count = (shortlist.get("counts") or {}).get("potential_eligible_vendors_found", 0)
        status = record.get("status")
        items.append({
            "id": tender_id, "status": status, "created_at": record.get("created_at"),
            "title": record.get("title") or output.get("metadata", {}).get("title") or form.get("tender_title") or "Tender Draft",
            "reference": record.get("reference") or output.get("metadata", {}).get("tender_id") or form.get("tender_id"),
            "file_id": record.get("file_id"),
            "artifact_id": artifact.get("id") or tender_id,
            "publication_status": "Published to vendors" if status == "published" else "Private draft - pending Buyer-Admin approval",
            "category": record.get("category") or form.get("category"),
            "location": record.get("location") or form.get("location"),
            "submission_deadline": record.get("submission_deadline") or form.get("submission_deadline"),
            "estimated_value_sar": record.get("estimated_value_sar") or form.get("estimated_value_sar"),
            "deliverable_count": len((output.get("deliverables") or {}).get("deliverables") or form.get("deliverables") or []),
            "milestone_count": len((output.get("timeline") or {}).get("milestones") or form.get("timeline") or []),
            "shortlisted_vendor_count": shortlist_count,
            "submission_count": len(submissions),
            "submitted_vendors": [{"vendor_id": item.get("vendor_id"), "vendor_name": item.get("vendor_name"), "submitted_at": item.get("submitted_at"), "status": item.get("status")} for item in submissions],
            "vendor_takeup_status": (
                f"{len(submissions)} vendor proposal(s) received" if submissions
                else ("Awaiting vendor proposals" if status == "published" else "Not visible to vendors")
            ),
            "award_status": "Buyer decision pending" if submissions else "No vendor selected",
        })
    return {"tenders": sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)}


@app.get("/api/tenders/{tender_id}")
def tender_detail(tender_id: str):
    tender = _TENDERS.get(tender_id)
    if not tender:
        from agents.marketplace_store import get_tender
        tender = get_tender(tender_id)
    if not tender:
        raise HTTPException(404, "tender not found")
    return {"tender": _published_tender_view(tender, include_artifact=True)}


@app.post("/api/tenders/{tender_id}/validate-vendors")
def validate_vendors_for_saved_tender(tender_id: str, buyer_id: str | None = None):
    """Validate vendors only against a tender that the buyer has already drafted."""
    from agents.marketplace_store import get_tender
    from agents.reputation import shortlist_vendors

    record = get_tender(tender_id)
    if not record:
        raise HTTPException(404, "Drafted tender not found")
    if buyer_id and record.get("buyer_id") and record["buyer_id"] != buyer_id:
        raise HTTPException(403, "Only the tender's Buyer-Admin can validate vendors against it")
    artifact = record.get("artifact") or {}
    form = artifact.get("input_snapshot") or {}
    if not form:
        raise HTTPException(409, "This saved tender has no requirements available for vendor validation")
    shortlist = shortlist_vendors(_shortlist_payload_from_form(form))
    shortlist["validated_tender"] = {
        "id": tender_id,
        "title": record.get("title") or form.get("tender_title") or "Tender Draft",
        "reference": record.get("reference") or form.get("tender_id"),
        "status": record.get("status"),
    }
    return shortlist


@app.post("/api/tenders/{tender_id}/proposals")
def submit_proposal(tender_id: str, req: ProposalReq):
    from agents.reputation import get_vendor

    tender = _TENDERS.get(tender_id)
    if not tender:
        raise HTTPException(404, "tender not found")
    vendor = get_vendor(req.vendor_id)
    if not vendor:
        raise HTTPException(404, "vendor not found")
    proposal_id = f"PRP-{uuid.uuid4().hex[:10].upper()}"
    proposal = {
        "id": proposal_id,
        "tender_id": tender_id,
        "vendor_id": req.vendor_id,
        "vendor_name": vendor["name"],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "submitted_demo",
        "price_sar": req.price_sar,
        "timeline_days": req.timeline_days,
        "technical_summary": req.technical_summary.strip(),
        "commercial_summary": req.commercial_summary.strip(),
        "vri": vendor["vri"]["category_specific"],
        "vri_level": vendor["vri"]["level"],
        "badge": vendor["badge"],
    }
    with _LOCK:
        _PROPOSALS[proposal_id] = proposal
        tender.setdefault("proposal_activity", [])
        tender["proposal_activity"] = [item for item in tender["proposal_activity"] if item.get("vendor_id") != proposal["vendor_id"]]
        tender["proposal_activity"].append(proposal)
    _save_marketplace_tender(tender_id, "published", tender.get("buyer_id"), tender)
    return {
        "proposal": proposal,
        "comparison": _proposal_comparison_for_tender(tender),
        "human_in_the_loop": "AI recommends only. Buyer controls final approval and award.",
    }


@app.get("/api/proposals/compare")
def compare_submitted_proposals(buyer_id: str | None = None):
    tenders = list(_TENDERS.values())
    if buyer_id:
        tenders = [tender for tender in tenders if tender.get("buyer_id") == buyer_id]
    comparisons = [
        _proposal_comparison_for_tender(tender)
        for tender in sorted(tenders, key=lambda item: item["created_at"], reverse=True)
    ]
    return {
        "comparisons": comparisons,
        "human_in_the_loop": "AI recommends only. Buyer controls final approval and award.",
    }


@app.get("/api/reputation")
def reputation_snapshot():
    from agents.reputation import build_marketplace_snapshot

    return build_marketplace_snapshot()


@app.get("/api/accounts/vendors")
def vendors():
    from agents.reputation import list_vendors

    return {"vendors": list_vendors()}


@app.get("/api/accounts/vendors/{vendor_id}")
def vendor_profile(vendor_id: str):
    from agents.reputation import get_vendor

    vendor = get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(404, "vendor not found")
    return {"vendor": vendor}


@app.get("/api/accounts/buyers")
def buyers():
    from agents.reputation import list_buyers

    return {"buyers": list_buyers()}


@app.get("/api/accounts/buyers/{buyer_id}")
def buyer_profile(buyer_id: str):
    from agents.reputation import get_buyer

    buyer = get_buyer(buyer_id)
    if not buyer:
        raise HTTPException(404, "buyer not found")
    return {"buyer": buyer}


@app.post("/api/intelligence/shortlist")
def vendor_shortlist(req: VendorShortlistReq):
    from agents.reputation import shortlist_vendors

    return shortlist_vendors(req.model_dump(mode="json"))


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
