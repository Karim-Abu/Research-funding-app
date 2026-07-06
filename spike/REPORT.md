# SPIKE-Report: „Begonnenes Innolink-PDF importieren"

Branch: `spike-innolink-pdf` · Datum: 2026-07-05 · Regel: kein Merge nach main, Ergebnis ist dieser Report.

## 1. Setup & Einschränkung

- **Das angekündigte Test-PDF unter `spike/fixtures/` war nicht vorhanden.** Um die Timebox zu halten, wurde ein synthetisches, Innolink-artiges Fixture erzeugt (`make_fixture.py` → `innolink_sample.pdf`, fiktives Projekt „SmartGrid Optimizer", keine echten Antragsdaten). Zusätzlich eine degradierte Variante (`innolink_sample_degraded.pdf`), die typisches pypdf-Verhalten bei realen Portal-Drucken simuliert: logische Zeilen fliessen zusammen.
- Extraktion: pypdf 5.1.0 (identisch zu `backend/app/ingestion/parsers.py::parse_pdf`), Logik im Spike dupliziert, **kein Import aus `backend/app` oder `lib/`**.
- Mapping: rein deterministisch (Label-/Synonym-Regexes je Feld, Noise-Filter für `Characters: n/m`, `Open Editor`, Tabellenzeilen; Sektions-Stopper). **Kein LLM.**
- Messung: `map_pdf.py` gegen `fixtures/ground_truth.json` (manuell verifizierbar).

## 2. Mapping-Quote

| Szenario | Quote | Detail |
|---|---|---|
| Sauberes Fixture (Zeilenstruktur erhalten) | **8/8 = 100 %** | alle 8 M6-Felder korrekt, inkl. Leerfeld-Erkennung (`INTRO.APP.NAME_EN` vorhanden, aber leer → korrekt als leer/unsicher markiert) |
| Degradiertes Fixture (Zeilen zusammengeflossen) | **0/8 = 0 %** | 6× nicht gefunden, 2× nur teilweise (Editor-Inhalt verschoben, als `uncertain` markiert) |

Abbruchkriterium: < ~60 % → „streichen". Ergebnis ist **bimodal**, nicht graduell: entweder fast alles oder fast nichts.

## 3. Fehlklassen

1. **Zeilenverschmelzung (dominant):** Wenn `page.extract_text()` Label und Inhalt in eine Zeile legt, greifen zeilenbasierte Label-Anker (`^abstract\b` …) nicht mehr. Das ist bei echten, aus Web-Portalen gedruckten PDFs die Regel, nicht die Ausnahme.
2. **Kurz-Labels sind kollisionsanfällig:** `Explanation` und `Explanations and Comments` sind nur mit Sektions-Kontext unterscheidbar; ohne saubere Sektionserkennung drohen Falsch-Zuordnungen.
3. **Editor-Felder (VC/SOL):** ohne erkennbare nummerierte Hauptfragen (3.1/4.1 …) ist die Blockgrenze unsicher → `uncertain` statt hartem Fehler; ein echtes Feature bräuchte hier zwingend HITL-Bestätigung.
4. **Leere begonnene Felder:** Label vorhanden, Inhalt fehlt (nur Zeichenzähler) — erkennbar, muss aber als „leer" und nicht als „nicht gefunden" gemeldet werden.

## 4. PDF-Strukturbefund

- pypdf liefert **keine Layout-/Font-Information** über `extract_text()`; Überschriften sind nur an Textmustern erkennbar. Reihenfolgen sind ok, aber Zeilentrennung ist nicht garantiert.
- `parse_pdf` im Backend behandelt verschlüsselte/gescannte PDFs bereits korrekt (fail-closed, `needs_manual_input`) — dieselben Pfade gälten für den Import.
- **Die entscheidende Unbekannte bleibt das echte Innolink-PDF.** Ob dessen interne Textstruktur zeilenerhaltend ist, konnte mangels Fixture nicht gemessen werden. Das synthetische Ergebnis ist eine obere Schranke (Best Case) plus untere Schranke (Worst Case), kein Punktwert.

## 5. Aufwandsschätzung echtes Feature (grob)

- Upload-Weg + Quellklasse + Parser-Anbindung: klein (Bausteine existieren).
- Robustes Mapping (Sektions-Heuristik, Synonyme DE/EN, Zeilenverschmelzungs-Toleranz z. B. via Label-im-Zeilenpräfix-Suche): mittel, mehrere Iterationen mit echten PDFs nötig.
- HITL-Review-UI („erkannte Felder bestätigen/korrigieren", pro Feld übernehmen): mittel — ohne dieses UI wäre das Feature gegen die HITL-Regel des Produkts.
- Gesamt: **deutlich mehr als ein Slice**; realistisch 2–3 Slices inkl. Tests, ohne LLM-Unterstützung beim Mapping.

## 6. Empfehlung

**Eingeschränkt bauen — aber erst nach einem 30-Minuten-Nachtest mit einem echten (eigenen) Innolink-PDF; ohne diesen Nachtest: streichen.**

Begründung:
- Das Mapping selbst ist machbar und deterministisch (100 % im Best Case, saubere Leerfeld- und Unsicherheits-Erkennung).
- Die Machbarkeit hängt fast vollständig an der Extraktionsstruktur des echten PDFs (0 % im Worst Case). Diese eine Frage ist mit `python spike/map_pdf.py <eigenes.pdf>` in Minuten beantwortbar, sobald ein eigenes Test-PDF unter `spike/fixtures/` liegt.
- Fällt der Nachtest unter ~60 %: streichen (Abbruchkriterium greift). Fällt er darüber: als eingeschränktes Feature bauen — nur die 8 M6-Felder, immer mit HITL-Bestätigungsschritt, `uncertain`-Felder nie automatisch übernehmen.

## 7. Reproduktion

```
backend\.venv\Scripts\python.exe spike\make_fixture.py
backend\.venv\Scripts\python.exe spike\map_pdf.py
backend\.venv\Scripts\python.exe spike\map_pdf.py spike\fixtures\innolink_sample_degraded.pdf
```
