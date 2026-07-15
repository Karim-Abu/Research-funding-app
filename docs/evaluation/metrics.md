# Evaluation Metrics

Dieses Dokument definiert R0-Metriken vor der eigentlichen Bewertung. Ziel ist ein stabiler Rahmen, keine erfundenen Ergebnisse.

| Metric | Definition | R0 Status |
|---|---|---|
| Finding Precision | Anteil korrekter gemeldeter Findings gegen Goldstandard. | Skeleton, noch keine echte Bewertung |
| Finding Recall | Anteil gefundener Gold-Findings gegen Goldstandard. | Skeleton, noch keine echte Bewertung |
| Evidence-Sufficiency-Agreement | Uebereinstimmung zwischen Sufficiency-Status und menschlichem Expertenurteil. | Skeleton, braucht annotierte Stichprobe |
| Import Field Mapping Accuracy | Anteil korrekt gemappter Innolink-Felder gegen Gold-Feldmapping. | Skeleton, keine Import-Implementierung in R0 |
| Copy-Paste-Readiness-Rate | Anteil der Felder, die nach definiertem Review-Skript manuell kopierbereit sind. | Skeleton, keine automatische Uebernahme |
| Manual Effort Reduction | Vergleich von Zeit/Schritten zwischen Baseline und unterstuetztem Workflow. | Skeleton, braucht Evaluationsprotokoll |
| Latency | Laufzeit je Harness-/Analysepfad. | Skeleton, noch keine Messpflicht |
| Cost | Deterministisch erfasste oder explizit als Placeholder markierte Kosten. | Placeholder; keine CHF erfinden |

## Interpretationsregeln

- Keine Zielwerte ohne Baseline erfinden.
- Fake/local-Ergebnisse immer als solche kennzeichnen.
- Coverage misst Verlinkung, nicht faktische Korrektheit.
- Cost darf `None` sein, solange keine deterministische Messung existiert.
- Metriken duerfen keine automatischen Proposal-Submission- oder Portal-Writeback-Claims erzeugen.

## Rollen-Modell-Evaluation (A1/A2/A3)

Metriken der Kandidatenvergleiche je Agentenrolle
(`backend/app/evaluation/role_model_scoring.py`, Runner
`scripts/run_role_model_eval.py`; Gold: `docs/evaluation/cases/<case>_gold.json`).

### A1 (Fact Extraction)

| Metric | Definition |
|---|---|
| Schema Success Rate | Anteil Invocations mit gateway-validiertem Output (Retry-Ende zählt als fail). |
| Fact Precision | Anteil vorhergesagter Fakten, die irgendeinen Gold-Fakt treffen (Wertgleichheit ODER ≥ 0.5 Keyword-Trefferquote auf dem Statement). |
| Fact Recall | Anteil Gold-Fakten mit mindestens einer treffenden Vorhersage (Greedy-Zuordnung, jede Vorhersage höchstens einmal). |
| Field Accuracy | Über Gold-Fakten mit `target_ref`: Match UND identischer `target_ref`. |
| Boundary Accuracy | **Ehrliche Neudefinition:** Fragment-Provenienz (`source_fragment_ids` ⊆ Gold-Fragmente) UND exakte Wertgrenze (`normalized_value` == Goldwert). Das A1-Schema (`ExtractedFactRecord@v1`) kennt keine Zeichen-Offsets; eine Offset-Boundary wäre eine Contract-Änderung und ist bewusst nicht Teil der Evaluation (Limitation). |
| Entity Preservation | Erwähnte Gold-Entities (Projekt-/Partnernamen) müssen wörtlich erhalten sein (keine Paraphrase). |
| False Portal-Text Adoption | Anteil Fakten-Statements, die Portal-Boilerplate enthalten (Zeichenzähler, «Open Editor», Seitenkopf, Frage-Wortlaute). Kleiner ist besser. |
| Missing Recall | Anteil `gold_missing`-Ziele, die als `missing_information` gemeldet werden (`target_ref`-Gleichheit ODER ≥ 0.34 Keyword-Quote). |

