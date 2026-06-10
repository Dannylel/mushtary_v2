# Mushtary AI Agents — Architecture & Flow

## The one rule connecting all three agents

```
AI generates → Human reviews → Human approves → Action taken
```

Nothing is ever published, activated, or awarded by the AI directly.
The approval step is always a human action gated in the backend.

---

## Agent 1 — Vendor Validation (agentic tool-use loop)

```
Vendor submits registration form
        │
        ▼
FastAPI receives POST /vendors/register
        │
        ▼
Celery task queued  ◄── returns job_id to frontend immediately
        │
        ▼
VendorValidationAgent.run()
        │
        ├─► LLM (local Ollama) receives: CR number, names, categories, doc list
        │         │
        │         ▼ (tool call)
        │   lookup_cr_amaly()             ← checks Saudi registry (stub → WATHQ post-MVP)
        │         │
        │         ▼ (tool call)
        │   check_duplicate_vendor()      ← queries local DB (stub now)
        │         │
        │         ▼ (tool call)
        │   validate_category_alignment() ← maps CR activities → platform categories
        │         │
        │         ▼ (tool call)
        │   check_document_completeness() ← checks required docs uploaded
        │         │
        │         ▼
        │   LLM reasons over all 4 tool results
        │         │
        │         ▼
        │   Returns JSON: outcome + flags + vendor_message + admin_note
        │
        ▼
guardrails.py validates JSON schema
        │
        ▼
AIArtifact saved to ai_artifacts table (status=DRAFT)
        │
        ├── AUTO_VALIDATED     → vendor status set to active
        ├── NEEDS_CORRECTION   → vendor notified with vendor_message
        └── FLAGGED_FOR_REVIEW → Platform Admin queue notified
```

**Key files**
| File | Purpose |
|---|---|
| [vendor_validation/agent.py](../agents/vendor_validation/agent.py) | Agentic tool-use loop |
| [vendor_validation/stubs.py](../agents/vendor_validation/stubs.py) | 4 tool stubs (replace with real integrations) |
| [vendor_validation/schemas.py](../agents/vendor_validation/schemas.py) | Input / output Pydantic models |
| [vendor_validation/prompts.py](../agents/vendor_validation/prompts.py) | System prompt + decision rules |

---

## Agent 2 — Tender Drafting (LangGraph: form source → 4 parallel sections → assemble)

```
Buyer form arrives by ONE of three roads (form_source node):
  uploaded SoW/RFP PDF → SoWExtractorAgent    (intra-document RAG for long docs)
  manual form           → passed through
  seed / nothing        → FormGeneratorAgent  (autonomous AI-filled form)
        │
        ▼
LangGraph fan-out: 4 section agents run in PARALLEL (local Ollama)
  context   │ scope*   │ execution  │ legal_eval*
  (*scope and legal_eval also retrieve reference excerpts from the
   tender knowledge base: clause library + Saudi procurement law)
        │
        ▼  fan-in
assemble → TenderDraft + AIArtifact  (status=DRAFT, buyer_approved=False)
        │
        ▼
Buyer reviews draft → edits if needed → Approve
        │
        ▼
Tender publish unlocked  ◄── BLOCKED until buyer approves
```

**Key files**
| File | Purpose |
|---|---|
| [graph/pipeline.py](../agents/graph/pipeline.py) | LangGraph tender-creation graph (primary path) |
| [graph/modes.py](../agents/graph/modes.py) | Run any single node alone, or the full graph |
| [tender_drafting/sections/](../agents/tender_drafting/sections/) | 4 section agents (context, scope, execution, legal_eval) |
| [tender_drafting/schemas.py](../agents/tender_drafting/schemas.py) | Section models + assemble_tender_draft |
| [rag/](../agents/rag/) | Local RAG: vector store, tender knowledge base, SoW retrieval |
| [sow_extractor/agent.py](../agents/sow_extractor/agent.py) | PDF/SoW → TenderBuyerForm |
| [form_generator/agent.py](../agents/form_generator/agent.py) | Seed → autonomous TenderBuyerForm |

