# Acceptance-Report — sieben getrennte Abnahmekategorien

Stand: 2026-07-15. Dieser Report trennt bewusst, WAS bewiesen ist: der
deterministische Fake-Pfad beweist Technik, der funktionale Import-Pfad
beweist fachliche Auslese, die Agent-Tests beweisen Schema-/Skill-Verträge,
die Live-Kategorien beweisen echten Betrieb.
Nicht Durchgeführtes steht wörtlich als **`not_run`** — es gibt keine
Pauschalaussage «ALL GREEN», wenn Live-Teile fehlen.
(Vorgängerstand mit der M10-Aufgabentabelle: Git-Historie dieses Dokuments.)

Kategorien: 1 Deterministic CI E2E · 2 Functional Import E2E ·
3 Agent Skill/Schema Tests · 4 Model Selection · 5 Live Firecrawl ·
6 Supervised Live E2E · 7 Known Limitations.

## 1. Technical deterministic E2E — **pass**

- Was: UI-/Persistenztechnik des Golden Path (Login → Intake → Import →
  Partner/Budget → Recherchebrief → Analyse → Editor → Qualitätsprüfung →
  Kopieransicht → Reload), deterministisch mit Fake-LLM/Fake-Web, ohne Keys.
- Nachweis: [`e2e/golden-path.spec.ts`](../../e2e/golden-path.spec.ts)
  («Technischer E2E (Fake-Provider) …»), im Gate als Suite-Lauf **und** als
  2. Lauf auf derselben frischen Demo-DB (zeitgestempelte Projekttitel).
- Ehrlichkeit des Fake-Modus (neu gepinnt): Demo-Recherche-Ergebnisse sind als
  «Demo» markiert und **nicht** als Quelle übernehmbar; ohne echte Webquellen
  wird **kein** Marktvergleich fabriziert (die Evidenzlücke wird ausgewiesen);
  die Ein-Lauf-Bestätigung heisst wahrheitsgemäss «Demo-Generator für diesen
  Durchlauf aktivieren».

## 2. Structured import E2E — **pass**

- Was: Ein unfertiger Antrag im **älteren** Innolink-Schema wird fachlich
  korrekt ausgelesen — Partner und Budget erscheinen ohne manuelle Neuanlage.
- Nachweis (exakte Erwartungswerte, rein synthetisches Fixture «TERRAFLUX»,
  [`spike/make_fixture.py`](../../spike/make_fixture.py)):
  - [`backend/tests/test_import_functional_fixture.py`](../../backend/tests/test_import_functional_fixture.py)
    (13 Tests): Titel; Dauer 18 Monate; genau 3 Partner (1 Forschungs- +
    2 Umsetzungspartner, Independence bestätigt); Budget
    200'000/105'000/13'000/82'000/94'300; Scientific Integrity «No» ohne
    Fremdkommentar; Management-Stunden 0 mit generiertem
    Erklärungsvorschlag; **leere Executive Summary bleibt leer**;
    Alt→Neu-Migration (IPR → 4.5.1–4.5.4, alt-4.5 → 4.6).
  - [`e2e/import-functional.spec.ts`](../../e2e/import-functional.spec.ts)
    (Pflichtteil des Gates): 15 strukturierte Kandidaten mit exakten Werten,
    HITL-Übernahme je Kandidat (Titelkonflikt verlangt «Geprüft
    überschreiben»), Partner/Budget ohne Neuanlage auf `/partner`,
    Budget-Vorprüfung konsistent (Umsetzungsbeitrag 59 %, Barbeitrag 6.5 %).

## 3. Agent skill/schema tests — **pass** (gate-pflichtige Backend-Suite)

- Was: versionierte Rollen-/Skill-Verträge, Output-Schema-Grenze, Registry
  fail-closed, Prompt-Pinning und die Scorer/Harness-Logik der
  Rollen-Modell-Evaluation — alles deterministisch, ohne Provider.
