# Mushtarry AI Integration Guide for Backend and Web Teams

> **Audience:** backend, web/mobile, platform, QA, security, product, and AI teams integrating this AI project into an existing Mushtarry website.
>
> **Goal:** replace the local demo shell with production-owned identity, data, storage, workflow, and user interfaces while keeping the AI service as an evidence-based advisory component.

## 1. Integration principles

1. The website/backend owns users, organizations, permissions, persistence, documents, tender state, contracts, payments, review queues, and final actions.
2. The AI service owns structured extraction, analysis, recommendations, confidence, evidence, and safe fallback-to-review.
3. Deterministic policy/rule code—not an LLM—must decide access, deadlines, eligibility, disqualification, publication, award, and state transitions.
4. Every high-impact AI response must carry an immutable request/case ID, model/prompt version, confidence, evidence, policy version, and recommended human action.
5. Do not migrate the demo’s synthetic vendor/buyer data into production. It is fixture data only.
6. AI outputs are advisory. The platform must never interpret an AI score as an award, legal verification, or final rejection.

## 2. Target integration architecture

```text
Existing website / mobile client
    │
    ├── Existing auth/session and tenant context
    │
Existing backend (system of record)
    ├── users, organizations, roles, tenders, proposals, contracts
    ├── documents/object storage and file scanning
    ├── eligibility rules, workflow/state machine, review queue
    ├── notifications, audit ledger, reporting
    │
    └── calls AI service through internal authenticated API/event queue
            │
            ├── drafting / SoW extraction / tender health
            ├── document intelligence / vendor validation findings
            ├── shortlist / proposal evidence / committee recommendation
            └── RAG and observability
```

The current FastAPI app is useful as a reference implementation and demo adapter. Production integration should either:

- expose its agent capabilities as an internal AI service behind the existing backend; or
- move the agents into a backend-owned worker/service boundary.

Do **not** have the public browser call model providers or internal AI agents directly.

## 3. Ownership matrix

| Capability | Backend/system of record | Web/mobile | AI service |
|---|---|---|---|
| Authentication/tenant/RBAC | Owns | Uses session/claims | Receives trusted context only |
| Organization/user roles | Owns | Manage/display | May analyse supplied context |
| Document upload/storage | Owns | Upload/progress/status | Reads authorised extracted text/metadata |
| OCR baseline | Owns or shared service | Display source pages | Classifies/extracts/compares fields |
| Eligibility policy | Owns/version-controls | Shows result | Suggests applicability/ambiguity |
| Tender lifecycle | Owns | Draft/review/publish UI | Drafts/reviews/recommends |
| Proposal lifecycle | Owns | Draft/submit/lock UI | Extracts/maps/evaluates evidence |
| VRI/BRI source events | Owns | Displays supported result | Produces approved analytics signals |
| Award/publish/reject | Owns | Authorized action UI | Never executes |
| Audit/retention | Owns | Displays authorised history | Emits trace metadata/artifacts |

## 4. Security and request context

Every request from the backend to AI needs a trusted server-to-server identity and this envelope:

```json
{
  "request_id": "req_...",
  "trace_id": "trace_...",
  "tenant_id": "tenant_...",
  "actor": {
    "user_id": "usr_...",
    "organization_id": "org_...",
    "role": "buyer_admin"
  },
  "case_id": "onboarding_case_...",
  "policy_version": "2026-07-01",
  "occurred_at": "2026-07-28T10:15:00Z"
}
```

Rules:

- Derive user/tenant/role from server-side authentication, never from a web request body.
- Enforce tenant and organization checks before loading a tender, proposal, vendor, document, artifact, or trace.
- Use short-lived service credentials/mTLS or equivalent for backend-to-AI traffic.
- Store documents privately. Pass the AI only the authorised content/metadata required for a task.
- Preserve source-page and source-document IDs for evidence. Do not include raw documents in logs.
- Keep the current signed demo-token implementation out of production.

## 5. Shared API response contract

All new AI endpoints should return a predictable envelope:

```json
{
  "request_id": "req_123",
  "trace_id": "trace_123",
  "status": "completed",
  "result": {},
  "confidence": 0.91,
  "risk_level": "low",
  "evidence": [],
  "findings": [],
  "missing_information": [],
  "recommended_human_action": "review_and_approve",
  "model": {"provider": "ollama", "name": "qwen3:4b", "prompt_version": "..."},
  "policy_version": "2026-07-01",
  "data_status": "verified|self_declared|synthetic_demo_only"
}
```

