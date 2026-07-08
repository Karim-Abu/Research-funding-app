# Model-Routing-Draft für R5-Feldagenten (EVAL.3-Vorbereitung)

- **Status: DRAFT / Planungsdokument — KEIN Runtime-Config.** Das produktive
  Routing bleibt ausschliesslich die eingefrorene Contract-YAML
  (`final_backend_contracts_v1_1/agents_v1_1.yaml`, `model_catalog` +
  Profil-`model:`-Blöcke) über die AgentRegistry. Dieses Dokument bindet nichts.
- **Datum:** 2026-07-08 (R5.1/R5.2-Ticket) · **Owner-Review ausstehend** für alle
  `TODO_OWNER`-Zeilen.
- **Keine Preise:** Preislogik läuft ausschliesslich über die EVAL.1-Preistabelle
  (`backend/app/evaluation/pricing.py`, aktuell bewusst leer). Hier stehen nur
  Modellklassen bzw. Routen-Aliasse als Vorschlag.

## Routing-Vorschläge (Feld-Keys → Modellklasse)

| Key | Contract-Profil (agents_v1_1.yaml) | Modellklasse (Vorschlag) | Routen-Alias (Vorschlag) | Status |
|---|---|---|---|---|
| A2_ABSTRACT | `A2.introduction_public_summary` (spec-only, nicht code-aktiv) | kleine Klasse | `anthropic_haiku_45` | TODO_OWNER |
| A2_EXECUTIVE_SUMMARY | `A2.introduction_public_summary` (spec-only, nicht code-aktiv) | mittlere Klasse | `anthropic_sonnet_46` | TODO_OWNER |
| A2_VALUE_CREATION | `A2.value_creation_market_logic` (aktiv) | mittlere Klasse | `anthropic_sonnet_46` (= heutiger Contract-Primary) | aktiv (Contract) |
| A2_SOLUTION | `A2.solution_innovation` (aktiv) | mittlere Klasse | `anthropic_sonnet_46` (= heutiger Contract-Primary) | aktiv (Contract) |
| A2_FINANCIAL_INDEP | kein 1:1-Contract-Profil vorhanden | kleine Klasse | TODO_OWNER | TODO_OWNER |
| A2_MGMT_HOURS | `A2.project_setup_workplan` (spec-only, nicht code-aktiv) | kleine Klasse | `anthropic_haiku_45` | TODO_OWNER |

Fallbacks folgen dem bestehenden Contract-Muster (mittlere Klasse ⇒
`openai_gpt_54`, kleine Klasse ⇒ `openai_gpt_54_mini`) — verbindlich erst mit
einem künftigen Contract-Slice.

## Explizite Ausschlüsse (verbindlich für EVAL.3)

- **A3_REVIEW wird NICHT als LLM eingetragen** — der A3-Review läuft heute
  deterministisch (`a3_review`-Scope); eine LLM-A3-Implementierung ist nicht
  Teil von R5.1/R5.2.
- **MARKET_SYNTHESIS wird bewusst NICHT gelistet** (kein R5-Scope).
- **Budget / Eligibility / Policy werden NIE als LLM geroutet** — Budgetlogik,
  Zulässigkeits- und Policy-Entscheide bleiben deterministisch
  (vgl. Repair-Leitplanke „Kein LLM im Budgetpfad").

## Hinweise

- Keine Feld-Prompts für Abstract/Executive Summary in diesem Ticket (erst R5.5).
- Aktivierung eines neuen Keys erfordert: Contract-Slice (Profil/Route),
  Prompt-Datei mit Version, `a2_fields`-Aktivierung, EVAL-Abdeckung — nicht
  dieses Dokument allein.