- Nachweis (Teil der Pflicht-Backend-Tests im Gate):
  [`test_agent_registry.py`](../../backend/tests/test_agent_registry.py) ·
  [`test_agent_schemas.py`](../../backend/tests/test_agent_schemas.py) ·
  [`test_role_skill_contracts.py`](../../backend/tests/test_role_skill_contracts.py) ·
  [`test_prompt_snapshots.py`](../../backend/tests/test_prompt_snapshots.py) ·
  [`test_role_model_eval_metrics.py`](../../backend/tests/test_role_model_eval_metrics.py) ·
  [`test_role_model_eval_harness.py`](../../backend/tests/test_role_model_eval_harness.py).

## 4. Model selection — Rollen-Modell-Evaluation (A1/A2/A3) — **`not_run`** (live)

- Was: Reproduzierbarer Kandidatenvergleich **je Agentenrolle** (A1 Extraction,
  A2 Drafting inkl. Quality-Ceiling, A3 Critic) auf den synthetischen Fällen
  F1/F2 (Dev) und H1 (Holdout, nie für Prompt-Tuning): automatische Gates +
  Fatal-Gates, blinde Human-Rubrik (Model A/B/C/…), Kosten/Latenz/Varianz,
  Prompt-SHA-Freeze. Ableitung der Modellroute je Rolle im
  [`model-selection-report`](../evaluation/model-selection-report.md).
- Status: opt-in ([`scripts/run_role_model_eval.py`](../../scripts/run_role_model_eval.py));
  ohne Live-Lauf wörtlich **`not_run`**. Der komplette Zyklus (Runs → Blindung
  → Ingest → Aggregation) ist per `--fake`-Dry-Run verifiziert; Dry-Run-Samples
  sind unübersehbar als `fake_dryrun` markiert und zählen nie als Live-Aussage.
  Gate-Statuszeile: «Model selection (A1/A2/A3)» liest
  `backend/var/evaluation/role_model_eval/summary.json`.

### Ebene C (Feldmetriken, Vorgänger) — Status siehe `backend/var/evaluation/model_quality_summary.md`

- Was: Gleicher synthetischer F1/D0-Eingabetext, gleiche Rubrik, OpenAI
  **und** Anthropic — Generierung ausschliesslich über den produktiven
  Gateway-Pfad (Registry-Profile, versionierte Prompts, echte Adapter; keine
  parallele Evaluationslogik). Deterministische Metriken: Begriffe erhalten,
  Pflichtunterabschnitte, Zeichenlimit, keine erfundenen Zahlen/Patente,
  keine Review-Notizen/Portalfragen als finale Prosa, KPI-Lücken als offen.
  Human-Rubric (Nützlichkeit/Struktur/Präzision) bleibt manuell.
- Status: opt-in ([`scripts/run_model_quality_eval.py`](../../scripts/run_model_quality_eval.py));
  ohne Lauf wörtlich **`not_run`**. Auswertung vom 2026-07-15 auf Basis der
  lokalen R5.9-REAL-Ergebnisse: beide Provider ausgewertet; Befunde u. a.
  fehlender Pflichtunterabschnitt 3.3 (OpenAI, VC-Feld) und nicht als offen
  markierte KPI-Lücken in zwei Kurzfeldern. Details und tatsächliche
  Modell-IDs im gitignorierten Summary. Ein Provider-Ausfall macht das Gate
  nie rot. Anleitung/Template:
  [`docs/evaluation/model_quality_report.md`](../evaluation/model_quality_report.md).

## 5. Live Firecrawl evaluation — Status siehe `backend/var/evaluation/live_research_smoke.md`

- Was: Public-safe synthetischer Recherchebrief; Canary-Marker (Projekttitel,
  Partnername, Budgetzahl) bleiben nachweislich aus bereinigter Query, Audit
  und Logs; die geblockte Canary-Query wird **nie** gesendet (der Live-Call
  nutzt die separat geprüfte public-safe Query).
