---
name: innolink-domain-guard
description: Wahrheits-Guard für alle Innolink-/Portal-Feld-Fakten der Research Funding App. Immer verwenden, wenn Code oder Text Feld-IDs, Zeichenlimits, Pflichtfeld-Regeln, Optionen, Upload-Regeln, Quality Gates, Budget-Schwellen oder Placeholder-Templates anlegt oder ändert — auch bei scheinbar kleinen Anpassungen wie "erhöh das Limit" oder "mach das Feld draftbar". Verhindert erfundene Portalregeln und Portal-Version-Drift.
---

# Innolink Domain Guard

## Purpose
Stellt sicher, dass jede Portal-Feld-Aussage im Code und in Texten aus der verifizierten
Field Matrix stammt — nie aus Modellgedächtnis. Reduziert Risiken: erfundene Feld-IDs
und Limits, stilles Aktivieren nicht unterstützter Felder, veraltete Portalregeln
(Version Drift), LLM-isierte Budgetregeln.

## When to Use
- Jede Änderung an: Feld-Definitionen, Zeichenlimits, Pflicht-Flags, Optionen,
  Upload-Regeln, Quality Gates, Placeholder-Templates, Export-/Copy-Mapping
- Beim Aktivieren eines Feldes als „draftbar"
- Beim Schreiben von Texten, die Portalverhalten behaupten (Doku, UI-Hilfetexte, Thesis)
- Innerhalb von `slice-planner` (Plan-Phase) und `slice-implementer` (Umsetzung),
  sobald Feld-Logik betroffen ist

## Inputs to Read First
1. Die Portal Field Matrix: `Portal_Field_Matrix_Innolink_v2_UI_Verified.md`
   — **Repo-Pfad beim ersten Einsatz verifizieren und hier eintragen: `<PFAD_SETZEN>`.**
   Datei nicht im Repo auffindbar → STOPP, beim User anfordern. Nie aus Gedächtnis arbeiten.
2. `.claude/skills/_shared/project-invariants.md` §3 (Feld-Invarianten, Budget-Schwellen)
3. Betroffene Code-Stellen: `backend/app/drafts/templates.py`, `lib/fields.ts`,
   `backend/app/api/fields.py`, `lib/portal-transfer.ts`

## Hard Rules
- Einzige Quelle für Feld-Fakten ist die UI-verifizierte Matrix (v2). Bei Konflikt:
  UI-verifiziert > Legacy-ID > Modellwissen. Modellwissen allein ist NIE eine Quelle.
- Keine Feld-ID, kein Limit, keine Option, keine Upload-Regel erfinden oder „plausibel
  ergänzen". Lücke in der Matrix = STOPP + Frage an User (Portal-Check nötig).
- Jede übernommene oder geänderte Portalregel erhält eine Quellenangabe
  (Field ID + Matrix-Abschnitt) und ein `last_checked`-Datum.
- Alle 161 Felder bleiben sichtbar; ein Feld wird nur draftbar, wenn der Plan es
  ausdrücklich vorsieht UND die Matrix-Regeln (Limit, Pflicht, Gate) im Code abgebildet sind.
- Zeichenlimits sind blockierende Fehler vor Copy und Export — nie zu Warnungen abstufen.
- Deterministische Schwellen bleiben Code-Konstanten, nie LLM-Output:
  Implementation-Partner-Beitrag 40–60 % (exkl. Overheads), Cash ≥ 5 %,
  max. 2 Admins, min. 1 Research Partner.
- Matrix-Einträge mit Status „zu prüfen" gelten als UNBESTÄTIGT: nicht als Fakt in
  Code oder Text verwenden; als offenen Punkt melden.

## Procedure
1. Betroffene Field IDs auflisten (aus Prompt, Plan oder Diff).
2. Für jede ID den Matrix-Eintrag nachschlagen: UI-Element, Pflicht, Optionen,
   Zeichenlimit, Upload-Regel, Quality Gate, Evidence-Pflicht, Status.
3. Matrix-Eintrag mit Ist-Code vergleichen (templates.py, fields.ts, api/fields.py).
4. Abweichungen tabellieren: Matrix sagt X, Code macht Y.
5. Für die beauftragte Änderung: exakte Regel aus der Matrix zitieren, Codeänderung
   daran ausrichten, `last_checked` setzen/aktualisieren.
