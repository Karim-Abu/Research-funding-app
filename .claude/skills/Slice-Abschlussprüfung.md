---
name: post-slice-review
description: Abschlussprüfung eines Slices der Research Funding App. Immer verwenden bei "Slice fertig", "review den Slice", "schliess R7b ab" oder wenn slice-implementer alle Schritte gemeldet hat. Prüft verify_all ALL GREEN, Akzeptanzkriterien gegen Belege, Diff gegen Plan, ruft security-sweep bei Governance-Berührung auf und schreibt das Milestone-Dokument. Verhindert "fertig"-Behauptungen ohne Nachweis.
---

# Post-Slice Review

## Purpose
Schliesst einen Slice ehrlich ab. Prüft, ob das, was der Plan versprochen hat,
nachweisbar existiert — nicht, ob es „so aussieht". Erzeugt das Milestone-Dokument
als Thesis-Beleg. Reduziert Risiken: unbewiesene Fertig-Meldungen, stille
Scope-Abweichungen, ungeprüfte Governance-Änderungen, falsche Claims in der Doku.

## When to Use
- `slice-implementer` meldet „alle Schritte abgeschlossen"
- Prompt-Typen: „Slice fertig", „review R7b", „Abschluss", „schreib das Milestone-Doc"
- NICHT als Ersatz für `security-sweep` (wird von hier aus aufgerufen)

## Inputs to Read First
1. Der freigegebene Plan des Slices (inkl. Akzeptanzkriterien und Do-Not-Touch-Liste)
2. `git diff main...HEAD` + Commit-Liste des Slices
3. `.claude/skills/_shared/project-invariants.md` §4–§6
4. Letztes Milestone-Dokument in `docs/` als Formatvorlage
5. `docs/repair/roadmap-v2.md` (Status-Update)

## Hard Rules
- `scripts/verify_all.ps1` muss mit `ALL GREEN` enden. Kein Teil-Grün, kein
  „E2E lief lokal nicht, ist aber sicher ok". FAIL bleibt FAIL.
- verify_all-Output wörtlich ins Review übernehmen — nie paraphrasieren oder erfinden.
  Kann der Skill das Skript nicht selbst ausführen: User um Ausführung bitten und
  auf den Output warten. Ohne Output kein PASS.
- Jedes Akzeptanzkriterium braucht einen Beleg (Testname, Diff-Stelle, Screenshot-Pfad,
  Kommando-Output). „Wurde umgesetzt" ohne Beleg zählt nicht.
- Diff wird gegen den Plan geprüft: Dateien ausserhalb des Plans = Abweichung,
  die der User explizit absegnen muss.
- Berührt der Diff Pfade aus project-invariants.md §4 → `security-sweep` ist Pflicht
  und muss PASS liefern, bevor dieses Review PASS geben darf.
- Milestone-Dokument durchläuft `thesis-narrative-guard` (verbotene Claims, §6).
- Kein Test darf für den Abschluss deaktiviert, geskippt oder abgeschwächt worden sein —
  Diff auf `skip`, auskommentierte Tests, gelockerte Assertions prüfen.

## Procedure
1. Plan laden, Akzeptanzkriterien als Checkliste extrahieren.
2. verify_all ausführen (lassen): `scripts/verify_all.ps1`. Output sichern.
   Nicht `ALL GREEN` → VERDIKT FAIL, Fehlerliste ausgeben, Ende (zurück an
   `bug-hunter` oder `slice-implementer`).
3. Kriterium für Kriterium: Beleg suchen und notieren. Ohne Beleg → offen.
4. Diff vs. Plan: geänderte Dateien mit Plan-Dateiliste abgleichen.
   Abweichungen listen (auch harmlose).
5. Test-Integrität: Diff nach `@pytest.mark.skip`, `it.skip`, `test.skip`,
   auskommentierten Tests, entfernten Assertions durchsuchen.
6. Governance-Berührung? → `security-sweep` auf den Diff anwenden. FAIL dort = FAIL hier.
7. Doku aktualisieren: Milestone-Dokument nach Vorlage schreiben
   (Ziel & Rahmen, Änderungen je Datei, Kernverhalten, Datenschutz/Governance-Bezug,
   Tests, Verifikation mit verify_all-Block wörtlich, offene Punkte).
   Roadmap-Status in `docs/repair/roadmap-v2.md` als Vorschlag markieren.
