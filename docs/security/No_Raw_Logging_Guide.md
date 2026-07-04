# No-Raw-Logging & Retention Guide (Milestone 9J)

The system must never persist or log a raw D1/D2 web-research query, a raw prompt, a raw
provider response, or the concrete partner/project/budget terms the firewall removed. This
guide states the rules, the enforcement, and the minimal retention policy.

## What is never stored / logged

- **Raw D1/D2/D3 query** — never persisted anywhere. Only its `raw_query_hash` (SHA256) is
  kept, on `SearchQueryApproval` and (as `normalized_query_hash`) on `ResearchTask`.
- **Raw prompt / raw provider response / Firecrawl request body** — never persisted.
  `ToolInvocation` stores only `input_hash`/`output_hash`; `AgentInvocation.context_meta` is
  metadata-only; `UsageRecord` holds token counts + cost only.
- **Firewall-removed values** (partner/project/budget) — never appear in audit/control
  details, exports, or logs. `redaction_summary` carries only `{category, label, count}`.

## Enforcement

- **Recording writes hashes + category metadata only.** Firewall decisions record a
  metadata-only `CTRL.QUERY_FIREWALL` ControlResult (`{data_class}:{decision}:risk{n}`) and
  an AuditEvent whose detail is `{data_class, decision, risk_score, detected_categories,
  raw_query_hash}`.
- **Defensive backstop:** `app/security/redaction.py::assert_no_raw_query` runs on every
  firewall audit/control detail. It raises in dev/test if the raw query (verbatim) or a
  supplied sensitive term appears; in production it degrades to a no-op (a logging guard must
  never break a request). `safe_detail()` builds a hash-only detail.
- **Log scrubbing:** `app/config/logging.py::RedactingFilter` scrubs
  `query`/`raw_query`/`query_text`/`query_preview` values from log lines while preserving
  `*_hash` fields.
- **Output guard:** the research-results contract, market-comparison warnings, and technical
  evidence/audit exports carry no raw query, prompt, provider response, Firecrawl body, or
  removed names (regression-tested).
- **Tests:** `tests/test_privacy_firewall.py` asserts fake partner/budget strings never
  appear in `AuditEvent`/`ControlResult`/`ToolInvocation`/results, and that the log filter
  scrubs a query while keeping its hash.

## Retention policy (minimal, MVP)

| Artifact | Contents | Retention | Reset |
|----------|----------|-----------|-------|
| `SearchQueryApproval` | hash + sanitized query + category summary + status | Kept for audit of the decision; **no raw query** | Removed by demo/test DB reset (drop/recreate) |
| `ResearchTask` (metadata) | sanitized `query_text`, `normalized_query_hash`, status | Kept with the project | Removed on project/DB reset |
| `AuditEvent` | action + metadata detail (hashes/categories) | Kept as the audit trail | Removed on DB reset |
| `ControlResult` | control id + status + short reason code | Kept as the control trail | Removed on DB reset |
| `sanitized_query` | public-safe query text | Kept (already public-safe) | Removed on DB reset |
| `raw_query_hash` | one-way SHA256 | Kept for correlation; not reversible | Removed on DB reset |

**Raw D1/D2 query is never persisted**, so there is nothing to purge for it. Demo/test
resets recreate the database from migrations (`alembic upgrade head`) + `app.seed`, which
removes all of the above; the deterministic demo seed
(`app/demo/seed.py`, `DemoSeedManifest`) owns only its seeded objects and is likewise
reset. A future production deployment should attach a time-based retention/rotation policy
to `AuditEvent`/`ControlResult`/`SearchQueryApproval` per the institution's data-protection
requirements.
