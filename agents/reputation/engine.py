from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from agents.categories import CATEGORIES


VRI_WEIGHTS = {
    "performance_rating": 0.20,
    "compliance_and_licenses": 0.15,
    "institutional_verification": 0.15,
    "delivery_performance": 0.15,
    "financial_strength": 0.10,
    "tender_success_rate": 0.10,
    "contract_history": 0.10,
    "ai_risk_signals": 0.05,
}

BRI_WEIGHTS = {
    "payment_reliability": 0.30,
    "evaluation_fairness": 0.20,
    "dispute_behavior": 0.20,
    "procurement_volume": 0.15,
    "platform_activity": 0.10,
    "ai_risk_signals": 0.05,
}

VENDOR_NAMES = [
    "Alpha Tech Solutions",
    "Gulf Systems & Networks",
    "Riyadh Digital Services",
    "TechBridge International",
    "Najd Cloud Services",
    "Eastern Cyber Defense",
    "Makkah Facilities Group",
    "Red Sea Catering Co",
    "Jeddah Logistics Partners",
    "Diriyah Design Studio",
    "Saudi BuildWorks",
    "Naseem HVAC Maintenance",
    "Dammam Industrial Supply",
    "Qassim Food Manufacturing",
    "Tabuk Solar Engineering",
    "Hail Water Solutions",
    "Madinah Medical Supplies",
    "Vision Events Production",
    "Riyadh Audit Advisory",
    "Falcon Security Services",
    "Tuwaiq Data Analytics",
    "Neom Smart Infrastructure",
    "Arabian Fleet Leasing",
    "Asir Training Institute",
    "Jubail Petrochem Services",
    "Yanbu Port Logistics",
    "Sahara Packaging Factory",
    "Najran Agricultural Tech",
    "Khobar Telecom Consulting",
    "Taif Hospitality Services",
]

BUYER_NAMES = [
    "Mushtary Test Buyer",
    "Riyadh Health Cluster",
    "Jeddah Airports Company",
    "Diriyah Culture Authority",
    "Eastern Province Municipality",
    "Saudi Logistics Hub",
    "Red Sea Hospitality Group",
    "Najd University",
    "Makkah Facilities Authority",
    "Qassim Food Security Co",
    "Tabuk Renewable Energy Office",
    "Madinah Heritage Foundation",
    "Dammam Industrial City",
    "Hail Education Services",
    "Asir Tourism Development",
    "Jubail Utilities Company",
    "Yanbu Port Authority",
    "Riyadh Sports Club",
    "Khobar Medical Center",
    "Taif Events Bureau",
    "Neom Innovation Office",
    "Saudi Retail Cooperative",
    "National Training Center",
    "GCC Procurement Lab",
    "Sahara Real Estate Group",
    "Falcon Aviation Services",
    "Arabian Fleet Authority",
    "Tuwaiq Data Office",
    "Najran Agriculture Authority",
    "Jazan Water Company",
]

SPECIAL_BADGES = [
    "Fast Delivery Vendor",
    "Excellent Communication",
    "Compliance Champion",
    "AI Optimized Vendor",
    "Strategic Partner",
]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(_clamp(value), 1)


def _vri_level(score: float) -> str:
    if score >= 85:
        return "Elite Vendor"
    if score >= 75:
        return "Strategic Vendor"
    if score >= 65:
        return "Trusted Vendor"
    if score >= 50:
        return "Verified Vendor"
    return "Under Review"


def _vendor_badge(rating: float, completed_contracts: int, compliance: float) -> str:
    if rating >= 4.6 and completed_contracts >= 10 and compliance >= 85:
        return "Elite Vendor"
    if rating >= 4.2 and completed_contracts >= 5:
        return "Trusted Vendor"
    if rating >= 3.6:
        return "Verified Vendor"
    if rating >= 3.0:
        return "Developing Vendor"
    return "Under Observation"


def _buyer_badge(rating: float, annual_spend: int, payment_reliability: float) -> str:
    if rating >= 4.6 and annual_spend >= 20_000_000 and payment_reliability >= 90:
        return "Strategic Buyer"
    if rating >= 4.2 and payment_reliability >= 85:
        return "Trusted Buyer"
    if rating >= 3.6:
        return "Verified Buyer"
    if rating >= 3.0:
        return "Developing Buyer"
    return "Under Observation"


