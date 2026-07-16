# F2 Synthetic Case — TERRAFLUX (Development-Set)

## Zweck

F2 ist der zweite synthetische Innosuisse/Innolink-Evaluationsfall (Development-Set,
neben F1). Er promotet das bestehende funktionale Import-Fixture
`spike/fixtures/innolink_structured.pdf` (erzeugt durch `spike/make_fixture.py`,
Projekt «TERRAFLUX») zur vollwertigen Fallakte mit A1-Goldstandard,
erwarteten Feldern und erwarteten Findings für die rollen­spezifische
Modell-Evaluation (`scripts/run_role_model_eval.py`).

F2 ist kein echter Antrag und enthält keine echten Partnernamen, keine echten
Personen, keine echten Budgetzahlen, keine NDA-Daten und keine proprietären
Projektdetails. Alle Werte stammen 1:1 aus dem synthetischen Fixture-Generator
`spike/make_fixture.py` (`STRUCTURED_LINES`) und sind durch
`e2e/import-functional.spec.ts` sowie `backend/tests/test_import_functional_fixture.py`
verifiziert.

---

## Testdatenstatus

| Eigenschaft | Wert |
|---|---|
| Funding instrument | Innosuisse Innovation Project with implementation partner |
| Project type | Synthetic Smart-City / Sensorik case (Bewässerung) |
| Data class | D0/D2 synthetic simulation (origin: synthetic) |
| Provider mode | fake/local; Real-Provider nur über Opt-in-Eval-Harness |
| Websearch | off |
| Confidential real data | none |
| NDA data | none |
| Purpose | Development-Set der Rollen-Modell-Evaluation (A1/A2/A3) |
| Rolle im Split | **Development** (zusammen mit F1); Holdout ist H1 |

---

## Synthetic Project Metadata

| Field | Synthetic Value |
|---|---|
| Application Name | TERRAFLUX - Adaptive Bewässerungssteuerung für Stadtgrün |
| Application Name (EN) | TERRAFLUX - Adaptive Irrigation Control for Urban Green |
| Start Date | 01.03.2026 |
| End Date | 31.08.2027 |
| Duration | 18 months |
| Scientific Integrity | No known severe sanction |
| Patent Search | Yes (synthetische Recherche, zwei verwandte Dokumente) |
| Patent Licences required | No |
| Prior written agreement | Yes (Konsortialvertrag) |

---

## Synthetic Project Outline

Das fiktive Projekt **TERRAFLUX** entwickelt eine adaptive Bewässerungssteuerung
für städtisches Grün. Sensorbasierte Bodenfeuchtemodelle steuern Ventile je
Grünfläche selbstlernend; der Wasserverbrauch soll um bis zu 25 Prozent sinken
und die Betriebsteams der Stadtgärtnereien entlasten.

Der Antrag ist bewusst unfertig:

- die Executive Summary ist **komplett leer** (0/2000 Zeichen),
- die Erläuterung der Management-Stunden fehlt (0 geplante Management-Stunden),
- Marktziele («zwölf Städte in drei Jahren») sind unbelegt,
- das quantifizierte Ziel (−25 % Wasserverbrauch) hat keine Baseline und keine
  Messmethode,
- SOTA (4.1) und Partner-Eignung (4.5) sind nur je ein Satz,
- der ökologische Nutzen (3.3) ist nicht quantifiziert.

---

## Synthetic Partners

| Rolle | Synthetischer Name | Land | Department | Industry | FTE | Vertretung | Projektrolle |
|---|---|---|---|---|---:|---|---|
| Research Partner | Nordlicht Institut für Angewandte Forschung | CH | Umweltsysteme | Research | 38 | Robin Muster | Modellentwicklung und Validierung |
| Implementation Partner 1 | Voltaris AG | CH | Produktentwicklung | Sensorik | 74 | Alex Beispiel | Systemintegration und Pilotierung |
| Implementation Partner 2 | Brimatec GmbH | CH | Betrieb | Gartenbau | 26 | Kim Probe | Pilotbetrieb in zwei Städten |

