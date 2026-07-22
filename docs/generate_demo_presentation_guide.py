"""Generate the presentation-ready Mushtary demo guide PDF."""
from pathlib import Path

from fpdf import FPDF


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Mushtary_Demo_Presentation_Guide.pdf"


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(70, 86, 120)
        self.cell(0, 7, "MUSHTARY | AI PROCUREMENT DEMO", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(210, 218, 235)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(210, 218, 235)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 110, 130)
        self.cell(0, 8, f"Local demo guide | Page {self.page_no()}", align="C")

    def title_page(self):
        self.add_page()
        self.set_fill_color(18, 31, 61)
        self.rect(0, 0, self.w, self.h, style="F")
        self.set_y(54)
        self.set_font("Helvetica", "B", 30)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 14, "Mushtary\nAI Procurement Demo", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(201, 217, 255)
        self.multi_cell(0, 8, "Presentation guide: product story, workflow, scoring rules, controls, and buyer decision support", align="C")
        self.set_y(226)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(113, 220, 203)
        self.cell(0, 8, "AI generates -> buyer reviews -> buyer approves -> action occurs", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(201, 217, 255)
        self.cell(0, 6, "Prepared for live MVP demonstration", align="C")

    def section(self, heading, intro=None):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(23, 40, 73)
        self.multi_cell(0, 9, heading)
        self.ln(1)
        if intro:
            self.set_font("Helvetica", "", 10.5)
            self.set_text_color(68, 78, 96)
            self.multi_cell(0, 5.5, intro)
            self.ln(4)

    def sub(self, heading):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(38, 63, 111)
        self.multi_cell(0, 6, heading)
        self.ln(1)

    def para(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 48, 63)
        self.multi_cell(0, 5.4, text)
        self.ln(2)

    def bullets(self, items):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 48, 63)
        for item in items:
            self.set_x(self.l_margin + 3)
            self.cell(5, 5.4, "-", new_x="RIGHT")
            self.multi_cell(self.w - self.l_margin - self.r_margin - 8, 5.4, item)
        self.ln(2)

    def callout(self, label, text):
        self.set_fill_color(239, 246, 255)
        self.set_draw_color(147, 197, 253)
        y = self.get_y()
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(29, 78, 216)
        self.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9.6)
        self.set_text_color(30, 64, 110)
        self.multi_cell(0, 5.1, text)
        h = self.get_y() - y + 4
        self.rect(self.l_margin - 2, y - 2, self.w - self.l_margin - self.r_margin + 4, h, style="D")
        self.ln(5)


