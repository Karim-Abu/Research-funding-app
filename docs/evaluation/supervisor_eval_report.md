# EVAL.4 — Supervisor Evaluation Report (Integrated Draft, F1 synthetic)

*Generiert:* 2026-07-09

## 1. Executive Summary

- **Fall:** F1 synthetic (D0 public/synthetic) — Innosuisse Innovation Project mit Umsetzungspartner. Keine echten D2-Daten, kein echter Antrag.
- **Provider-Modus:** openai, anthropic (real, manueller Opt-in, R5.9-REAL/R5.9b) — zusätzlich existiert eine deterministische Fake-Baseline (R5.9, `r5_9_integrated_draft_run_report.md`).
- **openai:** 7/8 Felder ohne `failed`-Status · total_tokens=16020 · cost_status=unknown_price=6.
- **anthropic:** 8/8 Felder ohne `failed`-Status · total_tokens=28186 · cost_status=unknown_price=6.
- **Kernlimitationen:** OpenAI (gpt-5.4) lieferte für `SOL.INNOVATION_SOLUTION.EDITOR` initial einen strukturell unvollständigen Entwurf (Feldregel `mandatory_structure_missing`, kein Schema-Fehler) — Anthropic liefert für dieses Feld vollständig und dient als dokumentierter Demo-Default (R5.9b). Kosten sind `unknown_price` (Preistabelle bewusst leer). Kein automatischer Auto-Accept, keine automatische Einreichung, keine Förderzusage.

## 2. Agent/Task Routing

| field_id | Agent (Profil) | Provider/Modell (beobachtet) | Modus | Purpose |
| --- | --- | --- | --- | --- |
| INTRO.APP.NAME | deterministisch (Template) | anthropic: —; openai: — | Deterministic | Antragstitel — deterministisch aus dem Projekttitel. |
| INTRO.APP.NAME_EN | deterministisch (Template) | anthropic: —; openai: — | Deterministic | Englischer Antragstitel — deterministisch aus F1-Stammdaten, keine automatische Übersetzung. |
| INTRO.APP.ABSTRACT | A2.introduction_public_summary | anthropic: anthropic_direct/claude-sonnet-4-6; openai: openai_direct/gpt-5.4-2026-03-05 | LLM | Öffentliche Kurzfassung des Vorhabens und Innovationsziels. |
| INTRO.APP.EXECUTIVE_SUMMARY | A2.introduction_public_summary | anthropic: anthropic_direct/claude-sonnet-4-6; openai: openai_direct/gpt-5.4-2026-03-05 | LLM | Ausführlichere Zusammenfassung: Ausgangslage, Innovationsziel, geplanter Nutzen. |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | A2.organisations_governance | anthropic: anthropic_direct/claude-sonnet-4-6; openai: openai_direct/gpt-5.4-2026-03-05 | LLM | Erläuterung zur finanziellen Unabhängigkeit der Partner. |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | A2.value_creation_market_logic | anthropic: anthropic_direct/claude-sonnet-4-6; openai: openai_direct/gpt-5.4-2026-03-05 | LLM + Research-Kontext (advisory) | Wertschöpfung, Geschäftsmodell und Markt — konsumiert advisory Market-Research-Kontext. |
| SOL.INNOVATION_SOLUTION.EDITOR | A2.solution_innovation | anthropic: anthropic_direct/claude-sonnet-4-6; openai: — | LLM + Research-Kontext (advisory) | Stand der Technik, Neuheit, Ziele, Vorarbeiten, Partner-Eignung — konsumiert advisory Partner-Research-Kontext. |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | A2.project_setup_workplan | anthropic: anthropic_direct/claude-sonnet-4-6; openai: openai_direct/gpt-5.4-2026-03-05 | LLM | Erläuterung der geplanten Management-Stunden. |

## 3. Integrated Draft Result

### Provider: openai

