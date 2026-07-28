# Mushtarry AI Procurement Intelligence — Project Reference

> **Purpose:** Complete technical reference for the AI project currently in this repository. It describes what exists, how requests move through the system, where each feature lives, how to run it, its safety controls, and its present demo limitations.
>
> **Status:** Local-first MVP/demo. It is not a production procurement system and must not be presented as one.

## 1. Product purpose and operating rule

Mushtarry is an AI-assisted procurement layer. It helps buyers create and improve tenders, structures Scope of Work (SoW) material, checks tender quality, identifies potentially eligible vendors, compares demo proposals, and presents buyer/vendor reputation signals.

The non-negotiable governance rule is:

```text
AI generates or recommends → authorised human reviews → authorised human approves → platform action occurs
```

AI must **not** publish a tender, make a legally binding vendor exclusion, award a contract, or override a human decision. The current project applies this rule to tender publication and committee-artifact approval.

## 2. What is included

| Capability | Current implementation |
|---|---|
| Tender drafting | Multi-agent tender drafting from a guided buyer form, seed, raw SoW, or uploaded PDF. |
| SoW intelligence | Review/rewrite of a supplied SoW and extraction of a structured buyer form. |
| Tender health | Five specialist checks plus an aggregate quality/readiness result. |
| Tender improvement | Revision of a drafted tender using health/committee findings, with changed-path records. |
| Tender PDF | Structured tender JSON rendered into formal `premium_bw` or `modern_bw` PDF templates. |
| Vendor shortlist | Deterministic, tender-specific profile scoring with VRI, requirement, price, risk, and committee signals. |
| Vendor committee | Evidence-bound LLM committee for a submitted vendor proposal: technical, commercial, compliance, delivery, risk. |
| Evaluation sample | Isolated LLM scoring then deterministic ranking of bundled sample submissions. |
| Vendor validation | Tool-using agent for CR/status, duplicate, category, and document checks. |
| Reputation | Synthetic vendor/buyer profiles, VRI, BRI, badges, contract/rating/document metadata. |
| RAG | Local semantic retrieval over human-approved procurement clauses/material. |
| Observability | Redacted durable AI events, trace IDs, activity feed, artifact persistence, prompt versions. |
| Web demo | FastAPI-served vanilla HTML/CSS/JS buyer and vendor sandbox. |

## 3. What is deliberately not production-ready

- Buyer/vendor identities, reputation, contracts, documents, and institutional verifications are synthetic demo data.
- Vendor registry, duplicate detection, category alignment, and base document completeness use stubs; no official verification occurs.
- There is no real vendor onboarding, document upload/OCR, external Wathq/Etimad/issuer integration, payment system, or contract system.
- Proposal submission is a sandbox limited to price, timeline, technical summary, and commercial summary.
- Sessions use signed demo tokens, not enterprise SSO/authentication.
- Jobs and live activity are in memory. SQLite provides local artifact/event/marketplace persistence only.
- Do not expose the local Ollama endpoint, demo signing secret, SQLite database, or generated files publicly.

## 4. Repository map

```text
api.py                         FastAPI web/API adapter and demo workflow coordinator
run.py                         CLI entry point for individual/all AI modes
main.py                        Legacy CLI/PDF entry point
pdf_renderer.py                Formal tender-PDF renderer
frontend/                      Demo browser client; no build step
agents/
  graph/                       Main LangGraph tender-drafting orchestration
  form_generator/              Short topic → structured buyer form
  sow_review/                  SoW readiness review/rewrite
  sow_extractor/               PDF/raw text → structured buyer form
  tender_drafting/             Four-section drafting agents and output schema
  tender_intelligence/         Tender Health Committee
  vendor_validation/           Registration validation agent and current stubs
  evaluation/                  Sample vendor scoring and ranking
  vendor_committee/            Submitted-proposal committee graph
  reputation/                  Synthetic profiles, VRI/BRI, shortlist calculations
  rag/                         Approved-source embeddings, retrieval, chunking
  prompts/                     Versioned system prompt files
  artifact_store.py            SQLite artifact and approval persistence
  marketplace_store.py         SQLite tender/proposal persistence
  observability.py             Redacted trace/event persistence
  guardrails.py                Structured-output validation and safe fallbacks
  tests/                       Unit/regression checks
docs/                          Product, architecture, operations, and reference material
outputs/                       Generated JSON/PDFs/uploads; runtime output, not source
data/mushtary.db               Local SQLite runtime database
```

## 5. Runtime architecture