---

## Synthetic Budget Snapshot

| Budget Element | Synthetic Value | Purpose |
|---|---:|---|
| Direct total project costs excluding overhead | CHF 200'000 | synthetic |
| Implementation Partner Own Contribution | CHF 105'000 | synthetic |
| Cash Contribution | CHF 13'000 | synthetic |
| Requested Innosuisse Funding | CHF 82'000 | synthetic |
| Requested Innosuisse Funding incl. Overhead | CHF 94'300 | synthetic |
| Project duration | 18 months | synthetic |

Goldstandard-Hinweis (bewusst **anders als F1** — keine Budget-Blocker):

- Cash contribution: CHF 13'000 / CHF 200'000 = **6.5 %** → ≥ 5 % erfüllt.
- Implementation partner contribution: CHF 118'000 / CHF 200'000 = **59 %** → ≥ 40 % erfüllt.
- Der Budget-Precheck zeigt zweimal «Erfüllt» (verifiziert in
  `e2e/import-functional.spec.ts`, Schritt 9).

---

## Synthetic Planned Hours

| Partner | Research | Implementation | Management |
|---|---:|---:|---:|
| Nordlicht Institut | 2400 | 0 | 0 |
| Voltaris AG | 0 | 1100 | 0 |
| Brimatec GmbH | 0 | 500 | 0 |

Expected finding: 0 von 4000 Stunden sind Management — eine Erklärung fehlt und
wird beim Import als Erklärungs-Kandidat vorgeschlagen (deterministisch).

---

# A1-Goldstandard (Fact Extraction)

Maschinenlesbar in `docs/evaluation/cases/F2_gold.json` (enthält auch die
A3-Gold-Findings); die Eingabefragmente
sind einmalig eingefroren in `docs/evaluation/cases/F2_fragments.json`
(deterministisch aus `spike/make_fixture.py::STRUCTURED_LINES` abgeleitet —
parser-unabhängig, inklusive Portal-Rauschen wie «Characters: 228/300» als
Negativziel für falsche Portaltextübernahme).

Kurzübersicht der Gold-Fakten (Details im JSON):

| Gold-ID | Fakt | Wert |
|---|---|---|
| F2-A1-001 | Antragstitel (DE) | TERRAFLUX - Adaptive Bewässerungssteuerung für Stadtgrün |
| F2-A1-002 | Antragstitel (EN) | TERRAFLUX - Adaptive Irrigation Control for Urban Green |
| F2-A1-003 | Projektdauer | 18 Monate |
| F2-A1-004 | Abstract-Kernziel | −25 % Wasserverbrauch |
| F2-A1-006 | Patentrecherche durchgeführt | Yes |
| F2-A1-007 | Lizenzen benötigt | No |
| F2-A1-008 | Verwertungsvereinbarung | Yes (Konsortialvertrag) |
| F2-A1-009 | Forschungspartner | Nordlicht Institut für Angewandte Forschung |
| F2-A1-010 | Umsetzungspartner 1 | Voltaris AG |
| F2-A1-011 | Umsetzungspartner 2 | Brimatec GmbH |
| F2-A1-012 | Direkte Projektkosten | CHF 200'000 |
| F2-A1-013 | Eigenleistung Umsetzungspartner | CHF 105'000 |
| F2-A1-014 | Barbeitrag | CHF 13'000 |
| F2-A1-015 | Beantragte Förderung | CHF 82'000 |
| F2-A1-016 | Beantragte Förderung inkl. Overhead | CHF 94'300 |
| F2-A1-018 | Quantifiziertes Ziel | −25 % in zwei Pilotstädten |
| F2-A1-019 | Geschäftsmodell | Abo je Grünfläche; zwölf Städte in drei Jahren |
| F2-A1-020 | Vorarbeiten | Laborprüfstand mit zwölf Ventilen |