| field_id | status | human_review_required | missing_inputs |
| --- | --- | --- | --- |
| INTRO.APP.NAME | deterministic | ja | 0 |
| INTRO.APP.NAME_EN | deterministic | ja | 0 |
| INTRO.APP.ABSTRACT | missing_inputs | ja | 1 |
| INTRO.APP.EXECUTIVE_SUMMARY | missing_inputs | ja | 7 |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | missing_inputs | ja | 2 |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | missing_inputs | ja | 26 |
| SOL.INNOVATION_SOLUTION.EDITOR | failed | ja | 0 |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | missing_inputs | ja | 1 |

### Provider: anthropic

| field_id | status | human_review_required | missing_inputs |
| --- | --- | --- | --- |
| INTRO.APP.NAME | deterministic | ja | 0 |
| INTRO.APP.NAME_EN | deterministic | ja | 0 |
| INTRO.APP.ABSTRACT | missing_inputs | ja | 2 |
| INTRO.APP.EXECUTIVE_SUMMARY | missing_inputs | ja | 5 |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | missing_inputs | ja | 1 |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | missing_inputs | ja | 12 |
| SOL.INNOVATION_SOLUTION.EDITOR | missing_inputs | ja | 12 |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | missing_inputs | ja | 2 |

## 4. Token & Cost Summary

### Provider: openai

| field_id | tokens in/out/total | latency_ms | cost_status |
| --- | --- | --- | --- |
| INTRO.APP.NAME | —/—/— | — | — |
| INTRO.APP.NAME_EN | —/—/— | — | — |
| INTRO.APP.ABSTRACT | 1808/187/1995 | 4937 | unknown_price |
| INTRO.APP.EXECUTIVE_SUMMARY | 1821/407/2228 | 5786 | unknown_price |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | 1832/211/2043 | 3276 | unknown_price |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | 2122/2250/4372 | 24324 | unknown_price |
| SOL.INNOVATION_SOLUTION.EDITOR | —/—/— | 11380 | — |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | 1817/235/2052 | 4043 | unknown_price |

- Total: input=11723 · output=4297 · total=16020 tokens · UsageRecords=6
- cost_status counts: unknown_price=6. **unknown_price** bedeutet: kein Eintrag in der (bewusst leeren) Preistabelle — **niemals** als "0 CHF/gratis" lesen. Ein `priced`-Betrag würde nur erscheinen, wenn die Preistabelle einen Owner-genehmigten Preis für (Provider, Modell) enthält — aktuell nicht der Fall.

### Provider: anthropic

| field_id | tokens in/out/total | latency_ms | cost_status |
| --- | --- | --- | --- |
| INTRO.APP.NAME | —/—/— | — | — |
| INTRO.APP.NAME_EN | —/—/— | — | — |
| INTRO.APP.ABSTRACT | 2903/496/3399 | 9703 | unknown_price |
| INTRO.APP.EXECUTIVE_SUMMARY | 2918/1030/3948 | 18391 | unknown_price |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | 2916/473/3389 | 8533 | unknown_price |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | 3301/3099/6400 | 50420 | unknown_price |
| SOL.INNOVATION_SOLUTION.EDITOR | 3543/3955/7498 | 65629 | unknown_price |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | 2905/647/3552 | 12068 | unknown_price |

- Total: input=18486 · output=9700 · total=28186 tokens · UsageRecords=6
- cost_status counts: unknown_price=6. **unknown_price** bedeutet: kein Eintrag in der (bewusst leeren) Preistabelle — **niemals** als "0 CHF/gratis" lesen. Ein `priced`-Betrag würde nur erscheinen, wenn die Preistabelle einen Owner-genehmigten Preis für (Provider, Modell) enthält — aktuell nicht der Fall.

## 5. Research Summary

- **Market Research (RESEARCH.1)**: 5 geplante Queries, 15 ResearchResults, 10 ToolInvocations, 0 importierte Quellen — siehe `research1_market_report_F1.md`.
- **Partner Research (RESEARCH.2)**: 5 geplante Queries, 15 ResearchResults, 10 ToolInvocations, 15 PartnerCandidates — siehe `research2_partner_report_F1.md`.

**Im Integrated Draft Run konsumierter Research-Kontext (je Provider):**