```text
Browser or future web client
  │  HTTPS/JSON + Bearer demo token
  ▼
FastAPI (`api.py`)
  ├── async in-memory job manager
  ├── agent/pipeline invocation
  ├── artifact, marketplace and event stores (SQLite)
  ├── PDF renderer and generated file download
  └── reputation/shortlist/demo proposal coordinator
  │
  ▼
Agents
  ├── Ollama/OpenAI-compatible chat model
  ├── Pydantic schemas + guardrails
  ├── prompt registry + prompt files
  ├── local RAG retrieval
  └── deterministic arithmetic/policy checks where implemented
```

### Model provider

The default provider is an OpenAI-compatible local Ollama server. Configuration comes from `.env`; see `.env.example`.

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `ollama` by default; code also supports a Gemini-compatible route. |
| `LLM_BASE_URL` | Local OpenAI-compatible endpoint, normally `http://localhost:11434/v1`. |
| `LLM_MODEL` | Generation model, default `qwen3:4b`. |
| `LLM_API_KEY` | Placeholder required by the client for local Ollama. |
| `RAG_EMBED_MODEL` | Embedding model, default `qwen3-embedding:0.6b`. |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_MAX_CONCURRENCY` | Model reliability controls. |
| `MAX_SOW_UPLOAD_BYTES` | PDF upload limit; default 25 MB. |
| `MUSHTARY_SESSION_SECRET` | Demo-token signing secret; must be set in a deployed environment. |

## 6. Core data contracts

### 6.1 AI artifact

Agents return an `AIArtifact` persisted by `artifact_store.py`. It contains an ID, trace ID, agent/prompt/model metadata, sanitised input snapshot, structured output, token usage, status, actor/vendor/tender context, timestamps, and approval metadata where applicable.

Artifacts are the audit record for generated tender drafts, vendor validation results, evaluation output, and committee output. They are not a replacement for a full production business audit ledger.

### 6.2 Buyer form and tender draft

`agents/buyer_form.py` defines the structured tender input. Key groups are:

- buyer/tender identity and category;
- dates, location, procurement method, budget and duration;
- SoW, objectives, deliverables, timeline and responsibilities;
- eligibility, certifications and mandatory/conditional/sector/optional/prestige documents;
- technical/financial evaluation configuration and disqualification criteria;
- proposal packaging and platform submission controls;
- commercial, legal, confidentiality, payment and governance controls.

The drafted tender is a structured JSON object. Major sections are `metadata`, `tender_data_sheet`, `introduction`, `instructions_to_bidders`, `award_and_contract`, `proposal_format`, `project_overview`, `objectives`, `scope_of_work`, `deliverables`, `timeline`, `team_requirements`, `general_terms`, `confidentiality`, `evaluation_criteria`, `payment_terms`, `annexures`, `tender_intelligence`, and `consistency_report`.

### 6.3 Vendor profile

`agents/reputation/engine.py` creates 31 fictional vendor profiles. Every profile carries `data_status: synthetic_demo_only` and includes:

- vendor organization and fictional CR/activity metadata;
- Vendor Admin/User role records;
- categories, capability, delivery, financial and reputation signals;
- mandatory, conditional, government, sector-specific, and optional-capability document metadata;
- eligibility summary and revalidation triggers;
- institutional verification records;
- fictional contract/rating history;
- VRI/badge data and a score version.

This is fixture data for UI, shortlist, and agent integration. It is not evidence of any real company, document, licence, institutional relationship, or procurement performance.

## 7. AI workflows

### 7.1 Form generation

**Input:** a short seed/topic, optional buyer ID/template/overrides.

**Process:** `FormGeneratorAgent` prompts the model to produce a Pydantic-compatible buyer form. Guardrails repair or fall back when structured output is invalid.

**Output:** a populated buyer-form object for buyer review. It is not a published tender.

### 7.2 Guided tender drafting

```text
Buyer form / project name + SoW
→ SoW extraction/normalisation where needed
→ context, scope, execution, legal/evaluation section agents
→ structured tender assembly
→ deterministic consistency checks
→ Tender Health Committee
→ artifact + JSON + PDF + shortlist context
→ Buyer-Admin approval required before publication
```

The four drafting section agents are:

| Agent | Owns |
|---|---|
| Context | tender metadata, data sheet, introduction, bidder instructions, award/proposal controls |
| Scope | project overview, objectives, scope categories/phases/general requirements |
| Execution | deliverables, timeline, team, reporting/escalation |
| Legal/Evaluation | legal terms, confidentiality, evaluation, payment, annexures |

### 7.3 SoW review and extraction

`SowReviewAgent` identifies unclear scope, missing deliverables/ownership/timeline/acceptance criteria, risks and rewrite recommendations.

`SowExtractorAgent` accepts raw text or a validated PDF upload. It uses bounded text extraction/retrieval, treats source text as untrusted data, and outputs a buyer form. Current upload support is PDF only; the server checks extension, magic header, and size before storing it under `outputs/uploads`.

### 7.4 Tender Health Committee

The Tender Health Committee is a post-draft quality control, not a vendor-award committee.

| Specialist | Checks |
|---|---|
| Scope Clarity | scope, deliverables, milestones, technical clarity, acceptance logic |
| Commercial Clarity | budget/pricing/payment/proposal commercial controls |
| Compliance Readiness | eligibility, required documents, submission and approval controls |
| Vendor Participation | likely bidder friction, ambiguities, market readiness |
| Aggregator | final quality, readiness, risks, and prioritised improvements |

Results stay in the JSON/UI. They are not silently inserted into the issued tender PDF. The buyer may trigger `improve-tender`, which creates a new revision with changed paths and records.

### 7.5 Vendor shortlist and recommendation

`shortlist_vendors()` accepts tender context: category/subcategory, budget, timeline, required certifications, minimum experience/similar projects, local-presence rule, and optional sector licence.

It first excludes clearly unsuitable synthetic vendors, then calculates profile-based signals. The current recommendation layer uses technical evaluation 50%, financial 20%, VRI 20%, and risk 10%; its internal Fit Score uses VRI, requirement match, proposal-quality proxy, price competitiveness, and risk adjustment. It returns top three, buckets, exclusions, rationale, compliance/risk/probability fields, and a deterministic committee summary.

**Important:** this pre-publication shortlist is based on synthetic profile data and must remain advisory.

### 7.6 Submitted-proposal committee

After a vendor submits a demo proposal, `vendor_committee/graph.py` runs five evidence-bound specialist nodes:

- technical fit;
- commercial/value;
- compliance/document readiness;
- delivery/performance;
- risks.

The aggregate returns per-agent scores, summary, evidence, risks, recommendations, final score, final recommendation, and committee reasoning. It can fall back to deterministic profile baselines if the LLM fails. The buyer may approve the committee artifact, but this is an approval record only—not a contract award.

### 7.7 Sample evaluation and ranking

The `agents/evaluation` flow demonstrates fair isolation:

```text
One vendor submission + tender policy/criteria/VRI → individual score
All individual scores only → ranking/explanation
```

The LLM supplies qualitative scoring/explanations. Code enforces criterion membership, score arithmetic, risk-adjustment bounds, eligibility, ordering, and rank. Bundled fixtures are in `agents/samples/`.

### 7.8 Vendor validation

The agent accepts CR number, Arabic/English names, categories, and document-type metadata. It invokes four tools:

1. CR lookup;
2. duplicate check;
3. category-to-activity alignment;
4. document completeness.

It returns `AUTO_VALIDATED`, `NEEDS_CORRECTION`, or `FLAGGED_FOR_REVIEW`, plus CR status, name-match confidence, category alignment, duplicate flag, missing documents, machine-readable flags, vendor/admin messages, trace, and document applicability assessment.

**Current limitation:** all four tools are demo adapters. The CR lookup is a mock dictionary; duplicate detection always returns no duplicate; category mapping is partial; and base completeness only requires CR. The output explicitly marks `verification_mode: DEMO_ADAPTERS_ONLY`.

### 7.9 Reputation intelligence

VRI is calculated from performance rating (20%), compliance/licenses (15%), institutional verification (15%), delivery (15%), financial strength (10%), tender success (10%), contract history (10%), and AI risk signals (5%).

Current BRI is calculated from payment reliability (30%), evaluation fairness (20%), dispute behaviour (20%), procurement volume (15%), platform activity (10%), and AI risk signals (5%). This differs from the product-intelligence BRI document and must be reconciled before production.

Badges, special badges, VRI/BRI, contracts, ratings, and institutional records are synthetic fixtures. Real scores require verified onboarding, contracts, delivery, payment, dispute, and rating events.

### 7.10 RAG

The RAG subsystem embeds only human-approved material. Its corpus contains procurement clauses for law/general terms, confidentiality, evaluation, payment, bid security, damages, eligibility, submission/award, warranty/delivery, and compliance/localisation.

Never add unapproved AI output, arbitrary user uploads, or unreviewed web content to the knowledge base. Rebuild/index approved sources with `agents.rag.index_documents`.

## 8. API and browser runtime

`api.py` hosts the FastAPI application and mounts `frontend/` as static content. The frontend has no bundler; `index.html`, `app.js`, and `styles.css` call the API directly.

Long-running AI calls are represented as jobs:

```text
POST /api/jobs/<kind> → { job_id, ... }
GET /api/jobs/{job_id} → PENDING | RUNNING | SUCCESS | FAILURE | CANCELLED
GET /api/activity?job_id=...&since=... → live activity cursor/events
GET /api/ai-events?trace_id=... or ?job_id=... → durable redacted trace
```

The browser wraps `fetch` and attaches `Authorization: Bearer <demo token>` after session selection. Job creation requires an authenticated demo actor and enforces that a requested actor matches that token.

## 9. Persistence and lifecycle

| Data | Current store | Lifecycle |
|---|---|---|
| Jobs/live activity | process memory | lost on process restart/reset |
| Draft/published tender/proposal activity | local SQLite and hydrated in-memory cache | persists locally; not production-grade |
| AI artifacts/approvals | local SQLite | persists locally |
| AI event trace | local SQLite | redacted; retention controlled by `AI_EVENT_RETENTION_DAYS` |
| Generated tender JSON/PDF | `outputs/` | local files; downloadable via API |
| Uploaded SoW PDFs | `outputs/uploads/` | local development storage |

Production replacement requirements: relational DB/migrations, private object storage, durable queue/workers, tenant-scoped access controls, backups, retention/deletion policy, encryption/key management, and service observability.

## 10. Safety and reliability controls

- Pydantic schemas validate structured agent output.
- `guardrails.py` applies safe fallback output when validation fails.
- Evaluation arithmetic/ranking membership is code-enforced, not model-enforced.
- Input is sanitised and SoW/retrieval text is framed as untrusted data.
- RAG rejects non-approved material before embedding.
- Model calls are bounded by timeout/retry/concurrency/circuit settings.
- Observability redacts sensitive fields and stores hashes/lengths rather than raw long content.
- Artifact/job access checks prevent one demo actor from reading another actor’s job/artifact when the endpoint is protected.
- Tender publication checks buyer ownership and blocks publication when the consistency report is `BLOCKED`.

## 11. Test suite

Run:

```powershell
uv run python -m unittest discover -s agents/tests -v
```

The suite covers AI-input framing/RAG approval, observability redaction and actor-token integrity, demo-profile shape, deterministic evaluation enforcement, schema guardrails, prompt registry consistency, RAG fail-safe behaviour, SoW extraction normalisation, and tender consistency.

It does not replace end-to-end browser/API tests, real registry-integration tests, document OCR benchmarks, load testing, penetration testing, or production data-quality tests.

## 12. Local setup and operation

1. Install dependencies from `agents/requirements.txt` in the selected Python environment.
2. Copy `.env.example` to `.env`; set model endpoint/model and a non-empty session secret.
3. Start a compatible local model service and ensure the generation and embedding models are available.
4. Start the API/UI using the project’s preferred command, for example:

```powershell
uv run python api.py
```

or use the existing project run command/launcher where configured.

5. Open the local URL printed by Uvicorn/FastAPI, sign in through the demo gate, and select a buyer or vendor flow.

Useful commands:

```powershell
# Run all tests
uv run python -m unittest discover -s agents/tests -v

