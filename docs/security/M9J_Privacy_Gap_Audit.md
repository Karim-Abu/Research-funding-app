# M9J — Privacy Gap Audit (pre-implementation findings)

This note records the state of the system **before** the M9J privacy baseline, and the
gaps M9J closes. It is the STEP-1 deliverable; the design decisions are in
[Data_Classification_and_Tool_Policy.md](Data_Classification_and_Tool_Policy.md),
[Search_Query_Firewall.md](Search_Query_Firewall.md) and
[No_Raw_Logging_Guide.md](No_Raw_Logging_Guide.md).

## Current state (verified in code)

- **Classification** is a 5-field `DataClassification`
  (`backend/app/contracts/classification.py`): `sensitivity`
  (public|internal|confidential), `origin`, `processing_mode`, `web_research_mode`,
  `nda_applies`. Stored as JSON on `Project` (immutable after creation).
- **Most-restrictive-wins + deny-by-default** already exists
  (`app/policy/classification.py::resolve_effective_classification`, defaults to
  `confidential` / `nda=True`).
- **Gates** today: `app/research/policy.py::evaluate_web_research` (web tool boundary),
  `app/agents/data_policy.py::evaluate` (model-route boundary), `app/runs/cloud_policy.py`
  (cloud-assisted runs). All are public/synthetic-only in the beta.
- **Web research path:** `app/api/research.py::create_research_task` →
  `app/research/service.py::create_research_task` (stores `query_text =
  normalize_query(query_preview)`) → `app/research/executor.py::research_executor`
  builds `SearchRequest(query=task.query_text)` → `provider.search()`. Firecrawl
  (`providers/firecrawl.py`) sends `request.query` **raw** in the POST body.
- **Logging is already conservative:** `ToolInvocation` stores `input_hash` only;
  `AgentInvocation.context_meta` is metadata-only; `UsageRecord` has no text; research
  `AuditEvent.detail` payloads are `{"purpose"…}` / `{"result_count"…}`;
  `ControlResult.detail` is a short reason string. `config/logging.py::RedactingFilter`
  scrubs password/csrf/auth — but not query text.

## Classified gaps (closed by M9J)

| # | Gap | Description | Closed by |
|---|-----|-------------|-----------|
| 1 | **Data-classification gap** | No explicit D0–D3/UNKNOWN labels; callers reason ad-hoc over 5 fields. | STEP 2 `data_class.py` (code-only derivation). |
| 2 | **Query-leakage gap** | The only thing stopping a confidential query from reaching Firecrawl is operational discipline; `query_text` is sent raw to the provider. No sanitization, no preview, no approval. | STEP 4 firewall + STEP 6 chokepoint enforcement (raw hashed-and-discarded; only sanitized query reaches the provider). |
| 3 | **Logging gap** | No query-redaction pattern; no enforced "no raw query in detail" rule. | STEP 8 `redaction.py` guard + `RedactingFilter` pattern + tests. |
| 4 | **Policy-routing gap** | No single source of truth for which tool a data class may use; each gate hard-codes its own subset. | STEP 3 central fail-closed `policy_matrix.py`. |
| 5 | **UI/approval gap** | The Quellen panel sends the raw query directly; no sanitize preview / human approval for sensitive classes. | STEP 7 D1/D2 preview + approval UX. |
| 6 | **Test-coverage gap** | No leakage regression tests, no provider-boundary test, no workspace-isolation test for research/approvals. | STEP 10 backend + frontend + Playwright. |

## Scope guardrails (carried into implementation)

- D0–D3/UNKNOWN are **code-only beta-internal**; **no finalized contract YAML is edited**.
- D3/NDA stays **blocked** in the MVP. D1/D2 require sanitize + human approval.
- **D2 live Firecrawl is gated** behind `D2_WEB_RESEARCH_ENABLED` (default off); mandatory
  tests use the fake provider; D0 public/synthetic stays live-capable.
- No LLM is used for sanitization (deterministic/regex/dictionary only).
