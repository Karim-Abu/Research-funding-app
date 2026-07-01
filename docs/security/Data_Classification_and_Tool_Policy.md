# Data Classification & Tool Policy (Milestone 9J)

This document defines the privacy data classes D0–D3/UNKNOWN and the central tool-access
matrix that governs which external surface each class may touch. The classes are a
**code-only, beta-internal** label derived from the finalized 5-field `DataClassification`
(`final_backend_contracts_v1_1/data_policy_v1_1.yaml`) — **no finalized contract is
modified**. The backend enforces this matrix; the UI never relaxes it.

## Data classes

| Class | Meaning | Derived from (effective classification) |
|-------|---------|------------------------------------------|
| **D0_PUBLIC** | Public / synthetic demo data | `sensitivity=public` **and** `origin ∈ {public_source, synthetic}` |
| **D1_INTERNAL** | Internal working data | `sensitivity=internal` |
| **D2_CONFIDENTIAL_IDEA** | Project idea, drafts, partner strategy, budget, IP, non-public business model | `sensitivity=confidential` |
| **D3_NDA_BLOCKED** | NDA / legally restricted | `nda_applies=true` (any sensitivity) |
| **UNKNOWN** | Missing / ambiguous — **deny-by-default** | no/garbage sensitivity, or `public` with a non-public origin |

Derivation is `app/security/data_class.py::derive_data_class`, applied to the **effective**
classification (`app/policy/classification.py::resolve_effective_classification`, which is
most-restrictive-wins + deny-by-default). Rules:

- **UNKNOWN fails closed** — blocked from every external tool.
- **D3 is blocked** in the MVP (all external AI/web). No NDA processing is built.
- **D2 is never sent to an external tool raw.** It may only produce a public-safe query
  after the Search Query Firewall + human approval.
- **D0** may use public web research directly.
- **D1** web research is blocked in the beta **unless** the query is sanitized + approved
  (same path as D2).

## Tool routing matrix (fail-closed)

Source of truth: `app/security/policy_matrix.py`. Any pair **not** listed is `BLOCKED`.

| Tool ↓ / Class → | D0 | D1 | D2 | D3 | UNKNOWN |
|---|---|---|---|---|---|
| Azure/LLM gateway | allow¹ | allow-if-approved¹ | allow-if-approved¹ | blocked | blocked |
| Direct provider (OpenAI/Anthropic) | allow¹ | blocked | blocked | blocked | blocked |
| **Firecrawl / web research** | **allow** | **sanitized+approval** | **sanitized+approval** | **blocked** | **blocked** |
| Market-comparison LLM | allow¹ | blocked | blocked | blocked | blocked |
| A2 drafting | allow¹ | blocked | blocked | blocked | blocked |
| A3 review | allow¹ | blocked | blocked | blocked | blocked |
| Export | allow | allow | allow | blocked | blocked |
| Logs | metadata-only | metadata-only | metadata-only | metadata-only | metadata-only |
| Local DB / storage | allow | allow | allow | allow | blocked |
| Provider vector store | blocked | blocked | blocked | blocked | blocked |

¹ *allow-if-cloud-confirmed* — subject to the existing M9D.2 cloud-processing confirmation
gate. The matrix **wraps** (does not replace) the existing gates
(`evaluate_web_research`, `data_policy.evaluate`, `cloud_policy`), so D0 behaviour is
unchanged.

## Firecrawl rules

- The provider is reachable **only** through Agent → Tool Request → Policy Gateway (matrix)
  → **Search Query Firewall** → provider, inside `app/research/{service,executor,
  import_service}.py`. No agent/profile constructs a provider or calls it directly
  (regression-tested).
- Firecrawl **never** receives a raw D1/D2 query. Only the firewall-sanitized query is
  sent, and only after human approval.
- **D2/D1 live gate:** even an approved sanitized query reaches a *live* Firecrawl only
  when `D2_WEB_RESEARCH_ENABLED=true`. Off by default; otherwise the fake provider is used
  (dev/test) or the task is blocked. **D0 public/synthetic stays live-capable.**
- Imported results become normal `public_source` / `public` `SourceDocument`s (a public
  pull-in, not a confidential push-out).

## Azure enterprise path — TARGET architecture, not a current guarantee

The following are **target controls** for a future confidential-cloud deployment. They are
**not active** in the MVP and this section makes **no claim** that they are in place today.

- Azure OpenAI in a **Regional/Standard** deployment (data-residency-scoped), reached over a
  **Private Endpoint** (no public egress).
- **No raw prompt/response logging** on the provider side; **stateful provider features**
  (vector stores, fine-tuning, retention) **disabled**; audit remains **metadata-only**.
- Even with these controls, Azure **does not eliminate legal/government-access risk**.
  Productive confidential use requires a **DPA / contractual basis** and a review by the
  **FHNW data-protection responsible person** before any real confidential data is processed
  in the cloud.

## MVP limitations

- D0–D3 are code-derived, not stored columns; a project always carries a full 5-field
  classification, so a real project never derives to UNKNOWN.
- D3/NDA and real confidential cloud processing are intentionally out of scope.
- Sanitization is deterministic (regex + per-project lexicon + dictionary), **no LLM**.
