# H1 Synthetic Case — VOLTRACK (HOLDOUT — nie für Prompt-Tuning verwenden)

> **HOLDOUT-Regel:** Dieser Fall dient ausschliesslich der finalen Validierung der
> Rollen-Modell-Evaluation. Er darf **nie** zur Prompt-Anpassung, Gate-Kalibrierung
> oder Kandidaten-Vorauswahl verwendet werden. Der Runner
> (`scripts/run_role_model_eval.py`) verweigert H1 ohne `--allow-holdout` und
> protokolliert den Prompt-Hash, damit Dev- und Holdout-Läufe nachweislich mit
> identischen Prompts liefen.

## Zweck

H1 ist der synthetische **Holdout-Fall** der rollen­spezifischen Modell-Evaluation
(A1/A2/A3) — bewusst aus einer anderen Domäne als F1 (Industrie-KI) und F2
(Smart-City-Bewässerung): Zustandsüberwachung in der **Batterie-Logistik**.

H1 ist kein echter Antrag und enthält keine echten Partnernamen, keine echten
Personen, keine echten Budgetzahlen, keine NDA-Daten und keine proprietären
Projektdetails.

---

## Testdatenstatus

| Eigenschaft | Wert |
|---|---|
| Funding instrument | Innosuisse Innovation Project with implementation partner |
| Project type | Synthetic Logistics / Battery Monitoring case |
| Data class | D0/D2 synthetic simulation (origin: synthetic) |
| Provider mode | fake/local; Real-Provider nur über Opt-in-Eval-Harness |
| Websearch | off |
| Confidential real data | none |
| NDA data | none |
| Purpose | **Holdout-Set** der Rollen-Modell-Evaluation (A1/A2/A3) |
| Rolle im Split | **Holdout** (`holdout: true` in `H1_gold.json`) |

---

## Synthetic Project Metadata

| Field | Synthetic Value |
|---|---|
| Application Name | VOLTRACK - Zustandsüberwachung für Batterie-Logistik |
| Application Name (EN) | VOLTRACK - Condition Monitoring for Battery Logistics |
| Start Date | 01.09.2026 |
| End Date | 28.02.2029 |
| Duration | 30 months |
| Scientific Integrity | No known severe sanction |
| Patent Search | Not yet performed |
| Freedom-to-Operate | Not yet assessed |

---

## Synthetic Project Outline

Das fiktive Projekt **VOLTRACK** entwickelt ein sensorbasiertes
Zustandsüberwachungssystem für den Transport und die Zwischenlagerung von
Lithium-Ionen-Batterien. Temperatur-, Stoss- und Ladezustandsdaten aus
Logistikketten werden zu einem Risikoprofil je Sendung verdichtet; kritische
Abweichungen sollen früh erkannt und Transportschäden reduziert werden.

Der Antrag ist bewusst unfertig:

- Abstract und Executive Summary enthalten Platzhalter,
- quantifizierte Ziele (−30 % Transportschäden, 95 % Erkennungsrate) haben keine
  Baseline und keine Messmethode,
