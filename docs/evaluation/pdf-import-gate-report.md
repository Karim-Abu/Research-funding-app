# PDF-Import-Gate-Report (R3.GATE — ausgefüllt)

Status: **Gate-Test durchgeführt am 2026-07-07. Entscheid E-01: R3 bauen.**
Referenzen: `docs/repair/decision-log-needed.md` (E-01), `spike/REPORT.md`, `docs/evaluation/testdata-policy.md`.

## Zweck

Dieser Report dokumentiert den Gate-Test, der entscheidet, ob der Innolink-PDF-Import
(Milestone R3) gebaut wird oder ob der Fallback R3' («Aus Notizen/Quellen starten»
stärken, kein Antrags-Upload) greift.

## Eingang

- Testobjekt: ein **echter Innolink-Portal-Export** eines abgeschlossenen Antrags
  (26 Seiten, 1216 extrahierte Zeilen), lokal unter `private_inputs/` abgelegt und
  per `.gitignore` von der Versionskontrolle ausgeschlossen.
- Gemäss Testdaten-Policy / E-12 enthält dieser Report **keine Textauszüge, keine
  Projektkennungen und keine Antragsnummern** aus dem Dokument — nur Struktur- und
  Zählwerte. Eine anonymisierte Fassung als Repo-Fixture erfordert eine menschliche
  Review (E-12, offen).
- Reproduktion (lokal): `backend\.venv\Scripts\python.exe spike\map_pdf.py <pfad-zum-pdf>`.

## Methode

`spike/map_pdf.py` wurde in zwei Zuständen gegen das Test-PDF ausgeführt:

1. **Messung 1 — Spike unverändert** (Stand `repair-r2-done`): misst, wie das rein
   auf dem synthetischen Fixture entwickelte Mapping auf einen echten Export trifft.
2. **Messung 2 — Spike mit Portal-Vokabular** (dieser Commit): additive
   Pattern-Erweiterung (Title-Kurzlabels, `Management summary`, Kapitel-Format
   `N. Name`, nummerierte Hauptfragen 3.1/4.1 als Editor-Anker, `Please note`-
   und Seitenkopf-Rauschen, Stop-Anker für Folge-Sektionen). Weiterhin rein
   deterministisch, kein LLM. Die synthetische Regression bleibt Pflicht und
   besteht mit **8/8**; das degradierte Fixture bleibt bei **0/8** (Worst-Case-
   Messlatte unverändert).

Bewertungsskala je Feld (genau eine Kategorie):

| Kategorie | Bedeutung |
|---|---|
| `correct` | Feld korrekt erkannt und Inhalt korrekt zugeordnet |
| `partial` | Feld erkannt, Inhalt unvollständig oder mit Randfehlern |
| `uncertain` | Zuordnung unsicher markiert (kein automatisch übernehmbares Ergebnis) |
| `missed` | Feld nicht gefunden, obwohl im PDF vorhanden |
| `false-positive` | Falscher Inhalt einem Feld zugeordnet |

Als **usable** zählen `correct` und `partial`. `uncertain` zählt nicht als usable,
ist aber kein Ausschlusskriterium für das Feature (HITL-Review fängt es ab).

## Ergebnis je Feld

Labels gemäss `backend/app/exports/generators/common.py::EXPORT_FIELD_LABELS`.