Erwartete Missing-Information-Ziele (`gold_missing`):

| Ziel | Begründung |
|---|---|
| INTRO.APP.EXECUTIVE_SUMMARY | im Antrag komplett leer (0/2000) |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | 0 Management-Stunden ohne Erklärung |

---

# Expected Fields (A2-Bezug)

Die 8 unterstützten Draft-Felder mit Erwartung für die A2-Evaluation. Der
projektspezifische Kontext für A2-Läufe ist Titel (DE/EN) + Outline
(Projektbeschreibung); Pflichtbegriff (`required_terms`): **TERRAFLUX**.

| Feld | Expected status | Gold-Kern |
|---|---|---|
| INTRO.APP.NAME | present | Titel DE (deterministisch) |
| INTRO.APP.NAME_EN | present | Titel EN (deterministisch, keine Übersetzung) |
| INTRO.APP.ABSTRACT | present | Bewässerungssteuerung, −25 % Wasserverbrauch, Stadtgärtnereien |
| INTRO.APP.EXECUTIVE_SUMMARY | **leer → Lücke ehrlich ausweisen** | keine Erfindung von Inhalten |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | leer / offen | Unabhängigkeit bestätigt (Checkboxen), Kommentar leer |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | present but weak | Abo-Modell, zwölf Städte (unbelegt), Kundenzugang über Fachverbände |
| SOL.INNOVATION_SOLUTION.EDITOR | present but weak | SOTA feste Zeitpläne; Neuheit Bodenfeuchtemodell + selbstlernende Ventilsteuerung; Ziel −25 %; Laborprüfstand |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | **fehlt → Lücke ehrlich ausweisen** | 0 Management-Stunden |

---

# Expected Findings

Goldstandard-Findings für die A3-Evaluation. «A3-Scope: ja» = Finding liegt im
LLM-Critic-Scope (VC/SOL); «nein» = deterministische Engine bzw. Import-Pfad
(zählt nicht gegen den A3-Recall).

| Finding ID | Area | Expected finding | Expected severity | A3-Scope | target_section |
|---|---|---|---|---|---|
| F2-F-001 | Executive Summary | Feld komplett leer | export_blocker | nein | — |
| F2-F-002 | Value Creation | Marktziel «zwölf Städte in drei Jahren» ohne Quelle/Evidenz | evidence_risk | ja | 3.1 |
| F2-F-003 | Value Creation | Kundenzugang ohne konkreten Kanal/Beleg | reviewer_risk | ja | 3.2 |
| F2-F-004 | Value Creation / Impact | Ökologischer Nutzen nicht quantifiziert, Messmethode fehlt | reviewer_risk | ja | 3.3 |
| F2-F-005 | Solution | State-of-the-art zu knapp und generisch | reviewer_risk | ja | 4.1 |
| F2-F-006 | Solution | Ziel −25 % ohne Baseline und Messmethode | reviewer_risk | ja | 4.3 |
| F2-F-007 | Solution / Partner Fit | Partner-Eignung nur ein Satz, nicht belegt | reviewer_risk | ja | 4.6 |
| F2-F-008 | Project Setup | 0 Management-Stunden ohne Erklärung | human_review_required | nein | — |

---

# Data Protection Notes

- F2 ist vollständig synthetisch (Fixture-Generator `spike/make_fixture.py`).
- Keine echten Organisationen, Personen, Budgets oder Projektkennungen.
- Die Fallakte ist committbar; Rohoutputs der Evaluation bleiben ausschliesslich
  im gitignorierten `backend/var/evaluation/`.

---

# Goldstandard Status

Status: abgeleitet aus dem verifizierten Import-Fixture (functional import gate
grün); für die Rollen-Modell-Evaluation freigegeben mit dem Start der Dev-Läufe.
