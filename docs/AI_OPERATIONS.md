# AI Operations and Incident Tracing

Every API response includes `X-Request-ID` and `X-Trace-ID`. Background-job responses also
include `job_id` and `trace_id`. These identifiers correlate the user request, model calls,
JSON repairs, deterministic fallbacks, RAG lookups, tools, artifacts, revisions, approval,
and publication.

Authenticated users can retrieve their redacted incident trail with:

```text
GET /api/ai-events?job_id=<job_id>
GET /api/ai-events?trace_id=<trace_id>
Authorization: Bearer <demo session token>
```

Events are retained in `data/mushtary.db` for `AI_EVENT_RETENTION_DAYS` (30 by default).
Operational events never store raw prompts, generated text, proposals, uploaded documents,
commercial-registration numbers, credentials, or model responses. Sensitive values are
represented by a SHA-256 fingerprint and length. Full review evidence remains in the
access-controlled artifact record.

## Incident workflow

1. Obtain the user's job ID, trace ID, tender ID, vendor ID, or artifact ID.
2. Query the trace and inspect events in timestamp order.
3. Check `result_mode`: `AI_SUCCESS`, `AI_REPAIRED`, `PARTIAL_SUCCESS`, or
   `DETERMINISTIC_FALLBACK`.
4. Inspect model/provider, prompt SHA-256, latency, retry, token usage, RAG source IDs,
   schema validation, and tool status.
5. Compare the immutable artifact revision with its `parent_artifact_id`.
6. Confirm that approval belongs to the authenticated actor and occurred after all blocking
   consistency checks.

## Required production infrastructure

The included FastAPI server remains a demo application. Before exposing it publicly, terminate
TLS at the platform edge, replace demo session tokens with the product identity provider,
place SQLite on encrypted storage or migrate audit tables to the encrypted production
database, ship `ai_events` to the central log platform, and configure access/retention policies
for Saudi procurement data.

Recommended alerts:

- AI call error rate or fallback rate above the agreed threshold.
- P95 model latency above the configured timeout budget.
- Repeated JSON repair or schema-validation failures by model/prompt hash.
- RAG retrieval failure or use of an unknown index manifest.
- Approval rejection, ownership mismatch, or blocked publication.
- Token or job-duration budget anomalies.
