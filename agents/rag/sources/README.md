# RAG source documents

Editable source material for the Tender Drafting knowledge base. These are the inputs;
the built index lives in `agents/rag/corpora/tender_kb/`. Edit/extend these, then re-index.

## Contents
- `clauses/` — starter **standard clause library** (English, category-agnostic). One themed
  file per area (general terms, confidentiality, evaluation, payment, bonds, penalties,
  eligibility, submission/award, warranty, compliance). Hand-written templates, not tied to
  any past tender — safe to use immediately. Edit freely to match house style.

## How to (re)build the index
```bash
ollama pull nomic-embed-text
# Standard clause library:
python -m agents.rag.index_documents agents/rag/sources/clauses --authority policy --rebuild
# Procurement law (the buyer-provided PDF at project root):
python -m agents.rag.index_documents Government_Tenders_and_Procurement_Law.pdf --authority law
```
Use `--rebuild` on the FIRST command to start fresh; later commands append.

## Not included yet
- **Approved past tenders** — deferred until human-approved tenders exist (`--authority past_tender --approved`).
