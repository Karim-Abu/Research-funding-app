# Provider Mode Matrix

How the system behaves across provider modes. **All mandatory verification runs in
deterministic / fake modes — no real provider or key is ever required.** Azure is **target
architecture, not deployed**; no production Azure compliance is claimed.

| Mode | Enabled flags | Required env | Allowed data classes | Blocked data classes | Expected behaviour | Tests | Out of scope |
|------|---------------|--------------|----------------------|----------------------|--------------------|-------|--------------|
| **1. deterministic_only** | (none) | — | D0/D1/D2 for local deterministic work | external tools for all | Exact-match evidence, template drafts, deterministic review, reliability pass — no external call | Most backend tests; `deterministic_only` runs in e2e; `test_m10_smoke` | any LLM/web use |
| **2. fake providers** | `AGENT_FAKE_PROVIDER`, `WEB_RESEARCH_FAKE_PROVIDER` | those flags = true | D0 web/agent (fake); D1/D2 web only via firewall + approval | D3/UNKNOWN external | Deterministic fake A1/A2/A3 + fake Firecrawl; drives ALL mandatory tests | all agent/web/market/reliability tests + Playwright | real network |
| **3. real OpenAI/Anthropic** | provider key + `AGENT_INSTITUTIONAL_ROUTE_APPROVED` for internal | `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, `RUN_REAL_PROVIDER_SMOKE` | D0 (public/synthetic) cloud with confirmation | D2/D3 external; D1 unless institutionally approved | Real A1/A2/A3 via ModelGateway; data policy + CostGuard enforced | optional env-gated real smoke only | mandatory CI |
| **4. real Firecrawl** | `WEB_RESEARCH_ENABLED` + `FIRECRAWL_API_KEY` (fake off) | `FIRECRAWL_API_KEY` | D0 public web research; D1/D2 only a firewall-sanitized + approved query when `D2_WEB_RESEARCH_ENABLED` | D3/UNKNOWN; raw D1/D2 queries | Real search/fetch of public sources; SSRF + firewall gates apply | not in mandatory CI (env-gated) | mandatory CI |
| **5. Azure enterprise** | — | — | — | — | **Target architecture only — not implemented/deployed.** Documented target controls: Regional/Standard deployment, Private Endpoint, no raw prompt logging, disabled stateful provider features, metadata-only audit. Does **not** eliminate legal/government-access risk; productive confidential use needs a DPA + FHNW data-protection review. | n/a | production Azure |

## Notes
- The web fake provider has its **own** flag (`WEB_RESEARCH_FAKE_PROVIDER`) — it is not
  implied by `AGENT_FAKE_PROVIDER`.
- D3 (NDA) and UNKNOWN are blocked from all external tools in every mode.
- No provider vector stores are used for confidential data in any mode.
- **D1/D2 web research (modes 2/4):** the raw submitted query is never stored or sent (hash
  only); the provider receives the firewall-**sanitized**, human-approved query. Deterministic
  sanitization is **risk reduction, not a secrecy guarantee** — undetected confidential terms
  can survive into the sanitized query. `D2_WEB_RESEARCH_ENABLED` therefore stays default-off;
  enabling live D2 research requires explicit governance approval and reviewer diligence
  (see [Search_Query_Firewall.md](../security/Search_Query_Firewall.md)).
