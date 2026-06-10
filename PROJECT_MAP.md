# Mushtary MVP — Project Map

A navigable index of every file. Status tags: **[ACTIVE]** in use · **[LEGACY]** kept for
back-compat, not on the main path · **[DOC]** documentation (some stale) · **[OUTPUT]** generated
artifact · **[CONFIG]** · **[STUB]** placeholder for a real integration · **[PROMPT]** model prompt text.

> New here? Start at [run.py](run.py) (the CLI) and [agents/llm_config.py](agents/llm_config.py)
> (model/provider config). Pipeline: `run.py → agents/graph → agents/*`. **All prompts live as
> individual files in [agents/prompts/](agents/prompts/).**

---

## 1. "Where do I find…?" (by task)

| I want to… | Go to |
|---|---|
| Run the app / pick a mode | [run.py](run.py) · modes in [agents/graph/modes.py](agents/graph/modes.py) |
| Change the model / endpoint / key | [agents/llm_config.py](agents/llm_config.py) or `.env` (see [.env.example](.env.example)) |
| **Edit a model prompt** | **[agents/prompts/](agents/prompts/)** — one `.md` per prompt (no code change needed) |
| Edit the LangGraph pipeline | [agents/graph/pipeline.py](agents/graph/pipeline.py) |
| Change the buyer-input fields | [agents/buyer_form.py](agents/buyer_form.py) (fields doc'd in [docs/Input Fields.docx](docs/)) |
| Tune how the AI writes a section | prompt: [agents/prompts/](agents/prompts/) `drafting_*` · logic: [agents/tender_drafting/sections/](agents/tender_drafting/sections/) |
| Change autonomous form generation | prompt: `agents/prompts/form_generator_system.md` · logic: [agents/form_generator/agent.py](agents/form_generator/agent.py) |
| Edit vendor validation / its tools | [agents/vendor_validation/agent.py](agents/vendor_validation/agent.py) · stubs in [stubs.py](agents/vendor_validation/stubs.py) |
| Edit evaluation scoring / ranking | [agents/evaluation/agent.py](agents/evaluation/agent.py) · prompts `agents/prompts/evaluation_*` |
| Extract a tender from a PDF | [agents/sow_extractor/agent.py](agents/sow_extractor/agent.py) |
| Add/inspect a data schema | each agent's `schemas.py` (+ [tender_drafting/schemas.py](agents/tender_drafting/schemas.py)) |
| See/raise prompt versions | [agents/prompt_registry.py](agents/prompt_registry.py) + each agent's `prompts.py` |
| Change the PDF layout | [main.py](main.py) (`build_pdf` / `TenderPDF`) |
| Read the data-flow diagrams | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ⚠ stale on provider |
| Find generated tenders/reports | [outputs/](outputs/) |
| Install deps | [agents/requirements.txt](agents/requirements.txt) |

---

## 2. Top-level layout

```
run.py            [ACTIVE] unified CLI (LangGraph modes)
main.py           [LEGACY] demo entry + PDF renderer (build_pdf)
PROJECT_MAP.md    this file
CLAUDE.md         [DOC] agent context (harness-protected; §3 provider note stale)
.env / .env.example / .gitignore   [CONFIG]
agents/           the Python package (all code)
docs/             [DOC] ARCHITECTURE.md, README.md, Input Fields.docx
outputs/          [OUTPUT] generated JSON/PDF (git-ignored)
```

## 3. `agents/` — the package

```
agents/
  llm_config.py        [CONFIG] single source of truth for provider/model/key (Ollama)
  base.py              [ACTIVE] BaseAgent + AIArtifact
  guardrails.py        [ACTIVE] validate LLM JSON → safe fallback
  prompt_registry.py   [ACTIVE] versioned prompt catalog (names/versions)
  buyer_form.py        [ACTIVE] TenderBuyerForm (the buyer input)
  categories.py        [ACTIVE] 20-sector taxonomy
  tasks.py             [LEGACY] Celery/Redis wrappers (future FastAPI; not wired)
  example_buyer.py     [DOC] a non-IT TenderBuyerForm reference snippet
  requirements.txt     [CONFIG] dependencies

  prompts/             [PROMPT] one file per model prompt + loader
    __init__.py        load_prompt(slug) / list_prompts()
    vendor_validation_system.md
    evaluation_scoring_system.md
    evaluation_ranking_system.md
    sow_extractor_system.md
    form_generator_system.md
    drafting_context_narrative_system.md
    drafting_scope_system.md
    drafting_execution_system.md
    drafting_legal_eval_system.md
    drafting_legacy_full_system.md   (legacy single-call 16-section prompt)

  graph/               [ACTIVE] LangGraph orchestration
    pipeline.py        form_source → [context|scope|execution|legal_eval] → assemble
    modes.py           run any agent alone / all together
    state.py           TenderState

  form_generator/      [ACTIVE] AI invents a full buyer form (no-input mode)
  vendor_validation/   [ACTIVE] tool-use loop; stubs.py [STUB] = WATHQ/Amaly/DB
  tender_drafting/     agent.py [LEGACY threadpool]; sections/ [ACTIVE, AI-driven]
  evaluation/          [ACTIVE] score→rank (vendor isolation); schemas.py has VRI/policy
  sow_extractor/       [ACTIVE] PDF/RFP → buyer form

  samples/             [ACTIVE] mock data + run_demo.py (evaluation end-to-end)
  tests/               only __init__.py (no real tests yet)
```

Per agent folder: `agent.py` (logic) · `prompts.py` (versions + user-message builder, loads system
prompt text from `agents/prompts/*.md`) · `schemas.py` (Pydantic I/O).

## 4. How prompts work now

Every system/instruction prompt is a standalone file in [agents/prompts/](agents/prompts/). Code loads
it with `load_prompt("<slug>")` — e.g. `agents/prompts.py` modules do
`SYSTEM_PROMPT = load_prompt("vendor_validation_system")`. The dynamic per-request **user** messages
(which inject form data) remain as `build_user_message(...)` functions in each `prompts.py`/agent —
those are request formatting, not stored prompts. Edit a prompt by editing its `.md`; bump the
version in `prompt_registry.py` / the agent's `prompts.py` per the CLAUDE.md convention.

## 5. Notes / remaining cleanups (optional)

- Shared infra (base/guardrails/llm_config/…) lives at `agents/` top level — standard for a package;
  not moved to avoid breaking imports + the (protected) CLAUDE.md path references.
- `docs/ARCHITECTURE.md` & `docs/README.md` are **stale** on the LLM provider (say Claude/OpenRouter;
  reality is local Ollama). Content kept as history; file links fixed for the new location.
- Legacy: `main.py` (ThreadPoolExecutor) and Celery `tasks.py` still exist, not wired to the graph.
- Could add real tests under [agents/tests/](agents/tests/).
