# R5.9 — Integrated Draft Run Report (F1 synthetic)

*Generiert:* 2026-07-09 · *Case:* `F1` · *data_mode:* `fake_test` · *provider_mode:* `fake`

## 1. Case Summary

- case_id: `F1` · project_id: `integrated-f1-synthetic` · run_id: `irun-c1139d58`
- provider_mode: `fake` · data_mode: `fake_test` · erzeugt: 2026-07-09T21:23:31.467007+00:00
- Felder im Paket: 8 · **Human Review erforderlich: ja** (kein Auto-Accept, kein automatisches Submit, nicht copy-ready).

## 2. Field Summary

| field_id | status | missing_inputs | human_review |
| --- | --- | --- | --- |
| INTRO.APP.NAME | deterministic | 0 | ja |
| INTRO.APP.NAME_EN | deterministic | 0 | ja |
| INTRO.APP.ABSTRACT | generated | 0 | ja |
| INTRO.APP.EXECUTIVE_SUMMARY | generated | 0 | ja |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | generated | 0 | ja |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | generated | 0 | ja |
| SOL.INNOVATION_SOLUTION.EDITOR | generated | 0 | ja |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | generated | 0 | ja |

## 3. Generated Draft Preview

**INTRO.APP.NAME** (deterministic)

> F1 QUALIMON — KI-gestützte Qualitätsüberwachung (synthetisch)

**INTRO.APP.NAME_EN** (deterministic)

> QUALIMON — AI-based Quality Monitoring for Production Lines

**INTRO.APP.ABSTRACT** (generated)

> Öffentliche Kurzfassung des Vorhabens und seines Innovationsziels, allgemein und ohne vertrauliche Details oder Partnernamen. Wo belastbare Angaben fehlen, bleibt eine [Platzhalter]-Markierung statt e…

**INTRO.APP.EXECUTIVE_SUMMARY** (generated)

> Ausführlichere Zusammenfassung des Projekts: Ausgangslage, Innovationsziel, geplanter Nutzen und Umsetzung, in allgemein verständlicher Sprache. Fehlende Baselines, Markt- oder Wirkungszahlen bleiben…

**ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS** (generated)

> Erläuterung zur finanziellen Unabhängigkeit der Partner gemäss den vorliegenden Angaben. Eigentums- und Beteiligungsverhältnisse sind noch zu belegen [Platzhalter]; ohne Nachweis wird die Unabhängigke…

**VC.BUSINESS_TARGETS_MODEL.EDITOR** (generated)

> 3.1 Wertschöpfung: erwartete wirtschaftliche und gesellschaftliche Wirkung, mit Belegen oder – wo Marktdaten fehlen – als Platzhalter markiert. 3.2 Geschäftsmodell und Markt: Zielkunden, Markteintritt…

**SOL.INNOVATION_SOLUTION.EDITOR** (generated)

> 4.1 Stand der Technik: bestehende Verfahren und deren Grenzen. 4.2 Neuheit: klare Abgrenzung gegenüber dem Stand der Technik. 4.3 Ziele: messbare Ziele mit Baseline und Zielwert, wo belegbar. 4.4 Vora…

**PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION** (generated)

> Die Management-Stunden umfassen allgemein Projektkoordination, Reporting, Review-Meetings, Projektsteuerung und Partnerabstimmung. Die konkrete Verteilung der Stunden auf diese Aufgaben ist noch zu er…

## 4. Usage Summary

| field_id | input_tokens | output_tokens | total_tokens | latency_ms | cost_status |
| --- | --- | --- | --- | --- | --- |
| INTRO.APP.NAME | — | — | — | — | — |
| INTRO.APP.NAME_EN | — | — | — | — | — |
| INTRO.APP.ABSTRACT | 10 | 20 | 30 | 26 | not_applicable |
| INTRO.APP.EXECUTIVE_SUMMARY | 10 | 20 | 30 | 7 | not_applicable |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | 10 | 20 | 30 | 6 | not_applicable |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | 10 | 20 | 30 | 7 | not_applicable |
| SOL.INNOVATION_SOLUTION.EDITOR | 10 | 20 | 30 | 7 | not_applicable |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | 10 | 20 | 30 | 8 | not_applicable |

- Total: input=60 · output=120 · total=180 tokens · UsageRecords=6
- cost_status counts: {'not_applicable': 6} (Fake-Provider ⇒ keine Preiswerte).

## 5. Research Usage

| Kontext | genutzt | ResearchCandidates | importierte D0/public-Quellen |
| --- | --- | --- | --- |
| Market (VC) | ja | 1 | 1 |
| Partner (SOL) | ja | 1 | 0 |

- ResearchCandidates/Snippets sind **advisory, keine Fakten und keine Evidence**; ihre IDs erscheinen nie in `used_anchor_ids`.

## 6. Quality Notes

- Jeder LLM-Feldvorschlag erfordert **menschliche Prüfung**; nichts ist automatisch übernommen, freigegeben oder copy-ready.
- Fehlende Markt-/SOTA-/Baseline-/Partner-/Budgetangaben erscheinen als `missing_inputs`/Platzhalter — keine erfundenen Werte.
- Marktzahlen/Partner-Fit aus Research-Kontext sind Kandidaten, keine bestätigten Aussagen. **Keine Förderzusage.**

## 7. Limitations

- Synthetischer F1-Demo-Lauf (Fake-Provider); **keine** finale Einreichung.
- **Nicht** automatisch copy-ready; Evidenz-/Faktenkorrektheit muss geprüft werden.
- Budget/Eligibility/Policy bleiben deterministisch und sind nicht Teil dieses Laufs.

---

Erzeugt mit `python scripts/run_integrated_draft_f1.py --provider fake` (Fake default; realer Provider erst im R5.9-REAL-Ticket). Feldvorschläge brauchen Human Review.
