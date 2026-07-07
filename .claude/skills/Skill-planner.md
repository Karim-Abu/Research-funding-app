# Skills — Research Funding App (Bachelorthesis)

Entwicklungs-Skills für die Arbeit AM Repo mit Claude Code, Codex oder Copilot.
Strikt getrennt von den Runtime-Agenten-Skills der App (requirement_extraction,
evidence_verification usw.) — diese hier steuern Modelle, die Code und Doku ändern,
nicht die App-Agenten.

Gemeinsame Faktenbasis aller Skills: `_shared/project-invariants.md`.
Bei Widerspruch gilt: `.claude/CLAUDEX.md` > project-invariants.md > Skill-Text.

## Die 8 Skills

| Skill | Zweck | Wann |
|---|---|---|
| `idea-triage` | Feature-Ideen stresstesten, Scope schützen | Bei jeder Idee ausserhalb der Roadmap; vor jedem neuen Plan |
| `slice-planner` | Verbindlichen Plan erstellen (starkes Modell) | Vor jedem Slice; nach idea-triage-GO |
| `slice-implementer` | Plan mechanisch abarbeiten (günstiges Modell) | Nach User-GO auf einen Plan |
| `bug-hunter` | Bug beweisen, dann minimal fixen | Bei jedem Fehler/roten Test |
| `security-sweep` | Privacy-/Governance-Audit des Diffs | Slice-Ende, nach Governance-Fixes, vor R9 |
| `post-slice-review` | Ehrlicher Slice-Abschluss + Milestone-Doc | Wenn Implementierer fertig meldet |
| `innolink-domain-guard` | Feld-Fakten nur aus der Matrix | Bei jeder Feld-/Limit-/Gate-Änderung |
| `thesis-narrative-guard` | Claims verteidigbar halten | Bei jedem Text über das System |

## Rollenverteilung nach Modellstärke

- **Starkes Modell (Fable/Opus-Klasse):** idea-triage, slice-planner, security-sweep
  (Gesamt-Sweep vor R9), heikle post-slice-reviews.
- **Günstiges Modell (Sonnet/Haiku, Codex, Copilot):** slice-implementer, bug-hunter
  (Standardfälle), routinemässige security-sweeps und post-slice-reviews.
- Faustregel: Entscheidungen trifft das starke Modell im Plan; das günstige Modell
  führt aus und stoppt bei jeder Unklarheit.

## Standard-Reihenfolge

```
Roadmap-Slice:   slice-planner → GO → slice-implementer → post-slice-review
                 (post-slice-review ruft security-sweep + thesis-narrative-guard auf)
Neue Idee:       idea-triage → (GO) → slice-planner → …wie oben
Bug:             bug-hunter → (Governance-Pfad? Vorschlag + GO) → Fix →
                 security-sweep bei Governance-Berührung
Feld-Logik:      innolink-domain-guard liefert die Faktenbasis, IN Planung und Umsetzung
Text/Doku:       thesis-narrative-guard
```

## Nie vermischen

