# Milestone 9J — Privacy, Data Classification & Search Query Firewall Baseline

**Scope:** a minimal but *technically enforced* privacy baseline so that confidential
proposal ideas cannot leak to external tools (Firecrawl / cloud LLMs) via raw search
queries. The guarantee no longer depends on prompt instructions — it is enforced in the
backend at the single web-research chokepoint. This is a **security-architecture** milestone,
not a new proposal feature.

## Branch / commit basis
- Branch **`feat/privacy-leakage-controls`**, from **`4fd108d`** ("Milestone 9I-B: Market
  Competitor Comparison").
- Tag **`milestone-9i-b-market-competitor-comparison`** added on `4fd108d` (STEP 0).
- No M9J auto-commit (only the STEP-0 tag + branch).

## Contract decision
D0–D3/UNKNOWN are a **code-only, beta-internal** label derived from the finalized 5-field
`DataClassification`; the central tool matrix and the firewall are code + docs. **No
finalized contract YAML was modified** — `git status` shows no change under
`final_backend_contracts_v1_1/`. (The only contract-adjacent code change is an *additive,
optional* `approval_id` field on the internal `ResearchTaskCreate` Pydantic model — the
finalized OpenAPI is untouched.)

## Changed files
- **New (backend):** `app/security/{data_class,policy_matrix,search_query_firewall,
  confidential_terms,approval_service,redaction}.py`, `app/api/firewall.py`,
  `app/contracts/firewall.py`, `app/migrations/versions/e2b6c4f8a1d3_search_query_approvals.py`,
  `tests/{test_data_class,test_privacy_firewall}.py`.
- **Modified (backend):** `app/research/{service,executor,import_service}.py`,
  `app/api/research.py`, `app/contracts/research.py`, `app/db/models.py`,
  `app/config/{settings,logging}.py`, `app/main.py`, `tests/test_public_web_research.py`.
- **New (frontend):** `lib/{data-class,firewall}.ts`,
  `app/api/projects/[id]/search-query-firewall/preview/route.ts`,
  `app/api/search-query-approvals/[id]/{approve,reject}/route.ts`,
  `test/firewall-panel.test.tsx`, `e2e/privacy-firewall.spec.ts`.
- **Modified (frontend):** `components/quellen/public-research-panel.tsx`,
  `app/quellen/page.tsx`, `lib/research.ts`.
- **Docs:** `docs/security/{M9J_Privacy_Gap_Audit,Data_Classification_and_Tool_Policy,
  Search_Query_Firewall,No_Raw_Logging_Guide}.md`, this report.

## Data class model
`app/security/data_class.py::derive_data_class` over the *effective* classification:
`nda_applies`→**D3**; `confidential`→**D2**; `internal`→**D1**; `public`+public/synthetic
origin→**D0**; missing/ambiguous→**UNKNOWN** (deny-by-default). D3/UNKNOWN are
`is_external_blocked`. See [Data_Classification_and_Tool_Policy.md](../security/Data_Classification_and_Tool_Policy.md).

## Policy matrix
`app/security/policy_matrix.py` — one authoritative `(class × tool) → decision` table,
**fail-closed** (unlisted pair = BLOCKED). It wraps, not replaces, the existing gates, so D0
behaviour is unchanged.

## Search Query Firewall design
Deterministic, local, no-LLM (`app/security/search_query_firewall.py`). Per-project lexicon
(title, partner names, representatives, aliases, budget) + generic detectors (e-mail, phone,
currency, NDA markers, confidential dictionary). Produces `raw_query_hash`, `sanitized_query`,
category-only `redaction_summary`, `risk_score`, and `allow|require_human_approval|block`.
**Block-on-uncertainty** for D2. Full design in [Search_Query_Firewall.md](../security/Search_Query_Firewall.md).

## Approval flow
`search_query_approvals` table + `app/security/approval_service.py`. Stores **only** the
hash + sanitized query + category summary (**never the raw query**). Single-use; changing
the query invalidates it; rejected/expired/used are refused; workspace-scoped. Endpoints:
`POST /projects/{id}/search-query-firewall/preview`, `POST
/search-query-approvals/{id}/approve|reject`.

## Web-research integration (the chokepoint)
Enforced in `app/research/service.py::create_research_task` (service layer — agents use the
same path and cannot bypass):
- **D0 + allow** → normalized query proceeds (existing behaviour, tests green).
- **D0 mid-risk / D1 / D2** → require an approved, hash-matching `approval_id`; only the
  stored **sanitized** query becomes `query_text`. The raw query is hashed and discarded.
- **D3 / UNKNOWN** → refused (403) at creation.
The executor bypasses the sensitivity block for an approved-sanitized D1/D2 task (the
external query is public-safe) but applies the **D2 live-provider gate**
(`D2_WEB_RESEARCH_ENABLED`, default off). Import (`import_service.py`) mirrors this so a
D2 sanitized flow can import the resulting `public_source`. The provider is reachable only
through service→executor/import (regression-tested).

## Logging safeguards & output guard
Recording writes hashes + category metadata only; `assert_no_raw_query` is a dev/test-fatal
backstop on firewall audit/control details; `RedactingFilter` scrubs query values from logs
(keeps hashes); the research-results contract and technical-evidence export expose no raw
query/prompt/provider response/Firecrawl body/removed names. See
[No_Raw_Logging_Guide.md](../security/No_Raw_Logging_Guide.md).

## Tests & results (fake provider only)
- **Backend `pytest`: 469 passed, 3 skipped** (+23 new — `test_data_class.py`,
  `test_privacy_firewall.py`: mapping, UNKNOWN fail-closed, most-restrictive-wins, matrix
  fail-closed, D0/D2 firewall, approval single-use / changed-query / rejected, D3+UNKNOWN
  blocked, D2 live gate, provider boundary, workspace isolation, no-raw-in-records, log
  redaction, D2 import → public_source).
- **Frontend `vitest`: 126 passed** (+4 — `firewall-panel.test.tsx`: D2 preview appears,
  approval required, sanitized query used, blocked message, no provider names; the existing
  public-research tests stay green under the default D0 path). `eslint` clean; `tsc --noEmit`
  clean; `next build` OK.
- **Playwright (`--workers=1`, fakes): 22 passed, 1 skipped** (+4 — Flow A D0 works, Flow B
  D2 sanitize→approve→search→import with no raw leak (API), Flow C D3+UNKNOWN blocked, Flow
  B UI preview→approve→results). Existing M9I-A/M9I-B specs stay green.
- **Manual Flow B leak check:** the backend log contained **0** occurrences of the raw
  partner name / budget figure / raw query, and **0** API-key/provider secrets.

## Acceptance criteria — status
Data classes explicit ✓ · UNKNOWN fails closed ✓ · Firecrawl never receives raw D2 text ✓ ·
D2/D1 require sanitized preview + approval ✓ · D3/NDA blocked ✓ · firewall backend-enforced
(agents cannot bypass) ✓ · raw query not persisted for D1/D2/D3 ✓ · logs metadata-only ✓ ·
leakage regression tests green ✓ · existing D0 web research works ✓ · M9I-B market comparison
still works ✓ · **no finalized contract modified** ✓ · full suite green ✓ · provider boundary
tested ✓ · workspace isolation tested ✓ · D2 live provider gated ✓ · export carries no raw
data ✓ · report includes the two required sections (below) ✓.

## Known limitations
- Sanitization is deterministic (regex + lexicon + dictionary); it is conservative and may
  over- or under-generalize. It is a safety net, not a guarantee of perfect anonymization —
  block-on-uncertainty errs toward blocking for D2.
- The frontend derives the panel's class from the intake/run context; the **backend** is the
  authoritative enforcement point regardless of the UI.
- D3/NDA and real confidential cloud processing remain out of scope; the Azure enterprise
  path is documented as *target architecture only*.

## Security is not product success
M9J makes confidential use *safe to attempt* — it does **not** prove proposal quality. It is
a security milestone, not a value/quality milestone. Preventing idea leakage is necessary
but not sufficient: a proposal can be privacy-safe and still be weak, unsupported, or a poor
funding fit. Quality is addressed elsewhere (deterministic evidence, A2/A3 review) and,
critically, by the reliability work below.

## Remaining MAS Reliability Risks (→ M9K)
The multi-agent system (A1/A2/A3 + advisory research/market layers) still carries reliability
risks that M9J does not address and that must be closed **before** a beta evaluation:

- **Cascading reliability loss** — an early weak/incorrect step (extraction, evidence, draft)
  propagates and compounds through later agents.
- **False consensus between agents** — agents agreeing does not make an output correct;
  apparent agreement can mask a shared error.
- **Semantic drift around eligibility / funding fit** — gradual meaning-shift so that
  eligibility or funding-fit claims no longer match the underlying rules/evidence.
- **Incorrect verification** — a claim marked "verified" that is not truly supported, or an
  evidence link that does not actually substantiate the statement.
- **Unsupported claims in generated drafts** — A2/A3 text asserting facts without a valid,
  verifiable source.

**M9K** will address these with reliability tests and quality gates (cross-agent consistency
checks, verification audits, drift detection, and unsupported-claim gating). Until then, all
generated content remains advisory and human-review-required.

## Readiness verdict for M9H / M10
M9J delivers the privacy substrate the target system needs to process confidential ideas at
all: explicit data classes, a fail-closed tool matrix, a backend-enforced query firewall,
single-use sanitized approvals, and metadata-only logging — with no finalized-contract
change and all existing flows (D0 web research, M9I-B market comparison) intact. The
firewall/approval + no-raw-logging discipline generalizes to any future external-tool
surface. **Ready for M9H / M10**, with **M9K (MAS reliability) as the required precondition
for a beta evaluation.**
