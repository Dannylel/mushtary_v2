"""
Hardcoded IT-infrastructure test buyer form — sample data for exercising the drafting
pipeline without a real buyer. Moved out of the legacy main.py; not used by run.py
(which AI-generates or extracts forms).
"""
from agents.buyer_form import (
    Deliverable,
    EvaluationCriteria,
    Responsibility,
    SubmissionControls,
    TenderBuyerForm,
    TimelineItem,
    VendorDocumentRequirement,
)


def _doc(
    name: str,
    level: str,
    category: str,
    applicability: str,
    authority: str | None = None,
    notes: str | None = None,
) -> VendorDocumentRequirement:
    return VendorDocumentRequirement(
        name=name,
        requirement_level=level,
        category=category,
        applicability=applicability,
        issuing_authority=authority,
        notes=notes,
    )


def build_test_form() -> TenderBuyerForm:
    mandatory_docs = [
        _doc("Commercial Registration (CR)", "mandatory", "Legal & Registration", "All vendors", "Ministry of Commerce", "Must be valid and active."),
        _doc("National Address Certificate", "mandatory", "Legal & Registration", "All vendors", "SPL / Wasel", "Must match CR details."),
        _doc("Authorized Signatory ID", "mandatory", "Identity & Authority", "All vendors", "National ID / Iqama", "Saudi National ID or Iqama for authorized signatory."),
        _doc("Authorization Letter / Power of Attorney", "mandatory", "Identity & Authority", "All vendors", "Company-issued / notarized if required", "Must confirm signing authority; company-stamped and signed."),
        _doc("IBAN Certificate / Bank Letter", "mandatory", "Banking & Financial", "All vendors", "Bank", "Must match the company legal name."),
    ]

    conditional_docs = [
        _doc("Articles of Association (AOA)", "conditional", "Legal & Registration", "If applicable", "Ministry of Commerce / Company records", "Latest version reflecting current ownership and activities."),
        _doc("VAT Registration Certificate", "conditional", "Legal & Registration", "If VAT-registered", "ZATCA", "Mandatory if the vendor is VAT-registered."),
        _doc("Zakat & Tax Certificate", "conditional", "Legal & Registration", "If applicable", "ZATCA", "Valid clearance certificate where applicable."),
        _doc("Brand Registration Certificate", "conditional", "Legal & Registration", "If brand name is used", "SAIP", "Required if bidding under a registered brand."),
        _doc("MISA Investment License", "conditional", "Legal & Registration", "Foreign companies in KSA", "MISA", "Required for foreign companies operating in KSA."),
        _doc("GOSI Certificate", "conditional", "Compliance & Labor", "If applicable", "GOSI", "Social insurance registration."),
        _doc("Saudization (Nitaqat) Certificate", "conditional", "Compliance & Labor", "Required where buyer or regulatory rules apply", "Ministry of Human Resources / Nitaqat", "Shows Saudization compliance."),
    ]

    sector_specific_docs = [
        _doc("CITC / CST License", "sector_specific", "IT Sector License", "Telecom / IT services", "CITC / CST", "Relevant for IT infrastructure, telecom, and digital services."),
        _doc("CST / NCA License or Compliance Evidence", "sector_specific", "IT / Cybersecurity Compliance", "IT, cybersecurity, and digital infrastructure", "CST / NCA", "Relevant where cybersecurity/digital infrastructure compliance applies."),
    ]

    optional_docs = [
        _doc("Company Profile", "optional", "Capability & Credibility", "All vendors", "Vendor-issued", "PDF company profile."),
        _doc("ISO Certifications", "optional", "Capability & Credibility", "If available", "ISO certification body", "Examples: ISO 9001, ISO 27001, ISO 20000, ISO 22301."),
        _doc("Past Project References", "optional", "Capability & Credibility", "All vendors", "Client-issued / vendor-submitted", "Relevant project experience and references."),
        _doc("Client Recommendation Letters", "optional", "Capability & Credibility", "If available", "Previous clients", "Improves buyer trust."),
    ]

    return TenderBuyerForm(
        tender_title="Data Center Infrastructure Upgrade",
        tender_id="TND-IT-001",
        buyer_name="Mushtary Test Buyer",
        buyer_description="Mushtary Test Buyer requires a qualified IT infrastructure vendor to upgrade its data center environment in Riyadh, Saudi Arabia.",
        tender_type="Request for Proposal (RFP)",
        procurement_method="Invited Tender",
        issue_date="02/06/2026",
        site_visit_required=True,
        site_visit_date="08/06/2026",
        clarification_deadline="12/06/2026",
        submission_deadline="30/06/2026 @ 11:00 AM KSA Time",
        opening_date="30/06/2026",
        proposal_validity_days=90,
        category="Information Technology",
        subcategory="IT Infrastructure & Data Centers",
        project_objective="Modernise the existing data center to improve performance, reliability, security posture, and compliance with applicable Saudi cybersecurity requirements.",
        scope_of_work="Full supply, installation, configuration, testing, and commissioning of new server hardware, core network switches, next-generation firewall, and backup systems. The scope includes data migration, rollback planning, staff training, as-built documentation, and warranty/support services.",
        deliverables=[
            Deliverable(name="Infrastructure Assessment Report", description="Current state analysis and upgrade recommendations", format="PDF"),
            Deliverable(name="Proposed Solution Design", description="Target architecture, technical design, BOM, network/security design", format="PDF"),
            Deliverable(name="Upgraded Server Infrastructure", description="Rack-mounted servers installed and configured", format="System/Physical"),
            Deliverable(name="Network & Security Equipment", description="Core switches and NGFW installed and configured", format="System/Physical"),
            Deliverable(name="Data Migration Completion Report", description="Migration evidence, downtime confirmation, and zero-loss validation", format="PDF"),
            Deliverable(name="Training Materials", description="IT staff training in Arabic and English", format="PDF/PPTX"),
            Deliverable(name="As-Built Documentation", description="Network diagrams, configuration records, licenses, and warranty details", format="PDF"),
        ],
        timeline=[
            TimelineItem(milestone="Infrastructure Assessment Report", date="Day 10 from contract award"),
            TimelineItem(milestone="Assessment & Design Approval", date="Day 15 from contract award"),
            TimelineItem(milestone="Equipment Delivery", date="Day 45 from contract award"),
            TimelineItem(milestone="Installation & Configuration Complete", date="Day 75 from contract award"),
            TimelineItem(milestone="Data Migration & UAT", date="Day 85 from contract award"),
            TimelineItem(milestone="Project Handover", date="Day 90 from contract award"),
        ],
        roles_and_responsibilities=[
            Responsibility(
                party="Buyer",
                responsibilities=[
                    "Provide data center access and security clearance.",
                    "Assign dedicated IT focal point.",
                    "Review and approve designs, plans, and deliverables within agreed review windows.",
                    "Conduct UAT and final sign-off.",
                ],
            ),
            Responsibility(
                party="Vendor",
                responsibilities=[
                    "Supply all approved hardware and software.",
                    "Execute installation, configuration, testing, and migration.",
                    "Provide project manager and technical lead.",
                    "Maintain applicable Saudi IT/cybersecurity compliance throughout.",
                    "Provide warranty and post-implementation support.",
                ],
            ),
        ],
        technical_requirements="Servers: rack-mounted, dual-processor, minimum 256GB RAM, 20TB SSD RAID-6. Core switches: Layer 3, minimum 1Tbps switching capacity, redundant PSU. Firewall: NGFW with IPS, minimum 10Gbps throughput. Virtualisation: VMware vSphere or Microsoft Hyper-V. Backup: daily full backup, weekly offsite backup, Veeam-compatible.",
        methodology_requirements="Vendor must provide implementation methodology, migration strategy, rollback plan, risk register, testing plan, and handover plan. All change windows require prior written approval.",
        estimated_value_sar=1500000,
        budget_range="SAR 1,200,000 - 1,800,000",
        payment_terms="Milestone-based: 20% on contract award, 40% on equipment delivery and acceptance, 30% on successful handover/UAT, and 10% after completion of the initial warranty observation period.",
        bid_security_required=True,
        bid_security_amount_or_percentage="2% of submitted bid value",
        performance_bond_required=True,
        performance_bond_percentage=5.0,
        performance_bond_validity="the full implementation period and the 3-year warranty/support period",
        retention_percentage=10.0,
        liquidated_damages_applicable=True,
        liquidated_damages_rate="0.5% of delayed milestone value per week, capped as per final contract",
        eligibility_criteria=[
            "Minimum 5 years of IT infrastructure project experience in KSA.",
            "Minimum 3 completed similar projects with contract value exceeding SAR 500,000 each.",
            "Must not be blacklisted or restricted by any government entity in Saudi Arabia.",
            "Must hold relevant CST/CITC/NCA-related license or provide applicability explanation.",
            "Must maintain valid Saudi legal, tax, address, banking, and signatory documentation.",
        ],
        minimum_years_experience=5,
        minimum_similar_projects=3,
        minimum_project_value_sar=500000,
        required_sector_license="CITC / CST License and CST / NCA compliance evidence where applicable",
        required_certifications=["Relevant vendor certifications", "ISO 27001 preferred", "ISO 9001 preferred"],
        blacklist_declaration_required=True,
        local_presence_required=True,
        saudization_required=True,
        required_documents=[d.name for d in mandatory_docs + conditional_docs + sector_specific_docs],
        mandatory_documents=mandatory_docs,
        conditional_documents=conditional_docs,
        sector_specific_documents=sector_specific_docs,
        optional_documents=optional_docs,
        prestige_documents=[],
        evaluation_model="70/30",
        technical_weight=70,
        financial_weight=30,
        minimum_score=70,
        evaluation_criteria=[
            EvaluationCriteria(name="Technical Proposal", weight=70, description="Technical parameters generated by LegalEvalSectionAgent."),
            EvaluationCriteria(name="Financial Proposal", weight=30, description="Financial parameters generated by LegalEvalSectionAgent."),
        ],
        mandatory_disqualification_criteria=[
            "Late submission after official platform deadline.",
            "Failure to submit mandatory legal registration documents.",
            "Failure to submit required technical proposal.",
            "Failure to submit separate commercial proposal.",
            "Failure to provide bid security if required.",
            "Conflict of interest not disclosed.",
            "Vendor is blacklisted, suspended, or legally restricted.",
        ],
        technical_evaluation_parameters=[],
        financial_evaluation_parameters=[],
        submission_method="Mushtarry platform only",
        proposal_format="Separate Technical Proposal and Commercial Proposal",
        submission_controls=SubmissionControls(
            platform_submission_only=True,
            separate_technical_commercial=True,
            technical_file_format="PDF",
            commercial_file_format="PDF/Excel",
            max_file_size_mb=50,
            resubmission_allowed_before_deadline=True,
            lock_after_deadline=True,
            late_submission_allowed=False,
            completeness_check_required=True,
            timestamp_is_official=True,
        ),
        contract_duration="90 days implementation + 3 years warranty/support",
        warranty_duration="3 years",
        confidentiality_required=True,
        location="Riyadh, Saudi Arabia",
        onsite_required=True,
        language_requirements="Arabic and English; Arabic takes precedence in case of conflict.",
    )