def _trust_level_from_rating(rating: float, role: str) -> str:
    suffix = "Vendor" if role == "vendor" else "Buyer"
    if rating >= 4.6:
        return f"Elite {suffix}" if role == "vendor" else "Strategic Buyer"
    if rating >= 4.2:
        return f"Trusted {suffix}"
    if rating >= 3.6:
        return f"Verified {suffix}"
    if rating >= 3.0:
        return f"Developing {suffix}"
    return "Under Observation"


def _component_score(components: dict[str, float], weights: dict[str, float]) -> float:
    return _round(sum(_clamp(components[key]) * weight for key, weight in weights.items()))


def _category_pair(index: int) -> tuple[str, str]:
    categories = list(CATEGORIES.keys())
    category = categories[index % (len(categories) - 1)]
    subcategories = CATEGORIES[category]
    return category, subcategories[index % len(subcategories)]


def _rating_from_score(score: float) -> float:
    return round(2.8 + (_clamp(score) / 100) * 2.0, 1)


def _base_vendor(index: int) -> dict[str, Any]:
    category, subcategory = _category_pair(index)
    secondary_category, secondary_subcategory = _category_pair(index + 5)
    categories = [category, secondary_category]
    subcategories = [subcategory, secondary_subcategory]
    if index % 4 == 0 and "Information Technology" not in categories:
        categories.append("Information Technology")
        subcategories.append("IT Infrastructure & Data Centers")
    tier_offset = [14, 8, 2, -5, -14][index % 5]
    delivery = _round(74 + tier_offset + (index % 7) * 2.1)
    compliance = _round(76 + tier_offset + (index % 4) * 2.5)
    institutional = _round(64 + tier_offset + (index % 6) * 3.0)
    contract_history = _round(60 + tier_offset + (index % 9) * 3.0)
    components = {
        "performance_rating": _round(72 + tier_offset + (index % 8) * 2.2),
        "compliance_and_licenses": compliance,
        "institutional_verification": institutional,
        "delivery_performance": delivery,
        "financial_strength": _round(66 + tier_offset + (index % 6) * 3.5),
        "tender_success_rate": _round(58 + tier_offset + (index % 7) * 3.8),
        "contract_history": contract_history,
        "ai_risk_signals": _round(82 + tier_offset - (index % 3) * 2.5),
    }
    overall = _component_score(components, VRI_WEIGHTS)
    category_specific = _round(overall + [5, 2, 0, -3, -7][index % 5])
    rating = _rating_from_score((components["performance_rating"] + delivery + compliance) / 3)
    completed_contracts = max(1, int(contract_history / 4) + (index % 5))
    certifications = ["Commercial Registration", "VAT Certificate", "Saudization Certificate"]
    certification_categories = set(categories)
    if certification_categories & {"Information Technology", "Telecommunications", "Financial Services & Fintech"}:
        certifications += ["ISO 27001", "ISO 9001"]
    elif certification_categories & {"Healthcare & Life Sciences", "Manufacturing & Industrial", "Facilities Management"}:
        certifications += ["ISO 9001"]
    elif certification_categories & {"Construction & Engineering", "Energy & Utilities"}:
        certifications += ["ISO 45001", "ISO 14001"]

    vendor_id = f"VND-{index + 1:03d}"
    return {
        "account_id": vendor_id,
        "role": "vendor",
        "name": VENDOR_NAMES[index],
        "email": f"vendor{index + 1:02d}@demo.mushtary.local",
        "status": "active" if index % 9 != 8 else "under_review",
        "city": ["Riyadh", "Jeddah", "Dammam", "Makkah", "Madinah", "Khobar"][index % 6],
        "categories": categories,
        "subcategories": subcategories,
        "years_experience": 3 + (index % 13),
        "similar_projects": 2 + (index % 14),
        "completed_contracts": completed_contracts,
        "active_contracts": index % 5,
        "average_contract_value_sar": 180_000 + (index % 10) * 145_000,
        "typical_bid_sar": 720_000 + (index % 12) * 95_000,
        "delivery_reliability": delivery,
        "on_time_delivery": _round(delivery - 2 + (index % 4)),
        "dispute_rate": round(max(0.4, 8.5 - delivery / 14 + (index % 3) * 0.6), 1),
        "rating": rating,
        "certifications": certifications,
        "institutional_verifications": _institutional_verifications(index, institutional),
        "vri": {
            "overall": overall,
            "category_specific": category_specific,
            "level": _vri_level(category_specific),
            "components": components,
        },
        "badge": _vendor_badge(rating, completed_contracts, compliance),
        "special_badges": _special_badges(index, delivery, compliance),
        "profile_summary": _vendor_summary(category, subcategory, completed_contracts),
    }