`confidence` is a number from `0.0` to `1.0`. A low confidence, contradictory evidence, unreadable document, or unavailable authoritative source must yield `recommended_human_action: human_review`; it must never trigger automated approval/rejection.

## 6. Existing demo API: what can be reused now

The current FastAPI application exposes these routes. Treat them as an MVP reference; several require replacement or hardening before direct production use.

### 6.1 Session and metadata

| Method/path | Request | Response/use | Production integration note |
|---|---|---|---|
| `POST /api/session/random` | `{ "role": "buyer"\|"vendor" }` | Fixed demo account + signed demo token | Replace with existing website authentication. |
| `POST /api/session/account` | `{ "role", "account_id" }` | Fixed demo account only | Remove; it deliberately blocks arbitrary account selection. |
| `GET /api/meta` | none | model, embedding model, categories, KB status/count | Useful for diagnostics only; do not expose model internals broadly. |
| `POST /api/demo/reset` | none | clears volatile demo state | Do not expose in production. |

### 6.2 AI job pattern

| Method/path | Request | Result |
|---|---|---|
| `POST /api/jobs/form` | `seed`, optional template/overrides/buyer ID | starts buyer-form generation |
| `POST /api/jobs/draft` | `seed`, optional template/overrides/buyer ID | starts full draft |
| `POST /api/jobs/draft-guided` | `project_name`, `scope_text`, optional template/overrides/buyer ID | starts guided SoW-to-tender draft |
| `POST /api/jobs/sow-review` | `project_name`, `scope_text` | starts SoW review/rewrite |
| `POST /api/jobs/populate-optional-sections` | project/SoW/overrides | fills optional buyer-form sections |
| `POST /api/jobs/extract` | multipart `file` PDF | extracts buyer form from uploaded PDF |
| `POST /api/jobs/draft-sow` | multipart `file` PDF | extracts and drafts full tender |
| `POST /api/jobs/improve-tender` | artifact, optional file/template/review prompt | creates a revised tender artifact |
| `POST /api/jobs/validate` | vendor validation request | starts vendor validation agent |
| `POST /api/jobs/evaluate` | none | runs bundled fixture evaluation only |
| `GET /api/jobs/{job_id}` | path ID | job status/result/error/trace |
| `POST /api/jobs/{job_id}/cancel` | path ID | requests cancellation |
| `POST /api/jobs/cancel-all` | none | cancels current actor’s jobs |

Job creation requires a valid authenticated actor in the current demo. A client polls the job and optional activity stream until terminal status.

```text
PENDING → RUNNING → SUCCESS | FAILURE | CANCELLED
```

### 6.3 Tender lifecycle and marketplace demo routes

| Method/path | Purpose | Production replacement/requirement |
|---|---|---|
| `GET /api/artifacts` / `GET /api/artifacts/{id}` | actor-scoped AI artifact/audit retrieval | Integrate with tenant-scoped audit/decision ledger. |
| `POST /api/artifacts/{id}/approve` | buyer approves draft or committee artifact | Existing backend must validate authorized Buyer Admin and distinguish draft publication from award. |
| `GET /api/tenders/saved` | buyer’s draft/published tender register | Replace IDs/statuses with the system-of-record tender service. |
| `GET /api/tenders/feed` | vendor-facing published tenders | Apply real eligibility, invitation, deadline, tenancy and access rules. |
| `GET /api/tenders/{id}` | tender detail | Enforce role/organization visibility. |
| `POST /api/tenders/{id}/validate-vendors` | shortlist against saved tender | Use real verified vendor data and saved tender policy. |
| `POST /api/tenders/{id}/proposals` | demo price/timeline/two summaries | Replace with full proposal draft/upload/submit/lock workflow. |
| `GET /api/proposals/compare` | buyer’s submitted-vendor comparison | Return only proposals the buyer is allowed to assess. |
| `GET /api/download/{file_id}/pdf|json` | generated output download | Serve through authorised object storage/download service. |

### 6.4 Reputation and intelligence routes

