# M10 Feature Freeze Audit

M10 freezes the backend feature scope. This audit records what is implemented, what is
enabled, what is beta-internal, and what is explicitly out of scope. No new product features
are added in M10.

## Implemented milestones
M1 Backend Foundation · M2 Source Ingestion · M3 Run Orchestration · M4 Requirements & Rules ·
M4.1 Unicode Ingestion · M5 Deterministic Evidence · M6 Template Drafts · M6.1 Demo Dataset ·
M7 Review/Recheck/Approval · M8 Export · M8.1 Innolink Copy Assistant · M9A Agent
Infrastructure · M9B A1 Fact Extraction · M9C A1 Evidence Mapping · M9D A2 Solution &
Innovation · M9D.1 E2E Stabilization · M9D.2 Cloud Processing Gate · M9E A2 Value Creation ·
M9G A3 Evidence Consistency · M9I-A Public Web Research · M9I-B Market & Competitor Comparison ·
M9J Privacy / Data Classification / Search Query Firewall · M9K MAS Reliability & Value
Assurance · **M10 Evaluation & Hardening**.

## Feature flags (settings)
| Flag | Default | Effect |
|------|---------|--------|
| `demo_data_enabled` | false | Enables the demo/evaluation seed (dev/test only). |
| `agent_fake_provider` | false | Deterministic fake A1/A2/A3 provider (no network/key). |
| `web_research_enabled` | false | Public web research feature gate. |
| `web_research_fake_provider` | false | Deterministic fake Firecrawl (its own flag). |
| `d2_web_research_enabled` | false | Allows an approved sanitized D2 query to reach a **live** provider. |
| `run_real_provider_smoke` | false | Optional, env-gated real-provider smoke (never required for CI). |
| `agent_institutional_route_approved` | false | Real cloud route for internal data (not approved in beta). |

Capabilities advertised truthfully via `GET /api/v1/capabilities`: `projects, sources,
source_parsing, partners, runs, requirements, evidence, drafts, review, export, reliability`
are on; `web_research`/`market_comparison` are on only when enabled **and** a provider (real
Firecrawl or the fake) is configured; `url_import` stays off.

## Beta-only internal endpoints (not in the finalized OpenAPI)
- **Market comparison** — `POST/GET /projects/{id}/market-comparisons`, item status.
- **Search Query Firewall** — `POST /projects/{id}/search-query-firewall/preview`,
  `POST /search-query-approvals/{id}/approve|reject`.
- **Reliability (M9K)** — `POST/GET /runs/{id}/reliability`.
These are documented beta-internal surfaces; they do not modify any finalized contract.

## Provider modes
- **deterministic_only** — no provider; exact-match evidence, template drafts, reliability.
- **fake providers** — `AGENT_FAKE_PROVIDER` / `WEB_RESEARCH_FAKE_PROVIDER`; drive ALL
  mandatory tests. No key.
- **real OpenAI/Anthropic / real Firecrawl** — optional, env-gated; never required.
- **Azure enterprise** — **target architecture only**, not deployed. See
  [Provider_Mode_Matrix.md](Provider_Mode_Matrix.md).

## Known unsupported areas (documented)
See [Known_Limitations.md](Known_Limitations.md): structured repeated portal fields (work
packages, milestones, full budget tables), SNF/Horizon, provider vector stores for
confidential data, live confidential cloud processing.

## Explicitly OUT of M10
- **M9H Innovation Challenge**
- **Full Azure production deployment / compliance**
- **NDA data processing** (D3 stays blocked)
- **Full SNF / Horizon support**
- **Automatic portal submission**
- **Automatic application approval**
- **Automatic funding-probability prediction**

M10 is stabilization, evaluation and documentation only.
