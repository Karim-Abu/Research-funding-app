# Baseline-Report R0.3 — Ist-Zustand am Goldfall F1 (QUALIMON)

Datum: 2026-07-07 · Fall: `docs/evaluation/cases/F1_synthetic_case.md` (Owner-approved) ·
Rohdaten: `docs/evaluation/baseline-f1-result.json` · Messskript: `scripts/baseline_f1.py`

Modus: Fake-Provider, `deterministic_only`, Websearch off, D2 synthetic simulation.
Regel: reine Messung — **nichts wurde gefixt**; Auffälligkeiten sind unter «Beobachtungen» nur notiert.

## 1. Blocker-Zahlen je Screen-Datenquelle (Divergenz-Nachweis)

Derselbe Projektzustand, fünf verschiedene Zahlen:

| Screen | Datenquelle | Angezeigte «Blocker»-Zahl |
|---|---|---|
| Dashboard | `lib/dashboard.ts::summarizeProjects` — zählt Projekte mit cardStatus `blockiert`; `blockiert` nur bei `warning_badge == run_stopped` (`lib/projects.ts::toCardStatus`) | **0** (F1 erscheint als «in Bearbeitung») |
| Anforderungen | `GET /runs/{id}/requirements` — OpenIssues der Assessments | **2** Blocker-Issues (dazu 6 warning, 2 info; Assessments: 2 blocked, 4 needs_input, 2 partial, 2 open, 1 fulfilled) |
| Qualitätsprüfung | `GET /runs/{id}/review` — ReviewPackage | **18** Blocker, 54 Warnungen, approval `blocked` |
| Qualitätsprüfung (Zuverlässigkeits-Kacheln) | `GET /runs/{id}/reliability` — RunQualitySummary | **12** Blocker, 42 Warnungen |
| Export | `lib/export-view.ts::summarizeExportReadiness` — blockerCount = ReviewPackage.blocker_count | **18** Blocker, 0/8 Felder kopierbereit |

Der im Weakness-Register beschriebene «0/9/17-Widerspruch» ist damit am Goldfall
reproduziert (hier als 0 / 2 / 18 / 12 / 18). Ursache: jede Anzeige leitet ihre Zahl
aus einer anderen Quelle bzw. Definition ab; es gibt keinen kanonischen Status (→ R1).

## 2. Roh-Findings gesamt und je Meldungstyp (Duplikat-Nachweis)

Nach vollständigem Durchlauf (Analyse → Feldtexte → Recheck → Reliability):
**72 offene Review-Findings** (18 blocker / 54 warning) plus 14 OpenIssues,
verteilt auf 20 unterschiedliche Meldungstexte. Die vier häufigsten Typen stellen
53 der 72 Findings:

| Anzahl | Severity | Meldung |
|---:|---|---|
| 31 | warning | Nicht belegte Aussage: für diese Aussage wurde keine verknüpfte Quelle gefunden (Beleg-Suffizienzprüfung). Bitte belegen oder abschwächen. |
| 10 | warning | Marktaussage ohne quellenbelegte Markt-/Konkurrenzangabe. |
| 7 | blocker | Nicht belegte Aussage: … (identischer Text wie oben, andere Severity) |
| 5 | blocker | Quantifizierte Aussage ohne passende Zahl im Beleg (Beleg-Suffizienzprüfung). |
| 4 | warning | Diese Anforderung benötigt zusätzliche Angaben, bevor sie abschliessend beurteilt werden kann. |
| 4 | blocker | «Das Feld … enthält noch sichtbare Platzhalter» (je 1× Abstract, Executive Summary, Value Creation, Solution) |
| 8 | warning | «Für … ist kein aktiver Evidenz-Verweis hinterlegt, obwohl verifizierte Fundstellen vorliegen.» (je 1× pro Feld) |
| 2 | blocker | Budget: «Umsetzungsanteil 39% ausserhalb 40–60%.» / «Barbeitrag 3% < 5%.» |
| 1 | warning | Quantifizierte Aussage ohne passende Zahl im Beleg (Beleg-Suffizienzprüfung). |

Die UI rendert diese Findings flach und ungruppiert (`components/review/quality-summary.tsx`)
— dieselbe Meldung erscheint bis zu 31-mal untereinander (→ R2 Dedupe/Fix Queue).

## 3. Manuelle Schritte und Zeit bis «exportfähiger Feldsatz»

Wiederholbare Checkliste (per `scripts/baseline_f1.py` automatisiert; identische
Schrittfolge wie im UI):

1. Login
2. Projekt anlegen (Intake)
3. Budget-Snapshot eintragen
4. –6. Drei Partner erfassen (Research / Implementation / Pilot Site)
7. Quelle hochladen + Verarbeitung abwarten
8. Standard-Analyse starten + abwarten
9. –16. Acht Feldtexte eintragen (je Feld: öffnen, Text setzen)
17. Prüfung aktualisieren (Recheck)
18. Qualitäts-/Reliability-Prüfung ausführen

**Ergebnis: Der exportfähige Feldsatz wird nicht erreicht.** Nach allen 18 Schritten
sind **0 von 8 Feldern kopierbereit** (alle `needs_review`), 18 Blocker offen.
Um Kopierbereitschaft zu erreichen, müssten zusätzlich u. a. 38 unbelegte Aussagen
belegt oder abgeschwächt, 4 Platzhalter aufgelöst, 2 Budget-Blocker fachlich gelöst
und menschliche Review-Entscheide je Feld getroffen werden — je Aussage einzeln
(kein geführter Weg, keine Fix Queue). Die Baseline dokumentiert das als offenen
Aufwand; eine Zeitmessung «bis exportfähig» ist ohne Reparaturen nicht sinnvoll
terminierbar.