- die Einsparungsannahme (CHF 340'000 pro Jahr) ist unbelegt,
- Marktgrösse und Wettbewerb fehlen,
- SOTA-Differenzierung ist generisch,
- Partner-Eignung ist nicht belegt,
- IPR/FTO ist ungeklärt,
- die Management-Erklärung ist zu knapp,
- der Barbeitrag liegt absichtlich unter 5 % (einziger Budget-Blocker).

---

## Synthetic Partners

| Rolle | Synthetischer Name | Land | Department | Industry | FTE | Vertretung | Projektrolle |
|---|---|---|---|---|---:|---|---|
| Research Partner | Rheintal Institut für Energiesysteme | CH | Batteriesysteme | Research | 52 | Sam Muster | Sensorfusion und Risikomodellierung |
| Implementation Partner 1 | Batterion Logistik AG | CH | Flottenbetrieb | Logistik | 112 | Toni Beispiel | Pilotflotte und Systemintegration |
| Implementation Partner 2 | CargoTherm GmbH | CH | Kühltransporte | Transport | 41 | Andrea Probe | Pilotrouten und Betriebsdaten |

---

## Synthetic Budget Snapshot

| Budget Element | Synthetic Value | Purpose |
|---|---:|---|
| Direct total project costs excluding overhead | CHF 500'000 | synthetic |
| Implementation Partner Own Contribution | CHF 200'000 | synthetic |
| Cash Contribution | CHF 20'000 | intentionally low |
| Requested Innosuisse Funding | CHF 280'000 | synthetic |
| Requested Innosuisse Funding incl. Overhead | CHF 322'000 | synthetic |
| Project duration | 30 months | synthetic |

Goldstandard-Hinweis (bewusst **genau ein** Budget-Blocker — anders als F1
[zwei] und F2 [keiner]):

- Cash contribution: CHF 20'000 / CHF 500'000 = **4.0 %** → **unter 5 % (Blocker)**.
- Implementation partner contribution: CHF 220'000 / CHF 500'000 = **44 %** → ≥ 40 % erfüllt.

---

## Synthetic Planned Hours

| Partner | Research | Implementation | Management |
|---|---:|---:|---:|
| Rheintal Institut | 3600 | 0 | 180 |
| Batterion Logistik AG | 0 | 1800 | 120 |
| CargoTherm GmbH | 0 | 600 | 0 |

Management-Stunden sind vorhanden, die Erklärung ist aber zu knapp (Expected
finding, analog F1-F-018).

---

# A1-Goldstandard (Fact Extraction)

Maschinenlesbar in `docs/evaluation/cases/H1_gold.json` (enthält auch die
A3-Gold-Findings); eingefrorene
Eingabefragmente in `docs/evaluation/cases/H1_fragments.json` (inklusive
Portal-Rauschen als Negativziel für falsche Portaltextübernahme).

Kurzübersicht der Gold-Fakten (Details im JSON):

| Gold-ID | Fakt | Wert |
|---|---|---|
| H1-A1-001 | Antragstitel (DE) | VOLTRACK - Zustandsüberwachung für Batterie-Logistik |
| H1-A1-002 | Antragstitel (EN) | VOLTRACK - Condition Monitoring for Battery Logistics |
| H1-A1-003 | Projektdauer | 30 Monate |
| H1-A1-004 | Ziel Transportschäden | −30 % |
| H1-A1-005 | Ziel Erkennungsrate | 95 % |
| H1-A1-006 | Einsparungsannahme (unbelegt) | CHF 340'000 pro Jahr |
| H1-A1-007 | Patentrecherche | noch nicht durchgeführt |
| H1-A1-008 | Forschungspartner | Rheintal Institut für Energiesysteme |
| H1-A1-009 | Umsetzungspartner 1 | Batterion Logistik AG |
| H1-A1-010 | Umsetzungspartner 2 | CargoTherm GmbH |
| H1-A1-011 | Direkte Projektkosten | CHF 500'000 |
| H1-A1-012 | Eigenleistung Umsetzungspartner | CHF 200'000 |
| H1-A1-013 | Barbeitrag | CHF 20'000 |
| H1-A1-014 | Beantragte Förderung | CHF 280'000 |
| H1-A1-015 | Beantragte Förderung inkl. Overhead | CHF 322'000 |
| H1-A1-016 | Pilotflotte | 12 Fahrzeuge auf 2 Routen |
| H1-A1-017 | Geschäftsmodell | Abo je überwachte Sendung |
| H1-A1-018 | Vorarbeiten | Messkampagne mit 40 Sendungen |

Erwartete Missing-Information-Ziele (`gold_missing`):

| Ziel | Begründung |
|---|---|
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | Kommentar leer, finale Bestätigung offen |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | Marktgrösse und Wettbewerb fehlen vollständig |

---

# Expected Fields (A2-Bezug)

Projektspezifischer Kontext für A2-Läufe: Titel (DE/EN) + Outline;
Pflichtbegriff (`required_terms`): **VOLTRACK**.

| Feld | Expected status | Gold-Kern |
|---|---|---|
| INTRO.APP.NAME | present | Titel DE (deterministisch) |
| INTRO.APP.NAME_EN | present | Titel EN (deterministisch, keine Übersetzung) |
| INTRO.APP.ABSTRACT | present with placeholder | Zustandsüberwachung Batterie-Logistik, −30 % Transportschäden, Platzhalter |
| INTRO.APP.EXECUTIVE_SUMMARY | partial | quantifizierte Claims (−30 %, 95 %) ohne Baseline, Platzhalter |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | leer / offen | Unabhängigkeit erklärt, finale Prüfung offen |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | present but weak | Abo-Modell, Einsparung CHF 340'000/Jahr unbelegt, Marktgrösse fehlt |
| SOL.INNOVATION_SOLUTION.EDITOR | present but weak | SOTA generisch; Sensorfusion + Risikoprofil; Ziele ohne Baseline; IPR/FTO offen |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | partial | Management-Erklärung zu knapp |

---

# Expected Findings

| Finding ID | Area | Expected finding | Expected severity | A3-Scope | target_section |
|---|---|---|---|---|---|
| H1-F-001 | Abstract | Platzhalter bleibt offen | export_blocker | nein | — |
| H1-F-002 | Executive Summary | KPI-Ziele ohne Baseline/Messmethode | reviewer_risk | nein | — |
| H1-F-003 | Executive Summary | Quantifizierter Claim ohne Beleg | evidence_risk | nein | — |
| H1-F-004 | Value Creation | Marktgrösse fehlt | reviewer_risk | ja | 3.1 |
| H1-F-005 | Value Creation | Einsparungsannahme CHF 340'000/Jahr ohne Beleg | evidence_risk | ja | 3.1 |
| H1-F-006 | Value Creation | Wettbewerb/USP nicht substanziert | reviewer_risk | ja | 3.1 |
| H1-F-007 | Value Creation | Kundenzugang/Go-to-Market unkonkret | reviewer_risk | ja | 3.2 |
| H1-F-008 | Value Creation / Impact | Ökologischer Nutzen (Batterie-Zweitleben) nicht quantifiziert | reviewer_risk | ja | 3.3 |
| H1-F-009 | Solution | SOTA-Differenzierung zu generisch | reviewer_risk | ja | 4.1 |
| H1-F-010 | Solution | KPI-Baseline fehlt (−30 %, 95 %) | reviewer_risk | ja | 4.3 |
| H1-F-011 | Solution | Datenqualität/Annotationsprozess der Messkampagne unklar | reviewer_risk | ja | 4.4 |
| H1-F-012 | Solution / Partner Fit | Partner-Eignung nicht mit Evidenz belegt | reviewer_risk | ja | 4.6 |
| H1-F-013 | Solution / IPR | IPR/FTO-Strategie ungeklärt | human_review_required | ja | 4.5 |
| H1-F-014 | Partner / Organisation | Finanzielle Unabhängigkeit: finale Prüfung offen | human_review_required | nein | — |
| H1-F-015 | Budget | Barbeitrag unter 5 Prozent | budget_blocker | nein | — |
| H1-F-016 | Project Setup | Management-Erklärung zu knapp | reviewer_risk | nein | — |
| H1-F-017 | Export | Nicht alle Felder kopierbereit | export_blocker | nein | — |

---

# Data Protection Notes

- H1 ist vollständig synthetisch und wurde eigens als Holdout verfasst.
- Keine echten Organisationen, Personen, Budgets oder Projektkennungen.
- Die Fallakte ist committbar; Rohoutputs der Evaluation bleiben ausschliesslich
  im gitignorierten `backend/var/evaluation/`.

---

# Goldstandard Status

Status: Holdout — gesperrt für Prompt-Tuning; Verwendung nur im finalen
Validierungslauf (`--allow-holdout`) mit identischem Prompt-Hash wie die
Dev-Läufe.
