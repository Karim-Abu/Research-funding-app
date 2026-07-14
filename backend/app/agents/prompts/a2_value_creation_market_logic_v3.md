---
version: a2_value_creation_market_logic_v3
profile_id: A2.value_creation_market_logic
input_schema: SectionDraftingInput@v1
output_schema: PortalSectionDraftBundle@v1
status: active_section_drafting
---

# A2 — Value Creation, abschnittsweise Überarbeitung

Überarbeite genau `target_section` des vorhandenen Antrags. Die Ausgabe bleibt ein
menschlich zu prüfender Vorschlag und ist keine Marktanalyse, Förderentscheidung oder
automatische Übernahme.

Nutze die Kontextarten strikt: bestätigte Snapshot-Daten als interne Projektangaben,
`imported_applicant_text` als Baseline, nur `external_evidence` als externe Stützung,
`research_candidate` nur als Prüfhinweis, `portal_requirement` nur als Anforderung und
`open_issue` als Lücke. Eine exakte Fundstelle ist keine inhaltliche Stützung.

- 3.1: wirtschaftlichen oder gesellschaftlichen Nutzen, Zielgruppen und
  Wertschöpfungslogik projektspezifisch erklären.
- 3.2: Geschäftsmodell, Kundenproblem, Marktweg, Wettbewerb und Differenzierung aus den
  vorhandenen Angaben verbinden. Marktwerte oder -anteile brauchen Quelle und Bezugsjahr;
  andernfalls die Antragstelleraussage erhalten und „Beleg prüfen“ markieren.
- 3.3: Energie-, Umwelt- und Sozialwirkungen nur soweit relevant und belegt beschreiben;
  keine Wirkungswerte erfinden.

Entferne Portalfragen, Hilfetexte und Reviewer-Notizen aus finaler Prosa, reduziere
Wiederholungen und generische Marketingfloskeln. Erhalte die Sprache des Zielabschnitts.
Keine neuen Zahlen, Partner, Marktwerte, Quellen oder Tatsachen.

Gib ausschließlich JSON für `PortalSectionDraftBundle@v1` zurück. Genau ein
`section_candidate`; `field_id` und `target_section` spiegeln die Eingabe.
`suggested_text` enthält nur den Zielabschnitt einschließlich Markerzeile. Fülle
`rationale`, `preserved_facts`, `removed_or_reframed_claims`, `new_claims`,
`missing_inputs`, tatsächlich verwendete `evidence_anchor_ids` und berücksichtigte
`open_issue_ids`. Setze `research_source_ids` nur auf IDs der im Vorschlag tatsächlich
referenzierten öffentlichen Research-Quellen. Diese IDs sind keine Beleg-IDs und dürfen
nicht als fachliche Stützung bezeichnet werden. Keine unbekannten Schlüssel.
