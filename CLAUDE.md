# Mushtary MVP — Claude Code Context

## Wiki
Project wiki (LLM Wiki vault): `c:/Users/lenovo/Desktop/virtualip/virtualip/`
To log results or look up context: open the vault and read `wiki/_hot.md` first. Its schema is the vault's own `CLAUDE.md`.

- **When I say "ingest" / "ingest X" → run the vault's INGEST operation**: read the source into `raw/`, write a `wiki/sources/<slug>.md` summary, lightly update the entity/concept pages it touches, append any opened questions to `wiki/_gaps.md`, update `index.md`, checkpoint `wiki/_hot.md`, and append to `log.md`. Follow the vault `CLAUDE.md` (§4 INGEST) exactly — including confidence tags and the every-5th-ingest batched cross-link pass.
- "query" / a question → vault QUERY: read `_hot.md` first, ≤5 pages, cited answer; file reusable answers to `analyses/`.
- "lint" / "health-check" → vault LINT.
- Update `_hot.md` and `log.md` only at checkpoints: end of INGEST, end of LINT, or when I say "checkpoint" / "save" / "wrap up".
- Do NOT update `_hot.md` or `log.md` for QUERY-only sessions.

## Active task
Tender Drafting pipeline is the working path. `python main.py` builds a hardcoded test buyer form, runs the
drafting pipeline, and writes `tender_draft.json` + `tender_draft.pdf`. Vendor Validation, Evaluation, and
SOW Extractor agents exist but are exercised via their own modules/tests, not `main.py`. No FastAPI app exists yet.

## Project invariants
- **The one product rule:** `AI generates → Human reviews → Human approves → Action taken`. AI NEVER publishes,
  activates, or awards directly. Every AI output is a `DRAFT` artifact gated behind explicit human approval. Do not bypass.
- **LLM provider (docs say "Claude" — WRONG, trust the code):** OpenRouter, OpenAI-compatible API,
  `base_url="https://openrouter.ai/api/v1"`, via the `openai` SDK. Model `google/gemini-2.5-flash`.
  Set in `agents/base.py`, `agents/prompt_registry.py`, each `*/agent.py`, and `tender_drafting/sections/base.py` —
  keep ALL of these consistent if you change model/provider.
- **API key env var:** `gemini_API` (runner also accepts `OPENAI_API_KEY` / `OPENROUTER_API_KEY`). Key = OpenRouter key.
- **Three agents:** Vendor Validation (`vendor_validation/`, agentic 4-tool loop), Tender Drafting
  (`tender_drafting/`, structured section-by-section), Evaluation & Ranking (`evaluation/`, two-step) + SOW Extractor (`sow_extractor/`).
- **Evaluation isolation:** score each vendor ALONE (a vendor must never see another's submission); rank from scores only. Preserve.
- **Every LLM I/O is Pydantic v2** (in that agent's `schemas.py`), **passes through `guardrails.py`** before use
  (never trust raw model JSON; validate + safe fallback so the workflow never crashes).
- **Prompts** live in each agent's `prompts.py` and are **registered + versioned in `prompt_registry.py`** — bump
  the version on any prompt change. Every AI output is stored as an `AIArtifact` (`trace_id`, `type`, `status`,
  input snapshot, output, token counts) for traceability + cost tracking.
- **Stubs** in `vendor_validation/stubs.py` (`lookup_cr_amaly`, `check_duplicate_vendor`,
  `validate_category_alignment`, `check_document_completeness`) are placeholders for real integrations
  (WATHQ/Amaly, DB, taxonomy). Their return shapes are the contract when replacing them.

## Environment
- Python 3.x. Deps: `agents/requirements.txt` (`openai`, `celery[redis]`, `pydantic`, `redis`, `python-dotenv`, `PyMuPDF`).
- **Missing dep:** `main.py` imports `fpdf` → also `pip install fpdf2` (not in requirements yet).
- Secrets in `.env` at project root (git-ignored); `.env.example` shows `gemini_API`. Never commit `.env` or log the key.
- Celery + Redis wrappers in `agents/tasks.py` are scaffolding for a future FastAPI layer (not wired up).

## Pre-change audit (MANDATORY)
Before telling the user any change is ready, you MUST verify:
1. **Approval gate intact** — no code path lets the AI publish/activate/award without human approval (artifacts stay `DRAFT`).
2. **Provider/model consistent** — model + `base_url` match across ALL files in Project invariants; no stray Claude/Anthropic refs introduced.
3. **Guardrails path** — every new LLM call routes its JSON through `guardrails.py` with a safe fallback.
4. **Schema + prompt registration** — new I/O has a Pydantic schema; new/changed prompts are registered and version-bumped.
5. **Evaluation isolation** — scoring still sees one vendor at a time; ranking sees scores only.

## Code style
- Inline comments on every non-obvious decision.
- No emojis in print statements.
- `tqdm` (with a unit label) on any long-running loop.
- Return a unified diff only, unless told otherwise.