| Method/path | Request | Current result | Production note |
|---|---|---|---|
| `GET /api/reputation` | none | synthetic marketplace snapshot | Replace with tenant/public-profile policy. |
| `GET /api/accounts/vendors` | none | all synthetic profiles | Never list cross-tenant private vendors by default. |
| `GET /api/accounts/vendors/{id}` | vendor ID | synthetic profile | Map to verified vendor profile/read permission. |
| `GET /api/accounts/buyers` / `{id}` | buyer ID | synthetic profile | Map to approved buyer-profile visibility. |
| `POST /api/intelligence/shortlist` | tender context | profile-based shortlist/top three/buckets | Use only verified, consented source events in production. |
| `GET /api/kb/search` | `q`, optional `k` | semantic clause hits | Restrict to approved corpus and authorized purpose. |
| `GET /api/activity` | cursor/job ID | in-memory activity lines | Replace/pair with SSE/WebSocket or job event store. |
| `GET /api/ai-events` | `trace_id` or `job_id` | redacted durable events | Restrict to authorized audit roles. |

## 7. Feature-by-feature integration workflows

### 7.1 Buyer tender drafting

**Web flow**

1. Buyer opens “Create Tender.”
2. Website supplies authenticated buyer/organization context; fields owned by the platform are read-only.
3. Buyer enters structured fields and SoW, optionally uploads a source PDF through backend storage.
4. Web calls backend `create draft`/`request AI draft`; backend creates a case/job and calls AI.
5. Web polls or subscribes to job state and displays progress without exposing raw model chain-of-thought.
6. Render the returned structured tender in editable sections.
7. Display health findings, score, risks, and improvements separately from the tender content.
8. Buyer saves a draft or asks for a revision.
9. Buyer Admin approves publication; backend transitions the tender state and emits audit events.

**Backend must provide AI**

```json
{
  "buyer": {"organization_id": "org", "display_name": "...", "description": "..."},
  "tender": {
    "id": "tnd", "title": "...", "category": "...", "subcategory": "...",
    "location": "...", "scope_of_work": "...", "budget": {}, "dates": {},
    "eligibility": {}, "required_documents": [], "evaluation": {},
    "commercial_controls": {}, "legal_controls": {}, "submission_controls": {}
  },
  "source_document_refs": []
}
```

**AI returns** a structured tender artifact, health/consistency data, trace metadata, and revision metadata. The UI should never parse free-form prose to recover fields.

### 7.2 Scope of Work review/extraction

**Review:** send project name and SoW text; display clarity/readiness, missing items, risks, and proposed rewrite. The buyer chooses whether to apply a rewrite.

**Extraction:** backend uploads/scans the PDF, obtains page-level OCR/text, then calls the extraction agent with an internal document reference and authorized text. Persist extracted fields with source-page citations. Show a side-by-side “source/evidence → extracted form field” review experience.

**Do not:** let a document’s instructions alter application policy; index the upload into RAG automatically; treat extraction as legal verification.

### 7.3 Tender health and revision

Render five specialist cards and an aggregate result:

- score and readiness;
- finding severity/category;
- risk/fix recommendation;
- affected tender section;
- aggregate priorities.

On “Improve,” backend submits the current structured artifact and buyer-approved improvement instruction. Save the new revision; preserve parent artifact ID, before/after change records, author, timestamp, and approval state. Never overwrite an approved/published revision.

### 7.4 Vendor onboarding and document intelligence (target implementation)

This is the next major feature and is not implemented end-to-end in the current demo.

```text
Vendor/Org setup
→ document upload + malware/file checks + private storage
→ OCR/page text
→ AI classification and field extraction
→ deterministic document/eligibility policy
→ AI consistency/applicability findings
→ Active | Limited | Needs Correction | Human Review
→ manager decision and immutable audit record
```

**Backend-owned entities**

```text
Organization, OrganizationUser, VendorProfile, VendorCategory,
VendorDocument, DocumentExtraction, ValidationCase, ValidationFinding,
EligibilityDecision, ReviewTask, AuditEvent
```

**AI document request**

```json
{
  "vendor_id": "vnd_...",
  "organization": {
    "legal_name_ar": "...", "legal_name_en": "...", "cr_number": "...",
    "activities": [], "selected_categories": []
  },
  "documents": [
    {
      "document_id": "doc_...", "declared_type": "commercial_registration",
      "mime_type": "application/pdf", "pages": [
        {"page": 1, "ocr_text": "...", "storage_ref": "private reference"}
      ]
    }
  ]
}
```

**AI response requirements**

- document type and confidence;
- normalised fields by document type;
- page/text evidence for every material field;
- unreadable/missing/contradictory-field flags;
- CR/name/activity/category/expiry/signatory/IBAN consistency findings;
- recommended action only: `accept_evidence`, `request_correction`, or `human_review`.

