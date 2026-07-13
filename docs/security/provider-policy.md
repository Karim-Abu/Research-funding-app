# ProviderPolicy — Provider × Datenklassen (R4.3)

> Maschinell durchgesetzt in `backend/app/config/provider_policy.py`
> (Enforcement im ModelGateway, `backend/app/agents/gateway.py`). Grundlage:
> E-02 (bestätigt 2026-07-08) und der Owner-Entscheid vom 2026-07-08
> (D1/D2-KI nur nach manuellem Opt-in + Warnung; D3/Unknown bleiben blockiert).
> Tests: `backend/tests/test_provider_policy.py`, `test_processing_gate.py`,
> `test_a2_redraft_api.py`.

## Ist-Zustand

- **Fake/local ist Default** für Tests, Demo und den lokalen KI-Pfad. Der
  Fake-Provider ist ein lokal-deterministischer Adapter ohne Netzwerkzugriff.
- **Direkte Consumer-APIs (OpenAI/Anthropic)** sind aktiv nur für **D0**
  (öffentlich/synthetisch) mit expliziter Cloud-Bestätigung pro Durchlauf
  (M9D.2). Für **echte D1/D2-Daten** (origin `real_project`) sind sie
  **blockiert — unabhängig von gesetzten API-Keys** (Contract DP-04).
- **D1/D2-KI** läuft ausschliesslich über den **lokalen Pfad**: der Nutzer
  schaltet KI beim Analyse-Start bewusst ein, sieht eine deutliche Warnung und
  bestätigt, sie verstanden zu haben (`local-ai-confirm-v1`). Der Lauf bleibt
  `local_only`; contract-konform (Matrix: internal/confidential × local_only =
  allowed). Kein Inhalt verlässt die Maschine.
- **D3 (NDA) und Unknown** sind für **jeden** Provider blockiert — auch für
  den Fake. Fail-closed ohne Ausnahme.
- **Evaluationsfälle (F1 synthetic):** synthetische/anonymisierte
  D2-Simulationen dürfen direkte APIs nur nutzen, wenn `AI_EVAL_MODE=real`
  gesetzt ist — das Setzen gilt als dokumentierte Owner-Freigabe
  (Mapping-Tabelle §3.1). Echte D2-Daten bleiben auch dann blockiert.

## Matrix (durchgesetzt, fail-closed — fehlender Eintrag = blockiert)

| Provider | D0 | D1 | D2 | D3 | Unknown | Vertrags-/Betriebsbasis |
|---|---|---|---|---|---|---|
| fake/local | erlaubt | erlaubt¹ | erlaubt¹ | blockiert | blockiert | lokal-deterministisch, keine externen Calls |
| direct_openai | erlaubt² | blockiert³ | blockiert³ | blockiert | blockiert | nur öffentliche/synthetische Beta-Daten (E-02) |
| direct_anthropic | erlaubt² | blockiert³ | blockiert³ | blockiert | blockiert | nur öffentliche/synthetische Beta-Daten (E-02) |
| azure | blockiert | blockiert | blockiert | blockiert | blockiert | Zielpfad, nicht aktiv (Contract: `azure_foundry.allowed_sensitivity: []`) |

¹ nur mit manuellem Opt-in + verstandener Warnung (Bestätigung pro Durchlauf,
`local-ai-confirm-v1`); erzwungen durch `data_policy` (`run_confirmation`).
² zusätzlich M9D.2-Cloud-Bestätigung pro Durchlauf erforderlich.
³ Ausnahme nur origin `synthetic`/`anonymized` **und** `AI_EVAL_MODE=real`
(Evaluationsfälle); origin `real_project` bleibt immer blockiert.

## Schichtung (UND-Verknüpfung, nie Lockerung)

Ein Modell-Call kommt nur zustande, wenn **alle** Schichten zustimmen:

1. `runs/cloud_policy` — Run-Erstellungs-Gate (Cloud: nur D0 + Bestätigung;
   Lokal: nur D1/D2 + Bestätigung).
2. `agents/data_policy` — Datenklassen-Matrix des Contracts (deny-by-default,
   restriktivste Einstufung gewinnt, NDA blockiert).
3. **ProviderPolicy (neu)** — provider × data_class (× origin/eval), geprüft
   im Gateway **vor** `adapter.available()`, damit gesetzte Keys nie eine
   blockierte Klasse öffnen. Unbekannte Adapter ⇒ blockiert.
4. `security/policy_matrix` — autoritative Tool-Matrix (unverändert).

Alle LLM-Aufrufe laufen über das ModelGateway (`gateway.invoke`) — das
Aufrufpfad-Inventar (R4.3, GO-Auflage 5) hat keinen Bypass gefunden. Der
Webresearch-Pfad (Firecrawl) ist getrennt und läuft über die Search Query
Firewall (`docs/security/Search_Query_Firewall.md`).

## Zielarchitektur (nicht Teil von R4)

Ziel für echte D1/D2-Daten ist die **Azure Enterprise Boundary**
(Auftragsverarbeitung, EU/CH-Datenregion, Key Vault/Managed Identity, gemäss
E-10-Doku). Bis dahin bleibt `azure` in der Matrix vollständig blockiert.
**R4 integriert keine echte Azure API. Azure Provider Adapter / Azure
Smoke-Test ist ein separater Slice.**
