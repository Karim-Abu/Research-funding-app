# R5.5-REAL — Real-Provider-Feld-Report (Abstract & Executive Summary)

*Generiert:* 2026-07-09 · *Preistabelle:* `2026-07-08.0`

## Pflichthinweise

- Nur **synthetic_eval** (F1-abgeleitet, D0 public). Keine echten
  D2-Daten, keine Partnernamen, keine Budgetzahlen.
- Keine Rohprompts und keine vollständigen Rohantworten in diesem Report;
  suggested_text/Bundle-Output liegen nur als Eval-Artefakt im
  git-ignorierten `backend/var/evaluation/r5_5/`. Keine API-Keys.
- Ein **Schema-Failure ist ein messbares Ergebnis** (Provider hat
  geantwortet, Output verfehlte `PortalFieldDraftBundle@v1`), kein
  Implementierungsfehler — der UsageRecord wird trotzdem ausgewiesen.
- Kostenstatus ist Mess-Pipeline, keine Kostenrechnung: `cost_chf` wird
  nur über `cost_status='priced'` summiert; 0.0 nie als gratis lesen.
- Alle Calls über die bestehende Grenze `run_a2_field_drafting` →
  `gateway.invoke`. Kein Azure, kein Firecrawl in diesem Smoke.

## INTRO.APP.ABSTRACT

### openai

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | gpt-5.4-2026-03-05 |
| Route | openai_direct |
| Status | schema_failed |
| reason / error_code | agent_invocation_failed |
| LLM-Calls | 2 |
| input_tokens | 2762 |
| output_tokens | 515 |
| total_tokens | 3277 |
| Latenz (ms) | 7024 |
| UsageRecords | 1 |
| usage_record_id | 1fb7d74c-a547-4646-a698-526fd25d4e9e |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 0 |
| human_review_required | None |
| Output-Länge (Zeichen) | 0 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

### anthropic

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | claude-sonnet-4-6 |
| Route | anthropic_direct |
| Status | schema_failed |
| reason / error_code | agent_invocation_failed |
| LLM-Calls | 2 |
| input_tokens | 3168 |
| output_tokens | 1983 |
| total_tokens | 5151 |
| Latenz (ms) | 33350 |
| UsageRecords | 1 |
| usage_record_id | f7473659-f40e-4c4e-ade9-a0f029ef28ab |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 0 |
| human_review_required | None |
| Output-Länge (Zeichen) | 0 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

## INTRO.APP.EXECUTIVE_SUMMARY

### openai

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | gpt-5.4-2026-03-05 |
| Route | openai_direct |
| Status | schema_failed |
| reason / error_code | agent_invocation_failed |
| LLM-Calls | 2 |
| input_tokens | 2784 |
| output_tokens | 1011 |
| total_tokens | 3795 |
| Latenz (ms) | 11727 |
| UsageRecords | 1 |
| usage_record_id | a461bad7-2ab2-4613-a859-4aecc5693c5a |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 0 |
| human_review_required | None |
| Output-Länge (Zeichen) | 0 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

### anthropic

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | claude-sonnet-4-6 |
| Route | anthropic_direct |
| Status | schema_failed |
| reason / error_code | agent_invocation_failed |
| LLM-Calls | 2 |
| input_tokens | 3198 |
| output_tokens | 2048 |
| total_tokens | 5246 |
| Latenz (ms) | 35513 |
| UsageRecords | 1 |
| usage_record_id | 52a4a632-3d33-4801-93a1-c5b14682bc7e |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 0 |
| human_review_required | None |
| Output-Länge (Zeichen) | 0 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

---

Erzeugt mit `RUN_REAL_PROVIDER_SMOKE=true AI_EVAL_MODE=real python scripts/run_r5_5_field_smoke.py --provider <openai|anthropic>` (Manual
Mode: CI ungesetzt), frische Temp-SQLite-DB, Keys aus `backend/.env`,
max 1 Lauf pro (Provider, Feld).