### A2 (Drafting) — 10 automatische Gates

1 valides Output-Schema (Gateway) · 2 Pflichtunterabschnitte · 3 Zeichenlimit ·
4 Sprachkonsistenz (**Stopwort-Heuristik**, dominante Sprache ≥ 60 %; das
Human-Bestätigungsfeld im Blindbogen bleibt massgeblich) · 5 projektspezifische
Fakten erhalten (`required_terms`) · 6 keine erfundenen
Zahlen/Partner/Patente/Quellen/TRL/Rechtsaussagen (Detektoren: Zahlen- und
Patentabgleich gegen Eingabekorpus, Organisations-Suffix-Regex, `TRL n`-Abgleich,
Rechtsfreigabe-Regexliste, Quellen-⊆-Abgleich) · 7 keine
Portalfragen/Review-Notizen als Prosa · 8 fehlende KPI-Daten als offen
gekennzeichnet · 9 Quellenreferenzen existieren (⊆ geseedete Quellen) · 10 keine
Auto-Freigabe (`human_review_required`, advisory-only).

**Fatal-Gates** (ein bestätigter Verstoss schliesst den Kandidaten für die Rolle
aus): erfundene Zahl/Quelle/Partner/Patent · falsche Rechts-/Eligibility-Freigabe ·
vertrauliche Marker in Query-/Log-Scans · nicht existente Evidence-/Fragment-ID ·
stiller Fake-Wechsel (Adapter-Selbstauskunft + `generation_kind` je Invocation) ·
fremde Portalabschnitte als finaler Feldtext. Regex-basierte Treffer markieren das
Sample als `fatal_candidate` und verlangen **menschliche Adjudikation**;
Harness-Beobachtungen (Fake-Wechsel, Evidence-IDs) sind hart.
Safety-/Factuality-Gates haben immer Vorrang vor Textscores.

### A3 (Critic)

| Metric | Definition |
|---|---|
| Finding Recall (severity-gewichtet) | Match = Feld + Sektions-Präfix + ≥ 0.34 Keyword-Quote; Gewichte: budget/export_blocker 3, evidence_risk/human_review_required 2, reviewer_risk 1. Nur Gold-Findings mit `a3_scope: true` (VC/SOL) zählen. |
| False Positive Rate | Anteil Vorhersagen ohne Gold-Match; ungematcht-aber-plausibel wird als «neu (Adjudikation)» ausgewiesen, nicht automatisch als FP verbucht. |
| Grouping Quality | 1 − Near-Duplicate-Paar-Quote (gleiches Ziel, Token-Jaccard ≥ 0.6). |
| Fixability Rate | Anteil Findings mit konkretem `suggested_improvement`/`recommended_next_action` (Proxy; Rubrik bleibt massgeblich). |
| False Consensus | Auf der absichtlich fehlerhaften Draft-Variante (injizierte unbelegte Zahl): kein Finding trifft den injizierten Fehler ⇒ 1 Event (harter Zähler). |

### Aggregation je Rolle/Kandidat

Gate Pass Rate · gewichteter A2-Qualitätswert (25/20/20/10/10/10/5 nach
bestandenem Fatal-Gate; Human-Buckets aus dem Blind-Ingest, deterministische
Gates im Konsistenz-Bucket, Kosten/Latenz relativ über Kandidaten) · Kosten pro
akzeptablem Output (nur bei `cost_status=priced`, sonst ehrlich **Tokens pro
akzeptablem Output** — nie 0 CHF) · Latenz (Mittel ± Stdabw.) · Varianz über
Wiederholungen (Gate-Flips je Fall/Feld) · Human Review Time und Rework Count
aus dem Blindbogen. Dev (F1, F2) und Holdout (H1) werden getrennt ausgewiesen;
der Prompt-SHA beweist identische Prompts.
