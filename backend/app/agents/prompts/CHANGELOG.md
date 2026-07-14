# Prompt CHANGELOG

Versionsprotokoll für die Prompt-Dateien in diesem Ordner (`*_vN.md`). Jede
inhaltliche Änderung an einer aktiven Prompt-Datei muss hier sichtbar werden —
`tests/test_prompt_snapshots.py` erzwingt das über einen Content-Hash pro Datei.

## 2026-07-14 — Research-Provenienz in A2 v3

- A2-Sektionsausgaben weisen verwendete öffentliche Research-Quellen separat über
  `research_source_ids` aus; Evidence Anchors und fachliche Stützung bleiben getrennt.
- Der bestehende Marktvergleich-v2-Prompt verbietet generische Ersatzidentitäten und
  strukturiert nur belegte Vergleichsdimensionen; der deterministische Validator bleibt
  die durchsetzende Instanz.

## Wie ändere ich einen Prompt?

Eine Änderung an einem aktiven Prompt lässt `test_prompt_snapshots.py` rot werden.
Grün wird sie nur auf genau einem der beiden Wege — beide sind **sichtbar** im Diff:

1. **Versions-Bump (bevorzugt bei echten Verhaltensänderungen):** neue Datei
   `<slug>_vN+1.md` anlegen, `version:` im Frontmatter auf denselben neuen Slug
   setzen (der `version`-Slug ist der Datei-Stem), im Snapshot-Dict den neuen
   Dateinamen ergänzen und hier eine Zeile hinzufügen.
2. **Snapshot-Update (nur bei bewusster Korrektur am selben Slug):** den gepinnten
   Hash in `test_prompt_snapshots.py` (`_PROMPT_SNAPSHOTS`) aktualisieren **und**
   hier eine Zeile mit dem Grund ergänzen.

Ohne einen dieser beiden Schritte bleibt der Test rot — genau das verhindert
stille Prompt-Änderungen.

## Aktive Prompts

| Prompt-ID (profile_id) | Version (Slug) | Zweck | Änderungsdatum | Grund |
|---|---|---|---|---|
| A2.solution_innovation | a2_solution_innovation_v3 | Abschnittsweise Solution-&-Innovation-Ueberarbeitung | 2026-07-13 | Kontextarten, Baseline-Ueberarbeitung, 4.1-4.6-Einzelausgabe und Claims-/Missing-Input-Trail; ersetzt v2 |
| A2.value_creation_market_logic | a2_value_creation_market_logic_v3 | Abschnittsweise Value-Creation-Ueberarbeitung | 2026-07-13 | 3.1-3.3-Einzelausgabe; Antragstellerangaben bleiben mit Beleg-Pruefhinweis erhalten; ersetzt v2 |
| A3.evidence_consistency | a3_evidence_consistency_v2 | Fachlicher Kritiker (advisory ReviewFindings) | 2026-07-13 | KPI-Kette, Methodik, SOTA, Zahlenkonsistenz, Partner-Fit, Quellenalter, Risikobreite und Floskeln; ersetzt v1 |
| A1.project_fact_extraction | a1_project_fact_extraction_v1 | A1 — Projekt-Fakten als advisory Vorschläge extrahieren | 2026-07-08 | Initiale Snapshot-Erfassung (R5.3) |
| A1.evidence_candidate_mapping | a1_evidence_candidate_mapping_v1 | A1 — Kandidaten-Zitate/Ziele vorschlagen (advisory) | 2026-07-08 | Initiale Snapshot-Erfassung (R5.3) |
| A1.public_competence_research | a1_public_competence_research_v1 | A1 — öffentliche Kompetenz-Evidenz strukturieren (advisory) | 2026-07-08 | Initiale Snapshot-Erfassung (R5.3) |
| A2.introduction_public_summary | a2_introduction_public_summary_v2 | A2 — Abstract & Executive Summary (INTRO.APP.ABSTRACT, INTRO.APP.EXECUTIVE_SUMMARY) | 2026-07-09 | R5.5b Schema-Stabilisierung: bindender Output-Format-Block (nur JSON, keine Fences, genau ein Candidate, field_id-Echo, exakte Bundle-Shape, placeholders/field_level_warnings immer als Array). Ersetzt a2_introduction_public_summary_v1 (2026-07-09, R5.5-Aktivierung) |
| A2.organisations_governance | a2_organisations_governance_v1 | A2 — Financial-Independence-Kommentar (ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS) | 2026-07-09 | R5.6-Aktivierung: vorsichtiger Governance-Vorschlag, keine Unabhängigkeitsbestätigung ohne Beleg, keine Rechtsberatung |
| A2.project_setup_workplan | a2_project_setup_workplan_v1 | A2 — Management-Hours-Erklärung (PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION) | 2026-07-09 | R5.6-Aktivierung: allgemeine Management-Tätigkeiten, keine erfundenen Stunden-/Prozentwerte |
| A2.solution_innovation | a2_solution_innovation_v2 | A2 — Solution & Innovation Drafting (SOL.INNOVATION_SOLUTION.EDITOR) | 2026-07-09 | R5.7: advisory Research-Kontext (Partner-Kandidaten + D0/public-Quellen) als untrusted/kein-Beleg, PartnerCandidates sind Vorschläge (keine finalen Entscheidungen/Track-Records), SOTA/Baseline/Validierung/FTO/TRL nie als Fakt → Placeholder/missing_input; bindender Output-Format-Block. Ersetzt a2_solution_innovation_v1 |
| A2.value_creation_market_logic | a2_value_creation_market_logic_v2 | A2 — Value Creation & Market Logic Drafting (VC.BUSINESS_TARGETS_MODEL.EDITOR) | 2026-07-09 | R5.7: advisory Research-Kontext (Markt-Kandidaten + D0/public-Quellen) als untrusted/kein-Beleg, Marktzahlen sind Kandidaten (nie Fakt) → Placeholder/missing_input; bindender Output-Format-Block. Ersetzt a2_value_creation_market_logic_v1 |
| A3.evidence_consistency | a3_evidence_consistency_v1 | A3 — Evidence & Consistency Review (advisory ReviewFindings) | 2026-07-08 | Initiale Snapshot-Erfassung (R5.3) |
| MC.market_comparison | market_comparison_v2 | Markt-/Wettbewerbsvergleich, nur aus importierten Quellen (beta-intern) | 2026-07-12 | R8: neue Item-Kategorien market_size_claim und customer_problem (Marktgrössen-Kandidaten/Kundenprobleme nur mit exaktem Zitat, nie als Fakt); Zitat-Verifikation unverändert. Ersetzt market_comparison_v1 (2026-07-08, initiale Snapshot-Erfassung R5.3) |

## Bekannte Risiken

- **P2 — Loader last-file-wins:** `prompt_assets.py` dedupliziert Prompts per
  `profile_id` ohne Kollisions-Guard; bei zwei Dateien mit gleicher `profile_id`
  gewänne alphabetisch die letzte Datei — still. Aktuell existiert **kein**
  Duplikat (alle `profile_id`/`version`-Slugs eindeutig). `test_prompt_snapshots.py`
  (`test_no_duplicate_identity`) macht ein künftiges Duplikat laut sichtbar. Eine
  echte Härtung des Loaders (Fehler bei Duplikat, analog `registry.py`) ist eine
  Verhaltensänderung und bewusst als deferred P2 offen (braucht Owner-Freigabe).
