"""
Registry-consistency tests: every PROMPT_NAME / PROMPT_VERSION declared in agent code must
have a matching entry (same version) in prompt_registry.REGISTRY. This is the invariant that
silently broke before — these tests make the drift impossible to miss.

Run:  python -m pytest agents/tests -q   (or python -m unittest discover agents/tests)
"""
import unittest

from agents.prompt_registry import REGISTRY


def _pairs_in_code() -> list[tuple[str, str]]:
    """Collect every (PROMPT_NAME, PROMPT_VERSION) pair declared by agent code."""
    from agents.vendor_validation import prompts as vv
    from agents.sow_extractor import prompts as sow
    from agents.tender_drafting import prompts as td
    from agents.tender_drafting import agent as td_agent
    from agents.graph import pipeline as graph_pipeline
    from agents.evaluation import prompts as ev
    from agents.form_generator import agent as fg

    return [
        (vv.PROMPT_NAME, vv.PROMPT_VERSION),
        (sow.PROMPT_NAME, sow.PROMPT_VERSION),
        (td.PROMPT_NAME, td.PROMPT_VERSION),
        (td_agent.PROMPT_NAME, td_agent.PROMPT_VERSION),
        (graph_pipeline.PROMPT_NAME, graph_pipeline.PROMPT_VERSION),
        (ev.SCORE_PROMPT_NAME, ev.SCORE_PROMPT_VERSION),
        (ev.RANK_PROMPT_NAME, ev.RANK_PROMPT_VERSION),
        (fg.PROMPT_NAME, fg.PROMPT_VERSION),
    ]


class TestRegistryConsistency(unittest.TestCase):
    def test_every_code_prompt_is_registered(self):
        for name, _version in _pairs_in_code():
            self.assertIn(name, REGISTRY, f"Prompt '{name}' used in code but not registered")

    def test_versions_match_registry(self):
        for name, version in _pairs_in_code():
            self.assertEqual(
                REGISTRY[name]["version"], version,
                f"Version drift for '{name}': code={version} registry={REGISTRY[name]['version']}",
            )

    def test_registry_entries_well_formed(self):
        for name, entry in REGISTRY.items():
            self.assertEqual(entry["name"], name, f"Entry key/name mismatch for '{name}'")
            for field in ("version", "intent", "agent", "inputs", "outputs", "model"):
                self.assertIn(field, entry, f"Registry entry '{name}' missing field '{field}'")

    def test_prompt_files_exist_for_loaded_slugs(self):
        # Every prompt .md referenced via load_prompt must exist (import-time check already
        # does this, but a missing file should fail HERE with a clear message, not at runtime).
        from agents.prompts import list_prompts

        expected = {
            "vendor_validation_system", "sow_extractor_system", "form_generator_system",
            "drafting_scope_system", "drafting_legal_eval_system",
            "drafting_execution_system", "drafting_context_narrative_system",
            "evaluation_scoring_system", "evaluation_ranking_system",
        }
        missing = expected - set(list_prompts())
        self.assertFalse(missing, f"Missing prompt files: {missing}")


if __name__ == "__main__":
    unittest.main()
