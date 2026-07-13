# Research-Spike: PII-Gateway (lokale Pseudonymisierung)

**Isolierter Spike — kein produktiver Code.** Prüft, ob ein **lokal** laufender
PII-Detektor deutsch-/schweizbezogene **synthetische** Texte vor einem externen
Modellaufruf **pseudonymisieren** kann. Ergebnis: reproduzierbare Messwerte je
Entität + eine begründete Go/No-Go-Empfehlung.

> **Pseudonymisierung/Tokenisierung, keine garantierte Anonymisierung.** Erkannte
> Werte werden durch typisierte Platzhalter ersetzt; ein Restrisiko bleibt.

## Abgrenzung (was dieser Spike NICHT tut)

- **Keine** Änderung am produktiven Datenpfad, an der Provider-Policy, an der
  Search Query Firewall oder am Logging. Kein Import aus `backend/app` oder `lib/`
  (Spike-Regel — Muster sind dupliziert).
- **Keine** Firecrawl-Verbindung. Die **Search Query Firewall bleibt der
  zwingende, separate Schutz** — dieser Detektor ersetzt sie nicht.
- **Keine** Open-WebUI-Integration.
- Die Reverse-Mapping-Tabelle (Rückersetzung) lebt **nur im Speicher** und wird
  nie in Datei, Log, Audit oder Git geschrieben.
- Nur **synthetische** Fixtures (frei erfundene Namen/Adressen/E-Mails/Telefon/
  Geburtsdaten/IBANs/Benutzernamen); keine echten oder vertraulichen Daten.

## Entitätstypen (7)

`PERSON` (Name), `EMAIL`, `PHONE` (Telefon), `ADDRESS` (Adresse),
`DOB` (Geburtsdatum / Datumsformate), `IBAN`, `USERNAME` (Benutzername).

## Zwei Detektor-Tiers

- **Tier A – deterministisch** (`detectors.py`, keine neuen Abhängigkeiten):
  `re`-Recognizer für E-Mail, Telefon (CH/intl.), **IBAN mit Mod-97-Prüfsumme**,
  Geburtsdatum, Benutzername sowie Name/Adresse über einen kleinen Vornamen-
  Gazetteer bzw. Strassensuffix-Heuristik. Die Muster für E-Mail/Telefon und die
  Firmensuffix-Ignoreliste sind aus
  `backend/app/security/confidential_terms.py` **dupliziert** (nicht importiert).
- **Tier B – ML** (`presidio_adapter.py`, optional): Microsoft Presidio + deutsches
  spaCy-Modell (`de_core_news_md`/`_sm`). Wird der ML-Stack nicht gefunden,
  **überspringt** der Harness diesen Tier ehrlich (kein Fehler).

## Ausführen

```powershell
# Tier A (Backend-venv genügt):
backend\.venv\Scripts\python.exe spike\pii_gateway\make_fixtures.py   # cases.json (re)generieren
backend\.venv\Scripts\python.exe spike\pii_gateway\evaluate.py --selftest
backend\.venv\Scripts\python.exe spike\pii_gateway\evaluate.py        # Tabelle + eval_report.json
backend\.venv\Scripts\python.exe spike\pii_gateway\evaluate.py --restore-demo

# Tier B (isolierter Spike-venv, nach Install — siehe requirements.txt):
spike\pii_gateway\.venv\Scripts\python.exe spike\pii_gateway\evaluate.py
```

## Metriken & Matching

- **Precision** = TP / (TP + FP), **Recall** = TP / (TP + FN), plus absolute
  **False Negatives** und **Latenz** (Median über 5 Durchläufe, indikativ).
- **Matching**: typbewusste Überlappung, 1:1 (ein vorhergesagter Span zählt als
  TP, wenn er einen noch freien Gold-Span **gleichen Typs** überlappt).
- Metriken (P/R/FN) sind **reproduzierbar** (deterministisch); die Latenz variiert
  naturgemäss und ist nur indikativ.

## Dependency-Fakten (Tier B — Freigabe erforderlich)

| Paket | Lizenz | Grösse | Bemerkung |
|-------|--------|--------|-----------|
| presidio-analyzer | MIT | ~0.2 MB | PII-Analyse-Framework |
| presidio-anonymizer | MIT | ~0.1 MB | Ersetzungs-/Operator-Layer |
| spacy | MIT | ~6 MB Wheel (+ numpy/thinc, ~50–120 MB Baum) | NLP-Engine |
| de_core_news_md | MIT | ~44 MB Download (Alt.: `_sm` ~15 MB) | deutsches NER-Modell |

Inferenz vollständig **lokal**, kein Netz. Risiko: mittelgrosser
Abhängigkeitsbaum; Installation **isoliert** in `spike/pii_gateway/.venv`
(nie in `backend/.venv`); Python-3.13-Wheel-Verfügbarkeit für spaCy vor Install
prüfen (sonst Spike-venv mit Python 3.12).

## Ergebnisse

### Tier A — deterministisch (17 synthetische Fälle, 30 Gold-Entitäten)

| Entität | TP | FP | FN | Precision | Recall |
|---------|----|----|----|-----------|--------|
| PERSON | 8 | 0 | 2 | 1.00 | 0.80 |
| EMAIL | 4 | 0 | 0 | 1.00 | 1.00 |
| PHONE | 4 | 0 | 0 | 1.00 | 1.00 |
| ADDRESS | 3 | 0 | 1 | 1.00 | 0.75 |
| DOB | 3 | 0 | 0 | 1.00 | 1.00 |
| IBAN | 2 | 0 | 0 | 1.00 | 1.00 |
| USERNAME | 3 | 0 | 0 | 1.00 | 1.00 |
| **Gesamt** | | | **3** | **1.00** | **0.90** |

