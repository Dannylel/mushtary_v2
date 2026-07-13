import unittest

from agents.reputation import list_buyers, list_vendors, shortlist_vendors


class TestDemoProfiles(unittest.TestCase):
    def test_vendor_profiles_include_agent_evidence(self):
        vendor = list_vendors()[0]
        for key in ("document_profile", "verification_evidence", "delivery_history", "commercial_profile", "capability_evidence", "reputation_evidence", "vri"):
            self.assertIn(key, vendor)

    def test_buyer_profiles_include_bri_evidence(self):
        buyer = list_buyers()[0]
        for key in ("evaluation_evidence", "payment_evidence", "governance_evidence", "reputation_evidence", "bri"):
            self.assertIn(key, buyer)

    def test_pinned_demo_vendor_is_eligible_for_default_it_shortlist(self):
        shortlist = shortlist_vendors({
            "category": "Information Technology",
            "subcategory": "IT Infrastructure & Data Centers",
            "required_certifications": ["ISO 27001 preferred", "ISO 9001 preferred"],
            "minimum_years_experience": 5,
            "minimum_similar_projects": 3,
            "local_presence_required": True,
        })
        vendor = next((item for item in shortlist["top_three"] if item["vendor_id"] == "VND-001"), None)
        self.assertIsNotNone(vendor)
        self.assertLess(vendor["technical_evaluation"], 100)
        self.assertLess(vendor["risk_score"], 100)