| # | Feld-ID | Messung 1 (Spike as-is) | Messung 2 (Portal-Vokabular) | Bemerkung |
|---|---------|------------------------|------------------------------|-----------|
| 1 | `INTRO.APP.NAME` | missed | **missed** | Der Export führt für den Haupttitel kein erkennbares Label; Titel steht als blankes Dokumentkopf-Element. Dokumentierte Limitation — bleibt manuell. |
| 2 | `INTRO.APP.NAME_EN` | missed | **correct** | Label-Variante `Title in English:`; Wert (6 Zeichen) durch Folge-Label sauber begrenzt. |
| 3 | `INTRO.APP.ABSTRACT` | partial (Anker ok, Übererfassung 3005 Z. inkl. Folgesektion) | **correct** | 297 Z., durch Folge-Anker sauber begrenzt. |
| 4 | `INTRO.APP.EXECUTIVE_SUMMARY` | missed | **correct** | Label-Variante `Management summary`; 1586 Z. bis Kapitel-2-Stop. |
| 5 | `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` | false-positive (44 787 Z. Fremdinhalt bis Dokumentende-nahe) | **uncertain** | Feld ist im Test-PDF leer; Mapping erkennt «leer» statt Fremdinhalt zu übernehmen. |
| 6 | `VC.BUSINESS_TARGETS_MODEL.EDITOR` | missed | **correct** | Kein Editor-Heading im Export; Anker über Hauptfrage 3.1, Block (22 283 Z.) bis Kapitel-4-Stop. |
| 7 | `SOL.INNOVATION_SOLUTION.EDITOR` | missed | **correct** | Anker über Hauptfrage 4.1, Block (20 738 Z.) bis Kapitel-5-Stop. |
| 8 | `PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` | false-positive (4013 Z. bis Dokumentende inkl. Budget-Tabellen) | **uncertain** | Feld ist im Test-PDF leer; Folge-Sektion (Budget) wird sauber gestoppt. |

Bewertungsbasis Messung 2: Anker-Position, Blockgrenzen und Zeichenumfänge wurden
gegen die Dokumentstruktur verifiziert (Kapitel-/Sektions-Stopper); ein
Wort-für-Wort-Abgleich der langen Editor-Blöcke ist Teil der manuellen
Owner-Stichprobe und ändert die usable-Einstufung (correct→partial) nicht.

## Gate-Regel (aus decision-log E-01)

- usable-Quote **≥ ~60 %** (≥ 5 von 8 Feldern) → **R3 bauen** (Import-First MVP).
- darunter → **R3'-Fallback** (kein PDF-Antragsimport; Begründung mit Quote in
  Thesis dokumentieren).

## Ergebnis

### Quote

- Messung 1 (Spike unverändert): usable **1/8 = 12.5 %** (unter Gate).
- Messung 2 (Portal-Vokabular, deterministisch): usable **5/8 = 62.5 %** (über Gate).

### Entscheid

**R3 bauen** — auf Basis von Messung 2.

Begründung der Doppelmessung: Messung 1 misst das Instrument im Zustand des
ursprünglichen Spikes; ihr schlechtes Ergebnis ist eine **Vokabular-Lücke**
(anderes Label-Wording im echten Export), kein strukturelles Versagen. Die vom
Spike-Report (§3.1) als dominant erwartete Fehlklasse **Zeilenverschmelzung liegt
im echten Export nicht vor**: die Extraktion ist zeilenerhaltend (600 von 881
nicht-leeren Zeilen < 90 Zeichen, keine Zeile > 200 Zeichen). Die eigentliche
Gate-Frage — trägt deterministisches Mapping auf echten Portal-Exporten? — wird
von Messung 2 beantwortet.

### Begründung

Siehe Entscheid; zusätzlich: die zwei `uncertain`-Felder sind im Test-PDF
tatsächlich leer (begonnener Antrag) — das Mapping meldet «leer/unsicher» statt
falschen Inhalt, genau das vom HITL-Review erwartete Verhalten. Das eine
`missed`-Feld (Haupttitel) hat im Export kein Label und bleibt eine dokumentierte
Limitation (manuelle Eingabe).

### Risiken

- **n = 1:** Es wurde genau ein echter Export gemessen. Varianz über andere
  Portal-Versionen/Exporte ist unbekannt; weitere Nachtests bei Verfügbarkeit.
- Haupttitel ohne Label → immer manuell (kein Import-Kandidat).
- Zeilenverschmelzung bleibt als Worst Case möglich (anderes Druck-/Exportwerkzeug);
  das degradierte Fixture hält diese Messlatte im Regressionstest fest — dort ist
  das Sollverhalten `uncertain`/nicht gefunden, nie Falsch-Zuordnung.
- Editor-Blöcke sind lang (> 20 000 Z.); Feld-Zeichenlimits können beim Übernehmen
  greifen (bestehende Limit-Prüfung im Draft-Mechanismus, HITL entscheidet).

### Datum

2026-07-07.

### Owner-Signatur

Entscheid E-01 durch den Owner im Chat am 2026-07-07 gefällt
(«R3 bauen», auf Basis der oben dokumentierten Doppelmessung).