The backend policy engine decides whether status is `Pending`, `Active`, `Limited`, `Under Review`, `Suspended`, or `Deactivated`.

### 7.5 Vendor eligibility and tender feed

Before exposing a tender, backend must calculate deterministic eligibility using:

- tender publication/deadline and invitation rule;
- vendor organization/status;
- approved category/subcategory;
- mandatory/conditional/sector document status and expiry;
- buyer/tender-specific qualification rules;
- conflict-of-interest restrictions;
- geography/local-presence requirements.

AI can explain ambiguous category/activity fit or identify missing evidence. It must not override the rule outcome. Vendor UI must never reveal competing proposals, internal committee results, buyer private notes, or hidden weighting.

### 7.6 Vendor proposal lifecycle

Replace the demo proposal form with:

```text
Draft → uploads/technical-commercial separation → completeness validation
→ vendor review → final submit before deadline → immutable timestamp/lock
→ buyer evaluation → award/rejection is backend-owned
```

**Required web views**

- tender requirement summary and deadline;
- technical proposal upload/sections;
- commercial proposal upload/sections;
- mandatory document checklist;
- validation findings and correction loop before submit;
- draft/submit status and immutable receipt;
- post-submission read-only view.

**Required backend controls**

- official server timestamp;
- deadline/late-submission policy;
- file type/size/virus checks;
- version control before deadline;
- lock/retract rules;
- no competitor visibility;
- separate technical/commercial access where policy requires it;
- append-only audit event for every action.

### 7.7 Proposal extraction, evaluation, and committee

Backend sends AI the approved tender requirement IDs plus authorized proposal text/document references. AI must return requirement-level, evidence-backed findings:

```json
{
  "requirement_id": "REQ-TECH-01",
  "status": "met|partially_met|not_met|uncertain",
  "score": 0,
  "confidence": 0.84,
  "evidence": [{"document_id": "doc", "page": 6, "quote": "..."}],
  "gap": "...",
  "recommended_action": "score_normally|request_clarification|human_review"
}
```

Run each vendor’s qualitative evaluation in isolation. Backend enforces criterion IDs, weights, pass/fail gates, formula arithmetic, disqualification rules, and final ranking. AI provides evidence, explanations, qualitative assessment, risk/caveat identification, and committee summaries.

The committee consists of Technical, Commercial, Compliance, Delivery, and Risk assessments. Persist each assessment, input evidence IDs, model/prompt version, aggregate, human reviewer, override reason, and final outcome separately. A committee recommendation is never an award.

### 7.8 Shortlisting and vendor recommendation

Use the current engine only as a UX/contract prototype. Production inputs must come from verified sources:

- category-specific performance;
- valid documents/licenses;
- approved institutional verification;
- real delivery/contract/payment/dispute events;
- tender requirements and buyer policy;
- market-price data with provenance.

Return the entire eligible set plus exclusion/review reasons to authorized buyers. Display a ranked shortlist only with: score version, evidence, uncertainty, conflict flags, risk rationale, and “AI recommendation only” notice.

### 7.9 VRI, BRI, ratings, and badges

Backend must own source events and score lifecycle. Required sources include verified onboarding, contracts, milestones, acceptance, payment, disputes, tender participation/outcomes, and mutually submitted ratings.

Implement ratings with blind submission, review window, anti-retaliation/collusion/outlier review, recency/value/complexity weighting, Bayesian normalisation, appeals, and score recalculation/version history. Do not display a reputation score for a cold-start user as if it were established evidence; use a “Verification profile / Limited history” state instead.

## 8. Web integration requirements

### 8.1 Use structured data, not generated HTML

The existing demo renders data in vanilla `app.js`. The website should map API JSON to its own components. Do not scrape the demo UI or parse PDF/free text for business fields.

### 8.2 Required reusable UI components

- asynchronous job/progress state: pending, running, success, failure, cancelled;
- agent finding card: severity, confidence, evidence, action;
- evidence viewer: page/document link plus highlighted extract;
- AI recommendation card: score, version, caveats, human-action requirement;
- tender document editor/revision diff;
- document checklist/status/expiry component;
- manager-review action panel;
- immutable audit timeline;
- empty/cold-start/limited-history profile state.

### 8.3 Client polling/subscription

