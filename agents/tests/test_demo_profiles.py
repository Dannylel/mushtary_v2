import unittest

from agents.reputation import list_buyers, list_vendors


class TestDemoProfiles(unittest.TestCase):
    def test_vendor_profiles_include_agent_evidence(self):
        vendor = list_vendors()[0]
        for key in ("document_profile", "verification_evidence", "delivery_history", "commercial_profile", "capability_evidence", "reputation_evidence", "vri"):
            self.assertIn(key, vendor)

    def test_buyer_profiles_include_bri_evidence(self):
        buyer = list_buyers()[0]
        for key in ("evaluation_evidence", "payment_evidence", "governance_evidence", "reputation_evidence", "bri"):
            self.assertIn(key, buyer)