def build():
    pdf = GuidePDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 18, 18)
    pdf.title_page()

    pdf.add_page()
    pdf.section("1. What Mushtary demonstrates", "Mushtary is a local-first procurement intelligence MVP. It turns a buyer brief into a structured tender, keeps the buyer in control of approval, lets a vendor submit a controlled demo proposal, and gives the buyer evidence-based comparison support.")
    pdf.sub("The product story")
    pdf.bullets([
        "A Buyer-Admin starts with procurement controls and a Scope of Work (SoW).",
        "AI reviews and expands the SoW, derives optional tender content, and drafts a structured RFP.",
        "Tender Intelligence and the AI Tender Committee identify clarity, commercial, compliance, delivery, and risk issues.",
        "The tender remains private until the Buyer-Admin explicitly approves publication.",
        "A Vendor sees only published opportunities, buyer trust context, requirements, and its own proposal form.",
        "The Buyer compares submitted proposals. AI is advisory only; contract award remains a buyer decision."
    ])
    pdf.callout("Core governance message", "AI never makes a binding procurement decision. It generates, reviews, structures, and recommends. The buyer reviews inputs and outputs, controls publication, and retains final award authority.")
    pdf.sub("Demo accounts")
    pdf.bullets([
        "Buyer-Admin: Taif Events Bureau (BUY-020).",
        "Vendor: Alpha Tech Solutions (VND-001).",
        "These curated accounts make the presentation repeatable and show synthetic BRI/VRI trust signals."
    ])

    pdf.add_page()
    pdf.section("2. How scoring and recommendations work", "Mushtary does not use one opaque score. It combines transparent signals so the buyer can understand why a tender or vendor appears strong, weak, eligible, or risky.")
    pdf.sub("Vendor Reputation Index (VRI): reliability for this type of work")
    pdf.bullets([
        "Performance rating: 20% | Compliance and licenses: 15% | Institutional verification: 15%.",
        "Delivery performance: 15% | Financial strength: 10% | Tender success rate: 10%.",
        "Contract history: 10% | AI risk signals: 5%.",
        "Score bands: 85-100 Elite Vendor; 75-84 Strategic Vendor; 65-74 Trusted Vendor; 50-64 Verified Vendor; below 50 Under Review."
    ])
    pdf.sub("Buyer Reliability Index (BRI): a trust signal for vendors")
    pdf.bullets([
        "Payment reliability: 30% | Evaluation fairness: 20% | Dispute behavior: 20%.",
        "Procurement volume: 15% | Platform activity: 10% | AI risk signals: 5%.",
        "The vendor sees the buyer's score, badge, payment reliability, and dispute context before deciding whether to participate."
    ])
    pdf.sub("Tender-specific vendor recommendation")
    pdf.bullets([
        "VRI contributes 20%; technical fit and proposal quality contribute 50%; commercial competitiveness contributes 20%; and risk assessment contributes 10%.",
        "The engine first checks tender requirements, then groups vendors into high, medium, and low match or excludes them with reasons.",
        "A high VRI alone cannot win. The recommendation is adjusted for the actual tender scope, certifications, experience thresholds, price, proposal content, and risk."
    ])
    pdf.callout("How to say it", "The score is an explainable decision-support signal, not an automatic award. It tells the buyer where to look and what to verify.")

    pdf.add_page()
    pdf.section("3. Recommended live presentation", "Use the Overview journey bar to keep the audience oriented: Define -> AI assist -> Approve -> Vendor view -> Compare. The flow below is the strongest end-to-end narrative.")
    steps = [
        ("1. Sign in as Buyer", "Choose Taif Events Bureau. Explain that role-based views separate buyer controls from vendor access."),
        ("2. Define the tender", "Open Draft Tender. Point out prefilled procurement controls: dates, commercial controls, eligibility, evaluation model, submission controls, and the buyer's initial SoW."),
        ("3. Evaluate / Rewrite SoW", "Show the readiness score, gaps, recommendations, and detailed rewrite. The agent writes a dense 10-part SoW covering scope, deliverables, responsibilities, quality, acceptance, governance, assumptions, exclusions, and handover."),
        ("4. Populate optional sections", "Click Populate Deliverables & Optional Sections. Show the AI-derived objective, technical requirements, deliverables, milestones, responsibilities, and evaluation inputs. Edit one field live to prove buyer control."),
        ("5. Generate tender", "Generate Tender From Approved SoW. Use the live activity console to narrate which job is running. Show the formal tender preview, Tender Intelligence, and the committee findings."),
        ("6. Revise with committee feedback", "Click Edit This Tender With AI Committee Feedback. The browser shows an exact change comparison: red struck-through values are replaced text; green values are new/revised text. This comparison is never added to the PDF."),
        ("7. Approve and publish", "Click Approve & Publish to Vendor Feed. State clearly that this is the human publication gate; drafts are invisible to vendors until this buyer action."),
        ("8. Vendor proposal", "Move to Vendor view. Show buyer BRI and tender requirements, then submit the Alpha Tech demo proposal."),
        ("9. Compare submitted vendors", "Return to Buyer and open Submitted Vendors. Show price, timeline, VRI, risk, probability, compliance context, and the advisory comparison. Close by restating that the buyer makes the award decision.")
    ]
    for heading, text in steps:
        pdf.sub(heading)
        pdf.para(text)

    pdf.add_page()
    pdf.section("4. What the AI components do", "The interface exposes multiple specialized AI or evidence-processing capabilities. Each is bounded by validated schemas, buyer-provided facts, deterministic safeguards, or a human approval step.")
    pdf.sub("Scope of Work review and expansion")
    pdf.para("The SoW reviewer assesses whether a vendor can price, plan, staff, and deliver with minimal clarification. It asks for a detailed, dense rewrite. If an initial model response is too compact, the application runs a dedicated AI expansion pass. If the model is unavailable or still inadequate, a structured deterministic fallback protects the demo.")
    pdf.sub("Tender drafting and Tender Intelligence")
    pdf.para("The drafting flow creates a validated buyer form, runs specialist tender drafting sections, assembles the RFP, retrieves approved clause context where appropriate, checks consistency, and renders PDF/JSON outputs. Tender Intelligence assesses readiness and turns findings into buyer-review priorities.")
    pdf.sub("AI Committee revision comparison")
    pdf.para("The revision workflow preserves committee evidence, applies revision logic to the tender artifact, and records before/after change records. The web preview renders these records as red replaced content and green revised content. PDF generation receives only the tender artifact, not presentation annotations.")
    pdf.sub("Vendor intelligence")
    pdf.para("The reputation layer supplies synthetic VRI/BRI profiles, badges, risk context, and tender-specific shortlisting. Vendor validation demonstrates CR, duplicate, category, and document-completeness checks using demo adapters. Buyer comparison gives immediate deterministic evidence signals and reuses any saved committee evidence.")

    pdf.add_page()
    pdf.section("5. Data, controls, and safe demo statements", "These talking points make the demonstration accurate and credible.")
    pdf.sub("What is local and synthetic")
    pdf.bullets([
        "The default demo is local-first. The configured local model processes tender content through the Ollama-compatible endpoint.",
        "Buyer/vendor accounts, VRI/BRI scores, badges, documents, and proposal data are synthetic demo data.",
        "Vendor validation integrations are demo adapters. They are not official legal, registry, issuer, or document-authenticity verification.",
        "In-memory jobs reset when the API restarts. Tender and proposal marketplace activity is persisted locally for the demo experience."
    ])
    pdf.sub("Controls to highlight")
    pdf.bullets([
        "Buyer-entered requirements are treated as facts and take precedence over generated content.",
        "Publication requires Buyer-Admin approval; vendors cannot access private drafts.",
        "The vendor sees its own participation context, not competing vendors' dossiers or buyer-only recommendations.",
        "Tender revision highlights are UI-only and are deliberately excluded from the formal PDF.",
        "AI recommendations remain advisory; no automatic vendor selection or award is implemented."
    ])
    pdf.callout("Suggested closing line", "Mushtary reduces the manual effort of turning a procurement need into a structured, reviewable tender and gives both sides clearer information - while keeping governance, publication, and award decisions with the buyer.")

    pdf.add_page()
    pdf.section("6. How to interpret the results", "Use these explanations while presenting the intelligence screens. They help the audience understand both the value and the limits of each score.")
    pdf.sub("Tender Health and readiness")
    pdf.bullets([
        "Tender Health considers scope clarity, commercial clarity, compliance readiness, delivery readiness, and risk of vendor questions.",
        "A low score does not reject the tender. It identifies gaps such as unclear deliverables, weak acceptance criteria, missing documents, incomplete timelines, or ambiguous pricing controls.",
        "The AI Committee turns those findings into improvement priorities. The buyer may apply them, review the red/green change comparison, and decide whether the tender is ready to publish."
    ])
    pdf.sub("Submitted vendor comparison")
    pdf.bullets([
        "The buyer sees each proposal's price, timeline, VRI level, compliance context, risk score, probability of success, and reasons supporting the ranking.",
        "An unusually low price can increase risk because it may signal under-scoping, unrealistic resourcing, or incomplete commercial assumptions.",
        "The recommendation is always accompanied by buyer questions and evidence gaps. It is a structured review aid, not an award instruction."
    ])
    pdf.sub("Useful optional screens")
    pdf.bullets([
        "Reputation Hub: explains the VRI and BRI profiles, badges, and tender-specific vendor matching.",
        "Vendor Validation: shows the evidence checks for registration format, duplicates, category alignment, and submitted documents.",
        "Evaluate and Rank: demonstrates that vendors are scored in isolation before ranking, preventing one proposal from seeing another proposal's content.",
        "Knowledge Base: shows the approved clause and procurement context used to ground the tender language."
    ])

    pdf.add_page()
    pdf.section("7. The two scoring modes: rules and AI judgement", "This is the key explanation to use when someone asks where a score came from. Mushtary deliberately combines two different forms of intelligence. They do different jobs and neither can make a binding award.")
    pdf.sub("A. Rule-based scoring: repeatable, measurable, and auditable")
    pdf.para("Rule-based scoring applies fixed formulas and pass/fail gates to structured data. Given the same vendor profile and the same tender requirements, it returns the same result. It is used where the platform can state exactly which evidence and weight influenced the result.")
    pdf.bullets([
        "Eligibility gates run first: relevant category, required sector license where applicable, local presence where required, active profile status, minimum years of experience, similar-project threshold, and required certifications. A failed gate can exclude a vendor before ranking.",
        "VRI and BRI are weighted calculations from their published components. They are reputation signals, not legal findings or official verification decisions.",
        "Tender shortlisting calculates requirement match, profile/proposal-quality signal, price competitiveness, VRI, and risk. The final recommendation formula is Technical Evaluation 50% + Price Competitiveness 20% + VRI 20% + Risk Score 10%.",
        "Technical Evaluation itself combines Requirement Match 75% and Proposal/Capability Quality 25%. Requirement Match rewards category, subcategory, relevant experience, similar projects, and certification alignment.",
        "Probability of Success is 72% of the recommendation score plus 28% of the risk score. A lower price is not automatically better: a highly abnormal price can reduce the risk signal."
    ])
    pdf.sub("B. LLM-assisted judgement: evidence-bound interpretation")
    pdf.para("The LLM is used where the system must read language and judge clarity, completeness, consistency, or the practical consequence of a gap. It receives a constrained tender or proposal context, is instructed not to invent facts, and must return a validated structured response with findings, evidence, risks, and recommendations.")
    pdf.bullets([
        "LLM output is schema-validated. If it is unavailable, malformed, or unsupported, the platform falls back to deterministic checks rather than failing the workflow.",
        "The UI exposes the mode: LLM Primary with Deterministic Fallback or Deterministic Fallback. This makes the source of the result explainable in the demo.",
        "The LLM can recommend what the buyer should clarify, verify, negotiate, or improve. It cannot approve publication, validate an official document, select a winner, or award a contract."
    ])

    pdf.add_page()
    pdf.section("8. Committees and their exact roles", "A committee is a structured set of specialist perspectives, not a group of autonomous decision makers. Each role focuses on a different evidence question; the buyer sees the result and decides what to do next.")
    pdf.sub("Tender Health Committee: is this tender ready to issue?")
    pdf.bullets([
        "Scope Clarity Agent: checks objectives, workstreams, deliverables, milestones, responsibilities, technical clarity, and acceptance logic.",
        "Commercial Clarity Agent: checks price breakdown expectations, payment controls, proposal packaging, commercial assumptions, and evaluation clarity.",
        "Compliance Readiness Agent: checks document requirements, eligibility, confidentiality, submission controls, mandatory criteria, and governance language.",
        "Vendor Participation Agent: estimates whether ambiguity in scope, commercial controls, or compliance burden may create vendor questions or reduce participation.",
        "Tender Health aggregate: Scope 35%, Commercial 25%, Compliance 25%, Participation 15%. Readiness is shown as Ready for Buyer-Admin review, Needs buyer review, or Needs revision. The score is capped when unresolved findings remain, preventing unjustified optimism."
    ])
    pdf.sub("AI Tender Committee: what should be improved before publication?")
    pdf.bullets([
        "Technical: scope, acceptance, technical requirements, and evaluation evidence.",
        "Commercial: pricing detail, payment linkage, commercial assumptions, and bidder instructions.",
        "Compliance: mandatory documents, rules, declarations, and consistency of controls.",
        "Delivery: deliverables, timeline, work-order process, reporting, and handover.",
        "Risk: clarity gaps likely to create questions, weak submissions, disputes, or delivery uncertainty.",
        "Committee priority score: Technical 25%, Commercial 20%, Compliance 20%, Delivery 20%, Risk 15%. The output becomes an edit request; the buyer can inspect red/green changes before publication."
    ])
    pdf.sub("Vendor proposal committee: is the submitted proposal well supported?")
    pdf.bullets([
        "Technical 30%, Commercial 20%, Compliance 20%, Delivery 15%, Risk 15% are combined for the post-proposal advisory score.",
        "Its roles review supplied proposal text and profile evidence only. It identifies decisive evidence, material gaps, risks, and buyer questions.",
        "For a fast live demo, the Submitted Vendors screen returns the deterministic evidence baseline immediately and reuses any saved committee result. This protects responsiveness while keeping the buyer comparison available."
    ])

    pdf.add_page()
    pdf.section("9. Workflow-by-workflow explanation", "Use this page as a speaking aid. Every workflow has an input, a processing layer, a visible output, and a human decision boundary.")
    workflows = [
        ("SoW review and rewrite", "Input: buyer's brief. Processing: LLM clarity review and dense rewrite, with a second AI expansion pass if the first rewrite is too short; deterministic detailed fallback if needed. Output: score, gaps, recommendations, and a structured scope. Boundary: buyer accepts, edits, or ignores the rewrite."),
        ("Populate optional sections", "Input: scope and buyer-entered tender facts. Processing: structured extraction of objective, requirements, deliverables, milestones, responsibilities, and evaluation inputs. Output: editable form fields. Boundary: buyer values are preserved; nothing is published."),
        ("Tender drafting", "Input: approved buyer facts and SoW. Processing: specialist drafting sections, structured validation, consistency reconciliation, and clause grounding. Output: draft RFP, preview, JSON, and PDF. Boundary: it remains a private draft."),
        ("Tender revision", "Input: Tender Intelligence and committee priorities. Processing: revision agent plus deterministic controls. Output: revised tender and browser-only before/after comparison. Boundary: buyer reviews all red/green changes; the formal PDF stays clean."),
        ("Publication", "Input: buyer-approved draft. Processing: publication gate and saved tender record. Output: vendor-visible opportunity. Boundary: only Buyer-Admin approval releases the tender."),
        ("Vendor validation and proposal", "Input: vendor identity, category, documents, price, timeline, and summaries. Processing: demo validation checks and controlled proposal capture. Output: buyer-visible proposal evidence. Boundary: validation is advisory/demo-only and does not certify official records."),
        ("Shortlist and submitted-vendor comparison", "Input: tender requirements plus vendor profile/proposal evidence. Processing: rule-based eligibility, weighted scoring, risk adjustment, and committee signals. Output: rank, reasons, risk, compliance context, probability, and buyer questions. Boundary: no automatic award.")
    ]
    for title, text in workflows:
        pdf.sub(title)
        pdf.para(text)

    pdf.add_page()
    pdf.section("10. Tender Generation Engine", "Tender generation converts a buyer-controlled brief into a complete, structured RFP. It is not a one-shot text-generation prompt: the process separates buyer facts, writing tasks, checks, and publication.")
    pdf.sub("Inputs that are treated as buyer facts")
    pdf.bullets([
        "Tender title, category, location, dates, procurement method, evaluation split, commercial controls, eligibility, documents, submission method, and buyer identity.",
        "Scope of Work, project objective, technical requirements, methodology requirements, deliverables, milestones, and responsibilities where the buyer enters them.",
        "A buyer-entered fact overrides a conflicting generated value. For example, buyer deliverables and milestone dates are retained when the tender is assembled."
    ])
    pdf.sub("Generation sequence")
    pdf.bullets([
        "1. The SoW is extracted or reviewed into a validated buyer-form structure. Required fields are normalized so incomplete model output does not break the workflow.",
        "2. Drafting specialists create the context, scope, execution, and legal/evaluation sections. They use structured schemas so the output can be rendered as formal sections, tables, and controls rather than unstructured prose.",
        "3. The system reconciles consistency: hard buyer facts replace conflicting generated facts; high-severity inconsistencies can block publication.",
        "4. Tender Health evaluates the completed draft. The buyer can apply committee changes and inspect the red/green comparison before approval.",
        "5. The final artifact is rendered into an 18-section RFP preview, JSON audit output, and a clean PDF."
    ])
    pdf.sub("Why the scope matters")
    pdf.para("The Scope of Work is the main semantic input. It controls what the system can derive safely. The reviewer requires a detailed ten-part scope: purpose, workstreams, vendor activities, deliverables, responsibilities, QA and acceptance, governance, dependencies, exclusions/change control, and handover. Unknown facts are marked for buyer confirmation rather than invented.")
    pdf.callout("What to say", "Tender generation is structured drafting under buyer controls. The system writes the document, but it does not replace the buyer's commercial facts, approve itself, or publish itself.")

    pdf.add_page()
    pdf.section("11. BRI and VRI: reputation models", "VRI and BRI are deterministic 0-100 composite indices. They transform several evidence components into one explainable trust signal, while preserving the individual components for inspection.")
    pdf.sub("VRI - Vendor Reputation Index")
    pdf.para("VRI answers: 'How reliable is this vendor for this category of work?' It is calculated as a weighted sum of normalized components: Performance Rating 20%, Compliance and Licenses 15%, Institutional Verification 15%, Delivery Performance 15%, Financial Strength 10%, Tender Success Rate 10%, Contract History 10%, and AI Risk Signals 5%.")
    pdf.bullets([
        "The overall VRI is supplemented by a category-specific VRI. This prevents a generally strong vendor from appearing equally strong in an unrelated category.",
        "Levels are operational labels: Elite (85-100), Strategic (75-84), Trusted (65-74), Verified (50-64), and Under Review (below 50).",
        "VRI is one input to tender matching; it is never the only ranking factor and is never an automatic eligibility approval."
    ])
    pdf.sub("BRI - Buyer Reliability Index")
    pdf.para("BRI answers: 'What is the procurement experience likely to be for a vendor?' It is a weighted sum of Payment Reliability 30%, Evaluation Fairness 20%, Dispute Behavior 20%, Procurement Volume 15%, Platform Activity 10%, and AI Risk Signals 5%.")
    pdf.bullets([
        "The vendor feed displays BRI alongside buyer badge, payment behavior, and dispute context so the vendor can evaluate the opportunity before submitting.",
        "BRI is designed to encourage transparent procurement and does not claim to be a credit rating, legal conclusion, or official payment certification.",
        "All current BRI and VRI evidence is synthetic demo data. In production, each component would require governed, auditable data sources and consent/retention policy."
    ])

    pdf.add_page()
    pdf.section("12. Tender Health: quality scoring before publication", "Tender Health measures the readiness of the tender document itself. It does not score vendors. It identifies whether the RFP is sufficiently clear and controlled for vendors to respond and for the buyer to evaluate responses fairly.")
    pdf.sub("Specialist health scores")
    pdf.bullets([
        "Scope Clarity: objectives, scope boundaries, deliverables, milestones, technical requirements, responsibilities, and measurable acceptance criteria.",
        "Commercial Clarity: pricing breakdown, payment linkage, evaluation parameters, bid security, proposal format, and commercial assumptions/exclusions.",
        "Compliance Readiness: eligibility, mandatory documents, confidentiality, declarations, platform controls, submission rules, and governance requirements.",
        "Vendor Participation: an estimate of vendor confidence and question risk based on ambiguity detected by the other health specialists."
    ])
    pdf.sub("Aggregate formula and readiness")
    pdf.para("The deterministic aggregate is Scope 35% + Commercial 25% + Compliance 25% + Vendor Participation 15%. The LLM aggregator is given the same configured weights and the four validated specialist outputs. A calibration ceiling reduces an overly optimistic aggregate when unresolved findings remain.")
    pdf.bullets([
        "85 or above: Ready for Buyer-Admin review. This is not automatic publication; the buyer must still validate dates, amounts, legal wording, and business intent.",
        "70-84: Needs buyer review before publication. The tender is usable, but identified weaknesses should be strengthened.",
        "Below 70: Needs revision before buyer approval. Material gaps may undermine pricing, compliance checks, or evaluation fairness."
    ])
    pdf.sub("LLM versus fallback in Tender Health")
    pdf.para("The local LLM is the primary reviewer. Every LLM output is parsed into a required schema. If a call fails, is malformed, or is disabled, the corresponding deterministic specialist fallback applies penalties for concrete missing controls. The UI identifies the analysis mode so the buyer knows whether the result was LLM-primary or fallback-driven.")

    pdf.add_page()
    pdf.section("13. AI Committees and recommendation boundaries", "Mushtary uses committee language to make different specialist perspectives visible. The committee is not a legal panel, award board, or autonomous actor.")
    pdf.sub("Pre-publication AI Tender Committee")
    pdf.para("This committee generates improvement priorities for the tender draft. Its weighted priority score is Technical 25%, Commercial 20%, Compliance 20%, Delivery 20%, and Risk 15%. Each role receives the tender and buyer form context and focuses on a specific weakness category.")
    pdf.bullets([
        "Technical Agent: whether requirements can be understood, scoped, tested, and evaluated.",
        "Commercial Agent: whether pricing, payment, cost breakdown, assumptions, and financial evaluation are sufficiently clear.",
        "Compliance Agent: whether documents, eligibility, declarations, controls, and procurement rules are coherent.",
        "Delivery Agent: whether work packages, deliverables, milestones, reporting, escalation, and handover are feasible and evidenced.",
        "Risk Agent: whether unresolved ambiguity can create vendor questions, weak proposals, delivery failure, or disputes."
    ])
    pdf.sub("Post-proposal vendor committee")
    pdf.para("The post-proposal committee reviews one submitted vendor at a time so it does not compare confidential proposal content across vendors. Its advisory formula is Technical 30%, Commercial 20%, Compliance 20%, Delivery 15%, and Risk 15%. The detailed committee is designed to return evidence, risks, recommendations, and buyer questions; it cannot approve or reject a vendor.")
    pdf.sub("Fast comparison design")
    pdf.para("For presentation responsiveness, Submitted Vendors returns the deterministic evidence baseline immediately and reuses a saved committee result where one exists. This is deliberate: the buyer sees the proposal, price, timeline, risk, compliance context, and reasons without waiting for a long model run. The display remains explicitly advisory.")

    pdf.add_page()
    pdf.section("14. Full scoring trace: from eligibility to buyer decision", "This page shows the order in which a vendor moves through the decision-support process.")
    pdf.sub("Step 1 - Eligibility gates (not a weighted score)")
    pdf.para("The vendor is checked for category alignment, active status, local-presence requirement, required sector license, minimum experience, similar-project threshold, and required certifications. A failure produces an exclusion reason. This prevents a high reputation score from bypassing a hard buyer requirement.")
    pdf.sub("Step 2 - Profile and tender-fit calculations")
    pdf.bullets([
        "Requirement Match begins from a baseline and adds points for category, subcategory, years above the minimum, similar projects above the minimum, and matched certifications. It is capped to preserve headroom for proposal evidence.",
        "Capability/Proposal Quality uses rating, certifications, institutional verifications, and on-time delivery signal where timeline matters.",
        "Price Competitiveness compares the vendor's typical bid or submitted price against the tender estimate. A reasonable range scores strongly; extreme underpricing or overpricing scores lower.",
        "Risk Adjustment applies penalties for high dispute rate, weak delivery reliability, abnormal price signal, or weak category VRI. Risk Score translates the adjustment and dispute evidence into a 0-100 confidence signal."
    ])
    pdf.sub("Step 3 - Recommendation and probability")
    pdf.para("Recommendation Score = Technical Evaluation x 50% + Price Competitiveness x 20% + Category VRI x 20% + Risk Score x 10%. Technical Evaluation = Requirement Match x 75% + Capability/Proposal Quality x 25%. Probability of Success = Recommendation Score x 72% + Risk Score x 28%.")
    pdf.sub("Step 4 - Buyer interpretation")
    pdf.para("The system presents the rank, reasons, risk level, compliance status, price/timeline evidence, and buyer questions. The Buyer-Admin decides whether to request clarification, validate evidence, negotiate, invite, exclude, publish, or award. Mushtary records advice and approvals; it does not make the final procurement decision.")

    pdf.output(str(OUTPUT))
    print(OUTPUT)


if __name__ == "__main__":
    build()