# Run the CLI modes
uv run python run.py --help

# Rebuild the approved clause corpus
uv run python -m agents.rag.index_documents agents/rag/sources/clauses --authority policy --rebuild
```

## 13. Key product gaps to keep visible

1. Real vendor onboarding and document ingestion/extraction.
2. Authoritative CR/licence/issuer integrations and configurable Saudi eligibility rules.
3. Real contract/delivery/payment/dispute/rating event model for VRI/BRI.
4. Full technical/commercial proposal file handling and requirement-to-evidence mapping.
5. Manager review queues, appeals, status transitions, and complete business audit trail.
6. Production identity, tenancy, RBAC, object storage, encryption, data residency, durable workers, and monitoring.

## 14. Future AI capability roadmap from product-intelligence specifications

This section is the AI scope still to be built from `docs/product_intelligence/`. It deliberately separates AI work from the backend/web work required to make it operational.

### 14.1 Vendor Document Intelligence Agent

**Source specifications:** `AICore.docx`, `Vendor Document Requirements Framework.docx`, and `Vendor-Side Workflow & Policy Specification (MVP).docx`.

The present validator receives document *types* only. The future agent must work from authorised OCR/page text and return structured evidence, never an unsupported claim that a document is officially verified.

| AI function | Expected input | Expected output |
|---|---|---|
| Document classification | OCR/page text and file metadata | document type, language, confidence, unsupported/unknown label |
| Field extraction | classified document + pages | normalised CR/licence/name/issuer/date/IBAN/signatory/activity fields with source pages |
| Expiry/quality detection | extracted dates and visual/OCR quality metadata | expired/near-expiry/unreadable/missing-field findings |
| Consistency checking | onboarding form + all extracted fields | CR/name/activity/signatory/IBAN/licence mismatches, severity, evidence, confidence |
| Category/licence interpretation | CR activities + vendor categories + tender category | likely alignment, ambiguity, sector licences to check, human-review recommendation |
| Document applicability assistant | categories, entity type, government/regulated intent | suggested mandatory/conditional/sector/optional requirements and rationale |

The agent response must always include `confidence`, `evidence`, `missing_information`, `risk_level`, `recommended_human_action`, `prompt_version`, and `model_version`. Low confidence, conflicting fields, invalid scans, or missing authoritative verification must result in `human_review` or `request_correction`.

**Not AI-owned:** actual file upload/storage, OCR service operation, registry access, official issuer verification, document-status state machine, and final eligibility decision.

### 14.2 AI-first vendor onboarding validation

The target model is “AI validates by default; people approve exceptions.” The AI performs repeatable checks and provides a confidence/risk assessment; a deterministic policy and manager retain authority.

```text
Vendor registration data + extracted document evidence
→ document/category/duplicate/consistency analysis
→ confidence + low/medium/high risk
→ recommended outcome
→ policy and human reviewer determine status
```

The target AI outcomes are:

| AI finding pattern | AI recommendation |
|---|---|
| Complete, internally consistent, high-confidence evidence | `ready_for_policy_auto_approval` |
| Missing correctable information or low-impact conflict | `request_correction` |
| Duplicate, material mismatch, suspicious behaviour, high uncertainty | `human_review` |

Future AI checks include duplicate-company similarity, CR/legal-name/category alignment, past-project/portfolio relevance, selected-category plausibility, licence applicability, red-flag detection, and revalidation impact when sensitive fields change.

Where the vendor consents and policy permits, category-confidence evidence may also include the company profile, portfolio/project references, declared website content and Balady/sector-licence evidence. External content is supporting evidence only and needs source/date/provenance; it is not automatic verification. Basic sanctions/red-flag checking is a later feature and requires an approved authoritative data source.

### 14.3 Tender logic and buyer governance intelligence

`AICore.docx` asks AI to identify tender completeness, inconsistent criteria, conflicts of interest, and policy problems. Current Tender Health covers part of this, but future AI needs structured policy findings:

- requirement-to-evaluation-criterion traceability;
- impossible or contradictory eligibility/evaluation conditions;
- missing mandatory documents, timeline, acceptance criteria, budget or scoring controls;
- hidden/bias-prone evaluation language;
- buyer/vendor organization, user, ownership, contact, or historical interaction overlap indicators supplied by backend;
- policy compliance findings and suggested correction text.

AI flags findings with evidence; it does not decide whether a tender is legally publishable.

### 14.4 Evidence-based Vendor Selection Engine

**Source specification:** `AI Vendor Selection Engine.docx`.

The product requires tender-specific selection, not “highest VRI wins.” The future AI needs to transform an RFP and each proposal into a common evidence graph:

```text
Tender requirement ID
→ mandatory/weighted rule
→ vendor profile/proposal/document evidence
→ met | partly met | not met | uncertain
→ confidence, gap, risk, explanation
```

The planned AI functions are:

- RFP requirement extraction/normalisation;
- proposal section, price, timeline, certification, experience, and deviation extraction;
- requirement-to-evidence mapping;
- proposal completeness/clarity/scope/timeline realism analysis;
- qualitative value-for-money and anomalous-pricing signals;
- risk explanations based on verified delivery, disputes, documents and uncertain evidence;
- ranked explanation and alternatives.

Backend must enforce the approved Fit Score formula, mandatory pass/fail criteria, price policy, tender weighting, and final ranking order. AI supplies qualitative assessment/evidence and may propose a score only within defined constraints.

### 14.5 Full AI Tender Committee

**Source specification:** `AI Tender Committee Simulation.docx`.

The current five-agent committee is a foundation. The future version needs evidence-grounded specialist outputs for each vendor proposal:

| Committee agent | Future AI analysis |
|---|---|
| Technical | requirement coverage, architecture/methodology, similar-project and certification evidence, capability gaps |
| Commercial | price breakdown, assumptions, cost/value comparison, budget alignment, abnormal pricing caveats |
| Compliance/Governance | licence/document evidence, regulatory/tender compliance, declared conflicts, missing evidence |
| Delivery/Performance | delivery-plan realism, milestone risk, historic delivery/quality evidence, capacity indicators |
| Risk | disputes, profile/document uncertainty, abnormal behaviour/pricing, concentration or conflict signals |
| Orchestrator | evidence-bound aggregate, alternatives, uncertainty, explicit “buyer review required” verdict |

Future committee requirements are configurable buyer-approved weights, evidence citations, confidence per assessment, no fabricated facts, durable reviewer override/reason, and complete reproducibility from the artifact/policy/model versions.

### 14.6 VRI: Vendor Reputation Intelligence

**Source specification:** `Vendor Reputation Index (VRI).docx`.

The project has a synthetic VRI formula. The AI/data work still required is to derive and maintain evidence-based component signals:

- category-specific performance rather than a generic score offset;
- delivery reliability from accepted milestones, on-time completion, quality acceptance and corrective actions;
- compliance/licence signals from verified documents and expiry events;
- institutional verification evidence with source/status/date;
- contract history and tender-success signals from platform events;
- financial-risk indicators only when lawful, sourced, explainable and approved;
- behavioural/anomaly risk signals with false-positive review controls;
- vendor improvement recommendations explaining which evidence would improve a score.

The score engine itself should be deterministic/versioned. AI is used to extract/normalise events, identify uncertainty or anomalies, produce category intelligence, and explain scores—not to invent reputation data.

### 14.7 BRI: Buyer Reliability Intelligence

**Source specification:** `Buyer Relaiability Index (BRI).docx`.

Future BRI AI functions:

- tender-clarity scoring from structured RFP quality evidence;
- evaluation-fairness analysis: published criteria versus applied scoring, repeated selection patterns, unexplained deviations, and conflict signals;
- communication-quality/response-time insight from authorised platform interaction events;
- payment-reliability and dispute-risk summaries from verified finance/contract events;
- vendor-facing risk explanation with recent-behaviour weighting and appeal controls.

The approved BRI component definition must be reconciled before implementation. The current code formula differs from the product-intelligence document. AI must never infer payment/compliance/fairness facts without source events.

### 14.8 Ratings, badge integrity, and anti-manipulation AI

**Source specification:** `Mushtarry Reputation Badge Framework.docx`.

Future AI features include:

- contract-review text classification/summarisation into rating categories;
- outlier detection against a vendor/buyer’s historic and peer-normalised pattern;
- retaliation signal detection after blind-rating reveal, with explainable evidence;
- collusion pattern detection across repeated buyer/vendor outcomes and abnormal rating clusters;
- suspicious badge/rating manipulation flags;
- recency/contract-value/complexity signals feeding deterministic Bayesian rating normalisation;
- recovery explanations based on recent verified performance.

AI flags and prioritises review; it must not silently suppress/reweight a rating or punish an account. The backend owns blind-review timing, visibility, appeals, public-display thresholds, and final rating weight calculation.

### 14.9 AI data, evaluation, and model-operations requirements

Because there is no real production dataset yet, AI work must begin with controlled fixtures and then move to consented pilots.

1. Create synthetic Arabic, English, bilingual, low-quality-scan, expired, mismatched and missing-document test sets with expected labels.
2. Create labelled RFP/proposal fixtures with requirement-to-evidence ground truth.
3. Measure document classification, field extraction, expiry extraction, mismatch detection, eligibility recommendation, evidence precision, ranking stability, false approval/rejection, and confidence calibration.
4. Maintain model/prompt/schema/policy versions and regression evaluations before release.
5. Add human reviewer corrections/appeals to approved evaluation datasets only under documented consent and privacy controls.

### 14.10 Recommended AI delivery order

```text
1. Vendor Document Intelligence Agent
2. Evidence/consistency findings + confidence/fallback contract
3. Tender requirement normalisation
4. Proposal extraction and requirement-to-evidence mapping
5. Evidence-based evaluation and committee
6. Real event ingestion for VRI/BRI
7. Rating integrity/anomaly models and category intelligence
```

This order avoids building reputation or predictive models before the platform has trustworthy source events.

## 15. Product-intelligence AI coverage matrix

This matrix provides traceability from every unique product-intelligence document to the current implementation and planned AI work. `Vendor-Side Workflow & Policy Specification (MVP)[1].docx` is a duplicate of the non-suffixed file and is not counted separately.

| Product document | AI features required | Current coverage | Remaining AI work |
|---|---|---|---|
| `AICore.docx` | vendor/buyer registration validation, category matching, tender-logic checks, confidence/risk routing, explainability, exception-based human review | vendor demo validator, tender health, artifact/trace foundation | real document intelligence, buyer registration validation, duplicate/registry/portfolio/site/licence evidence, sanctions/red-flag adapter when approved, conflict analysis, calibrated confidence, manager-feedback evaluation |
| `AI Vendor Selection Engine.docx` | RFP structuring, eligibility prefilter, requirement/proposal/price analysis, risk adjustment, ranking, alternatives, explanations | synthetic shortlist and isolated sample evaluation | real proposal parsing, requirement evidence matrix, verified eligibility, price benchmark provenance, approved formula/version, uncertainty and clarification workflow |
| `AI Tender Committee Simulation.docx` | Technical, Commercial, Compliance, Delivery, Risk and orchestrator assessments; vendor comparison; “why selected?” | five-agent proposal committee plus deterministic baseline | verified evidence, configurable approved weights, VRI context, cross-vendor comparison that does not leak submissions, reviewer overrides and reproducibility |
| `Vendor Reputation Index (VRI).docx` | eight weighted components, category-specific VRI, institutional evidence, risk/probability/vendor-improvement insight | deterministic formula on synthetic profiles | real source events, component/cold-start policy, category history, anomaly review, versioned explanations, predictive evaluation/monitoring |
| `Buyer Relaiability Index (BRI).docx` | vendor ratings, payment, fairness, tender clarity, communication, disputes; buyer-risk and bid guidance | different synthetic BRI formula | reconcile target formula, real payment/interaction/tender/evaluation/dispute events, fairness evaluation, vendor-facing cautions, recovery/appeal controls |
| `Mushtarry Reputation Badge Framework.docx` | weighted ratings, recency/Bayesian correction, badges, blind review, outlier/retaliation/collusion detection, recovery | synthetic badges and rating fixtures | real review lifecycle, verified-event eligibility, anomaly models/evaluation, public thresholds, deterministic badge calculation and recovery explanations |
| `Vendor Document Requirements Framework.docx` | tiered document applicability/extraction/validation, category confidence, manager exception recommendation | detailed synthetic metadata plus document-type applicability demo | OCR/extraction, source evidence, issuer/expiry/name/activity checks, sector and prestige document schemas, verified adapters, uncertainty and correction messages |
| `Vendor-Side Workflow & Policy Specification (MVP).docx` | AI-first validation, category eligibility, revalidation, tender/proposal completeness support, status/risk explanations | standalone validator and synthetic eligibility profile | onboarding case integration, field-change impact analysis, live proposal completeness/evidence findings, conflict signals, production audit/human-review feedback |

## 16. Exact proposed models and unresolved specification decisions

The following values are proposals found in product-intelligence documents. They must be approved, versioned, tested and configured before production; documentation alone does not make them final policy.

### 16.1 Proposed Vendor Fit Score

`AI Vendor Selection Engine.docx` proposes:

```text
Fit Score = VRI × 40%
          + Requirement Match × 30%
          + Proposal Quality × 20%
          + Price Competitiveness × 10%
          + Risk Adjustment