6. Kein Matrix-Eintrag oder Status „zu prüfen" → STOPP, Frage formulieren
   („Bitte im Innolink-Portal prüfen: …").
7. Ergebnis im Output-Format ausgeben. Codeänderungen selbst laufen über
   slice-implementer/bug-hunter — dieser Skill liefert die verifizierte Faktenbasis.

## Checks
- [ ] Jede berührte Field ID in der Matrix nachgeschlagen (nicht aus Gedächtnis)
- [ ] Quellenangabe (Field ID + Abschnitt) je Regel notiert
- [ ] last_checked gesetzt/aktualisiert
- [ ] Keine „zu prüfen"-Einträge als Fakt verwendet
- [ ] Zeichenlimits als blockierend erhalten
- [ ] Budget-Schwellen unverändert deterministisch
- [ ] Draftbar-Schaltung nur mit Plan-Auftrag + vollständiger Regelabbildung

## Stop Conditions
- Matrix-Datei im Repo nicht gefunden
- Field ID nicht in der Matrix vorhanden
- Matrix-Eintrag hat Status „zu prüfen" und die Änderung hängt davon ab
- Auftrag verlangt Abweichung von einer Matrix-Regel (z. B. höheres Limit) —
  das kann nur ein Portal-Check des Users legitimieren, nie der Skill

## Output Format
```
DOMAIN GUARD — <Kontext: Slice/Bug/Text>
| Field ID | Matrix-Regel (Zitat) | Ist-Zustand Code | Aktion | last_checked |

UNBESTÄTIGT ("zu prüfen"): <IDs> → Portal-Check durch User nötig
STOPP-PUNKTE: keine | <…>
FREIGEGEBENE FAKTENBASIS FÜR: slice-planner | slice-implementer | Textautor
```

## Do Not Touch
- Die Matrix-Datei selbst (Aktualisierung nur durch User nach Portal-Check)
- Budget-Schwellen-Konstanten ohne User-Auftrag
- `lib/portal-transfer.ts`-Semantik (Copy bleibt auditierte Übernahme)

## Common Failure Patterns
- Feldregeln aus Trainingswissen „ergänzen", weil die Matrix-Suche mühsam ist.
- Legacy-IDs verwenden, obwohl die UI-verifizierte ID abweicht.
- Ein Feld draftbar schalten, ohne Limit/Gate/Pflicht im Code abzubilden.
- Limit-Überschreitung zur Warnung abstufen, „damit der Flow nicht blockiert".
- „zu prüfen"-Einträge als bestätigt behandeln.
- last_checked vergessen → Portal-Drift bleibt unsichtbar.

## One-Screen Version
```
Rolle: Wahrheits-Guard für Innolink-Feldfakten. Einzige Quelle:
Portal_Field_Matrix_Innolink_v2_UI_Verified.md (im Repo). Modellgedächtnis
zählt NICHT als Quelle.
Regeln: Keine Feld-ID, kein Zeichenlimit, keine Option, keine Upload-Regel
erfinden. Lücke oder Status "zu prüfen" in der Matrix → STOPP + Frage
("Bitte im Portal prüfen: …"). Jede Regel mit Field ID + Matrix-Abschnitt +
last_checked belegen. UI-verifiziert schlägt Legacy-ID.
Invarianten: Alle 161 Felder sichtbar, draftbar nur mit explizitem Auftrag UND
abgebildeten Regeln. Zeichenlimits sind blockierende Fehler. Budget-Schwellen
(40–60 % Partner-Beitrag, Cash ≥5 %, max 2 Admins, min 1 Research Partner)
sind Code-Konstanten, nie LLM-Output.
Vorgehen: Field IDs listen → Matrix nachschlagen → mit Code vergleichen
(templates.py, lib/fields.ts, api/fields.py) → Abweichungen tabellieren.
Output: Tabelle Field ID / Matrix-Regel (Zitat) / Ist-Code / Aktion /
last_checked + Liste UNBESTÄTIGT + STOPP-Punkte.
```
