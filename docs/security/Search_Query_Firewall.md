# Search Query Firewall (Milestone 9J)

The Search Query Firewall (`app/security/search_query_firewall.py`) is a deterministic,
local, **no-LLM** screen that every web-research query for a confidential (D1/D2) project
must pass **before** anything is sent to Firecrawl. It guarantees that a raw confidential
query never leaves the system: the raw text is hashed and discarded, and only a
firewall-sanitized, human-approved query is ever searched.

## Interface

`evaluate_query(db, *, project_id, workspace_id, actor_user_id, raw_query, data_class,
intended_tool, purpose=None, source_context_ids=None) -> FirewallResult` with:

- `raw_query_hash` — SHA256 of the normalized query (NFKC + casefold + whitespace
  collapse). Correlates preview ↔ create without persisting the raw text.
- `sanitized_query` — public-safe query (sensitive spans removed/generalized).
- `redaction_summary` — `[{category, label, count}]`, **category metadata only, never raw
  values**.
- `risk_score` (0–10) → mapped to a coarse `low|medium|high` label for the UI.
- `decision` — `allow | require_human_approval | block`.
- `reasons[]`, `detected_sensitive_categories[]`.

## Detection

- **Generic detectors (all classes):** e-mail, phone, currency amounts (`CHF/EUR/USD/…` +
  figure), NDA markers, a small versioned confidential-keyword dictionary
  (`app/security/confidential_terms.py`, `CONFIDENTIAL_DICTIONARY_VERSION`).
- **Project-specific lexicon (D1/D2 only)** — built from **local** data only, never fetched
  (binding correction 10): project **title**, **partner names** (`Partner.name`),
  organization **representatives** (`Partner.official_representative`), partner location,
  project-specific **aliases** (where available), and the **budget** figure
  (`budget_framework_chf`, with common groupings). A user-maintained sensitive-term list is
  a documented future hook. For a **public (D0)** project this lexicon is **not** applied —
  those names are public by definition (this keeps the existing D0 flow unchanged).

## Sanitization

Deterministic removal/generalization (no LLM, no external call): partner/project names,
budget figures, e-mail/phone, and confidential keywords are removed; full-sentence
descriptions are reduced toward public problem/technology/category terms. **Omission /
generalization is preferred over bracket placeholders.** By construction the sanitized
query contains none of the detected sensitive terms.

## Decision rules

| Class | 0–2 | 3–5 | 6–10 |
|-------|-----|-----|------|
| **D0** | allow | require approval | block |
| **D1 / D2** | require approval | require approval | block |
| **D3 / UNKNOWN** | block | block | block |

**Block-on-uncertainty (binding correction 9):** for D1/D2, a query that reads like a
free-form idea (too long) — or whose sanitized form has nothing usable left — is
**blocked**, never auto-sanitized-and-sent. The user is asked to generalize.

Risk weights (`CATEGORY_WEIGHTS`) are calibrated so that a couple of removable identifiers
(partner + budget) stays **sanitizable** (require approval), while an NDA marker or a
free-form idea **blocks** on its own.

## Approval flow (`app/security/approval_service.py`, table `search_query_approvals`)

1. `POST /projects/{id}/search-query-firewall/preview` runs the firewall. For
   `require_human_approval` it persists a **pending** `SearchQueryApproval` storing only the
   `raw_query_hash` + `sanitized_query` + `redaction_summary` (**never the raw query**).
2. `POST /search-query-approvals/{id}/approve|reject` decides it (only `pending` may
   transition).
3. `createResearchTask` with the `approval_id` re-hashes the incoming query and calls
   `consume_for_task`: it must match an **approved, unused** approval for the same project,
   then marks it **used** (`used_by_research_task_id`). Only the stored `sanitized_query`
   becomes `ResearchTask.query_text`.

Properties: **single-use**; **changing the query** (different hash) → `expired` (409);
rejected/expired/used → refused; every decision writes a metadata-only `CTRL.QUERY_FIREWALL`
ControlResult + AuditEvent; all rows are **workspace-scoped** (cross-workspace → 403/404).

## D2 live-provider flag

`D2_WEB_RESEARCH_ENABLED` (default `false`): even an approved sanitized D2/D1 query reaches
a **live** Firecrawl only when this flag is on. Otherwise the fake provider is used
(dev/test) or the executor blocks with `d2_live_web_research_disabled`. D0 is unaffected.

## UI

For D0 the panel runs the query directly. For D1/D2 it shows **"Vor Webrecherche prüfen"**,
then the **"Bereinigte Suchanfrage"** with the removed categories, the note *"Die Websuche
erhält nur die bereinigte Anfrage."*, and an approve action. Blocked queries show a
"formulieren Sie die Anfrage allgemeiner" message. No provider/model names, no raw policy
codes, no numeric score, and the raw confidential query is never rendered back.