```

The current demo also exposes an AI recommendation layer of Technical 50%, Financial 20%, VRI 20%, Risk 10%. These are not the same model. Product/AI must choose whether these are separate stages or consolidate them into one approved formula.

Price intelligence must assess value for money rather than “lowest price wins” and flag suspiciously low pricing with evidence/uncertainty. A market benchmark requires an approved source and timestamp.

### 16.2 Proposed Tender Committee weights

`AI Tender Committee Simulation.docx` proposes Technical 30%, Commercial 20%, Compliance 15%, Delivery 15%, Risk 10%, and VRI 10%. It also identifies buyer-configurable weights as a future enterprise feature. Backend must validate totals and retain the approved weight version; AI must not change weights.

### 16.3 Proposed VRI model

The product document proposes Performance Rating 20%, Compliance/Licences 15%, Institutional Verification 15%, Delivery 15%, Financial Strength 10%, Tender Success 10%, Contract History 10%, and AI Risk Signals 5%.

Proposed levels are 85–100 Elite, 75–84 Strategic, 65–74 Trusted, 50–64 Verified, and below 50 Under Review. Category-specific VRI, cold-start/missing-data handling, risk-signal orientation, component confidence, appeals, and score visibility still require policy.

### 16.4 Proposed BRI model

The product document proposes Vendor Ratings 25%, Payment Reliability 25%, Evaluation Fairness 20%, Tender Clarity 15%, Communication 10%, and Dispute History 5%.

Proposed levels are 85–100 Strategic Buyer, 75–84 Trusted Buyer, 65–74 Verified Buyer, 50–64 Developing Buyer, and below 50 Under Review. This conflicts with the current code’s Payment 30%, Fairness 20%, Dispute Behaviour 20%, Procurement Volume 15%, Platform Activity 10%, and Risk 5%. Reconciliation is mandatory.

Future BRI AI should support vendor protection: buyer payment/fairness risk warnings, tender-risk analysis, payment confidence, and evidence-based “whether to bid” guidance. Recent improved behaviour should receive more weight and old issues should decay under an approved recovery policy.

### 16.5 Proposed rating and badge rules

The badge framework proposes:

- review categories: Technical Capability, Delivery Timeliness, Quality, Communication, Professional Conduct;
- contract influence: value 40%, recency 40%, complexity 20%;
- recency influence: 0–12 months 100%, 12–24 months 70%, 24–36 months 40%, over 36 months 20%;
- Bayesian adjustment using platform average, minimum-review threshold, vendor average, and vendor review count;
- ratings become public after at least three completed contracts; before that show `New Vendor — Rating in Progress`;
- blind two-way ratings are revealed after both parties submit or after a 14-day window;
- badge bands: 4.6–5.0 Elite, 4.2–4.5 Trusted, 3.6–4.1 Verified, 3.0–3.5 Developing, below 3.0 Under Observation.

Badges cannot be purchased or manually granted. Only verified activity should influence them. AI may flag manipulation, retaliation, collusion and outliers, but any suppression/reweighting/penalty requires deterministic policy and a review/appeal path. Badges should update after verified ratings, contracts, compliance and trust changes and support recovery through recent improved performance.

### 16.6 Institutional and prestige document intelligence

The future document agent needs schemas for more than a generic “institutional verification.” It must classify/extract, where supplied:

- Aramco registration, vendor ID, IKTVA, prequalification;
- SEC registration and classification/approval;
- SABIC registration/vendor ID, supplier prequalification, HSE, quality/technical approval;
- STC registration/vendor code, prequalification/classification, technical/security approval, supplier agreement/NDA status;
- NEOM, Red Sea, Qiddiya, Royal Commission, PIF portfolio and major EPC/oil-and-gas prequalification evidence;
- Balady, SAMA, CST, SFDA, energy, media, sport, culture/entertainment, tourism, education/TVTC, interior/security, TGA/NCEC and other sector licences.

These are optional/conditional signals according to applicability. AI must not invent issuer recognition, treat absence of an optional document as a failure, or infer authenticity from document appearance.

### 16.7 Buyer onboarding and dual-role intelligence

`AICore.docx` covers buyer as well as vendor registration. Future AI should perform the same safe identity/document/category consistency checks for buyer organizations where relevant and help identify vendor/buyer overlap or conflicts. A dual-role organization must keep buyer/vendor evidence and operational context separated. Dual-role activation and high-risk cases remain human-governed.

### 16.8 Future procurement intelligence products

Once real, consented and verified outcome data exists, future AI may provide:

- top and high-risk vendor insights per category;
- vendor improvement simulations explaining the evidence needed to reach a target VRI band;
- tender-risk and probability-of-success models with calibration/error monitoring;
- industry performance benchmarks with privacy/minimum-cohort controls;
- deeper premium vendor insights, buyer vendor-intelligence tools and enterprise predictive analytics.

These are post-data features, not MVP claims. They require sufficient representative data, fairness/privacy review, explainability, monitoring and strict separation between prediction and procurement authority.

### 16.9 Policy conflicts to resolve before implementation

1. Vendor workflow permits Admin rejection and category `Rejected`; the document framework says no rejection in MVP and missing conditional/sector documents produce `Limited`.
2. `AICore.docx` discusses immediate low-risk auto-approval and also a manager-veto/oversight window. Choose one state machine and timeout policy.
3. Selection, recommendation and committee documents propose different weights. Define separate named score stages or one consolidated model.
4. VRI’s “AI Risk Signals” is added positively; define it explicitly as a safety score or convert it into a penalty so direction is unambiguous.
5. The current BRI formula does not match its product document.
6. “AI extracts metadata only” must be reconciled with any future need to process raw page text/images: define an approved, minimal-content processing and retention contract.
7. The selection document says `vendor category = tender category → exclude`; this is almost certainly a drafting error and should be confirmed as `not equal → exclude` before implementation.
8. `AICore.docx` uses a low-risk confidence example of at least 85%. Treat this as a configurable proposal, not a production threshold, until calibrated on labelled data.

### 16.10 Explicit AI/non-AI boundaries and MVP exclusions

Vendor financing, direct buyer/vendor messaging, public vendor marketplace profiles, and general marketplace administration are not AI deliverables in the vendor-side MVP. Advanced analytics are post-MVP. AI may support later intelligence inside those products, but the product/backend teams own their workflows, permissions, payments and external communications.

For the backend/web implementation contract, see [AI_BACKEND_WEB_INTEGRATION.md](AI_BACKEND_WEB_INTEGRATION.md).