- Status: opt-in ([`scripts/run_live_research_smoke.py`](../../scripts/run_live_research_smoke.py));
  ohne Lauf wörtlich **`not_run`**. Lauf vom 2026-07-15: **PASS** —
  Firewall-Entscheid `block` für die Canary-Query (Redaktionen budget×2,
  partner×2, project×1), 0 Canary-Leaks in Query/Audit/Logs, Live-Suche mit
  3 echten Ergebnissen (erste Domain `iea.blob.core.windows.net`),
  **kein `example.org` im Live-Modus**; Leer-/Fehlerzustände (0 Treffer,
  Kontingent, Ausfall) werden dokumentiert statt ersetzt.

## 6. Supervised live E2E — **`not_run`**

- Was: Begleiteter Live-Durchlauf mit realen Providern — nur mit
  Owner-Freigabe und ausschliesslich synthetischen/anonymisierten Inhalten;
  A3 über eine vom A2-Provider unabhängige Route, Firecrawl nur nach
  menschlicher Query-Freigabe, externe Störung ⇒ ehrliches `partial_live`.
- Protokoll: [`docs/demo/demo-runbook.md`](demo-runbook.md) §6b (inkl.
  Zweimal-Regel: Volllauf + gezielter Wiederholungslauf der kritischen
  Provider-/Research-Schritte). Nach Durchführung hier Datum, Provider und
  tatsächliche Modell-IDs eintragen (aus dem Technical Evidence: `model_id`,
  `actual_model_id`, `prompt_version`); Evidenz-Archiv unter
  `backend/var/evaluation/supervised_live/<datum>/`.

## Private SEDATE-Acceptance (lokal, nicht committet) — **12/12 PASS**

[`scripts/run_private_innolink_acceptance.py`](../../scripts/run_private_innolink_acceptance.py)
gegen das gitignorierte echte Innolink-PDF (2026-07-15): Titel erkannt ·
Executive Summary `empty` · 3 Partner (1 F + 2 U) · 18 Monate ·
Umsetzungsbeitragsquote 52.52 % (Soll 52.5 ± 0.5) · Barbeitragsquote 6.46 %
(Soll ~6.5 ± 0.5) · Alt→Neu-Migration vorhanden (4.5.1, 4.5.2/4.5.3, 4.5.4,
4.6) · 0 Pflichtblocker aus dem Regelkern (leerer Independence-Kommentar bei
bestätigten Antworten und 0 Management-Stunden lösen keinen Blocker aus).
Die Ausgabe enthält nur Feldnamen, Zählwerte und Pass/Fail — keine PII, keine
Antragstexte. Narrative Quote des produktiven Mappings auf demselben PDF:
weiterhin 5 von 8 Feldern automatisch nutzbar (Messung
[`spike/map_pdf.py`](../../spike/map_pdf.py), vgl.
[`pdf-import-gate-report.md`](../evaluation/pdf-import-gate-report.md)).

## Live-Readiness (Ebene E) — verankert und getestet

- **Eine versionierte Registry je Agentrolle:** Profil + Skill-/Prompt-Version
  (aus den sha256-gepinnten Prompt-Assets), Provider/Modellroute,
  `output_schema@vN`, Timeout, Retries, optional
  `reasoning_effort`/`max_cost_chf`
  ([`backend/tests/test_agent_registry.py`](../../backend/tests/test_agent_registry.py)).
- **Fake/deterministisch/live sind getrennte, sichtbare Modi; Live fällt nie
  still auf Fake zurück:** Capabilities melden bei Live-Absicht ohne Provider
  ausdrücklich `live_unavailable` (die UI erklärt den Grund); das Gateway
  liefert `SafeFailure` statt eines Fake-Ersatzes; Firecrawl kennt
  disabled/fake/live explizit
  ([`backend/tests/test_live_readiness.py`](../../backend/tests/test_live_readiness.py)).
- **Versionen im Artefakt:** Das vom Provider gemeldete Modell
  (`actual_model_id`) wird pro Invocation persistiert und steht mit
  `prompt_version` im Technical-Evidence-Export; neue Runs frieren
  Prompt-Versionen + Modellrouten in `snapshot_versions` ein.