Skriptlaufzeit (API-Ebene, ohne UI-Bedienzeit): 5.0 s. Reproduzierbarkeit: zwei
unabhängige Läufe lieferten identische Zahlen (18/54/72, 12/42, 0/8).

## 4. Abdeckung der Goldstandard-Findings (F1-F-001…020)

Gemäss F1-Hinweis: fehlende Erkennung ist **kein Testfehler**, sondern Baseline-Dokumentation.

| Gold-Finding | Baseline-Ergebnis |
|---|---|
| F1-F-001 Platzhalter Abstract | **erkannt** (Platzhalter-Blocker) |
| F1-F-002 KPI ohne Baseline/Messmethode | nicht erkannt (keine Rubric, → R6) |
| F1-F-003 Quantifizierter Claim ohne Beleg | **erkannt** (5× blocker + 1× warning) |
| F1-F-004 Marktgrösse fehlt | teilweise (generisch: «Marktaussage ohne Quelle», 10×) |
| F1-F-005 Einsparungsannahme ohne Beleg | teilweise (über «Nicht belegte Aussage» abgedeckt, nicht spezifisch) |
| F1-F-006 Wettbewerb/USP schwach | nicht erkannt |
| F1-F-007 Go-to-Market unvollständig | nicht erkannt |
| F1-F-008 Impact nicht quantifiziert | nicht erkannt |
| F1-F-009 SOTA-Abgrenzung generisch | nicht erkannt (→ R6 Rubric) |
| F1-F-010 KPI-Baseline fehlt | nicht erkannt (→ R6 Rubric) |
| F1-F-011 Datenquellen/-qualität unklar | nicht erkannt (→ R8/ICT-Check) |
| F1-F-012 Validierungsdesign unvollständig | nicht erkannt |
| F1-F-013 IPR/FTO unvollständig | nicht erkannt (kein Check vorhanden) |
| F1-F-014 Finanzielle Unabhängigkeit → Human Review | teilweise (Assessment `needs_input` sichtbar; kein explizites Human-Review-Finding) |
| F1-F-015 Partner-Fit ohne Evidenz | nicht erkannt (→ R7b) |
| F1-F-016 Barbeitrag < 5 % | **erkannt** («Barbeitrag 3% < 5%.») |
| F1-F-017 Umsetzungsbeitrag < 40 % | **erkannt** («Umsetzungsanteil 39% ausserhalb 40–60%.») |
| F1-F-018 Management-Erklärung zu generisch | nicht erkannt |
| F1-F-019 Work Packages unspezifisch | nicht erkannt (keine WP-Struktur, E-04) |
| F1-F-020 Nicht alle Felder kopierbereit | **erkannt** (0/8 kopierbereit) |
| Ergänzung B: Attachment-/Risk-Readiness | nicht geprüft (keine Attachment-Gates, → R7.3) |

Bilanz: 5 erkannt, 3 teilweise, 12 nicht erkannt, 1 nicht prüfbar.

## 5. Beobachtungen (nur notiert, nicht gefixt)

1. **Statusdivergenz** (Abschnitt 1) — kein kanonischer Status; Dashboard-Definition
   («blockiert» = nur gestoppte Runs) unterschlägt sämtliche inhaltlichen Blocker.
2. **Stale-Findings vor Recheck:** Direkt nach den Feld-Edits zeigt das ReviewPackage
   10 Blocker / 4 Warnungen — darunter 8 Platzhalter-Blocker der alten Template-Stände
   (nur noch 4 Felder hatten tatsächlich Platzhalter). Erst der manuelle Recheck
   korrigiert das (dann 18/54 mit den echten Befunden). `recheck_required` ist korrekt
   gesetzt, aber die Zahlen springen beim Aktualisieren stark (10 → 18 Blocker).
3. **Duplikatflut** (Abschnitt 2) — identische Meldungstexte bis 31× ohne Gruppierung.
4. **Technische Feldlabels in Meldungen:** «Das Feld ‹Open Editor (Editor für
   Innovation Solution)› …» — verletzt die CLAUDEX-Regel «kein ‹Open Editor› als
   nutzersichtbarer Feldname».
5. **Gerundete Budget-Meldungen:** 38.57 % wird als «39% ausserhalb 40–60%» gemeldet,
   2.86 % als «3% < 5%» — fachlich korrekt erkannt, aber die gerundete Darstellung
   kann Nutzer verwirren (39 % liest sich als «knapp daneben», 3 % vs. 2.86 %).
6. **F1-Zusatzstrukturen nicht erfassbar:** IPR/FTO-Status, Impact 3.3 und
   Work-Package-Snapshot aus F1 haben keinen Erfassungsort in App/API
   (dokumentiert gemäss F1-Baseline-Skript Schritt 7).
7. **Keine Belege verknüpfbar im Massenfall:** 38 «nicht belegte» Aussagen müssten
   einzeln je Claim bearbeitet werden; es gibt keinen geführten Ablauf.

## 6. Reproduktion

```powershell
# Backend mit frischer DB starten (Fake-Provider):
cd backend
$env:DATABASE_URL='sqlite:///./var/baseline_f1.db'; $env:APP_ENV='development'; $env:DEMO_DATA_ENABLED='true'
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.demo.seed --reset --evaluation
# separates Fenster:
$env:AGENT_FAKE_PROVIDER='true'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# Messung:
cd ..
backend\.venv\Scripts\python.exe scripts\baseline_f1.py > docs\evaluation\baseline-f1-result.json
```

Vorher-/Nachher-Vergleich in R9 (R9.8): denselben Lauf wiederholen und gegen diesen
Report diffen.
