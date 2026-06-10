"""
Platform-wide category taxonomy for Mushtary.
Used for tender creation dropdowns, vendor registration, and category alignment validation.

Structure:
  CATEGORIES = { "Category Name": ["Subcategory 1", "Subcategory 2", ...] }

Source: MoM 2 March 2026 (Section 5 & 6) — client confirmed all major Saudi industry sectors
must be covered. Saudi Arabia is the primary market; GCC expansion is the roadmap.
"""

CATEGORIES: dict[str, list[str]] = {

    "Information Technology": [
        "IT Infrastructure & Data Centers",
        "Software Development & Integration",
        "Cybersecurity Solutions",
        "Cloud Services & Managed Hosting",
        "Data Analytics & Business Intelligence",
        "ERP & Enterprise Systems",
        "Telecommunications & Connectivity",
        "IT Support & Maintenance",
        "Artificial Intelligence & Automation",
        "Digital Transformation Consulting",
    ],

    "Construction & Engineering": [
        "Civil & Structural Engineering",
        "Architectural & Design Services",
        "MEP (Mechanical, Electrical, Plumbing)",
        "Project Management & Supervision",
        "Infrastructure Development",
        "Interior Design & Fit-Out",
        "Roads & Transportation Infrastructure",
        "Water & Drainage Systems",
        "Survey & Geotechnical Services",
        "Building Materials & Supplies",
    ],

    "Manufacturing & Industrial": [
        "Industrial Equipment & Machinery",
        "Raw Materials & Commodities",
        "Packaging & Labelling",
        "Quality Control & Testing",
        "Factory Automation & Robotics",
        "Metal & Steel Fabrication",
        "Plastics & Chemicals Manufacturing",
        "Food & Beverage Manufacturing",
        "Pharmaceutical Manufacturing",
        "Printing & Publishing",
    ],

    "Energy & Utilities": [
        "Oil & Gas Equipment & Services",
        "Renewable Energy (Solar / Wind)",
        "Electricity Generation & Distribution",
        "Water Treatment & Desalination",
        "Waste Management & Environmental Services",
        "Energy Auditing & Efficiency Consulting",
        "Pipeline & Infrastructure Maintenance",
        "Petrochemicals",
        "Nuclear Energy Services",
    ],

    "Healthcare & Life Sciences": [
        "Medical Equipment & Devices",
        "Pharmaceutical Supplies & Distribution",
        "Hospital Management Systems",
        "Laboratory & Diagnostic Services",
        "Healthcare IT & Telemedicine",
        "Medical Consumables & PPE",
        "Mental Health & Rehabilitation Services",
        "Healthcare Consulting & Accreditation",
        "Dental & Optical Supplies",
    ],

    "Logistics & Supply Chain": [
        "Freight & Cargo Transportation",
        "Warehousing & Cold Storage",
        "Last-Mile Delivery",
        "Customs Clearance & Brokerage",
        "Fleet Management & Leasing",
        "Supply Chain Consulting",
        "Packaging & Fulfilment",
        "Port & Terminal Operations",
        "Air Cargo & Aviation Logistics",
    ],

    "Retail & Consumer Goods": [
        "Consumer Electronics",
        "Food & Grocery Retail",
        "Fashion & Apparel",
        "Home & Furniture",
        "Sporting Goods & Outdoor",
        "Toys & Baby Products",
        "Beauty & Personal Care",
        "E-commerce Platform Services",
        "Retail Technology & POS Systems",
        "Visual Merchandising & Store Design",
    ],

    "Professional Services": [
        "Legal & Regulatory Advisory",
        "Financial Advisory & Accounting",
        "Management Consulting",
        "HR & Recruitment Services",
        "Training & Corporate Development",
        "Translation & Interpretation",
        "Research & Market Analysis",
        "Audit & Compliance",
        "Intellectual Property Services",
    ],

    "Facilities Management": [
        "Cleaning & Janitorial Services",
        "Security & Guarding Services",
        "Building Maintenance & Repair",
        "HVAC Maintenance",
        "Catering & Hospitality Services",
        "Pest Control",
        "Landscaping & Horticulture",
        "Parking Management",
        "Waste Collection & Disposal",
    ],

    "Media, Marketing & Events": [
        "Digital Marketing & SEO",
        "PR & Communications",
        "Event Management & Production",
        "Video Production & Broadcasting",
        "Photography Services",
        "Advertising & Creative Design",
        "Social Media Management",
        "Market Research & Brand Strategy",
        "Exhibition & Conference Services",
        "Content Creation & Copywriting",
    ],

    "Education & Training": [
        "E-learning Platform Development",
        "Corporate & Professional Training",
        "Curriculum & Content Development",
        "Educational Equipment & Supplies",
        "Testing & Assessment Services",
        "Language Training",
        "STEM & Technical Education",
        "School & University Consulting",
    ],

    "Financial Services & Fintech": [
        "Banking Technology Solutions",
        "Insurance Services",
        "Fintech & Payment Solutions",
        "Investment & Asset Management",
        "Microfinance & SME Lending",
        "Credit & Risk Advisory",
        "Regulatory Compliance (SAMA / CMA)",
        "Accounting Software & ERP",
    ],

    "Real Estate & Property": [
        "Property Development & Sales",
        "Property Management Services",
        "Valuation & Appraisal",
        "Real Estate Technology (PropTech)",
        "Land Development & Planning",
        "Commercial Leasing",
        "Smart Building Solutions",
    ],

    "Tourism, Hospitality & Entertainment": [
        "Hotel & Resort Management",
        "Travel Agency & Tour Operator",
        "Event Venue Management",
        "Catering & Food Services",
        "Theme Parks & Entertainment",
        "Cultural & Heritage Tourism",
        "Sports & Recreation Facilities",
        "Airline & Aviation Services",
    ],

    "Agriculture & Food": [
        "Agricultural Equipment & Machinery",
        "Irrigation & Water Management",
        "Food Processing & Packaging",
        "Animal Feed & Livestock",
        "Pesticides, Fertilizers & Agro-Chemicals",
        "Aquaculture & Fisheries",
        "Organic Farming Solutions",
        "Agricultural Consulting & Technology",
    ],

    "Government & Public Sector": [
        "Smart City Solutions",
        "E-Government Systems",
        "Public Safety & Surveillance",
        "Defence & Security Equipment",
        "Social Services Technology",
        "Urban Planning & Infrastructure",
        "Records Management & Archiving",
        "Public Transport Systems",
    ],

    "Automotive": [
        "Vehicle Supply & Fleet Sales",
        "Automotive Parts & Accessories",
        "Vehicle Maintenance & Repair",
        "EV Charging Infrastructure",
        "Fleet Leasing & Management",
        "Automotive Technology & Telematics",
    ],

    "Telecommunications": [
        "Mobile & Fixed Network Infrastructure",
        "Satellite Communications",
        "Internet Service Provision",
        "VoIP & Unified Communications",
        "Network Security & Monitoring",
        "Telecom Consulting & Managed Services",
    ],

    "Mining & Resources": [
        "Mining Equipment & Machinery",
        "Geological Survey Services",
        "Mineral Processing",
        "Environmental Remediation",
        "Safety & Compliance in Mining",
    ],

    "Other": [
        "Other / Not Listed Above",
    ],
}


# Flat list of all categories (for validation / dropdowns)
ALL_CATEGORIES: list[str] = sorted(CATEGORIES.keys())


def get_subcategories(category: str) -> list[str]:
    return CATEGORIES.get(category, [])


def is_valid_category(category: str) -> bool:
    return category in CATEGORIES


def is_valid_subcategory(category: str, subcategory: str) -> bool:
    return subcategory in CATEGORIES.get(category, [])
