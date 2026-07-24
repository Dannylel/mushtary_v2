import tempfile
import unittest
from pathlib import Path

from agents import activity
from agents import artifact_store
from agents import observability
from agents.observability import bind_context, redact


class TestAIObservability(unittest.TestCase):
    def test_recursive_redaction_hides_sensitive_values(self):
        value = {
            "vendor": {
                "cr_number": "7000000000",
                "nested": {"api_key": "secret-value"},
            },
            "safe_count": 3,
        }
        safe = redact(value)
        self.assertTrue(safe["vendor"]["cr_number"]["redacted"])
        self.assertTrue(safe["vendor"]["nested"]["api_key"]["redacted"])
        self.assertEqual(safe["safe_count"], 3)
        self.assertNotIn("7000000000", str(safe))
        self.assertNotIn("secret-value", str(safe))

    def test_activity_is_scoped_to_one_job(self):
        with bind_context(trace_id="trace-a", job_id="job-a"):
            activity.publish("info", "job a")
        with bind_context(trace_id="trace-b", job_id="job-b"):
            activity.publish("info", "job b")
        events, _ = activity.get_since(0, job_id="job-a")
        self.assertTrue(events)
        self.assertTrue(all(event["job_id"] == "job-a" for event in events))
        self.assertNotIn("job b", [event["text"] for event in events])
        unscoped, _ = activity.get_since(0)
        self.assertEqual(unscoped, [])

    def test_durable_events_are_queryable_by_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = observability.DB_PATH
            observability.DB_PATH = Path(tmp) / "audit.db"
            try:
                with bind_context(request_id="req-test", trace_id="trace-test", job_id="job-test"):
                    observability.emit("ai.call.completed", input_tokens=12, output_tokens=4)
                events = observability.list_events(trace_id="trace-test")
                self.assertEqual(events[-1]["event"], "ai.call.completed")
                self.assertEqual(observability.trace_usage("trace-test")["input_tokens"], 12)
            finally:
                observability.DB_PATH = previous


class TestApprovalIntegrity(unittest.TestCase):
    def test_wrong_actor_cannot_mutate_approval_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = artifact_store.DB_PATH
            artifact_store.DB_PATH = Path(tmp) / "audit.db"
            try:
                stored = artifact_store.save_artifact({
                    "id": "artifact-1",
                    "trace_id": "trace-1",
                    "type": "TENDER_DRAFT",
                    "actor_id": "BUY-001",
                    "status": "DRAFT",
                    "prompt_name": "test",
                    "prompt_version": "1.0.0",
                    "model_used": "test-model",
                    "input_snapshot": {},
                    "output": {},
                })
                self.assertEqual(stored["status"], "DRAFT")
                attempted_overwrite = dict(stored)
                attempted_overwrite["output"] = {"mutated": True}
                artifact_store.save_artifact(attempted_overwrite)
                self.assertEqual(artifact_store.get_artifact("artifact-1")["output"], {})
                self.assertIsNone(
                    artifact_store.approve_artifact("artifact-1", buyer_id="BUY-OTHER")
                )
                self.assertEqual(
                    artifact_store.get_artifact("artifact-1")["status"], "DRAFT"
                )
                approved = artifact_store.approve_artifact(
                    "artifact-1", buyer_id="BUY-001"
                )
                self.assertEqual(approved["status"], "APPROVED")
                self.assertIsNone(
                    artifact_store.approve_artifact("artifact-1", buyer_id="BUY-001")
                )
            finally:
                artifact_store.DB_PATH = previous

    def test_demo_actor_tokens_are_signed_and_tamper_evident(self):
        import api

        token = api._issue_actor_token("buyer", "BUY-001")
        self.assertEqual(api._decode_actor_token(token)["actor_id"], "BUY-001")
        payload, signature = token.split(".", 1)
        tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + signature
        self.assertIsNone(api._decode_actor_token(tampered))


if __name__ == "__main__":
    unittest.main()
