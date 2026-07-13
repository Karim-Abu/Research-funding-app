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
| Status | proposal_valid |
| reason / error_code | — |
| Schema-Fehlerkategorie | none |
| LLM-Calls | 1 |
| input_tokens | 2058 |
| output_tokens | 206 |
| total_tokens | 2264 |
| Latenz (ms) | 5005 |
| UsageRecords | 1 |
| usage_record_id | 6ca5e64a-a26a-470d-b0dd-94a2c939046a |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 1 |
| human_review_required | True |
| Output-Länge (Zeichen) | 229 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

### anthropic

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | claude-sonnet-4-6 |
| Route | anthropic_direct |
| Status | proposal_valid |
| reason / error_code | — |
| Schema-Fehlerkategorie | none |
| LLM-Calls | 1 |
| input_tokens | 3227 |
| output_tokens | 546 |
| total_tokens | 3773 |
| Latenz (ms) | 10623 |
| UsageRecords | 1 |
| usage_record_id | 538b2e67-2b83-4a9e-963b-e571f1a693cf |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 3 |
| human_review_required | True |
| Output-Länge (Zeichen) | 195 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

## INTRO.APP.EXECUTIVE_SUMMARY

### openai

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | gpt-5.4-2026-03-05 |
| Route | openai_direct |
| Status | proposal_valid |
| reason / error_code | — |
| Schema-Fehlerkategorie | none |
| LLM-Calls | 1 |
| input_tokens | 2076 |
| output_tokens | 349 |
| total_tokens | 2425 |
| Latenz (ms) | 4736 |
| UsageRecords | 1 |
| usage_record_id | 47061047-c18b-4adb-9a19-c06f2e49797a |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 4 |
| human_review_required | True |
| Output-Länge (Zeichen) | 257 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

### anthropic

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | claude-sonnet-4-6 |
| Route | anthropic_direct |
| Status | proposal_valid |
| reason / error_code | — |
| Schema-Fehlerkategorie | none |
| LLM-Calls | 1 |
| input_tokens | 3214 |
| output_tokens | 1068 |
| total_tokens | 4282 |
| Latenz (ms) | 17138 |
| UsageRecords | 1 |
| usage_record_id | e72b51f4-1a08-48a1-a4e1-089c3dd9e1b0 |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |
| missing_inputs | 5 |
| human_review_required | True |
| Output-Länge (Zeichen) | 1056 |
| Qualitätsnotiz (manuell) | _vom Reviewer auszufüllen_ |

---

Erzeugt mit `RUN_REAL_PROVIDER_SMOKE=true AI_EVAL_MODE=real python scripts/run_r5_5_field_smoke.py --provider <openai|anthropic>` (Manual
Mode: CI ungesetzt), frische Temp-SQLite-DB, Keys aus `backend/.env`,
max 1 Lauf pro (Provider, Feld).