8. Milestone-Text mit `thesis-narrative-guard` prüfen.
9. Verdikt ausgeben. Push weiterhin nur nach GO des Users.

## Checks
- [ ] verify_all-Output liegt wörtlich vor und endet mit ALL GREEN
- [ ] Jedes Akzeptanzkriterium hat Beleg oder ist als offen markiert
- [ ] Diff-Dateien == Plan-Dateien, Abweichungen dokumentiert
- [ ] Keine geskippten/abgeschwächten Tests im Diff
- [ ] security-sweep PASS (falls Governance-Pfade berührt)
- [ ] Milestone-Dokument geschrieben und narrative-geprüft
- [ ] Offene Punkte / Follow-ups gelistet

## Stop Conditions
- verify_all nicht ausführbar oder Output nicht verfügbar → stoppen, User bitten.
- Akzeptanzkriterium ohne Beleg und ohne klare Nacharbeit → stoppen, klären.
- Undokumentierte Änderung an Governance-Pfaden entdeckt → stoppen, security-sweep
  + User-Entscheid, bevor irgendein PASS möglich ist.

## Output Format
```
POST-SLICE REVIEW — <Slice-ID>
VERDIKT: PASS | FAIL

## verify_all (wörtlich)
<Block>

## Akzeptanzkriterien
| Kriterium | Beleg (Test/Diff/Output) | Status |

## Diff vs. Plan
Plan-Dateien: … / Zusätzlich geändert: … | keine Abweichung

## Test-Integrität
keine Skips/Abschwächungen | <Findings>

## Security-Sweep
nicht erforderlich (keine Governance-Pfade) | PASS | FAIL (→ Findings)

## Milestone-Dokument
docs/<name>.md geschrieben, narrative-guard: PASS

## Offene Punkte / Follow-ups
- …
```

## Do Not Touch
- Kein Produktcode ändern (Fixes gehen zurück an bug-hunter/slice-implementer)
- `scripts/verify_all.ps1`
- Bestehende Milestone-Dokumente früherer Slices (nur neues anlegen)

## Common Failure Patterns
- PASS bei Teil-Grün („nur Playwright ist rot, das ist flaky").
- verify_all-Ergebnis behaupten statt Output zeigen.
- Akzeptanzkriterien pauschal abhaken.
- Scope-Abweichungen verschweigen, weil „es funktioniert ja".
- Milestone-Doc mit verbotenen Claims („production-ready", „vollautomatisch").
- security-sweep überspringen, weil der Slice „nur Frontend" war
  (lib/fields.ts, lib/placeholders.ts, components/portal-transfer/* SIND Governance).

## One-Screen Version
```
Rolle: Abschluss-Reviewer für einen Slice. Nichts gilt als fertig ohne Beleg.
Pflicht: scripts/verify_all.ps1 ausführen (lassen) — Output wörtlich zitieren,
muss mit ALL GREEN enden. Teil-Grün = FAIL.
Dann: 1) Jedes Akzeptanzkriterium des Plans mit Beleg (Testname/Diff/Output)
abhaken, ohne Beleg = offen. 2) git diff main...HEAD gegen Plan-Dateiliste —
jede zusätzliche Datei ist eine meldepflichtige Abweichung. 3) Diff nach
skip/auskommentierten Tests/gelockerten Assertions durchsuchen. 4) Wenn Diff
security/review/copy/placeholder/firewall-Pfade berührt: Security-Sweep-Prompt
ausführen, muss PASS sein. 5) Milestone-Doc schreiben (Ziel, Änderungen, Tests,
Verifikation mit verify_all-Block, offene Punkte) — verbotene Claims:
vollautomatisch, production-ready, prüft Förderfähigkeit, garantiert Erfolg,
Copy-Paste=Freigabe, Azure=sicher.
Output: VERDIKT PASS/FAIL + Kriterien-Tabelle + Abweichungen + offene Punkte.
Kein Push ohne mein GO.
```
