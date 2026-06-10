# Tender Drafting knowledge base

This folder holds the persisted RAG corpus the Tender Drafting section agents retrieve from.
It is **empty until you populate it** — until then, drafting runs exactly as before (no
reference excerpts injected), so nothing breaks.

## Files (created automatically once you index)
- `vectors.npy` — float32 embedding matrix
- `chunks.jsonl` — one JSON object per chunk: `{"text": ..., "metadata": {...}}`

(Both are build artifacts — consider git-ignoring them and rebuilding from sources.)

## What to populate it with
1. **Approved past tenders** — real RFPs that were human-approved. Best precedent for
   structure and wording. Index with `--approved --authority past_tender`.
2. **Standard clause library** — vetted legal/eval/payment/penalty/confidentiality clauses
   (one clause or clause-group per file works well). `--authority policy`.
3. **Procurement rules / law text** — the regulations the draft must respect.
   `--authority law`.

## How to build it
```bash
ollama pull nomic-embed-text          # one-time: pull the local embedding model
python -m agents.rag.index_documents path/to/approved_tenders --approved --authority past_tender
python -m agents.rag.index_documents path/to/clauses          --authority policy
python -m agents.rag.index_documents path/to/regulations.pdf  --authority law
```
Use `--rebuild` on the first call to start fresh; later calls append.

## Rule (project invariant)
Only index **human-approved** material. Never index un-approved AI drafts — the model would
learn to imitate its own un-vetted output. Retrieved excerpts are used for **style and
standard wording only**; the buyer brief remains the single source of facts.
