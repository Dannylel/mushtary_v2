# Graph Report - mushtarry-AI  (2026-09-14)

## Corpus Check
- 134 files · ~175,842 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .css 1)

## Summary
- 1254 nodes · 3419 edges · 66 communities (57 shown, 1 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 264 edges (avg confidence: 0.92)
- Token cost: 847,454 input · 0 output

## Community Hubs (Navigation)
- Evaluation Ranking Agent
- Buyer Form Schemas
- Category Taxonomy & Demo Engine
- Legacy Entry Point & PDF Rendering
- Tender Drafting Prompts & KSA Standards
- Buyer Account & Demo Profiles
- Tender Health Aggregation
- Tender Buyer Form Sections
- Frontend Activity & Table UI
- Tender Drafting LangGraph Pipeline
- Frontend Rendering Helpers
- Activity Feed & Observability
- Prompt Registry & AI Events API
- Vendor Validation Agent
- LLM Config & Circuit Breaker
- Frontend Committee & Draft Approval UI
- Tender KB Singleton & Clause Schemas
- Tender Draft Assembly & Platform Policy
- Agent Mode Dispatch & Execution Schemas
- Vendor Committee LangGraph
- Marketplace Proposal Comparison
- Base Agent & Artifact Model
- RAG Text Chunking
- RAG Vector Store
- Vendor Document Requirements Assessment
- Artifact Store Persistence
- Output Guardrails & Validation
- AI Governance & Vendor Recommendation Formula
- Marketplace Tender Storage
- SOW Review Agent
- Mushtary AI Agents Architecture Overview
- Standard Tender Clause Library
- Tender Consistency & Compliance Gate
- Frontend Draft Field Overrides
- RAG Configuration & Knowledge Base
- Knowledge Base Indexing Script
- AI Operations & Backend Integration
- Demo Presentation Guide Generator
- Saudi Procurement Law & Regulations
- Embedding Generation
- Python Dependencies
- Prompt Registry Consistency Tests
- RAG Fail-Safe Retrieval Tests
- SEVEN's F&B Attractions RFP
- Mushtarry MVP Guide & Reputation Indices
- Frontend AI Committee & Health UI
- Tender Revision Change Tracking
- JCSA Food Supply RFP (Riyadh Season)
- LangChain Streaming Activity Callback
- AFC Asian Cup Engagement RFPs
- AI Agents Open Questions & Vendor Fit Score
- Statutory Proposal Assessment Criteria
- SCA Hospitality Framework RFP
- Frontend Reputation Hub UI
- LLM JSON Repair Utilities
- Activity Log Handler
- Input Sanitization
- Hero Background Image Asset

## God Nodes (most connected - your core abstractions)
1. `TenderBuyerForm` - 78 edges
2. `emit()` - 52 edges
3. `esc()` - 39 edges
4. `build_pdf()` - 36 edges
5. `EvaluationRankerAgent` - 30 edges
6. `_safe_text()` - 30 edges
7. `safe_parse()` - 25 edges
8. `TenderPDF` - 25 edges
9. `AIArtifact` - 22 edges
10. `SoWExtractorAgent` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Draft Tender View / Buyer Form` --semantically_similar_to--> `Confidentiality & Data Protection Clause`  [INFERRED] [semantically similar]
  frontend/index.html → agents/rag/sources/clauses/02_confidentiality.md
- `Draft Tender View / Buyer Form` --semantically_similar_to--> `Evaluation Methodology Clause`  [INFERRED] [semantically similar]
  frontend/index.html → agents/rag/sources/clauses/03_evaluation_methodology.md
- `Draft Tender View / Buyer Form` --semantically_similar_to--> `Payment Terms Clause`  [INFERRED] [semantically similar]
  frontend/index.html → agents/rag/sources/clauses/04_payment_terms.md
- `Draft Tender View / Buyer Form` --semantically_similar_to--> `Bid Security, Performance Bonds & Guarantees Clause`  [INFERRED] [semantically similar]
  frontend/index.html → agents/rag/sources/clauses/05_bid_security_and_bonds.md
- `Draft Tender View / Buyer Form` --semantically_similar_to--> `Delay, Liquidated Damages & Penalties Clause`  [INFERRED] [semantically similar]
  frontend/index.html → agents/rag/sources/clauses/06_liquidated_damages_and_penalties.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Tender Health Committee Review Pipeline** — agents_prompts_tender_health_scope_system, agents_prompts_tender_health_commercial_system, agents_prompts_tender_health_compliance_system, agents_prompts_tender_health_participation_system, agents_prompts_tender_health_aggregator_system [EXTRACTED 0.90]
- **Tender Drafting Section Agent Pipeline** — agents_prompts_drafting_context_narrative_system, agents_prompts_drafting_scope_system, agents_prompts_drafting_execution_system, agents_prompts_drafting_legal_eval_system [EXTRACTED 0.90]
- **Vendor Evaluation and Ranking Flow** — agents_prompts_evaluation_scoring_system, agents_prompts_evaluation_ranking_system, readme_evaluation_ranking_flow [EXTRACTED 0.85]
- **Tender Drafting RAG Knowledge Base** — agents_rag_corpora_tender_kb_readme, agents_rag_sources_readme, agents_rag_sources_clauses_01_governing_law_and_general, agents_rag_sources_clauses_02_confidentiality, agents_rag_sources_clauses_03_evaluation_methodology, agents_rag_sources_clauses_04_payment_terms, agents_rag_sources_clauses_05_bid_security_and_bonds, agents_rag_sources_clauses_06_liquidated_damages_and_penalties, agents_rag_sources_clauses_07_eligibility_and_qualifications, agents_rag_sources_clauses_08_submission_and_award, agents_rag_sources_clauses_09_warranty_delivery_and_acceptance, agents_rag_sources_clauses_10_compliance_localization_and_conduct [INFERRED 0.85]
- **Human-Approval-Gated Multi-Agent Pipeline** — docs_architecture_vendor_validation_agent, docs_architecture_tender_drafting_agent, docs_architecture_evaluation_ranking_agent, docs_architecture_aiartifact, docs_architecture_governance_rule [EXTRACTED 1.00]
- **Reputation & Fit-Score Formulas Requiring Version Reconciliation** — docs_project_guide_vri, docs_project_guide_bri, documentation_ai_project_reference_vri, documentation_ai_project_reference_bri, docs_readme_vendor_fit_score, documentation_ai_project_reference_vendor_fit_score [INFERRED 0.85]
- **Mushtary AI Advisory Committee Pipeline** — docs_mushtary_demo_presentation_guide_tender_health_committee, docs_mushtary_demo_presentation_guide_ai_tender_committee, docs_mushtary_demo_presentation_guide_vendor_proposal_committee [EXTRACTED 1.00]
- **Shared Saudi Statutory Document Requirements Pattern** — docs_taqdim_khadamat_iaasha_sca_08_aug_24_statutory_documents_requirement, docs_karasat_alshurut_walmuwasafat_records_licenses_requirement, docs_government_tenders_and_procurement_law_law [INFERRED 0.85]
- **Weighted Technical/Financial Evaluation Formula Pattern** — docs_tender_draft_1_evaluation_methodology, docs_taqdim_khadamat_iaasha_sca_08_aug_24_financial_evaluation_formula, docs_government_tenders_and_procurement_law_proposal_assessment_criteria [INFERRED 0.75]

## Communities (66 total, 1 thin omitted)

### Community 0 - "Evaluation Ranking Agent"
Cohesion: 0.07
Nodes (63): EvaluationRankerAgent, EvaluationRankerAgent — local LLM (Ollama via agents/llm_config), VRI + Vendor…, Keep narrative judgement in the model, but make all arithmetic deterministic., LLM writes explanations; eligibility, membership, ordering and ranks are…, Score a single vendor submission. Called once per vendor., Aggregate scores into a ranked list. Called once after all vendors scored., EvaluationState, Any (+55 more)

### Community 1 - "Buyer Form Schemas"
Cohesion: 0.07
Nodes (50): Deliverable, EvaluationCriteria, BaseModel, Kept for backward compatibility with the existing agents. Later, the web UI can…, Used by the future UI as dropdown/selectable document options.…, These map nicely to future UI toggles/dropdowns., Responsibility, SubmissionControls (+42 more)

### Community 2 - "Category Taxonomy & Demo Engine"
Cohesion: 0.08
Nodes (54): Platform-wide category taxonomy for Mushtary. Used for tender creation…, _adverse_buyer_profile(), _adverse_vendor_profile(), _ai_recommendation_layer(), _base_buyer(), _base_vendor(), build_marketplace_snapshot(), _buyer_badge() (+46 more)

### Community 3 - "Legacy Entry Point & PDF Rendering"
Cohesion: 0.14
Nodes (59): main(), LEGACY entry point — drafts a tender from the hardcoded IT-infrastructure test…, _as_dict(), _as_list(), build_pdf(), _content_seen(), _cover_date(), _cover_info_row() (+51 more)

### Community 4 - "Tender Drafting Prompts & KSA Standards"
Cohesion: 0.05
Nodes (57): Drafting Context/Narrative System Prompt, Document Hierarchy Compatibility (Section 1.3-1.5), Drafting Execution System Prompt, Escalation Tiers (First/Second/Final), Work Order Process, Drafting Legacy Full System Prompt (16-section RFP), Mandatory + Scored Evaluation Criteria Schema, KSA Regulatory Standards Reference (NCAR, CITC, SASO, SAMA, SDAIA) (+49 more)

### Community 5 - "Buyer Account & Demo Profiles"
Cohesion: 0.09
Nodes (51): get_buyer(), account_session(), AccountSessionReq, _apply_form_overrides(), buyer_profile(), _demo_session(), _format_date(), GuidedDraftReq (+43 more)

### Community 6 - "Tender Health Aggregation"
Cohesion: 0.16
Nodes (38): Tag the current thread; subsequent token events from it carry this label., set_label(), chat_json_with_usage(), Return JSON text, repairing one malformed local-model response when necessary.…, TenderDraft, _agent_result(), _aggregate_fallback(), _ai_committee_agent() (+30 more)

### Community 7 - "Tender Buyer Form Sections"
Cohesion: 0.15
Nodes (37): TenderBuyerForm, AwardAndContract, CommercialProposalFormat, ContextSections, InstructionsToBidders, Introduction, ProposalFormatRequirements, BaseModel (+29 more)

### Community 8 - "Frontend Activity & Table UI"
Cohesion: 0.09
Nodes (31): activeJobs, activityStart(), activityStop(), addEditableRow(), addTenderTableRow(), appendEvent(), applyHealthPromptPatch(), cancelActiveJob() (+23 more)

### Community 9 - "Tender Drafting LangGraph Pipeline"
Cohesion: 0.11
Nodes (25): LangGraph orchestration layer for the Mushtarry agents., build_tender_graph(), node_assemble(), node_consistency(), node_context(), node_execution(), node_form_source(), node_legal_eval() (+17 more)

### Community 10 - "Frontend Rendering Helpers"
Cohesion: 0.12
Nodes (31): barRow(), block(), buildDocChips(), docList(), esc(), kv(), loadDemoAccounts(), loadDraftVendorRecommendations() (+23 more)

### Community 11 - "Activity Feed & Observability"
Cohesion: 0.12
Nodes (20): get_label(), get_since(), Activity feed — a process-wide, thread-safe event stream of what the agents are…, Return events for one authorized execution scope; never expose the global feed., bind_context(), _connect(), current_context(), ensure_trace() (+12 more)

### Community 12 - "Prompt Registry & AI Events API"
Cohesion: 0.09
Nodes (28): publish(), Append one event to the feed. Cheap; safe to call from any thread., get(), Prompt Registry — single source of truth for all prompt versions. Every prompt…, ai_events(), artifact_detail(), artifacts(), buyers() (+20 more)

### Community 13 - "Vendor Validation Agent"
Cohesion: 0.16
Nodes (22): _dispatch_tool(), VendorValidationAgent — local LLM (Ollama via LangChain, see…, VendorValidationAgent, build_user_message(), Prompts for VendorValidationAgent. The system prompt text lives in…, CategoryAlignmentResult, CRLookupResult, DocumentCompletenessResult (+14 more)

### Community 14 - "LLM Config & Circuit Breaker"
Cohesion: 0.16
Nodes (25): Resolved at call time from env (LLM_MODEL) — defaults to the local model., _bounded_int_env(), chat_text(), chat_with_usage(), _circuit_before_call(), _circuit_record(), get_api_key(), get_base_url() (+17 more)

### Community 15 - "Frontend Committee & Draft Approval UI"
Cohesion: 0.16
Nodes (27): approveCommitteeArtifact(), approveTenderDraft(), editTenderInputs(), errorHTML(), kbSearch(), loadBuyerProposalComparison(), loaderHTML(), loadReputationHub() (+19 more)

### Community 16 - "Tender KB Singleton & Clause Schemas"
Cohesion: 0.20
Nodes (22): get_tender_kb(), Process-wide singleton so the index is loaded from disk once, not per section…, EvaluationSection, GeneralTerms, LegalEvalSections, MandatoryCriterion, PaymentScheduleItem, PaymentTerms (+14 more)

### Community 17 - "Tender Draft Assembly & Platform Policy"
Cohesion: 0.22
Nodes (20): assemble_tender_draft(), _enforce_platform_policy(), _has_mushtarry(), Objectives, ProjectOverview, Kept for backward compatibility. The tender document can still avoid showing…, Guarantee the everything-on-Mushtarry clauses appear, wherever the model forgot., ScopeCategory (+12 more)

### Community 18 - "Agent Mode Dispatch & Execution Schemas"
Cohesion: 0.24
Nodes (18): Mode dispatch — run any single agent alone, or the full pipeline together.…, DeliverablesSection, EscalationTier, ExecutionSections, TeamRequirements, TeamRole, Timeline, _as_dict() (+10 more)

### Community 19 - "Vendor Committee LangGraph"
Cohesion: 0.20
Nodes (18): chat_json_text(), JSON-oriented variant of chat_text with one automatic repair attempt., _aggregate(), build_vendor_committee_graph(), CommitteeState, _fallback_agent(), _json_object(), Any (+10 more)

### Community 20 - "Marketplace Proposal Comparison"
Cohesion: 0.16
Nodes (21): get_vendor(), _buyer_for_tender(), compare_submitted_proposals(), _duration_days(), _hydrate_published_tenders(), _job_full_draft(), _load_marketplace_tenders(), _proposal_comparison_for_tender() (+13 more)

### Community 21 - "Base Agent & Artifact Model"
Cohesion: 0.17
Nodes (13): ABC, AIArtifact, ArtifactStatus, BaseAgent, Any, BaseModel, Entry point for each agent. Must return an AIArtifact., Represents a stored AI output — maps to ai_artifacts DB table. (+5 more)

### Community 22 - "RAG Text Chunking"
Cohesion: 0.16
Nodes (11): chunk_text(), Text chunking — split a long document into overlapping, embeddable pieces.…, Return a list of overlapping text chunks. Empty input yields an empty list., RAG (retrieval-augmented generation) package — local-first, fail-safe. Two…, build_focused_sow_text(), _head_tail_truncation(), Intra-document retrieval for the SoW Extractor. Problem it fixes: the extractor…, The original fallback behavior: keep the beginning and the end. (+3 more)

### Community 23 - "RAG Vector Store"
Cohesion: 0.14
Nodes (10): Path, Chunk, One indexable unit of text plus arbitrary provenance metadata. metadata is…, Path, Load a store from disk. A missing/empty directory yields an empty store., In-memory vector store with optional disk persistence., Embed and append chunks. No-op for an empty list., Convenience: wrap raw strings as Chunks sharing one metadata dict. (+2 more)

### Community 24 - "Vendor Document Requirements Assessment"
Cohesion: 0.16
Nodes (10): assess_document_requirements(), Any, Agent-assisted vendor document applicability assessment for the MVP. It is…, emit(), Persist one privacy-safe event. Observability must never break the AI workflow., BaseSectionAgent, Shared base for all section agents. Each section agent gets a focused prompt…, Base for LLM-backed section agents (native LangChain via agents.llm_config).… (+2 more)

### Community 25 - "Artifact Store Persistence"
Cohesion: 0.27
Nodes (15): approve_artifact(), _connect(), get_artifact(), get_latest_artifact(), list_artifacts(), _now(), Any, Connection (+7 more)

### Community 26 - "Output Guardrails & Validation"
Cohesion: 0.19
Nodes (10): Guardrails — validate AI output schema before storing. If output is malformed,…, Validate raw LLM output against a Pydantic schema. Returns None on failure —…, Validate and return fallback if validation fails. Guarantees a valid object is…, safe_parse(), validate_output(), BaseModel, Guardrails tests: malformed LLM output must produce the fallback, never an…, _Schema (+2 more)

### Community 27 - "AI Governance & Vendor Recommendation Formula"
Cohesion: 0.16
Nodes (16): AI Governance Principle: AI is advisory only, buyer retains award authority, AI Tender Committee, Buyer Reliability Index (BRI), Tender-Specific Vendor Recommendation Formula (Technical 50% + Price 20% + VRI 20% + Risk 10%), LLM-Assisted Judgement, Mushtary AI Procurement Platform, Rule-Based Scoring, Tender Generation Engine (+8 more)

### Community 28 - "Marketplace Tender Storage"
Cohesion: 0.20
Nodes (14): _connect(), delete_tender(), get_tender(), list_tenders(), Any, Connection, Durable SQLite storage for demo tender drafts and published tenders., Remove a superseded draft record after its published tender is stored. (+6 more)

### Community 29 - "SOW Review Agent"
Cohesion: 0.24
Nodes (12): _detailed_scope(), _ensure_detailed_rewrite(), _expand_rewrite_with_ai(), _extract_json(), _fallback(), _needs_expansion(), Any, BaseModel (+4 more)

### Community 30 - "Mushtary AI Agents Architecture Overview"
Cohesion: 0.18
Nodes (14): Tender Drafting Knowledge Base (tender_kb), Human-Approved-Only Indexing Rule, Mushtary AI Agents — Architecture & Flow, Vendor Scoring Isolation Rationale, Evaluation & Ranking Agent (Agent 3, two-step parallel), AI Generate → Human Review → Human Approve → Action Governance Rule, Tender Drafting Agent (Agent 2, LangGraph pipeline), Vendor Validation Agent (Agent 1, tool-use loop) (+6 more)

### Community 31 - "Standard Tender Clause Library"
Cohesion: 0.23
Nodes (14): General Terms & Governing Law Clause, Confidentiality & Data Protection Clause, Evaluation Methodology Clause, Payment Terms Clause, Bid Security, Performance Bonds & Guarantees Clause, Delay, Liquidated Damages & Penalties Clause, Eligibility & Qualification Requirements Clause, Submission, Validity & Award Clause (+6 more)

### Community 32 - "Tender Consistency & Compliance Gate"
Cohesion: 0.30
Nodes (10): _agent_review(), _deterministic_findings(), _hard_fact_reconcile(), Any, Consistency and compliance gate between tender drafting and publication. Buyer-…, reconcile_tender(), TenderDeliverable, TenderMilestone (+2 more)

### Community 33 - "Frontend Draft Field Overrides"
Cohesion: 0.22
Nodes (14): applyPopulatedOptionalSections(), checked(), checkedLabels(), collectDraftOverrides(), evaluationWeights(), lines(), missingRequiredDraftFields(), numberOrNull() (+6 more)

### Community 34 - "RAG Configuration & Knowledge Base"
Cohesion: 0.22
Nodes (9): get_min_score(), get_top_k(), RAG configuration — single source of truth for the embedding model and…, TenderKnowledgeBase — the persistent corpus the Tender Drafting section agents…, Fail-safe similarity search. Returns [] on any error or empty corpus., BaseModel, RAG Pydantic v2 schemas. Keeping chunks and retrieval hits as validated models…, A chunk returned by a search, with its similarity score (cosine, 0..1). (+1 more)

### Community 35 - "Knowledge Base Indexing Script"
Cohesion: 0.27
Nodes (10): build_index(), _gather(), main(), Path, Build / rebuild the Tender Drafting knowledge base from source documents. Usage…, Extract paragraph text from a .docx (a zip of XML) with no extra dependency., Index every supported file under input_path into the tender KB. Returns the…, _read_docx() (+2 more)

### Community 36 - "AI Operations & Backend Integration"
Cohesion: 0.17
Nodes (13): FastAPI (Demo Web UI Layer), AI Operations and Incident Tracing, Sensitive Value Redaction (SHA-256 fingerprint), AI Result Mode (AI_SUCCESS/AI_REPAIRED/PARTIAL_SUCCESS/DETERMINISTIC_FALLBACK), Trace ID / Request ID Correlation, AIArtifact (ai_artifacts table), Mushtarry AI Integration Guide for Backend and Web Teams, AI Service Interface Roadmap (/v1/ai/*) (+5 more)

### Community 37 - "Demo Presentation Guide Generator"
Cohesion: 0.18
Nodes (4): build(), GuidePDF, FPDF, Generate the presentation-ready Mushtary demo guide PDF.

### Community 38 - "Saudi Procurement Law & Regulations"
Cohesion: 0.18
Nodes (13): Government Tenders and Procurement Law (Royal Decree M/128), Local Content and Government Procurement Authority, Local Content and SME Prioritization Rationale (Article 9), Government Procurement Portal, Public Tender Method, Implementing Regulations of the Government Tenders and Procurement Law, Unified Procurement Agency, Saudi Export-Import Bank (Saudi EXIM Bank) (+5 more)

### Community 39 - "Embedding Generation"
Cohesion: 0.29
Nodes (10): get_embed_model(), embed_query(), embed_texts(), _normalize(), Local embeddings via the same OpenAI-compatible endpoint used for generation…, L2-normalize each row so dot products equal cosine similarity. Zero rows stay…, Embed many texts. Returns an (N, D) normalized float32 array. Used at index…, Embed a single query string. Returns a 1-D normalized float32 vector. (+2 more)

### Community 40 - "Python Dependencies"
Cohesion: 0.20
Nodes (12): AI Agents Python Requirements (requirements.txt), Celery[redis] (Async Task Queue), fpdf2 (Tender PDF Rendering), LangChain Core, LangGraph, numpy (Cosine Vector Index), OpenAI-Compatible Client (openai package), PyMuPDF (Document Ingestion / SOW Extractor) (+4 more)

### Community 41 - "Prompt Registry Consistency Tests"
Cohesion: 0.20
Nodes (6): list_prompts(), Prompt store — every model prompt lives in its own file under this folder.…, All available prompt slugs (filenames without .md)., _pairs_in_code(), Collect every (PROMPT_NAME, PROMPT_VERSION) pair declared by agent code., TestRegistryConsistency

### Community 42 - "RAG Fail-Safe Retrieval Tests"
Cohesion: 0.24
Nodes (6): Thin, fail-safe read wrapper around a persisted VectorStore., True only if there is something to retrieve., Render hits as a prompt block. Empty hits -> empty string (injects nothing).…, TenderKnowledgeBase, RAG fail-safe tests: the RAG layer must NEVER break the pipeline — empty corpus…, TestKnowledgeBaseFailsafe

### Community 43 - "SEVEN's F&B Attractions RFP"
Cohesion: 0.22
Nodes (11): Brand Review, Culinary Review, F&B Operator Role, Phase 1: Consultancy of F&B Offering, Phase 2: Operation of F&B Venues, Phase Award Independence Rationale: awarding Phase 1 vendor does not guarantee Phase 2 award, Public Investment Fund (PIF), In-Attraction F&B Operator Search and Selection RFP (+3 more)

### Community 44 - "Mushtarry MVP Guide & Reputation Indices"
Cohesion: 0.20
Nodes (11): Mushtarry MVP — Complete Project Guide, agents/artifact_store.py (SQLite Persistence), Buyer Reliability Index (BRI), Tender Consistency and Compliance Agent, Tender Health Committee, AI Vendor Selection Engine, Vendor Reputation Index (VRI), BRI Formula (Payment/Fairness/Dispute/Volume/Activity/Risk) (+3 more)

### Community 45 - "Frontend AI Committee & Health UI"
Cohesion: 0.29
Nodes (11): buildAITenderCommittee(), buildHealthPromptPatch(), buyerReputationHTML(), complianceStatus(), findHealthAgent(), metricCard(), probabilityOfSuccess(), renderAIRecommendationLayer() (+3 more)

### Community 46 - "Tender Revision Change Tracking"
Cohesion: 0.24
Nodes (10): _append_unique(), _change_records(), _changed_paths(), _committee_agent(), download(), _job_improve_tender(), Return changed JSON paths for UI-only revision highlighting., Produce compact before/after values for browser-only revision comparison. (+2 more)

### Community 47 - "JCSA Food Supply RFP (Riyadh Season)"
Cohesion: 0.20
Nodes (10): Budget Remit Exclusion Rule: proposals exceeding budget remit are automatically excluded, Food Supply RFP - Riyadh Season and General Requirement, Jockey Club of Saudi Arabia (JCSA), Riyadh Racing Season, The Saudi Cup, Budget Remit Exclusion Rule: proposals exceeding budget remit are automatically excluded, Food Supply RFP - Riyadh Season and General Requirement, Jockey Club of Saudi Arabia (JCSA) (+2 more)

### Community 48 - "LangChain Streaming Activity Callback"
Cohesion: 0.36
Nodes (6): _make_activity_callback(), _flush(), on_llm_end(), on_llm_error(), on_llm_new_token(), Build a LangChain callback that mirrors streamed tokens into the activity feed.…

### Community 49 - "AFC Asian Cup Engagement RFPs"
Cohesion: 0.25
Nodes (8): AFC Asian Cup Saudi Arabia 2027, AFC U23 Asian Cup 2026, Employee Engagement Services RFP (RFP-062-2025), Event Categories A-D (Major/Medium/Small/Daily), Local Organizing Committee AFC Asian Cup 2027 (LOC AFC27), Project Team Saudization Requirement, Technical Evaluation Criteria (Methodology 30% / Creative 40% / Team 20% / Activities 10%), Workforce Engagement Program

### Community 50 - "AI Agents Open Questions & Vendor Fit Score"
Cohesion: 0.29
Nodes (7): langchain-openai (ChatOpenAI Client), AI Agents — Requirements & Open Questions, Amaly E-magazine CR Verification Access (Blocker), Local Ollama LLM Provider (qwen3:4b), TenderPolicy (technical/financial weight, pricing_approach, output_detail), Vendor Fit Score Formula, Proposed Vendor Fit Score (VRI 40% + Requirement Match 30% + Proposal Quality 20% + Price 10% + Risk Adj.)

### Community 51 - "Statutory Proposal Assessment Criteria"
Cohesion: 0.40
Nodes (5): Proposal Assessment Criteria (Articles 24-25), Proposal Assessment Objectivity Rationale: criteria must be clear, objective, serve public interest, not target specific bidders, Technical and Financial Proposal Evaluation Criteria, Technical Evaluation Criteria (Menu Variety, Presentation, Responsiveness, Past Work), Tender Evaluation Methodology (70% Technical / 30% Financial)

### Community 52 - "SCA Hospitality Framework RFP"
Cohesion: 0.40
Nodes (5): Records and Statutory Licenses Requirement (CR, Zakat, Tax, Social Insurance, Chamber, Saudization), Financial Evaluation Formula (lowest qualifying bid = 100% of 40 points; others scaled), Framework Agreement RFP for Hospitality Services (SCA-PRC-RFP-2024-10), Saudi Contractors Authority (SCA), Statutory Documents Requirement (CR, Zakat, Tax, Social Insurance, Chamber, Saudization)

### Community 53 - "Frontend Reputation Hub UI"
Cohesion: 0.60
Nodes (5): badgeList(), renderBuyerAccountTable(), renderReputationHub(), renderVendorAccountTable(), scoreBadgeClass()

### Community 54 - "LLM JSON Repair Utilities"
Cohesion: 0.50
Nodes (4): _json_object_from_text(), Extract one JSON object from common local-model wrappers., Repair an already-produced JSON response without re-running its business…, repair_json_text()

### Community 55 - "Activity Log Handler"
Cohesion: 0.50
Nodes (3): _ActivityLogHandler, Forward agents.* INFO logs into the activity feed as narrator lines., LogRecord

### Community 57 - "Hero Background Image Asset"
Cohesion: 0.67
Nodes (3): Construction/Hospitality Project Workflow Iconography, Use as Landing/Marketing Hero Background, Tropical Resort Hospitality Background

## Ambiguous Edges - Review These
- `Government Tenders and Procurement Law (Royal Decree M/128)` → `Employee Engagement Services RFP (RFP-062-2025)`  [AMBIGUOUS]
  docs/RFP_Culture & Engagement.pdf · relation: conceptually_related_to

## Knowledge Gaps
- **77 isolated node(s):** `ArtifactStatus`, `DOC_TYPES`, `platformCategories`, `_nativeFetch`, `FIXED_DEMO_ACCOUNTS` (+72 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 329 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Government Tenders and Procurement Law (Royal Decree M/128)` and `Employee Engagement Services RFP (RFP-062-2025)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `TenderBuyerForm` connect `Tender Buyer Form Sections` to `Tender Consistency & Compliance Gate`, `Buyer Form Schemas`, `Buyer Account & Demo Profiles`, `Tender Health Aggregation`, `Tender Drafting LangGraph Pipeline`, `Tender KB Singleton & Clause Schemas`, `Tender Draft Assembly & Platform Policy`, `Agent Mode Dispatch & Execution Schemas`, `Base Agent & Artifact Model`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `emit()` connect `Vendor Document Requirements Assessment` to `Evaluation Ranking Agent`, `Buyer Form Schemas`, `Tender Consistency & Compliance Gate`, `Buyer Account & Demo Profiles`, `Tender Health Aggregation`, `Embedding Generation`, `Activity Feed & Observability`, `Vendor Validation Agent`, `LLM Config & Circuit Breaker`, `Tender Revision Change Tracking`, `Vendor Committee LangGraph`, `Base Agent & Artifact Model`, `LLM JSON Repair Utilities`, `Output Guardrails & Validation`, `SOW Review Agent`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `build_pdf()` connect `Legacy Entry Point & PDF Rendering` to `Buyer Form Schemas`, `Marketplace Proposal Comparison`, `Buyer Account & Demo Profiles`, `Tender Revision Change Tracking`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 46 inferred relationships involving `TenderBuyerForm` (e.g. with `FormGeneratorAgent` and `_resolve_form()`) actually correct?**
  _`TenderBuyerForm` has 46 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ArtifactStatus`, `DOC_TYPES`, `platformCategories` to the rest of the system?**
  _77 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Evaluation Ranking Agent` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._