def _institutional_verifications(index: int, score: float) -> list[str]:
    institutions = ["Mushtarry", "Saudi Aramco", "SABIC", "STC", "SEC"]
    count = 1
    if score >= 70:
        count += 1
    if score >= 78:
        count += 1
    if score >= 86:
        count += 1
    if score >= 92:
        count += 1
    shift = index % len(institutions)
    rotated = institutions[shift:] + institutions[:shift]
    return rotated[:count]


def _special_badges(index: int, delivery: float, compliance: float) -> list[str]:
    badges: list[str] = []
    if delivery >= 88:
        badges.append("Fast Delivery Vendor")
    if index % 4 == 0:
        badges.append("Excellent Communication")
    if compliance >= 88:
        badges.append("Compliance Champion")
    if index % 6 == 0:
        badges.append("AI Optimized Vendor")
    if index % 10 == 0:
        badges.append("Strategic Partner")
    return badges[:3]


def _vendor_summary(category: str, subcategory: str, completed_contracts: int) -> str:
    return (
        f"Demo supplier focused on {subcategory} under {category}, "
        f"with {completed_contracts} completed platform contracts."
    )


def _base_buyer(index: int) -> dict[str, Any]:
    category, subcategory = _category_pair(index + 2)
    tier_offset = [12, 7, 1, -4, -12][index % 5]
    payment = _round(78 + tier_offset + (index % 7) * 2.0)
    fairness = _round(76 + tier_offset + (index % 6) * 2.4)
    dispute_behavior = _round(82 + tier_offset - (index % 4) * 2.0)
    activity = _round(70 + tier_offset + (index % 8) * 2.5)
    annual_spend = 4_000_000 + (index % 12) * 2_100_000
    components = {
        "payment_reliability": payment,
        "evaluation_fairness": fairness,
        "dispute_behavior": dispute_behavior,
        "procurement_volume": _round(min(100, annual_spend / 300_000)),
        "platform_activity": activity,
        "ai_risk_signals": _round(86 + tier_offset - (index % 3) * 2.3),
    }
    bri = _component_score(components, BRI_WEIGHTS)
    rating = _rating_from_score((payment + fairness + dispute_behavior) / 3)
    completed_tenders = 3 + (index % 18)
    buyer_id = f"BUY-{index + 1:03d}"
    return {
        "account_id": buyer_id,
        "role": "buyer",
        "name": BUYER_NAMES[index],
        "email": f"buyer{index + 1:02d}@demo.mushtary.local",
        "status": "active" if index % 10 != 9 else "under_review",
        "city": ["Riyadh", "Jeddah", "Dammam", "Makkah", "Madinah", "Tabuk"][index % 6],
        "primary_category": category,
        "primary_subcategory": subcategory,
        "completed_tenders": completed_tenders,
        "active_tenders": index % 4,
        "annual_procurement_spend_sar": annual_spend,
        "payment_reliability": payment,
        "average_payment_days": max(12, int(48 - payment / 3)),
        "dispute_rate": round(max(0.2, 7.8 - dispute_behavior / 15 + (index % 2) * 0.7), 1),
        "rating": rating,
        "bri": {
            "overall": bri,
            "level": _trust_level_from_rating(rating, "buyer"),
            "components": components,
        },
        "badge": _buyer_badge(rating, annual_spend, payment),
        "special_badges": _buyer_special_badges(index, payment, fairness),
        "profile_summary": (
            f"Demo procurement entity active in {subcategory}, with {completed_tenders} "
            "completed tenders and buyer-controlled award decisions."
        ),
    }


def _buyer_special_badges(index: int, payment: float, fairness: float) -> list[str]:
    badges: list[str] = []
    if payment >= 90:
        badges.append("Reliable Payment")
    if fairness >= 88:
        badges.append("Fair Evaluation")
    if index % 5 == 0:
        badges.append("Transparent Procurement")
    if index % 8 == 0:
        badges.append("Strategic Partner")
    return badges[:3]


VENDORS = [_base_vendor(i) for i in range(30)]
BUYERS = [_base_buyer(i) for i in range(30)]


@dataclass
class ShortlistRequest:
    category: str = "Information Technology"
    subcategory: str = "IT Infrastructure & Data Centers"
    estimated_value_sar: float | None = 1_500_000
    timeline_days: int | None = 90
    required_certifications: tuple[str, ...] = ("ISO 27001",)
    minimum_years_experience: int | None = 5
    minimum_similar_projects: int | None = 3
    local_presence_required: bool = True
    required_sector_license: str | None = None


