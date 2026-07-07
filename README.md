# Mushtary MVP - AI Procurement Agents

AI backend and local demo UI for a Saudi B2B procurement/tendering platform.

The system is local-first by default: generation runs through Ollama using `qwen3:4b`,
and RAG embeddings use `qwen3-embedding:0.6b`. Gemini support exists in config for
temporary API use, but the normal project path is local Ollama.

**Product rule:** `AI generates -> Human reviews -> Human approves -> Action taken.`
The AI never publishes, activates, or awards anything. Every generated tender is a
`DRAFT` until a Buyer Admin approves it.

## What was added

- Two tender drafting modes in the web UI:
  - Quick Prompt mode: one short idea becomes a full tender.
  - Project + SoW Guided mode: user enters project name and scope, Qwen reviews/rewrites
    the scope, then the user generates the tender from the approved scope.
- Tender form controls in the UI:
  - template selector for `Modern B/W` and `Premium B/W`
  - category/subcategory dropdowns
  - tender type, procurement method, dates, evaluation split, minimum score
  - checkboxes for commercial protections and vendor requirements
- Tender Health Committee:
  - Scope Clarity Agent
  - Commercial Clarity Agent
  - Compliance Readiness Agent
  - Vendor Participation Agent
  - Aggregator Agent
- AI Tender Committee:
  - Technical Agent
  - Commercial Agent
  - Compliance Agent
  - Delivery Agent
  - Risk Agent
  - Final AI recommendation score and improvement priorities
- Health feedback loop:
  - The health/AI committee output can be applied to the current generated tender.
  - It edits the existing tender artifact through `/api/jobs/improve-tender`.
  - It does not dump feedback into the SoW field or create a separate guided draft.
- Formal tender PDF design:
  - template selection between `modern_bw` and `premium_bw`
  - modern Saudi-green cover page, formal tender hierarchy, table of contents, headers,
    footers, page numbers, AI draft watermark, and final thank-you page
  - premium classic layout with traditional tables, serif typography, and restrained styling
  - Tender Data Sheet directly after cover page
  - formal hierarchy: Section 1 Document Governance, Section 2 Bidder Requirements,
    Section 3 Project Requirements, Section 4 Commercial, Legal, and Approval
  - richer payment section with payment schedule tables, invoice requirements, payment
    controls, tax/currency, retention/withholding, and timeline
  - Approval block, signature/stamp section, trace ID, version/status controls
- Health review stays on the website only; it is not included inside the issued tender PDF.
- Temporary buyer logo support:
  - Put a logo image at `assets/buyer_logo.png`, or
  - pass `buyer_logo_path` in tender metadata / tender data sheet.
- More resilient JSON parsing for local model responses, including accidental JSON lists.
- Drafting prompts are hierarchy-aware and aligned with the current renderer:
  - context prompt feeds Section 1.3-1.5
  - scope prompt feeds Section 3.1-3.3
  - execution prompt feeds Section 3.4-3.6
  - legal/evaluation/payment prompt feeds Section 4.1-4.5
  - legal prompt uses the RAG clause library and requires table-ready payment detail

## Agents

| Agent | Folder | Purpose |
|---|---|---|
| Form Generator | `agents/form_generator/` | Turns a short seed/topic into a full buyer form. |
| SoW Review | `agents/sow_review/` | Scores and rewrites a user-written scope before tender generation. |
| SoW Extractor | `agents/sow_extractor/` | Turns SoW text/PDF into a structured buyer form. |
| Tender Drafting | `agents/tender_drafting/` | Expert section agents write the tender sections. |
| Tender Health Committee | `agents/tender_intelligence/` | Multi-agent review of quality, risk, compliance, and participation. |
| Vendor Validation | `agents/vendor_validation/` | Vendor registration validation through a tool-use loop. |
| Evaluation & Ranking | `agents/evaluation/` | Scores bids in isolation, then ranks vendors. |
| RAG | `agents/rag/` | Clause/law knowledge base and embeddings. |

## Tender drafting pipelines

### Mode 1: Quick Prompt

```text
User short prompt
  -> Form Generator Agent
  -> Expert tender section agents
  -> Tender assembler
  -> Tender Health Committee
  -> Formal PDF + frontend preview
```

Example input:

```text
hospital MRI machine supply and installation
```

The system invents a complete buyer form from the seed, then drafts the tender.

### Mode 2: Project + SoW Guided Mode

```text
Project name + user-written scope
  -> SoW Review Agent
  -> User reviews/edits rewritten scope
  -> SoW Extractor creates buyer form
  -> Expert tender section agents
  -> Tender assembler
  -> Tender Health Committee
  -> Formal PDF + frontend preview
```

