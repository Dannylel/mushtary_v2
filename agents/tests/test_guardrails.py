"""
Guardrails tests: malformed LLM output must produce the fallback, never an exception.
"""
import unittest

from pydantic import BaseModel

from agents.guardrails import safe_parse, validate_output


class _Schema(BaseModel):
    name: str
    score: int


_FALLBACK = _Schema(name="fallback", score=0)


class TestGuardrails(unittest.TestCase):
    def test_valid_payload_passes_through(self):
        result = safe_parse({"name": "ok", "score": 7}, _Schema, _FALLBACK, "t1")
        self.assertEqual(result.name, "ok")
        self.assertEqual(result.score, 7)

    def test_missing_field_falls_back(self):
        result = safe_parse({"name": "no score"}, _Schema, _FALLBACK, "t2")
        self.assertIs(result, _FALLBACK)

    def test_wrong_type_falls_back(self):
        result = safe_parse({"name": "x", "score": "not-an-int-at-all"}, _Schema, _FALLBACK, "t3")
        self.assertIs(result, _FALLBACK)

    def test_validate_output_returns_none_on_failure(self):
        self.assertIsNone(validate_output({"bogus": True}, _Schema, "t4"))


if __name__ == "__main__":
    unittest.main()