def list_vendors() -> list[dict[str, Any]]:
    return VENDORS


def list_buyers() -> list[dict[str, Any]]:
    return BUYERS


def get_vendor(vendor_id: str) -> dict[str, Any] | None:
    return next((vendor for vendor in VENDORS if vendor["account_id"] == vendor_id), None)


def get_buyer(buyer_id: str) -> dict[str, Any] | None:
    return next((buyer for buyer in BUYERS if buyer["account_id"] == buyer_id), None)


def build_marketplace_snapshot() -> dict[str, Any]:
    vendor_vris = [vendor["vri"]["category_specific"] for vendor in VENDORS]
    buyer_bris = [buyer["bri"]["overall"] for buyer in BUYERS]
    return {
        "summary": {
            "buyer_count": len(BUYERS),
            "vendor_count": len(VENDORS),
            "average_vendor_vri": round(mean(vendor_vris), 1),
            "average_buyer_bri": round(mean(buyer_bris), 1),
            "elite_or_strategic_vendors": sum(1 for vendor in VENDORS if vendor["vri"]["category_specific"] >= 75),
            "trusted_or_strategic_buyers": sum(1 for buyer in BUYERS if buyer["bri"]["overall"] >= 75),
        },
        "buyers": BUYERS,
        "vendors": VENDORS,
        "badge_rules": {
            "vendor": [
                "Elite Vendor: rating 4.6-5.0, 10+ contracts, strong compliance.",
                "Trusted Vendor: rating 4.2-4.5 and at least 5 completed contracts.",
                "Verified Vendor: rating 3.6-4.1 with verified documents and activity.",
                "Developing Vendor: rating 3.0-3.5 or early recovery profile.",
                "Under Observation: below 3.0 or material performance issues.",
            ],
            "buyer": [
                "Strategic Buyer: rating 4.6-5.0, high volume, excellent payment reliability.",
                "Trusted Buyer: rating 4.2-4.5 with good payment behavior.",
                "Verified Buyer: rating 3.6-4.1 and transparent procurement activity.",
                "Developing Buyer: rating 3.0-3.5 or new organization.",
                "Under Observation: below 3.0 or procurement complaints detected.",
            ],
        },
    }