- **Provider-Preflight ohne Antragsinhalt:**
  [`scripts/run_provider_preflight.py`](../../scripts/run_provider_preflight.py)
  prüft Key → API-Erreichbarkeit → Modell-Echo → strukturierte Ausgabe →
  verständliche Rate-Limit-/Quota-Klassifikation; ohne Opt-in wörtlich
  `not_run`. Keine Rohprompts/Keys im Report.

## Abschlussgate `verify_all` (deterministisch, Fake-Provider)

Pflichtzeilen: Backend-Tests · Migration · Frontend-Tests · lint/tsc/build ·
Playwright-Suite · technischer E2E (2. Lauf) · **funktionaler Import** ·
**Review-Truth** · **DOCX-Render-Smoke (eigene Zeile, benötigt Word)** ·
API-Smoke · Testdaten-Marker · Legacy-Status-Guard. Das Gate endet mit
«TECHNISCHES GATE (deterministisch, Fake-Provider): GRÜN/ROT» und listet die
sechs Kategorien einzeln (inkl. «Model selection (A1/A2/A3)»); Live-Kategorien
erscheinen als `not_run`, solange sie nicht durchgeführt wurden. Es gibt kein
«ALL GREEN» mehr.

Letzter vollständiger Gate-Lauf nach dieser Umstellung: siehe
Konsolen-Summary (`scripts/verify_all.ps1`); die Zeilen «funktionaler
Import», «review truth» und «docx render smoke» müssen `pass` zeigen.

## 7. Known Limitations

- **Fake-Modus liefert bewusst keine Markt-/Webinhalte:** Demo-Recherche ist
  als solche markiert und nicht übernehmbar; der Marktvergleich bleibt ohne
  echte Webquellen leer (ehrlicher Leerzustand statt Fake-Analyse).
- **PDF-Titel bleibt bestätigungspflichtig:** konservative Erkennung
  (Dokumentkopf ohne Label ⇒ «unsicher»; gelabelt ⇒ Konfliktdialog gegen den
  bestehenden Projekttitel) — nie stille Übernahme.
- **Zwei reale Mapping-Lücken wurden in dieser Abnahme gefunden und behoben**
  (Beleg: SEDATE-PDF): die Spaltenüberschrift «Cash Contributions» wurde als
  Wert «s» gefangen und beschattete den korrekten Tabellenwert; der
  Integritätskommentar wurde aus fremden «Explanations…»-Labels gezogen.
  Beide Fälle sind jetzt regressionsgetestet.
- **Modellqualität (Ebene C) misst deterministische Signale**, keine
  inhaltliche Wahrheit; der Human-Rubric-Teil bleibt Pflicht.
- **DOCX-Render-Smoke benötigt lokal Microsoft Word** (bewusst; die eigene
  Gate-Zeile macht die Abhängigkeit sichtbar).
- **OneDrive-Sync/SQLite:** stale `.next`-Locks werden im Gate geräumt;
  E2E-Läufe sind mit `--workers=1` serialisiert (Single-Writer).
- **Kein Portal-Writeback, keine Förderentscheide:** Texte werden nur zum
  manuellen Kopieren vorbereitet; jede Übernahme bleibt menschlich.

## Manuelle Prüfschritte

- Runbook §5 (Demoablauf) und §5a (funktionaler Import) live nachvollziehen.
- `scripts/run_private_innolink_acceptance.py` lokal ausführen (12/12 PASS).
- Opt-in-Läufe nach Runbook §6a starten und die Statuszeilen der sechs
  Kategorien im Gate-Summary prüfen (`not_run` verschwindet nur durch echte
  Durchführung).
- Blind-Scoring der Rollen-Modell-Evaluation nach
  [`blind_rubric_a2.md`](../evaluation/blind_rubric_a2.md) /
  [`blind_rubric_a3.md`](../evaluation/blind_rubric_a3.md) durchführen
  (`mapping.json` erst nach Abschluss öffnen).