Latenz: < 1 ms für alle 17 Fälle (rein regexbasiert). Die formatierten Typen
(E-Mail/Telefon/IBAN/Datum/Benutzername) erreichen **100 %** Recall/Precision;
freie **Namen** und **nicht-deutsche Adressen** fehlen (2 unbekannte Vornamen
ausserhalb des Gazetteers, 1 Adresse im französischen Format) — die erwartete
Schwäche eines deterministischen Detektors.

### Tier B — Presidio 2.2.363 + spaCy 3.8.13, Modell `de_core_news_md` (Python 3.13, isolierter venv)

| Entität | TP | FP | FN | Precision | Recall |
|---------|----|----|----|-----------|--------|
| PERSON | 10 | 2 | 0 | 0.83 | 1.00 |
| EMAIL | 4 | 0 | 0 | 1.00 | 1.00 |
| PHONE | 4 | 0 | 0 | 1.00 | 1.00 |
| ADDRESS | 3 | 3 | 1 | 0.50 | 0.75 |
| DOB | 2 | 0 | 1 | 1.00 | 0.67 |
| IBAN | 2 | 0 | 0 | 1.00 | 1.00 |
| USERNAME | 2 | 4 | 1 | 0.33 | 0.67 |
| **Gesamt** | | | **3** | **0.75** | **0.90** |

Latenz: ~109 ms für alle 17 Fälle (~6.4 ms/Dokument), also rund **200× langsamer**
als Tier A. Beide Tiers sind **reproduzierbar** (spaCy-Inferenz ist deterministisch).

### Vergleich (auf diesen synthetischen Fixtures)

- **Freie Namen:** der ML-Tier erkennt die zwei **unbekannten Vornamen**
  («Ravi Subramaniam», «Amara Okonkwo»), die der Gazetteer von Tier A verfehlt
  (PERSON-Recall 1.00 vs. 0.80) — der zentrale Mehrwert des ML-Ansatzes.
- **Präzision & formatierte Typen:** Tier A ist präziser (1.00 vs. 0.75). Presidio
  über-markiert: `LOCATION` wird auf `ADDRESS` gemappt und erfasst auch blosse
  Ortsnamen (→ ADDRESS-FP), die `USERNAME`-Heuristik ist verrauscht, und einzelne
  Datumsformate entgehen `DATE_TIME` (DOB-Recall 0.67). Bei E-Mail/Telefon/IBAN
  sind beide gleichauf (regex/Prüfsumme sind exakt).
- **Latenz:** Tier A < 1 ms, Tier B ~109 ms (Modell-Laufzeit).

**Fazit:** Die Ansätze sind **komplementär** — deterministisch für formatierte PII
(exakt, schnell, hohe Präzision), ML für freie Namen (höherer Recall). Der
`LOCATION→ADDRESS`-Mapping-Verlust und die Username-Heuristik erklären die
niedrigere ML-Präzision und wären in einem Produktivpfad nachzuschärfen (hier
bewusst nicht — Spike).

## Wichtige Limitation (Requirement 7)

Ein PII-Detektor erkennt **Identifikatoren**, keine Bedeutung. Er entfernt
**nicht zuverlässig**:

- die **Rohidee**/Projektbeschreibung,
- **Geschäftsgeheimnisse**,
- **proprietäre Methodik**,
- **Partnerstrategie**,
- **Budgetlogik**.

Der Spike belegt das mit vier `secret-*`-Fällen (Idee, Methodik, Strategie,
Budgetlogik): **beide Tiers** markieren dort **keine** Entität — der vertrauliche
Inhalt bliebe nach der Pseudonymisierung **vollständig erhalten**. Deshalb ist
Pseudonymisierung kein Ersatz für die Datenklassen-/Firewall-Kontrollen.

## Go/No-Go (Fazit, s. `eval_report.json`)

- **JA** als lokaler **Pseudonymisierungs-Vorfilter für klar formatierte PII**
  (E-Mail, Telefon, IBAN, Datum, Benutzername): deterministisch 100 %
  Recall/Precision, < 1 ms. Genau hier ist ein lokaler Vorfilter sinnvoll.
- **NEIN** als **alleiniger Anonymisierungsersatz**: freie Namen/Adressen
  bleiben lückenhaft. Deterministisch Recall 0.79 (freie Typen); der ML-Tier
  hebt freie Namen auf Recall 0.93, **senkt aber die Präzision auf 0.75**
  (Über-Markierung von Orten/Benutzernamen). Beide sind **Pseudonymisierung ohne
  Garantie**.
- **Empfehlung:** Falls ein lokaler PII-Vorfilter eingeführt wird, dann als
  **hybrider** Schritt — deterministisch für formatierte Identifikatoren, ML nur
  additiv für Personennamen, mit menschlicher Prüfung. Das ist ein separater
  Produktentscheid, **nicht Teil dieses Spikes**.
- Die **Search Query Firewall bleibt in jedem Fall der zwingende, separate
  Schutz**; **Rohidee, Geschäftsgeheimnisse, Methodik, Partnerstrategie und
  Budgetlogik entfernt kein PII-Detektor** (belegt durch die `secret-*`-Fälle:
  null erkannte Entitäten, Inhalt bliebe vollständig erhalten).

## Dateien

- `make_fixtures.py` → `fixtures/cases.json` — synthetische DE/CH-Fälle mit Gold-Spans.
- `detectors.py` — Tier A (deterministisch).
- `presidio_adapter.py` — Tier B (optional, ML).
- `pseudonymize.py` — typisierte Platzhalter + Speicher-only Reverse-Map.
- `evaluate.py` — Harness (`--selftest`, `--restore-demo`), schreibt `eval_report.json`.
- `requirements.txt` — Dependency-Fakten für Tier B (nicht auto-installiert).
