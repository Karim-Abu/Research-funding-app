# Model-Routing-Draft für R5-Feldagenten (EVAL.3-Vorbereitung)

- **Status: DRAFT / Planungsdokument — KEIN Runtime-Config.** Das produktive
  Routing bleibt ausschliesslich die eingefrorene Contract-YAML
  (`final_backend_contracts_v1_1/agents_v1_1.yaml`, `model_catalog` +
  Profil-`model:`-Blöcke) über die AgentRegistry. Dieses Dokument bindet nichts.
- **Datum:** 2026-07-09 (zuletzt R5.5) · **Owner-Review ausstehend** für alle
  `TODO_OWNER`-Zeilen.
- **Keine Preise:** Preislogik läuft ausschliesslich über die EVAL.1-Preistabelle
  (`backend/app/evaluation/pricing.py`, aktuell bewusst leer). Hier stehen nur
  Modellklassen bzw. Routen-Aliasse als Vorschlag.

## Routing-Vorschläge (Feld-Keys → Modellklasse)

| Key | Contract-Profil (agents_v1_1.yaml) | Modellklasse (Vorschlag) | Routen-Alias (Vorschlag) | Status |
|---|---|---|---|---|
| A2_ABSTRACT | `A2.introduction_public_summary` (**code-aktiv, R5.5**) | kleine Klasse | Shared-Profil-Route; Contract-Primary heute `anthropic_sonnet_46`; finale Modell-ID TODO_OWNER | **code-aktiv (R5.5)** |
| A2_EXECUTIVE_SUMMARY | `A2.introduction_public_summary` (**code-aktiv, R5.5**) | mittlere Klasse | Shared-Profil-Route; Contract-Primary heute `anthropic_sonnet_46`; finale Modell-ID TODO_OWNER | **code-aktiv (R5.5)** |
| A2_VALUE_CREATION | `A2.value_creation_market_logic` (aktiv) | mittlere Klasse | `anthropic_sonnet_46` (= heutiger Contract-Primary) | aktiv (Contract) |
| A2_SOLUTION | `A2.solution_innovation` (aktiv) | mittlere Klasse | `anthropic_sonnet_46` (= heutiger Contract-Primary) | aktiv (Contract) |
| A2_FINANCIAL_INDEP | kein 1:1-Contract-Profil vorhanden | kleine Klasse | TODO_OWNER | TODO_OWNER |
| A2_MGMT_HOURS | `A2.project_setup_workplan` (spec-only, nicht code-aktiv) | kleine Klasse | `anthropic_haiku_45` | TODO_OWNER |

Fallbacks folgen dem bestehenden Contract-Muster (mittlere Klasse ⇒
`openai_gpt_54`, kleine Klasse ⇒ `openai_gpt_54_mini`) — verbindlich erst mit
einem künftigen Contract-Slice.

## Demo-Default & Compare-Provider (A2_ABSTRACT / A2_EXECUTIVE_SUMMARY, R5.5)

- Beide Felder werden vom **einzigen** Profil `A2.introduction_public_summary`
  bedient; dessen eingefrorener Contract-Block ist heute `model.primary:
  anthropic_sonnet_46`, `fallback: openai_gpt_54`. Das ist die **verbindliche
  Runtime** — R5.5 ändert daran nichts (keine Runtime-/Contract-Änderung).
- **OpenAI (`openai_gpt_54`)** ist als **initialer Demo-Default** dokumentiert
  (Kandidat) — **nicht** hardcodiert und **nicht** erzwungen. Ein Wechsel des
  Runtime-Primaries erfordert einen Contract-Slice **+ Owner-Freigabe**.
- **Anthropic (`anthropic_sonnet_46`)** ist der heutige Contract-Primary und dient
  als **Compare-Provider** — dokumentiert, nicht erzwungen.
- Finale Modell-ID je Feld: **TODO_OWNER** (kleine vs. mittlere Klasse, entschieden
  über Kosten/Qualität via EVAL.1/EVAL.2). Keine Preise in diesem Dokument.

## Explizite Ausschlüsse (verbindlich für EVAL.3)

- **A3_REVIEW wird NICHT als LLM eingetragen** — der A3-Review läuft heute
  deterministisch (`a3_review`-Scope); eine LLM-A3-Implementierung ist nicht
  Teil von R5.1/R5.2.
- **MARKET_SYNTHESIS wird bewusst NICHT gelistet** (kein R5-Scope).
- **Budget / Eligibility / Policy werden NIE als LLM geroutet** — Budgetlogik,
  Zulässigkeits- und Policy-Entscheide bleiben deterministisch
  (vgl. Repair-Leitplanke „Kein LLM im Budgetpfad").

## Hinweise

- Feld-Prompts für Abstract/Executive Summary sind mit R5.5 aktiv
  (`a2_introduction_public_summary_v1`, gemeinsames Profil).
- Aktivierung eines neuen Keys erfordert: Contract-Slice (Profil/Route),
  Prompt-Datei mit Version, `a2_fields`-Aktivierung, EVAL-Abdeckung — nicht
  dieses Dokument allein.
