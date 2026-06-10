# Mushtary MVP — AI Procurement Agents

AI backend for a Saudi B2B procurement/tendering platform. Local-first: all LLM calls run
against a local Ollama server — no cloud API, no key, no vendor data leaving the machine.

**The one product rule:** `AI generates → Human reviews → Human approves → Action taken.`
The AI never publishes, activates, or awards anything. Every output is a `DRAFT` artifact.

## The agents

| Agent | Folder | What it does |
|---|---|---|
| Tender Drafting | `agents/tender_drafting/` | Buyer form → full RFP draft (4 section agents in parallel via LangGraph) |
| SOW Extractor | `agents/sow_extractor/` | SoW/RFP PDF → structured buyer form (intra-document RAG for long docs) |
| Form Generator | `agents/form_generator/` | Seed/topic → complete AI-invented buyer form |
| Vendor Validation | `agents/vendor_validation/` | Vendor registration → approve / correct / flag (agentic 4-tool loop) |
| Evaluation & Ranking | `agents/evaluation/` | Bids → isolated per-vendor scores → ranked recommendation |

A local RAG layer (`agents/rag/`) grounds the drafting agents on a standard clause library and
the Saudi Government Tenders and Procurement Law (corpus in `agents/rag/corpora/tender_kb/`).

## Setup

```bash
# 1. Install Ollama (https://ollama.com), then pull the models:
ollama pull qwen2.5:7b-instruct-q4_K_M     # generation
ollama pull qwen3-embedding:0.6b           # RAG embeddings

# 2. Python deps (Python 3.11+):
pip install -r agents/requirements.txt

# 3. (Optional) copy .env.example to .env to override model/endpoint.
```

Configuration lives in `agents/llm_config.py` and `agents/rag/config.py` — env overrides:
`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `RAG_EMBED_MODEL`.

## Run

```bash
python run.py                                   # full pipeline, AI invents the buyer form
python run.py --seed "hospital MRI supply"      # steer the topic
python run.py --mode form --seed "solar O&M"    # buyer form only
python run.py --mode extract --sow some_rfp.pdf # SoW PDF -> buyer form
python run.py --mode scope --seed "catering"    # one drafting section alone
python run.py --mode validate --input vendor.json
python run.py --mode score    --input scoring.json
python run.py --mode rank     --input ranking.json
```

Outputs land in `outputs/` (JSON + rendered PDF for full mode).
`main.py` is the legacy demo entry (hardcoded IT test form); the PDF renderer is `pdf_renderer.py`.

## Tests

```bash
python -m unittest discover -s agents/tests -v
```

Covers: prompt-registry consistency (names + versions), guardrails fallback behavior, and
RAG fail-safe paths (no Ollama required).

## Rebuilding the RAG corpus

```bash
python -m agents.rag.index_documents agents/rag/sources/clauses --authority policy --rebuild
python -m agents.rag.index_documents Government_Tenders_and_Procurement_Law.pdf --authority law
```

Only index human-approved material — never un-approved AI drafts.

## Project docs

- `docs/ARCHITECTURE.md` — agent flows and shared infrastructure
- `docs/README.md` — open blockers / client questions
- `CLAUDE.md` — working context for AI-assisted development
