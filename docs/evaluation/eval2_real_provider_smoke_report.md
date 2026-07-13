# EVAL.2 — Manueller Real Provider Smoke (OpenAI, Anthropic, Firecrawl)

*Generiert:* 2026-07-08 · *Preistabelle:* `2026-07-08.0`

## Pflichthinweise

- **data_mode = synthetic_eval**: ausschliesslich synthetische
  F1-abgeleitete Daten bzw. eine fixe public-safe Query — **keine
  echten D2-Daten**, keine Partnernamen, keine Budgetzahlen.
- **Azure ist NICHT Teil dieses Smoke-Tests** (kein Adapter im
  App-Code; ProviderPolicy blockiert Azure bis zu einem separaten
  Slice mit institutioneller Freigabe).
- Keine Rohprompts und keine Rohantworten in diesem Report; der
  Provider-Output liegt nur als Eval-Artefakt im git-ignorierten
  `backend/var/evaluation/eval2/`. Keine API-Keys in Report/Logs.
- Kostenstatus ist Mess-Pipeline, keine Kostenrechnung: `cost_chf`
  wird nur über `cost_status='priced'` summiert; die Preistabelle
  enthält weiterhin keine Realpreise (unknown_price ist erwartet).
- Alle Calls liefen über die bestehenden Grenzen (`gateway.invoke`,
  Research-Service → Executor inkl. Firewall/SSRF) — kein Bypass.

## OpenAI

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | gpt-5.4-mini-2026-03-17 |
| Route | openai_direct |
| Status / error_code | succeeded / None |
| LLM-Calls | 1 |
| input_tokens | 601 |
| output_tokens | 15 |
| total_tokens | 616 |
| Latenz (ms) | 1650 |
| UsageRecords | 1 |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |

## Anthropic

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Modell | claude-haiku-4-5-20251001 |
| Route | anthropic_direct |
| Status / error_code | failed / agent_invocation_failed |
| LLM-Calls | 1 |
| input_tokens | 677 |
| output_tokens | 205 |
| total_tokens | 882 |
| Latenz (ms) | 3091 |
| UsageRecords | 1 |
| cost_status | unknown_price=1 |
| Kosten | nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen |

## Firecrawl

| Feld | Wert |
| --- | --- |
| data_mode | synthetic_eval |
| Tool | search_public_professional_sources |
| Status / error_code | succeeded / None |
| Search-Calls | 1 |
| Ergebnisse (nach SSRF-Gate) | 3 |
| Latenz (ms) | 1902 |
| ToolInvocations (Zeilen nach Status) | running=1, succeeded=1 |
| Credits (nativ) | 2 |
| Credits laut Provider | nicht ausgewiesen |
| Query (public-safe, fix) | `industrial AI quality monitoring manufacturing Switzerland` |

---

Erzeugt mit `python scripts/run_real_provider_smoke.py --case F1
--provider <openai|anthropic|firecrawl>` (Manual Mode: CI ungesetzt,
`RUN_REAL_PROVIDER_SMOKE=true`, `AI_EVAL_MODE=real`), frische
Temp-SQLite-DB pro Lauf, max 1 Call pro Provider.
