# RAG source documents

Editable source material for the Tender Drafting knowledge base. These are the inputs;
the built index lives in `agents/rag/corpora/tender_kb/`. Edit/extend these, then re-index.

The indexer reads **.pdf, .docx, .md, .txt**.

## What's indexed (206 chunks total)
- **Clause library** (`clauses/`, `--authority policy`, 27 chunks) — hand-written standard
  English clauses (general terms, confidentiality, evaluation, payment, bonds, penalties,
  eligibility, submission/award, warranty, compliance). Edit freely to match house style.
- **Procurement law** (`--authority law`, 72 chunks) — Saudi Government Tenders and
  Procurement Law, from `docs/Government_Tenders_and_Procurement_Law.pdf`.
- **Past tenders** (`--authority past_tender`, 107 chunks) — real published English RFPs in
  `docs/` used as drafting precedent: SEVEN's F&B operator RFP, RFP Culture & Engagement,
  RFPF Food Supply, Catering Management (Al Naseer), Scope of Work Board Annual Report.

## How to (re)build the index
```bash
ollama pull qwen3-embedding:0.6b
# 1) Standard clause library (start fresh):
python -m agents.rag.index_documents agents/rag/sources/clauses --authority policy --rebuild
# 2) Procurement law:
python -m agents.rag.index_documents "docs/Government_Tenders_and_Procurement_Law.pdf" --authority law
# 3) Real past tenders (English) — append each:
python -m agents.rag.index_documents "docs/149.2024 - SEVEN's in attractions FB RFP.pdf" --authority past_tender --approved
python -m agents.rag.index_documents "docs/RFP_Culture & Engagement.pdf" --authority past_tender --approved
python -m agents.rag.index_documents "docs/RFPF-Food Supply Riyadh Season-Aug'24.pdf" --authority past_tender --approved
python -m agents.rag.index_documents "docs/Catering Management-Al naseer Club.docx" --authority past_tender --approved
python -m agents.rag.index_documents "docs/Scope of Work for Board Annual Report 2025 - Final.docx" --authority past_tender --approved
```
Use `--rebuild` only on the FIRST command; the rest append.

## Held out (intentionally)
- **Arabic tenders** in `docs/` (`تقديم خدمات إعاشة…`, `كراسة الشروط والمواصفات`) — excluded
  while the platform is English-only, to avoid polluting English retrieval. Index them later
  with `--authority past_tender --approved` if Arabic support is added.
- The duplicate `RFPF-Food Supply…-1.pdf` is skipped (identical to the non-`-1` copy).

## Also useful as test inputs
The same real RFP PDFs in `docs/` are good inputs for the **SOW Extractor** — upload one in
the demo UI's "Extract from PDF" tab to see a buyer form pulled out of a real tender.