This mode is better when the buyer already knows the project and wants control over
the scope before the full tender is generated.

### Health feedback loop

After generation, the Tender Health Committee may flag weak areas, for example:

- missing project objective
- empty deliverables
- missing acceptance criteria
- missing total duration or milestones
- missing mandatory vendor documents

The frontend button **Apply Health Feedback to Tender** sends the current tender plus
the health and AI committee findings to `/api/jobs/improve-tender`. The backend edits
the existing tender artifact and returns an improved tender preview/PDF candidate.

This loop does not add a new prompt to the Scope of Work field and does not start a new
guided draft. It is intended to improve the tender that was already generated.

## Tender section agents

The final tender is not written by one giant prompt. It is assembled from specialist
section agents:

| Section agent | Writes |
|---|---|
| Context Agent | Metadata, Tender Data Sheet, introduction, instructions to bidders, award rules, proposal format. |
| Scope Agent | Project overview, objectives, scope of work. |
| Execution Agent | Deliverables, timeline, team requirements, reporting, escalation. |
| Legal / Evaluation Agent | Terms and conditions, confidentiality, evaluation methodology, payment terms, annexures. |

The assembler combines these into one `TenderDraft`, then platform rules are enforced
deterministically so Mushtarry submission, work order, deliverable, and invoice controls
are always present.

## Tender Health Committee

The health committee reviews the generated tender after assembly.

| Health agent | Evaluates |
|---|---|
| Scope Clarity Agent | Objective, deliverables, milestones, acceptance criteria, technical clarity. |
| Commercial Clarity Agent | Pricing, payment basis, invoice controls, commercial proposal requirements. |
| Compliance Readiness Agent | Eligibility, mandatory documents, submission controls, buyer approval controls. |
| Vendor Participation Agent | Risk of vendor questions and likely market participation. |
| Aggregator Agent | Final score, risk summary, publish readiness, improvement priorities. |

The frontend shows the health score, agent summaries, reasoning summaries, findings,
evidence, recommendations, and missing/weak requirements.

## Why agents output JSON instead of Markdown

The drafting agents return structured JSON because the tender is assembled, validated,
scored, and rendered section by section.

JSON lets the app reliably read fields such as:

- `scope_of_work.categories`
- `deliverables.deliverables`
- `timeline.milestones`
- `evaluation_criteria.mandatory_criteria`
- `payment_terms`
- `tender_intelligence`

Markdown is better as a final presentation format, but it is fragile as an internal
agent contract: headings can change, tables can break, and required sections are harder
to validate. Mushtarry therefore uses JSON for agent outputs, then renders that JSON
into a professional PDF and frontend preview.

## Tender PDF output

The generated PDF is designed to feel like a formal tender package that a buyer can
review before issuing to vendors.

There are two selectable templates:

| Template | Purpose |
|---|---|
| `modern_bw` | Saudi-green modern tender package with a SCA-inspired cover, formal hierarchy, structured tables, grouped table of contents, draft watermark, footer, and final thank-you page. |
| `premium_bw` | Classic procurement style with serif typography, traditional tables, conservative spacing, and formal bolding. |

The modern template includes:

- Cover page with project name, request number, version, issue date, publisher, and
  copyright information.
- Tender Data Sheet immediately after the cover page.
- Grouped table of contents, for example `Section 1: Document Governance` with
  numbered entries underneath.
- Formal hierarchy across governance, bidder requirements, project requirements, and
  commercial/legal/approval sections.
- Structured tables for Tender Data Sheet, submission rules, evaluation criteria,
  payment schedule, invoice requirements, payment controls, and approval.
- AI-generated draft watermark in the upper-left area of content pages.
- Green rule styling and header/footer treatments; health and committee results stay
  in the website and are not rendered into the tender PDF.
- Final thank-you page that is excluded from the table of contents.

Logo behavior:

```text
assets/buyer_logo.png
```

If this file exists, it is used on the cover page. If no logo is found, the renderer
falls back to a simple initials box based on the buyer entity name.

## Setup

Install Ollama, then pull the local models:

```bat
ollama pull qwen3:4b
ollama pull qwen3-embedding:0.6b
```

Install Python dependencies:

```bat
uv sync
```

Or, if not using `uv`:

```bat
pip install -r agents\requirements.txt
```

Optional local environment file:

```bat
copy .env.example .env
```

Recommended local `.env`:

```env
LLM_PROVIDER="ollama"
LLM_BASE_URL="http://localhost:11434/v1"
LLM_MODEL="qwen3:4b"
LLM_API_KEY="ollama"
RAG_EMBED_MODEL="qwen3-embedding:0.6b"
```

## Run the web demo

From the project root:

```bat
uv run python api.py
```

Open:

```text
http://localhost:8000
```

If port `8000` is already busy:

```bat
netstat -ano | findstr :8000
taskkill /PID THE_PID_HERE /F
uv run python api.py
```

## How to use the UI

### Draft Tender

Before generating, set the tender controls at the top of the Draft Tender tab:

- template design (`Modern B/W` or `Premium B/W`)
- category and subcategory
- tender type and procurement method
- issue date, submission deadline, evaluation split, and minimum score
- required vendor documents and commercial protections

Then use either:

- **Quick Prompt:** enter a short topic and click **Run Full Pipeline**.
- **Project + SoW Guided Mode:** enter project name and scope, click
  **Evaluate / Rewrite SoW**, edit if needed, then click
  **Generate Tender From Approved SoW**.

After the tender is generated:

- Review the frontend preview.
- Download PDF or JSON.
- Review Tender Health Score.
- Review AI Tender Committee scores and improvement priorities.
- Use **Apply Health Feedback to Tender** if the health or AI committee finds gaps.

### Extract from PDF

Upload an SoW/RFP PDF.

- **Extract Buyer Form:** only extracts the structured form.
- **Full Pipeline: Extract -> Draft Tender:** extracts and then generates the tender.

### Vendor Validation

Runs the vendor validation agent over:

- CR number
- legal names
- selected category
- uploaded document types

Returns approve/correct/flag-style output for human admin review.

### Evaluate & Rank

Runs the bundled sample bid evaluation:

```text
each vendor scored in isolation -> ranking sees only scores -> recommendation
```

### Knowledge Base

Searches the local RAG corpus used by the drafting agents.

## CLI commands

```bat
uv run python run.py
uv run python run.py --seed "hospital MRI supply"
uv run python run.py --mode form --seed "solar O&M"
uv run python run.py --mode extract --sow some_rfp.pdf
uv run python run.py --mode scope --seed "catering"
uv run python run.py --mode validate --input vendor.json
uv run python run.py --mode score --input scoring.json
uv run python run.py --mode rank --input ranking.json
```

Outputs are written to `outputs/`.

## What to expect

Generated files are organized under `outputs/`:

| Folder | Contents |
|---|---|
| `outputs/tenders/` | Generated tender JSON and PDF files, including modern/premium previews. |
| `outputs/evaluation/` | Vendor evaluation and ranking outputs. |
| `outputs/forms/` | Extracted or generated buyer forms. |
| `outputs/legacy_demo/` | Legacy demo artifacts kept for comparison. |
| `outputs/uploads/` | Uploaded PDFs/files used by the local demo. |

Typical tender outputs look like:

```text
outputs/tenders/tender_<job_id>.json
outputs/tenders/tender_<job_id>.pdf
outputs/tenders/preview_modern_bw.pdf
outputs/tenders/preview_premium_bw.pdf
```

Local Qwen generation can take several minutes because the app runs multiple drafting,
health, and improvement agents. The browser job panel shows progress while the backend
works.

## Tests and checks

```bat
node --check frontend\app.js
uv run python -B -m py_compile api.py pdf_renderer.py agents\tender_drafting\schemas.py agents\tender_drafting\sections\legal_eval.py agents\tender_intelligence\health.py
uv run python -m unittest discover -s agents\tests -v
```

## RAG corpus

The local RAG layer grounds drafting agents on clause/policy/law material.

Rebuild examples:

```bat
uv run python -m agents.rag.index_documents agents/rag/sources/clauses --authority policy --rebuild
uv run python -m agents.rag.index_documents "docs/Government_Tenders_and_Procurement_Law.pdf" --authority law
```

Only index human-approved material. Do not index unapproved AI drafts.

## Key files

| File | Purpose |
|---|---|
| `api.py` | FastAPI demo backend and async job manager. |
| `frontend/` | Local browser UI. |
| `agents/graph/pipeline.py` | LangGraph tender drafting pipeline. |
| `agents/tender_drafting/sections/` | Expert section agents. |
| `agents/tender_intelligence/` | Tender Health Committee and AI Tender Committee scoring. |
| `agents/sow_review/` | Guided SoW review/rewrite agent. |
| `pdf_renderer.py` | Modern and premium tender PDF renderer. |
| `assets/buyer_logo.png` | Optional temporary buyer logo used on the tender PDF cover. |
| `agents/prompts/` | System prompts for drafting and health agents. |
| `agents/prompt_registry.py` | Prompt registry and versions. |

## Notes

- Local Qwen 3 4B can be slow on laptop GPUs; full tender generation can take minutes.
- Gemini API support exists but may hit free-tier request limits quickly because the
  pipeline uses multiple agents.
- Keep API keys only in `.env`; never commit real keys.