- **idea-triage plant nicht.** Verdikt ist das Ende. Planen macht slice-planner.
- **slice-planner implementiert nicht.** Endet immer mit WARTE AUF GO.
- **slice-implementer plant nicht nach.** Unklarheit = Stopp, nicht Interpretation.
- **bug-hunter refactort nicht** und baut keine Features in den Fix.
- **security-sweep fixt nicht.** Findings gehen an bug-hunter oder in einen Plan.
- **post-slice-review ändert keinen Produktcode.** Fehler gehen zurück in den Loop.
- Ein Chat/Session = eine Rolle. Rollenwechsel = neue Session oder expliziter,
  benannter Wechsel („jetzt post-slice-review").

## Einsatz mit den Tools

**Claude Code:** Skills liegen in `.claude/skills/` und triggern über die
description automatisch. Explizit erzwingen: „Nutze den Skill slice-planner für R7b."

**Codex / Copilot / Modelle ohne Skill-System:** One-Screen Version (letzter
Abschnitt jeder SKILL.md) als System-/Erst-Prompt einfügen. Für slice-implementer
zusätzlich den freigegebenen Plan (`docs/plans/plan-<slice>.md`) mitgeben.
Die One-Screen-Versionen sind eigenständig lauffähig; die Langfassung ist die
Referenz bei Streitfällen.

**Günstige Modelle generell:** Immer nur EINEN Skill pro Session geben. Mehrere
Skills gleichzeitig verwässern die Hard Rules.

## Beispiel-Workflows

### Neuer Slice (R7b Partner/Attachments/Intake)
1. Starkes Modell + `slice-planner`: „Plane R7b nach roadmap-v2.md."
2. Plan lesen, ggf. korrigieren, dann: „GO." Plan als `docs/plans/plan-r7b.md` ablegen.
3. Günstiges Modell + `slice-implementer` + Plan: „Setze Schritt 1 um." … Schritt für Schritt.
4. Bei Feld-Logik im Slice: `innolink-domain-guard` liefert vorab die Faktenbasis.
5. Implementierer meldet fertig → `post-slice-review`: verify_all, Kriterien, Diff vs. Plan,
   security-sweep (R7b berührt Partner-Pfade → Pflicht), Milestone-Doc.
6. Review PASS → GO für Push.

### Bug („Copy-Button kopiert Feld X nicht")
1. `bug-hunter`: Erwartet/Beobachtet klären.
2. Absichts-Check: Blockiert der Placeholder-Blocker oder ein Zeichenlimit? Dann ist es
   Sollverhalten — kein Fix, sondern Erklärung.
3. Sonst: fehlschlagender Test → Ursache → minimaler Fix. Copy-Pfad = Governance →
   Fix-Vorschlag zuerst, GO abwarten.
4. Nach dem Fix: `security-sweep` auf den Diff (Copy-Governance berührt).

### Neue Feature-Idee („PDF-Import produktiv machen")
1. `idea-triage`: Nicht-Ziele? Roadmap-Fit (Spike war R7a, produktiv ist NICHT geplant)?
   Thesis-Wert? Kosten?
2. Wahrscheinlichstes Verdikt: DEFER auf Post-Thesis-Backlog oder Einordnung über E-04.
3. Nur bei GO: `slice-planner` — nie direkt implementieren.

## Skills testen (Abnahme nach Installation)

1. **slice-planner:** „Plane R7b." → Muss Roadmap zitieren, Schritt-Tabelle mit Tests
   liefern und mit WARTE AUF GO enden. Schreibt es Code → Skill-Verstoss.
2. **slice-implementer:** Mini-Plan mit absichtlicher Lücke geben („Schritt 2: Feld
   validieren" ohne Datei). → Muss bei Schritt 2 stoppen und fragen.
3. **security-sweep:** Test-Branch mit `logger.info(f"draft: {draft_text}")` in einer
   Backend-Datei. → Muss als P0 in Kategorie 1 erscheinen.
4. **bug-hunter:** „Bug: D3-Projekt kann keine KI-Vorschläge erzeugen." → Muss als
   Sollverhalten erkennen, kein Fix.
5. **thesis-narrative-guard:** Text mit „Die App prüft vollautomatisch die
   Förderfähigkeit und ist production-ready" prüfen lassen. → Drei Findings + Ersatz.
6. **innolink-domain-guard:** „Erhöh das Abstract-Limit auf 500 Zeichen." → Muss
   Matrix zitieren (300) und stoppen statt ändern.

Besteht ein Skill seinen Test nicht: Hard Rules des Skills schärfen, nicht den
Test aufweichen.

## Pflege

- `_shared/project-invariants.md` bei jeder Architektur-Entscheidung aktualisieren
  (neuer Nicht-Ziel-Punkt, neuer Governance-Pfad, Roadmap-Änderung).
- In `innolink-domain-guard/SKILL.md` den Repo-Pfad der Portal Field Matrix eintragen
  (`<PFAD_SETZEN>`), sobald verifiziert.
- Skills sind Teil des Repos: Änderungen an Skills wie Codeänderungen behandeln
  (Commit, Begründung).