The demo polls `GET /api/jobs/{id}` and `GET /api/activity?since=<cursor>&job_id=<id>`. Production should prefer backend-owned SSE/WebSocket/job-event subscription where feasible. Never show raw streaming model tokens as a decision explanation; show approved progress labels and final structured findings.

### 8.4 Error and state handling

| Condition | Web behaviour |
|---|---|
| `401` | refresh/re-authenticate; do not retry blindly |
| `403` | show “not authorized”; do not reveal resource metadata |
| `404` | show unavailable/not found |
| `409` | show state conflict (for example, blocked publication or obsolete revision), refresh resource |
| `413` | show file too large |
| `415` | show unsupported file type |
| `422` | display field-level validation errors |
| job `FAILURE` | show safe error/trace reference; retain draft input |
| AI low confidence/fallback | render human-review state, never a green approval state |

## 9. Backend implementation checklist

### Before connecting AI features

- [ ] Tenant and organization context exists on every relevant entity.
- [ ] Role checks exist for Buyer Admin, Buyer User, Vendor Admin, Vendor User, Platform Manager/Reviewer, and Auditor.
- [ ] Tender, document, proposal, decision, and audit IDs are stable UUIDs/opaque IDs.
- [ ] Object storage is private; document URLs are short-lived and authorized.
- [ ] A durable job/work queue exists and survives deployment/restart.
- [ ] APIs are versioned and publish an OpenAPI schema.

### For each AI endpoint

- [ ] Validate request schema and scope/authorization before calling AI.
- [ ] Attach request/trace/tenant/actor/case/policy context.
- [ ] Persist submitted input reference and immutable result artifact.
- [ ] Preserve prompt/model/schema/policy versions.
- [ ] Implement idempotency key for job-creating requests.
- [ ] Enforce timeout, retry policy, and safe `human_review` fallback.
- [ ] Emit audit and operational events without leaking document contents/PII.
- [ ] Return a stable response envelope, not model-specific prose.

## 10. AI-service interface roadmap

The current `/api/*` endpoints can be preserved behind an adapter initially. The recommended stable internal interfaces are:

```text
POST /v1/ai/tenders/draft
POST /v1/ai/tenders/review-sow
POST /v1/ai/tenders/extract
POST /v1/ai/tenders/health-check
POST /v1/ai/tenders/revise

POST /v1/ai/vendor-documents/analyse
POST /v1/ai/vendors/eligibility-findings
POST /v1/ai/vendors/shortlist

POST /v1/ai/proposals/extract
POST /v1/ai/proposals/evaluate
POST /v1/ai/proposals/committee

POST /v1/ai/reputation/compute-signals
GET  /v1/ai/jobs/{id}
GET  /v1/ai/artifacts/{id}
```

Keep the AI service stateless where possible; pass IDs and retrieve authorized content through an internal data-access layer or supply a bounded task payload. The backend remains the authoritative owner of data and workflow state.

## 11. Observability, audit, and privacy

The repository already records redacted AI events and artifacts. Preserve and expand this pattern:

- correlation: request ID, trace ID, case ID, tenant ID, tender/proposal/vendor/document ID;
- model: provider, model, prompt version, schema version, run duration, token/cost metrics;
- decision: input snapshot reference/hash, evidence IDs, confidence, findings, fallback state, policy version;
- human: reviewer ID, action, override reason, timestamp;
- privacy: redaction, data classification, retention policy, deletion workflow, access controls.

Do not store raw prompts/proposals/documents in general application logs. Do not expose traces across tenants. Only privileged audit roles should access detailed AI artifacts.

## 12. Testing and release gates

### Existing repository tests

The current unit suite tests prompt registry, guardrails, input framing, RAG approval, observability redaction, token integrity, deterministic evaluation, demo-profile shape, and consistency behaviour.

### Integration team must add

- API contract tests against the stable integration schema;
- authorization/tenant-isolation tests for every resource;
- end-to-end tender draft → approval → vendor feed → proposal → comparison tests;
- proposal deadline/lock/retry/idempotency tests;
- document upload/OCR/extraction/mismatch fixtures in Arabic and English;
- rules-engine tests for document/category/license/status transitions;
- AI quality evaluation datasets and threshold gates;
- load, failure/recovery, backup, observability, and security tests.

## 13. Migration order

