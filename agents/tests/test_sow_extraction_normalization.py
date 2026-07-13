import unittest

from agents.sow_extractor.agent import _fallback_from_text, _normalize_extraction_data


class TestSowExtractionNormalization(unittest.TestCase):
    def test_null_deliverable_fields_are_reviewable_strings(self):
        fallback = _fallback_from_text("Scope of Work: deliver a service", "trace-test")
        data = _normalize_extraction_data(
            {
                "deliverables": [{"name": "Mobilization", "description": None, "format": None}],
                "timeline": [{"milestone": "Kickoff", "date": None}],
            },
            "Scope of Work: deliver a service",
            fallback,
        )
        self.assertEqual(data["deliverables"][0]["name"], "Mobilization")
        self.assertEqual(data["deliverables"][0]["description"], "Details to be confirmed during buyer review.")
        self.assertIsNone(data["deliverables"][0]["format"])
        self.assertEqual(data["timeline"][0]["date"], "As per buyer-approved plan")
