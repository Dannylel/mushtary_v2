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
- Tender Health Committee:
  - Scope Clarity Agent
  - Commercial Clarity Agent
  - Compliance Readiness Agent
  - Vendor Participation Agent
  - Aggregator Agent
- Health feedback loop:
  - The health output can be applied back into the guided prompt/SoW.
  - This does not rewrite the whole tender.
  - It appends targeted missing requirements such as objective, deliverables, acceptance
    criteria, timeline, and mandatory documents.
- Formal tender PDF design:
  - Cover page
  - Tender Data Sheet
  - Draft / Pending Buyer Approval status
  - Headers, footers, page numbers, watermark
  - Approval block, signature/stamp section, trace ID, version/status controls
- More resilient JSON parsing for local model responses, including accidental JSON lists.

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

The frontend button **Apply Health Feedback to Prompt** copies these findings back into
the guided SoW prompt. This is a low-usage correction loop because it does not call the
LLM to rewrite the entire tender. The user can review the patched prompt and regenerate.

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

Use either:

- **Quick Prompt:** enter a short topic and click **Run Full Pipeline**.
- **Project + SoW Guided Mode:** enter project name and scope, click
  **Evaluate / Rewrite SoW**, edit if needed, then click
  **Generate Tender From Approved SoW**.

After the tender is generated:

- Review the frontend preview.
- Download PDF or JSON.
- Review Tender Health Score.
- Use **Apply Health Feedback to Prompt** if the health committee finds gaps.

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

## Tests and checks

```bat
node --check frontend\app.js
uv run python -m py_compile api.py agents\llm_config.py agents\sow_review\agent.py agents\sow_extractor\agent.py agents\tender_intelligence\health.py agents\tender_drafting\sections\base.py
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
| `agents/tender_intelligence/` | Tender Health Committee. |
| `agents/sow_review/` | Guided SoW review/rewrite agent. |
| `pdf_renderer.py` | Formal tender PDF renderer. |
| `agents/prompts/` | System prompts for drafting and health agents. |
| `agents/prompt_registry.py` | Prompt registry and versions. |

## Notes

- Local Qwen 3 4B can be slow on laptop GPUs; full tender generation can take minutes.
- Gemini API support exists but may hit free-tier request limits quickly because the
  pipeline uses multiple agents.
- Keep API keys only in `.env`; never commit real keys.