1. Establish identity, tenants, organizations, RBAC, storage, audit ledger, and durable jobs in the existing backend.
2. Integrate buyer drafting/SoW review/health with structured tender data and revision storage.
3. Implement vendor onboarding, document storage/OCR, deterministic eligibility rules, and manager review queue.
4. Connect live tender eligibility and proposal submit/lock workflow.
5. Add evidence-based proposal extraction/evaluation/committee with human approval.
6. Ingest real contract/payment/delivery/dispute/rating events before enabling real VRI/BRI.
7. Decommission synthetic demo data from all production paths; retain it only for automated tests and demo environments.

## 14. Questions that must be answered before production build

1. Which official/approved registry and issuer integrations are legally available for CR, licenses, tax, GOSI, Nitaqat, Etimad, and institutional verification?
2. Which statuses may be assigned automatically, and which always require a manager? Is any automatic rejection allowed?
3. What Saudi data-residency, consent, retention, and deletion obligations apply to uploaded documents and AI processing?
4. What is the authorized tender/proposal state machine, including resubmission and clarification rules?
5. What exact VRI/BRI formulas, evidence thresholds, public visibility rules, appeal process, and score-version policy are approved?
6. Which team owns document OCR, virus scanning, object storage, rules configuration, human review, and model evaluation?

## 15. Future AI integrations from product-intelligence specifications

The following capabilities are planned AI work, not claims about the current production state. Backend/web teams should design their contracts now so these features can be added without rewriting core workflow.

### 15.1 Vendor Document Intelligence

The AI service will analyse authorised OCR/page text for vendor documents. It requires document IDs, page text, declared type, vendor onboarding fields, selected categories, and current date. It returns structured extraction and findings, for example:

```json
{
  "document_id": "doc_cr_123",
  "classification": {"type": "commercial_registration", "confidence": 0.97},
  "fields": {
    "cr_number": "...",
    "legal_name_ar": "...",
    "legal_name_en": "...",
    "activities": [],
    "issue_date": "...",
    "expiry_date": "..."
  },
  "evidence": [{"page": 1, "field": "cr_number", "text": "..."}],
  "findings": [],
  "recommended_human_action": "accept_evidence"
}
```

Web must provide evidence/source-page review. Backend must provide secure document references/OCR, issuer verification adapters, policy enforcement, and review-state transitions. AI must not claim that a document is authentic or officially verified unless the backend supplies an authoritative verified result.

### 15.2 Onboarding intelligence and eligibility explanations

Future AI inputs: organization identity, CR activities, selected categories, extracted document fields, verified external results, and applicable policy-rule IDs.

Future AI outputs: duplicate/mismatch/category/licence/applicability findings, confidence, risk, evidence, and a recommended review/correction action. Backend owns `Pending`, `Active`, `Limited`, `Under Review`, `Suspended`, and `Deactivated`; web displays the reason and correction path.

### 15.3 Tender-policy and fairness intelligence

Future Tender Health additions need backend-supplied policy/tender history data to flag:

- missing or conflicting evaluation rules;
- requirement-to-criterion gaps;
- impossible timelines or unclear acceptance criteria;
- document/licence applicability gaps;
- potential buyer/vendor ownership/contact/conflict overlap;
- potentially biased or inconsistent tender/evaluation patterns.

The UI must label these as AI findings and provide a buyer correction/review action. Publication remains backend-controlled.

### 15.4 Proposal evidence and selection intelligence

To support the Vendor Selection Engine, backend must retain stable IDs for:

```text
tender requirement → criterion → proposal document/page/section → vendor evidence → decision
```

AI will return `met`, `partially_met`, `not_met`, or `uncertain` per requirement with evidence and confidence. Web should display an evidence matrix, not only a score. Backend applies weights, disqualifications, price rules, and ranking policy.

### 15.5 Tender Committee v2

The future committee retains Technical, Commercial, Compliance, Delivery, and Risk agents, but every specialist result must expose evidence IDs, missing evidence, confidence, caveats, and a reviewer action. Backend must store individual and aggregate artifacts, policy/weight version, human override, and final buyer decision. Web should support an explainable comparison view and must not call it an “award.”

### 15.6 VRI/BRI and rating-integrity intelligence

Future AI requires event feeds, not only profiles:

- contract award, milestone, acceptance, quality, payment, dispute, tender outcome, communication, and rating events;
- source/document verification status;
- category/subcategory tagging;
- reviewer/appeal outcomes.

AI will provide event extraction, anomaly/outlier/retaliation/collusion flags, category performance insights, tender clarity/fairness analysis, and explanations. Backend owns score formula, Bayesian/recent-performance calculations, badge state, review windows, appeal outcomes, visibility, and recalculation history.