- openai · Market (VC): genutzt=ja, candidates=1, imported_sources=0
- openai · Partner (SOL): genutzt=ja, candidates=1, imported_sources=0
- anthropic · Market (VC): genutzt=ja, candidates=1, imported_sources=0
- anthropic · Partner (SOL): genutzt=ja, candidates=1, imported_sources=0

- **ResearchCandidates/Snippets sind advisory, keine Fakten und keine Evidence.** Sie werden nie automatisch als `evidence_anchor_ids` zitiert.

## 6. Quality Assessment Table

Platzhalter — **wird nicht von Claude/der KI bewertet**, nur von menschlichen Reviewern anhand von [agent_quality_scoring_template.md](agent_quality_scoring_template.md) ausgefüllt.

### Provider: openai

| field_id | field_fit | specificity | factuality | missing_input_handling | language_quality | reviewer_notes |
| --- | --- | --- | --- | --- | --- | --- |
| INTRO.APP.NAME | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.NAME_EN | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.ABSTRACT | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.EXECUTIVE_SUMMARY | TODO | TODO | TODO | TODO | TODO | TODO |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | TODO | TODO | TODO | TODO | TODO | TODO |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | TODO | TODO | TODO | TODO | TODO | TODO |
| SOL.INNOVATION_SOLUTION.EDITOR | TODO | TODO | TODO | TODO | TODO | TODO |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | TODO | TODO | TODO | TODO | TODO | TODO |

### Provider: anthropic

| field_id | field_fit | specificity | factuality | missing_input_handling | language_quality | reviewer_notes |
| --- | --- | --- | --- | --- | --- | --- |
| INTRO.APP.NAME | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.NAME_EN | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.ABSTRACT | TODO | TODO | TODO | TODO | TODO | TODO |
| INTRO.APP.EXECUTIVE_SUMMARY | TODO | TODO | TODO | TODO | TODO | TODO |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | TODO | TODO | TODO | TODO | TODO | TODO |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | TODO | TODO | TODO | TODO | TODO | TODO |
| SOL.INNOVATION_SOLUTION.EDITOR | TODO | TODO | TODO | TODO | TODO | TODO |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | TODO | TODO | TODO | TODO | TODO | TODO |

## 7. Safety/Governance

- **Kein Auto-Submit**: keine automatische Innolink-/Portal-Einreichung.
- **Kein Auto-Accept**: jeder Feldvorschlag erfordert explizite menschliche Annahme/Ablehnung/Bearbeitung.
- **Human Review Pflicht** für jeden KI-generierten Feldvorschlag (`human_review_required=true`).
- **Keine Rohprompts, keine Systemmessages, keine API-Keys** in diesem Report — nur Feldentwürfe (Produktoutput) und Metadaten.
- Nur synthetische F1-Daten — keine echten D2-Daten, keine echten Partnernamen, keine echten Budgetzahlen.
- **Keine Förderzusage** und keine implizite Aussage zur Bewilligungswahrscheinlichkeit.

## 8. Limitations

- Nur die 8 aktuell unterstützten Innolink-Felder (`registry.m6_draft_fields()`).
- Nur der synthetische F1-Fall — keine Aussage über reale Antragsdaten.
- Preise können `unknown_price` sein (Preistabelle bewusst leer, kein Owner-genehmigter Preis eingetragen).
- ResearchCandidates sind nie Evidence — auch nicht bei hoher `confidence`.
- OpenAI zeigte für Solution eine Struktur-Lücke (jetzt via Anthropic-Demo-Default dokumentiert umgangen, R5.9b) — keine dauerhafte Prompt-/Contract-Änderung nötig, aber weiterhin als bekannte Provider-Eigenschaft zu beobachten.
- **Die finale Einreichungsverantwortung bleibt beim Menschen** — dieser Report ersetzt keine fachliche/rechtliche Prüfung.

---

Erzeugt mit `python scripts/run_supervisor_report.py` aus den bestehenden R5.9-REAL-Artefakten (`backend/var/evaluation/r5_9_real/*.json`, git-ignoriert). Kein neuer Provider-Call.