---

## Agent 3 — Evaluation & Ranking (two-step parallel)

```
Tender submission deadline passes
        │
        ▼
FastAPI POST /tenders/{id}/evaluate
        │
        ▼
One Celery task spawned PER vendor  ◄── all run in parallel
        │
        ├── score_vendor(vendor_A) ──► LLM scores A in isolation → VendorScore A
        ├── score_vendor(vendor_B) ──► LLM scores B in isolation → VendorScore B
        └── score_vendor(vendor_C) ──► LLM scores C in isolation → VendorScore C
                │
                ▼  (all tasks complete)
        rank_vendors([Score_A, Score_B, Score_C])
                │
                ▼
        LLM ranks + writes recommendation paragraph
                │
                ▼
        guardrails.py validates
                │
                ▼
        AIArtifact saved  (buyer_approved=False)
                │
                ▼
        Buyer reviews ranked list + reasoning in UI → clicks Approve
                │
                ▼
        Award recorded in DB  ◄── BLOCKED until buyer approves
```

**Why two steps?**
Scoring runs one vendor at a time in isolation — a vendor must never see another vendor's
submission. Ranking is a separate aggregation step that only sees scores, not raw submissions.

**Key files**
| File | Purpose |
|---|---|
| [evaluation/agent.py](../agents/evaluation/agent.py) | score_vendor() + rank_vendors() |
| [evaluation/schemas.py](../agents/evaluation/schemas.py) | VendorScoringInput, VendorScore, RankedResult |
| [evaluation/prompts.py](../agents/evaluation/prompts.py) | Scoring + ranking system prompts |

---

## Shared infrastructure

```
agents/
├── llm_config.py      ← SINGLE source of truth: local Ollama endpoint + model (env-overridable)
├── base.py            ← BaseAgent: trace_id, input sanitization, artifact builder
├── guardrails.py      ← Schema validation + safe fallback (workflow never crashes)
├── prompt_registry.py ← Versioned prompt catalog (all prompts registered here)
├── prompts/           ← One .md file per system prompt (loaded via load_prompt)
├── graph/             ← LangGraph pipeline + mode dispatch (primary entry path)
├── rag/               ← Local RAG: embeddings, vector store, tender KB, SoW retrieval
└── tasks.py           ← Celery task wrappers (scaffolding for future FastAPI layer)
```

### AIArtifact — every AI output stored with full traceability

```
ai_artifacts table
├── trace_id           ← unique per run, used for debugging
├── type               ← VENDOR_VALIDATION | TENDER_DRAFT | EVALUATION
├── status             ← DRAFT | APPROVED | REJECTED
├── prompt_name        ← links to prompt_registry.py
├── prompt_version     ← bump when prompt changes
├── input_snapshot     ← sanitized copy of inputs used
├── output             ← structured JSON output
├── input_tokens       ← cost tracking
└── output_tokens      ← cost tracking
```

### Celery job pattern — all agents are async

```
FastAPI endpoint
    │
    ├── .delay(payload)  →  Celery queues task  →  returns job_id
    │
    └── frontend polls GET /jobs/{job_id}/status
              │
              └── PENDING | STARTED | SUCCESS | FAILURE
```

---

## Stubs that need replacing

See [README.md](README.md) for the full list of blockers and open questions.

| Stub | File | Replaces with |
|---|---|---|
| `lookup_cr_amaly()` | vendor_validation/stubs.py | Amaly scrape or WATHQ API |
| `check_duplicate_vendor()` | vendor_validation/stubs.py | DB query on vendors table |
| `validate_category_alignment()` | vendor_validation/stubs.py | Full category taxonomy mapping |
| `check_document_completeness()` | vendor_validation/stubs.py | Confirmed required-docs rules |
| Saudi tender examples | tender_drafting/prompts.py | Real examples from client |

---

*Maintained by: AI Engineering team*
*Last updated: 2026-06-10 (local Ollama + LangGraph + RAG architecture)*