### 15.7 Future AI data contract requirements

All new entities that can influence AI must carry:

```text
tenant_id, organization_id, entity_id, source_event_id, data_status,
source_system, observed_at, verified_at, policy_version, consent/retention class
```

`data_status` should distinguish `verified`, `self_declared`, `imported_pending_review`, `synthetic_demo_only`, and `rejected`. This is essential so AI can explain uncertainty and so the UI does not represent unverified data as fact.

### 15.8 AI roadmap handoff order

| Order | AI capability | Backend/web prerequisite |
|---:|---|---|
| 1 | document classification/extraction/consistency | secure documents, OCR, onboarding case, reviewer UI |
| 2 | eligibility/applicability recommendations | versioned rules, organization/category/licence data |
| 3 | tender requirement normalisation | stable tender/criterion editor and policy IDs |
| 4 | proposal extraction/evidence matrix | proposal upload, section/page IDs, submission lock |
| 5 | evidence-based evaluation/committee | deterministic scorer, reviewer/override/audit flow |
| 6 | real VRI/BRI data signals | contracts/payments/disputes/ratings event model |
| 7 | anomaly, retaliation, collusion, recovery intelligence | sufficient labelled events, appeals/review process |

### 15.9 Product-intelligence source traceability

| Source document | AI integration area in this guide |
|---|---|
| `AICore.docx` | onboarding/document intelligence, tender-policy/fairness checks, confidence/risk routing, human exceptions and audit |
| `AI Vendor Selection Engine.docx` | requirement/proposal evidence, prefiltering, Fit Score configuration, ranking and explanation |
| `AI Tender Committee Simulation.docx` | five specialist agents, orchestrator, configurable weights, evidence and buyer approval |
| `Vendor Reputation Index (VRI).docx` | verified event feeds, category-specific signals, vendor explanations and predictive roadmap |
| `Buyer Relaiability Index (BRI).docx` | buyer event feeds, fairness/tender clarity/payment/communication/dispute intelligence and vendor protection |
| `Mushtarry Reputation Badge Framework.docx` | blind ratings, Bayesian/recency weighting, public thresholds, manipulation detection, badge recovery |
| `Vendor Document Requirements Framework.docx` | document taxonomy, applicability, evidence status, sector/prestige extraction and Limited/Review outcomes |
| `Vendor-Side Workflow & Policy Specification (MVP).docx` | onboarding, revalidation, eligible feed, proposal completeness/lock, conflict controls and AI audit integration |

`Vendor-Side Workflow & Policy Specification (MVP)[1].docx` is a duplicate and does not create a separate requirement set.

## 16. Future AI integration acceptance contracts

This section closes the remaining integration gaps identified in the product-intelligence coverage audit.

### 16.1 Document types the backend/web contract must support

The document subsystem must use configurable document-type IDs and applicability rules. It must not hard-code only the six types currently shown in the demo UI.

| Tier | Minimum supported document families |
|---|---|
| Legal/registration | CR, Articles of Association, national address, VAT, Zakat/Tax, brand registration, MISA |
| Identity/authority | signatory National ID/Iqama reference, authorization letter/power of attorney |
| Banking | IBAN/bank letter with organization-name consistency finding |
| Government/labour | Etimad, Nafath/Absher verification result, GOSI, Nitaqat/Saudization |
| Sector licences | Balady, SAMA, CST, SFDA, energy, media, sport, culture/entertainment, tourism, TVTC/education, interior/security, TGA/NCEC, NCA and extensible `other` |
| Institutional/prestige | Aramco, IKTVA, SEC, SABIC, STC, NEOM/Red Sea/Qiddiya, Royal Commission, PIF portfolio, EPC/oil-and-gas prequalification |
| Capability | company profile, ISO, past projects, recommendation letters, awards/accreditations, government/organization classification |

For each document record, backend should expose to AI only authorised OCR/evidence plus `document_id`, declared type, issuer/source status, issue/expiry dates if already known, applicability context and verification result. Web must show `self-declared`, `extracted`, `verified`, `expired`, `unreadable`, `not applicable`, `needs correction` and `under review` distinctly.

### 16.2 Required event feeds for future AI

