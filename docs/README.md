# Mushtary AI Agents — Requirements & Open Questions

This document tracks everything the AI engineering team needs clarified or provided
before each agent can be fully built. Share this with the client / backend team.

---

## Agent 1 — Vendor Validation Agent

**Purpose:** Automatically validate vendor registrations by checking CR number, legal name,
category alignment, duplicates, and document completeness.

### What we need

#### 1. Amaly E-magazine Access (BLOCKER)
The MVP uses the public Amaly E-magazine as the source for Saudi CR verification.

- **Question:** Is this a scrape of a public website, a paid API, or an exported dataset?
- **If website scrape:** Provide the URL and a sample vendor lookup result (HTML or screenshot).
- **If API:** Provide API docs, base URL, auth method (API key / OAuth), and a sample response payload.
- **If dataset:** Provide a sample CSV/JSON so we can build the lookup against it.
- **Fallback plan:** What should the agent do if Amaly is unreachable? (Auto-flag? Return unknown?)

**Sample Amaly response we need to replicate (at minimum):**
```
cr_number, legal_name_ar, legal_name_en, status (active/expired), activities[], issue_date, expiry_date
```

---

#### 2. Business Category Taxonomy (BLOCKER)
The agent needs to map a vendor's CR-registered activities to platform categories.

- **Question:** What is the full approved category + subcategory list on the platform?
- The spec mentions adding: Manufacturing, Retail, IT, and all major sectors.
- **Provide:** A flat list or hierarchy of all platform categories (English + Arabic names).

**Example of what we need:**
```
Category: Information Technology
  └─ Subcategory: Software Development
  └─ Subcategory: IT Consulting
  └─ Subcategory: Cybersecurity

Category: Manufacturing
  └─ Subcategory: Food & Beverage
  └─ Subcategory: Industrial Equipment
  ...
```

---

#### 3. Required Documents List (NEEDED)
The agent checks whether a vendor has uploaded all required documents.

- **Question:** Which documents are mandatory for ALL vendors?
- **Question:** Are there conditional requirements? (e.g., VAT certificate only if revenue > X?)
- **Question:** Are there category-specific required documents?

**Known documents from spec (confirm/expand this list):**
| Document | Mandatory? | Condition |
|---|---|---|
| Commercial Registration (CR) | Yes | All vendors |
| VAT Certificate | ? | ? |
| Brand Registration Certificate | No | Only if applicable |
| Saudization (Nitaqat) Certificate | ? | ? |
| ISO Certificate | No | Optional |

---

#### 4. Duplicate Detection Rules (NEEDED)
- **Question:** Is a duplicate defined by matching CR number only, or also by legal name similarity?
- **Question:** What happens to the duplicate — auto-reject, or flag for admin review?
- **Question:** Can two separate vendor accounts exist for the same CR (e.g., different branches)?

---

#### 5. Name Matching Threshold (NEEDED)
The vendor types their legal name; the agent compares it against what Amaly returns.

- **Question:** How strict should name matching be? (exact match? fuzzy match above X% similarity?)
- **Question:** Should Arabic and English names both be matched, or just one?
- **Question:** Common case: vendor types "Al Madar Trading Co." but Amaly has "Al-Madar Trading Company" — pass or fail?

---

## Agent 2 — Tender Drafter Agent

**Purpose:** Generate detailed tender specifications in the style of Saudi Arabia procurement standards.

### What we need

#### 1. Real Saudi Tender Examples (BLOCKER — client promised to provide via email)
- **We need at minimum 3–5 examples** covering different categories (IT, Construction, Services).
- **Demo scenario confirmed:** IT Infrastructure (client recommendation — most structured for demo).
- These become few-shot examples in the prompt and define the output structure.
- **Without these, we cannot calibrate the output quality to Saudi standards.**

#### 2. Tender Field Definitions — ✅ Confirmed from client docs
- [x] Title
- [x] Scope of work / summary
- [x] Technical requirements (structured list)
- [x] Evaluation criteria with weightings (buyer sets tech/financial split — default 70/30)
- [x] Required vendor documents
- [x] Eligibility conditions
- [x] Estimated value (SAR)
- [x] Suggested submission deadline

#### 3. Language of Output (NEEDED)
- Should the AI draft tenders in English only, Arabic only, or bilingual?
- If bilingual — does the AI translate, or does a human translator handle Arabic?

---

## Agent 3 — Evaluation & Ranking Agent

**Purpose:** Score vendor submissions against tender criteria and produce a ranked recommendation list.

### ✅ Resolved from client message + vendor docs (2026-04-22)

#### Scoring Model — RESOLVED
- **Vendor Fit Score formula:**
  ```
  Fit Score = (VRI × 40%) + (Requirement Match × 30%) + (Proposal Quality × 20%) + (Price Competitiveness × 10%)
  ```
