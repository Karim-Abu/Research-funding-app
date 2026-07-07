# PDF-Import-Gate-Report (R0.2 — Vorlage)

Status: **Vorlage — Gate-Test noch nicht ausgeführt.**
Referenzen: `docs/repair/decision-log-needed.md` (E-01), `spike/REPORT.md`, `docs/evaluation/testdata-policy.md`.

## Zweck

Dieser Report dokumentiert den Gate-Test, der entscheidet, ob der Innolink-PDF-Import
(Milestone R3) gebaut wird oder ob der Fallback R3' («Aus Notizen/Quellen starten»
stärken, kein Antrags-Upload) greift.

## Eingang

- Ein **echtes anonymisiertes** oder **synthetisch-realistisches** Innolink-PDF.
- Ein vertrauliches Original darf **nie** ins Repo (Testdaten-Policy / E-12).
  Lokale Nutzung ausserhalb der Versionskontrolle (z. B. `private_inputs/`, per
  `.gitignore` ausgeschlossen) ist zulässig; committet wird höchstens eine
  anonymisierte Fassung nach menschlicher Review mit Review-Vermerk.

## Methode

1. `spike/map_pdf.py` gegen das Test-PDF ausführen
   (`backend\.venv\Scripts\python.exe spike\map_pdf.py <pfad-zum-pdf>`).
2. Ergebnis je der 8 aktiven Felder bewerten (Feld-IDs aus der Registry;
   Labels gemäss `backend/app/exports/generators/common.py::EXPORT_FIELD_LABELS`):

| # | Feld-ID | Bewertung | Bemerkung |
|---|---------|-----------|-----------|
| 1 | `INTRO.APP.NAME` | _offen_ | |
| 2 | `INTRO.APP.NAME_EN` | _offen_ | |
| 3 | `INTRO.APP.ABSTRACT` | _offen_ | |
| 4 | `INTRO.APP.EXECUTIVE_SUMMARY` | _offen_ | |
| 5 | `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` | _offen_ | |
| 6 | `VC.BUSINESS_TARGETS_MODEL.EDITOR` | _offen_ | |
| 7 | `SOL.INNOVATION_SOLUTION.EDITOR` | _offen_ | |
| 8 | `PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` | _offen_ | |

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

## Gate-Regel (aus decision-log E-01)

- usable-Quote **≥ ~60 %** (≥ 5 von 8 Feldern) → **R3 bauen** (Import-First MVP).
- darunter → **R3'-Fallback** (kein PDF-Antragsimport; Begründung mit Quote in
  Thesis dokumentieren).

## Ergebnis

### Quote

_offen — nach Testlauf ausfüllen (usable n/8 = … %)._

### Entscheid

_offen — «R3 bauen» oder «R3' Fallback» gemäss Gate-Regel._

### Begründung

_offen._

### Risiken

_offen — z. B. Varianz je Portal-Export, Zeilenverschmelzung (vgl. spike/REPORT.md §3)._

### Datum

_offen._

### Owner-Signatur

_offen — Entscheid E-01 wird vom Owner gefällt, nicht von Claude Code._
