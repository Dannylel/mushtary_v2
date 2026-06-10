TenderBuyerForm(
    tender_title="Board Annual Report 2025",
    tender_id="TND-001",
    buyer_name="Ashraq",
    buyer_description="Preparation of annual board report",

    category="Consulting Services",
    subcategory="Corporate Reporting",

    project_objective="Prepare governance-compliant annual report",

    scope_of_work="""
    On-site engagement, data collection, drafting chairman and CFO messages,
    report compilation, review and revision.
    """,

    deliverables=[
        {"name": "Draft Report", "description": "First draft", "format": "Word"},
        {"name": "Final Report", "description": "Final approved report", "format": "Word"}
    ],

    timeline=[
        {"milestone": "Draft Submission", "date": "5 April 2026"},
        {"milestone": "Final Submission", "date": "21 April 2026"}
    ],

    roles_and_responsibilities=[
        {
            "party": "Buyer",
            "responsibilities": [
                "Provide access to data",
                "Assign focal point"
            ]
        },
        {
            "party": "Vendor",
            "responsibilities": [
                "Prepare report",
                "Ensure compliance",
                "Maintain confidentiality"
            ]
        }
    ],

    payment_terms="Payment upon submission and approval of deliverables",

    eligibility_criteria=[
        "Experience in corporate reporting",
        "Governance expertise"
    ],

    required_documents=[
        "Company profile",
        "Previous reports",
        "Technical proposal",
        "Commercial proposal"
    ],

    evaluation_criteria=[
        {"name": "Methodology", "weight": 30, "description": "Approach quality"},
        {"name": "Experience", "weight": 30, "description": "Relevant projects"},
        {"name": "Team", "weight": 20, "description": "Qualifications"},
        {"name": "Price", "weight": 20, "description": "Cost"}
    ],

    submission_deadline="March 2026",
    submission_method="Email",
    proposal_format="Separate Technical and Commercial proposals"
)