- **VRI (Vendor Reputation Index):** 8-component composite score (0–100), category-specific
- **Technical criteria scoring:** 0–10 per criterion
- **Weighted total:** buyer sets tech/financial split (default 70/30 or 60/40)

#### Technical vs Financial Weightage — RESOLVED
- Buyer configures the split per tender (e.g., 70/30, 60/40, 50/50)
- Default: **70/30** (most commonly used)
- Stored in `TenderPolicy.technical_weight_percent / financial_weight_percent`

#### Pricing Evaluation Approach — RESOLVED
- Buyer selects: `lowest_cost` | `best_value` | `custom_formula`
- Stored in `TenderPolicy.pricing_approach`
- Custom formula: buyer writes free-text instructions

#### Output Detail Level — RESOLVED
- Buyer selects: `high_level_summary` | `detailed_with_justification`
- Stored in `TenderPolicy.output_detail`

#### Disqualification Criteria — RESOLVED
- Multi-select dropdown — buyer builds their own policy
- Policies are saveable and reusable
- **Policy limit: 2 saved policies per org** (additional policies charged extra)
- Policy management is **Buyer-Admin role only** — regular users cannot change policy
- Default disqualifiers (always active):
  - Late submission
  - Missing mandatory documentation
  - Non-compliance with submission format
  - Fails minimum eligibility criteria
  - Legal/regulatory violations
  - Conflict of interest
  - Non-compliant technical specs
- Optional disqualifiers (buyer activates):
  - No bid security (bank guarantee / LC / SME certificate)
  - Non-compliant pricing
  - Insufficient experience (years, certifications, KSA presence)
  - Custom (buyer writes free-text rule)

#### Agent Isolation — RESOLVED
- ✅ Each vendor scored in isolation — agent never sees other submissions
- ✅ Agent sees: vendor VRI + submission summary (no raw documents)
- ✅ Ranking is a separate aggregation step

#### Explainability — RESOLVED
- Per-criterion score breakdown shown to buyer (when `detailed_with_justification`)
- Vendors do NOT see their own evaluation scores

### Still needed

#### VRI Data Source (BLOCKER)
- The VRI score is pre-computed and passed into the agent — but who computes it?
- **Question:** Is VRI computed by the platform from historical contract data, or is it seeded manually at launch?
- **Question:** How is VRI initialised for new vendors with no history? (default score? "New Vendor" label?)
- **Sample vendor submission + tender bid:** client promised to provide via email — needed for prompt tuning

---

## General / Infrastructure

#### LLM Provider — ✅ Resolved
- Using **local Ollama** (OpenAI-compatible endpoint via LangChain `ChatOpenAI`) — default model `qwen2.5:7b-instruct-q4_K_M`
- No API key needed locally; configuration lives in `agents/llm_config.py` (env: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`)
- RAG embeddings: `qwen3-embedding:0.6b` on the same endpoint (`agents/rag/config.py`)

#### Prompt Language — NEEDED
- Should system prompts be written in English only? (Current decision: English-only for now)
- Data localisation: resolved by running fully local — no vendor data leaves the machine

---

## Summary Checklist

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Amaly E-magazine access method + sample response | Client / Backend | ❌ Needed |
| 2 | Full platform category taxonomy | Client | ❌ Needed |
| 3 | Required documents list per vendor type | Client | ❌ Needed |
| 4 | Duplicate detection rules | Client / Product | ❌ Needed |
| 5 | Name matching tolerance rules | Product | ❌ Needed |
| 6 | Real Saudi tender examples (3–5 docs) | Client | ❌ Promised via email |
| 7 | Tender output field list confirmed | Product | ✅ Done |
| 8 | Tender language (EN / AR / bilingual) | Client | ❌ Needed |
| 9 | Scoring model + Vendor Fit Score formula | Client docs | ✅ Done |
| 10 | Tech/financial weightage model | Client | ✅ Done (default 70/30) |
| 11 | Disqualification criteria list | Client | ✅ Done |
| 12 | Pricing evaluation approach | Client | ✅ Done |
| 13 | Output detail level options | Client | ✅ Done |
| 14 | Policy limit (2 per org) + Admin-only management | Client | ✅ Done |
| 15 | VRI initialisation for new vendors | Client / Product | ❌ Needed |
| 16 | Sample vendor submission + tender bid | Client | ❌ Promised via email |
| 17 | LLM provider | Engineering | ✅ Local Ollama (qwen2.5:7b-instruct) |
| 18 | Data localisation | Legal / Client | ✅ Resolved (fully local — no data leaves the machine) |

---

*Maintained by: AI Engineering team*
*Last updated: 2026-04-22*