def shortlist_vendors(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    req = _parse_shortlist_request(raw or {})
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for vendor in VENDORS:
        exclusion = _exclusion_reason(vendor, req)
        if exclusion:
            excluded.append({
                "vendor_id": vendor["account_id"],
                "vendor_name": vendor["name"],
                "reason": exclusion,
                "vri": vendor["vri"]["category_specific"],
            })
            continue
        eligible.append(_score_vendor_for_tender(vendor, req))

    eligible.sort(key=lambda item: item["fit_score"], reverse=True)
    for rank, vendor in enumerate(eligible, start=1):
        vendor["rank"] = rank
    buckets = {
        "high_match": [v for v in eligible if v["fit_score"] >= 80],
        "medium_match": [v for v in eligible if 65 <= v["fit_score"] < 80],
        "low_match": [v for v in eligible if v["fit_score"] < 65],
    }
    top_three = eligible[:3]
    return {
        "tender": {
            "category": req.category,
            "subcategory": req.subcategory,
            "estimated_value_sar": req.estimated_value_sar,
            "timeline_days": req.timeline_days,
            "required_certifications": list(req.required_certifications),
            "minimum_years_experience": req.minimum_years_experience,
            "minimum_similar_projects": req.minimum_similar_projects,
        },
        "counts": {
            "potential_eligible_vendors_found": len(eligible),
            "high_match_vendors": len(buckets["high_match"]),
            "medium_match_vendors": len(buckets["medium_match"]),
            "low_match_vendors": len(buckets["low_match"]),
            "excluded_vendors": len(excluded),
        },
        "top_recommendation": top_three[0] if top_three else None,
        "top_three": top_three,
        "buckets": buckets,
        "excluded": excluded,
        "committee": _committee_summary(top_three),
        "human_in_the_loop": "AI recommends only. Buyer approval is required before any award.",
    }


def _parse_shortlist_request(raw: dict[str, Any]) -> ShortlistRequest:
    certs = raw.get("required_certifications") or []
    if isinstance(certs, str):
        certs = [certs]
    cert_tuple = tuple(str(item).strip() for item in certs if str(item).strip())
    return ShortlistRequest(
        category=str(raw.get("category") or "Information Technology"),
        subcategory=str(raw.get("subcategory") or "IT Infrastructure & Data Centers"),
        estimated_value_sar=_number_or_none(raw.get("estimated_value_sar")),
        timeline_days=_int_or_none(raw.get("timeline_days") or raw.get("deadline_days")),
        required_certifications=cert_tuple or ("ISO 27001",),
        minimum_years_experience=_int_or_none(raw.get("minimum_years_experience")) or 5,
        minimum_similar_projects=_int_or_none(raw.get("minimum_similar_projects")) or 3,
        local_presence_required=bool(raw.get("local_presence_required", True)),
        required_sector_license=raw.get("required_sector_license") or None,
    )


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    number = _number_or_none(value)
    return int(number) if number is not None else None


def _exclusion_reason(vendor: dict[str, Any], req: ShortlistRequest) -> str | None:
    if req.category not in vendor["categories"]:
        return "Category mismatch"
    if req.minimum_years_experience and vendor["years_experience"] < req.minimum_years_experience:
        return "Below minimum years of experience"
    if req.minimum_similar_projects and vendor["similar_projects"] < req.minimum_similar_projects:
        return "Below minimum similar project count"
    if req.required_certifications:
        certs = {cert.lower() for cert in vendor["certifications"]}
        required = {cert.lower() for cert in req.required_certifications}
        if not any(cert in certs for cert in required):
            return "Missing required certification evidence"
    if req.local_presence_required and vendor["city"] not in {"Riyadh", "Jeddah", "Dammam", "Makkah", "Madinah", "Khobar"}:
        return "Local presence mismatch"
    if vendor["status"] != "active":
        return "Vendor profile under review"
    return None


def _score_vendor_for_tender(vendor: dict[str, Any], req: ShortlistRequest) -> dict[str, Any]:
    requirement_match = _requirement_match(vendor, req)
    proposal_quality = _proposal_quality(vendor, req)
    price_score = _price_competitiveness(vendor, req)
    risk_adjustment = _risk_adjustment(vendor, price_score)
    vri = vendor["vri"]["category_specific"]
    fit_score = _round(
        vri * 0.40
        + requirement_match * 0.30
        + proposal_quality * 0.20
        + price_score * 0.10
        + risk_adjustment
    )
    committee = _vendor_committee(vendor, requirement_match, proposal_quality, price_score, risk_adjustment)
    return {
        "vendor_id": vendor["account_id"],
        "vendor_name": vendor["name"],
        "badge": vendor["badge"],
        "special_badges": vendor["special_badges"],
        "vri": vri,
        "vri_level": vendor["vri"]["level"],
        "rating": vendor["rating"],
        "fit_score": fit_score,
        "risk_level": _risk_level(fit_score, risk_adjustment),
        "delivery_reliability": vendor["delivery_reliability"],
        "price_competitiveness": price_score,
        "requirement_match": requirement_match,
        "proposal_quality": proposal_quality,
        "risk_adjustment": risk_adjustment,
        "committee": committee,
        "why_selected": _why_selected(vendor, req, fit_score, risk_adjustment),
    }


def _requirement_match(vendor: dict[str, Any], req: ShortlistRequest) -> float:
    score = 45.0
    if req.category in vendor["categories"]:
        score += 22
    if req.subcategory in vendor["subcategories"]:
        score += 12
    if req.minimum_years_experience:
        score += min(10, max(0, vendor["years_experience"] - req.minimum_years_experience + 1) * 2)
    if req.minimum_similar_projects:
        score += min(8, max(0, vendor["similar_projects"] - req.minimum_similar_projects + 1) * 1.6)
    certs = {cert.lower() for cert in vendor["certifications"]}
    matches = sum(1 for cert in req.required_certifications if cert.lower() in certs)
    if req.required_certifications:
        score += min(12, matches / len(req.required_certifications) * 12)
    return _round(score)


def _proposal_quality(vendor: dict[str, Any], req: ShortlistRequest) -> float:
    score = 58 + vendor["rating"] * 5.5
    score += min(8, len(vendor["certifications"]) * 1.2)
    score += min(8, len(vendor["institutional_verifications"]) * 2.0)
    if req.timeline_days and vendor["on_time_delivery"] >= 88:
        score += 4
    return _round(score)


def _price_competitiveness(vendor: dict[str, Any], req: ShortlistRequest) -> float:
    if not req.estimated_value_sar:
        return 75.0
    ratio = vendor["typical_bid_sar"] / req.estimated_value_sar
    if 0.85 <= ratio <= 1.05:
        return _round(92 - abs(0.95 - ratio) * 40)
    if 0.70 <= ratio < 0.85:
        return _round(82 - (0.85 - ratio) * 90)
    if 1.05 < ratio <= 1.20:
        return _round(82 - (ratio - 1.05) * 110)
    return _round(54 if ratio < 0.70 else 48)


def _risk_adjustment(vendor: dict[str, Any], price_score: float) -> float:
    penalty = 0.0
    if vendor["dispute_rate"] > 5:
        penalty -= 4
    if vendor["delivery_reliability"] < 75:
        penalty -= 5
    if price_score < 60:
        penalty -= 5
    if vendor["vri"]["category_specific"] < 60:
        penalty -= 4
    return max(-15, penalty)


def _risk_level(fit_score: float, risk_adjustment: float) -> str:
    if fit_score >= 78 and risk_adjustment >= -3:
        return "Low"
    if fit_score >= 62 and risk_adjustment >= -8:
        return "Medium"
    return "High"


def _vendor_committee(
    vendor: dict[str, Any],
    requirement_match: float,
    proposal_quality: float,
    price_score: float,
    risk_adjustment: float,
) -> dict[str, Any]:
    technical = _round(requirement_match)
    commercial = _round(price_score)
    compliance = _round(vendor["vri"]["components"]["compliance_and_licenses"])
    delivery = _round(vendor["delivery_reliability"])
    risk = _round(100 + risk_adjustment * 4 - vendor["dispute_rate"] * 2)
    vri = vendor["vri"]["category_specific"]
    final = _round(
        technical * 0.30
        + commercial * 0.20
        + compliance * 0.15
        + delivery * 0.15
        + risk * 0.10
        + vri * 0.10
    )
    return {
        "final_score": final,
        "weights": {
            "technical": 30,
            "commercial": 20,
            "compliance": 15,
            "delivery": 15,
            "risk": 10,
            "vri": 10,
        },
        "agents": [
            {"agent": "Technical Agent", "score": technical, "summary": "Category, experience, certification, and requirement alignment."},
            {"agent": "Commercial Agent", "score": commercial, "summary": "Value-for-money price signal, not lowest-price-only logic."},
            {"agent": "Compliance Agent", "score": compliance, "summary": "Licenses, documents, and verification strength."},
            {"agent": "Delivery Agent", "score": delivery, "summary": "Historical delivery reliability and on-time performance."},
            {"agent": "Risk Agent", "score": risk, "summary": "Disputes, abnormal pricing, profile status, and behavioral signals."},
            {"agent": "VRI Signal", "score": vri, "summary": "Category-specific Vendor Reputation Index."},
        ],
    }


def _why_selected(vendor: dict[str, Any], req: ShortlistRequest, fit_score: float, risk_adjustment: float) -> list[str]:
    reasons = [
        f"{vendor['vri']['level']} with category VRI {vendor['vri']['category_specific']}/100.",
        f"Matches {req.category} tender requirements with {vendor['similar_projects']} similar projects.",
        f"Delivery reliability is {vendor['delivery_reliability']}% with {vendor['completed_contracts']} completed contracts.",
    ]
    if vendor["institutional_verifications"]:
        reasons.append("Verified by " + ", ".join(vendor["institutional_verifications"]) + ".")
    if risk_adjustment < 0:
        reasons.append(f"Risk adjustment applied: {risk_adjustment} points.")
    if fit_score >= 80:
        reasons.append("Recommended as a high-match vendor; buyer approval remains required.")
    return reasons


def _committee_summary(top_three: list[dict[str, Any]]) -> dict[str, Any]:
    if not top_three:
        return {
            "recommended_vendor": None,
            "final_recommendation": "No eligible vendor found for this tender configuration.",
            "comparison": [],
        }
    best = top_three[0]
    return {
        "recommended_vendor": best["vendor_name"],
        "final_score": best["committee"]["final_score"],
        "risk_level": best["risk_level"],
        "final_recommendation": (
            f"{best['vendor_name']} provides the strongest current balance between "
            "technical fit, VRI, delivery reliability, compliance, and commercial value. "
            "This is advisory only; the buyer must approve any award."
        ),
        "comparison": [
            {
                "rank": vendor["rank"],
                "vendor_name": vendor["vendor_name"],
                "fit_score": vendor["fit_score"],
                "committee_score": vendor["committee"]["final_score"],
                "vri": vendor["vri"],
                "risk_level": vendor["risk_level"],
            }
            for vendor in top_three
        ],
    }