| AI capability | Required backend events |
|---|---|
| VRI | document verified/expired, contract awarded/completed, milestone accepted/late, quality accepted/corrective action, tender submitted/won/lost, dispute opened/resolved, rating revealed |
| BRI | tender published/completed, criteria approved/applied, clarification response, vendor rating revealed, invoice due/paid/late, dispute/complaint opened/resolved |
| Badge/recovery | rating revealed, completed contract, compliance improvement, verified institutional evidence, old-evidence decay/recalculation |
| Retaliation/collusion | blind rating submissions/reveal, contract/award relationships, reviewer flags/appeal outcomes |
| Selection/committee | approved requirement/criterion/weight versions, vendor eligibility snapshot, proposal/document versions, market-price source/time, buyer decision/override |

Each event must be immutable or corrected by a compensating event and include source, timestamp, tenant/entity/category IDs, data status and policy version.

### 16.3 Cold-start and evidence-status UI contract

Backend and web must prevent synthetic, sparse or self-declared data from appearing equivalent to verified performance.

| Evidence state | Public/decision-support presentation |
|---|---|
| no completed verified history | `New Vendor — Rating in Progress` / Verification Profile |
| fewer than approved minimum contracts | show evidence count and limited-history warning; suppress public star score if policy requires |
| self-declared/imported | label source and exclude from verified components unless approved |
| verified | eligible for configured score component |
| disputed/under appeal | show review state; retain old decision/version until resolved policy says otherwise |
| synthetic demo | never enter production score, recommendation or public profile |

### 16.4 Score configuration and version contract

Backend must store named, versioned configurations rather than one generic `score`:

```text
vendor_fit_score_version
ai_recommendation_layer_version
tender_committee_weight_version
vri_version
bri_version
rating_normalization_version
badge_rule_version
risk_model_version
```

Every API response and UI explanation must identify which configuration produced it. Changes trigger a new version and controlled recalculation; they must not silently rewrite historic decisions.

The proposed product values—including Fit 40/30/20/10 plus risk, committee 30/20/15/15/10/10, VRI component weights, BRI 25/25/20/15/10/5, rating recency/value/complexity weights, three-contract public threshold and 14-day blind-rating window—remain configuration proposals until product/legal approval.

### 16.5 Human feedback and appeal contract

For every AI finding or recommendation, backend needs fields for:

```text
review_status, reviewer_id, reviewed_at, reviewer_action,
override_reason_code, override_comment, corrected_fields,
appeal_id, appeal_outcome, superseded_artifact_id
```

The AI team receives de-identified, consented corrections through an approved evaluation-data pipeline. Production reviewer actions must not automatically fine-tune or change prompts/models.

### 16.6 Model quality/release contract

The AI service cannot be accepted on “looks good” testing. For each future feature, teams must agree on:

- labelled Arabic/English test corpus and domain owner;
- accuracy/precision/recall and false-approval/false-rejection thresholds;
- evidence correctness and citation coverage;
- confidence calibration and low-confidence fallback threshold;
- ranking stability/fairness and subgroup/category checks;
- latency/availability/cost limits;
- prompt-injection/adversarial document tests;
- rollback model/prompt/schema version and incident owner.

### 16.7 Data privacy and raw-document boundary

The product document says AI extracts metadata and does not export raw files. Integration should therefore keep raw files in backend-controlled private storage, provide the AI only bounded authorised page content/images when necessary, prevent model-provider retention/training, and define deletion/retention for derived text, embeddings and extracted fields. The AI service must return structured data/evidence references, not copy entire documents into artifacts or logs.

### 16.8 Product-specification conflicts requiring joint decision

Backend/web implementation must pause hard-coded policy work until these are resolved:

1. rejection versus `Limited`/`Under Review` in MVP;
2. immediate low-risk auto-approval versus a manager-veto window;
3. selection/recommendation/committee score naming and differing weights;
4. BRI product formula versus current demo formula;
5. whether VRI risk input is a positive safety score or negative penalty;
6. which category/licence mappings and authoritative sources are approved.
7. correction of the selection-document prefilter statement that currently excludes a vendor when its category equals the tender category;
8. whether the example 85% low-risk auto-validation threshold is approved and calibrated.

The AI service can support either approved policy through versioned contracts; it must not choose product/legal policy itself.

## 17. Source references

- Project architecture and implementation: [AI_PROJECT_REFERENCE.md](AI_PROJECT_REFERENCE.md)
- Current local demo: [README.md](../README.md)
- Product-intelligence specifications: `docs/product_intelligence/`
- AI operations: [AI_OPERATIONS.md](../docs/AI_OPERATIONS.md)
- Current source API: [api.py](../api.py)
