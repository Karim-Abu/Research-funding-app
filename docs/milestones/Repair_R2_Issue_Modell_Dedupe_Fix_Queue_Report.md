# Repair-Milestone R2 — Issue-Modell, Dedupe & Fix Queue

**Scope:** Vollständige Umsetzung von R2 gemäss Prompt-Pack
`claude_code_prompt_pack_innolink_repair_v2.md` (R2.1–R2.7) und
`docs/repair/roadmap-v2.md`, inklusive des vorgezogenen R1-Restabschlusses
(zwei vorbestehende E2E-Fehlschläge). Ein Prompt = ein Commit. Ziel ist
**weniger Rauschen, klare Prioritäten**: dieselben Findings, aber gruppiert,
klassifiziert und als priorisierte Aufgabenliste — keine neuen Prüfregeln,
keine KI-Inhalte.

## Branch / Commit-Basis

- Branch **`repair-v2`**; Basis-Tag **`repair-r1-done`** auf `136c850`,
  **`repair-r2-done`** auf diesem Stand. **Kein Push** (wartet auf Owner-GO).

## Commits (ein Prompt = ein Commit)

| Commit | Prompt | Inhalt |
|---|---|---|
| `9904f3a` | Bugfix (R1-Rest) | `e2e/demo-dataset.spec.ts` an ehrliche Herkunfts-Badges angepasst (App korrekt seit Owner-Commit `2b455a4`, Test veraltet) |
| `5622e9e` | Bugfix (R1-Rest) | Quellen-Seite löst die gespeicherte Projektklasse auf (State-Resolution, kein Policy-Downgrade); `flatFromDataClassification` neu |
| `136c850` | R1-Abschluss | Milestone-Report R0+R1 finalisiert (verify_all ALL GREEN wörtlich); Tag `repair-r1-done` |
| `f24d116` | R2.1 | Fingerprint-Modul: `compute_finding_fingerprint` (Row-Identität, Zahlen maskiert) + `compute_display_group_key` (UI-Gruppierung OHNE claim_core) — 13 Tests zuerst |
| `c528e46` | R2.2 | Additive Migration `7b091c3d3e24`: `fingerprint`/`severity_class`/`fix_recommendation`/`last_seen_at` nullable auf `review_findings` + `open_issues`; Downgrade + Row-Preservation-Roundtrip |
| `978e11e` | R2.3 | Befüllung bei Neuerzeugung (`package.py::apply_findings`, `gate.py`): sechs severity-Klassen; **Findings-Idempotenz-Regression = Merge-Gate ab R2** |
| `9fe51df` | R2.4 | `review/fix_queue.py` + `GET /runs/{id}/review/fix-queue` (+ Next.js-Proxy): Gruppen nach display_group_key, Prioritäten 1–6, Beispiele mit Einzel-Claims |
| `b577b20` | R2.5 | UI hinter Flag `groupedFindings`: «Nächste Aufgaben» (Top-5) + gruppierte Liste auf Qualitätsprüfung/Anforderungen; Reliability-Meldungen gebündelt («31 × …») |
| `b75286e` | R2.6-Katalog | `docs/repair/message-catalog.md` als ENTWURF (STOPP für Owner-Review) |
| `98fda27` | R2.6 | Owner-Approve (2026-07-07, Chat) → `rules/messages.py` verdrahtet; Alttext «Kein passender Partner vorhanden» entfernt; Zweig-Semantik unverändert |
| `ebd3f73` | R2.7 | Loader-Validierung `source_ref`/`source_version`/`last_checked`/`validity_status` (Format, fail-closed; leere Felder toleriert — Inhalte liefert der Owner) |
| `fdc75e7` | E2E-Anpassung | `m10-2-ux.spec.ts` akzeptiert die R2.5-Fix-Queue als Review-Guidance (`fix-queue-next` ODER Fallback `next-steps`; Sichtbarkeit + Inhalt weiterhin gefordert) |

## Kernverhalten

### Zwei Schlüssel, zwei Zwecke (Owner-Vorgabe)
- **`finding_fingerprint`** — stabile technische Identität EINES Findings
  (Familie + Feld + normalisierter claim_core + source_id; Zahlen → `#`).
  Gleiche Aussage mit anderer Zahl ⇒ gleicher Fingerprint.
- **`display_group_key`** — UI-Gruppierung `severity_class|Meldungsfamilie`,
  enthält NIE den claim_core. Vier «Quantifizierte Aussage ohne passenden
  Zahlenbeleg»-Findings mit verschiedenen Claims ⇒ EINE Gruppe; die
  Einzel-Claims bleiben als Beispiele in der Gruppe sichtbar.

### Sechs severity-Klassen (genau diese)
`export_blocker` (Platzhalter/Zeichenlimit/leeres Pflichtfeld) ·
`eligibility_blocker` (Blocker-OpenIssues, via Registry-Kategorie) ·
`budget_blocker` (Kategorie budget) · `reviewer_risk` (Rubric, ab R6.4) ·
`evidence_risk` (reliability:*/Evidenz/a3) · `style_risk` (Rest).
Fix-Queue-Priorität in genau dieser Reihenfolge.

### Messbarer Effekt am F1-Goldfall (QUALIMON)
Gleicher Ablauf wie die R0.3-Baseline (identisch reproduzierte Zahlen:
18 Blocker / 54 Warnungen / **72 offene Findings**):

| Vorher (Baseline R0.3) | Nachher (R2, Fix-Queue-API) |
|---|---|
| 72 einzelne Findings, 20 Meldungstexte, grösste Wiederholung 31× identisch | **7 Gruppen** (1 export_blocker, 1 budget_blocker, 5 evidence_risk) |
| Kein Einstiegspunkt («womit anfangen?») | Top-5 «Nächste Aufgaben», priorisiert: 4 × Platzhalter → 2 × Budget-Blocker → 38 × Nicht belegte Aussage → 10 × Marktaussage → 8 × fehlender Evidenz-Verweis |

Messskript-Output (Rohzahlen) im Abschluss-Review dieser Session; Ablauf
reproduzierbar über `scripts/baseline_f1.py`-Flow + `GET …/review/fix-queue`.

### R2.6 — Entity-spezifische Meldungen
Katalog `docs/repair/message-catalog.md` (Owner-approved 2026-07-07): je
Zweig der beiden Partner-Regeln und der finanziellen Unabhängigkeit ein
fester Text (drei Texte wörtlich aus dem Prompt-Pack). `missing` benennt die
fehlende Angabe und bleibt `needs_input` — **kein geratenes pass/fail**, alle
`mapping_key`s unverändert (Diff-Nachweis).

### Feature-Flag
`groupedFindings` (lib/flags.ts): Default AN; `NEXT_PUBLIC_GROUPED_FINDINGS=off`
schaltet ab. Bei Fehler/leerer Fix-Queue-Antwort fällt die UI unabhängig vom
Flag automatisch auf die alte Darstellung zurück.

## Datenschutz-/Governance-Bezug (manueller Security-Sweep)

Der Diff berührt `reliability/gate.py`, `review/package.py`, `rules/handlers.py`
(Governance-Pfade). Geprüft:
- `backend/app/security/*`: **unverändert**.
- `finding_code`-Erzeugungsformate: **unverändert** — `review/checks.py` ist
  im gesamten Slice unberührt; in `gate.py` keine `finding_code=`-Zeile im
  Diff. Nur additive Spalten befüllt.
- Zweig-Semantik `rules/handlers.py`: **unverändert** — Diff zeigt
  ausschliesslich Textquellen-Tausch (`rule_message(...)`), alle
  `mapping_key`s identisch; Regressionstest `missing ⇒ needs_input`.
- Scope-Hash-Bestandteile in `review/package.py`: **unverändert** (nur
  `apply_findings` additiv erweitert; `compute_scope_hash` untouched).
- Contract-WERTE: unverändert (R2.7 nur Loader; Tests mit synthetischen
  Rohdaten statt YAML-Edits).
- Kein Roh-Claim-Text in Gruppenschlüsseln, Logs oder Audit-Details:
  claim_core wird ausschliesslich **gehasht** (`fingerprint`); Audit-Events
  unverändert (`code`/`severity`-Metadaten). Marker-Test im Fix-Queue-Test.
- Neuer Endpoint `GET /runs/{id}/review/fix-queue`: `require_session` +
  Workspace-Scoping (`_require_run`), read-only (Nachweis:
  `test_endpoint_view_is_read_only`).
- Keine rohen field_ids als UI-Text (nur in Deep-Links).

## Tests

- **Backend neu (47):** `test_finding_fingerprint.py` (13),
  `test_finding_v2_backfill.py` (10, enthält die **Idempotenz-Regression**:
  Re-Run/Recheck erzeugt keine zusätzlichen Rows), `test_fix_queue.py` (6,
  inkl. «4 gleichartige, unterschiedliche Claims ⇒ 1 Gruppe count=4» und
  Marker-Test gegen Claim-Text im group_key), `test_rule_messages.py` (10,
  inkl. grep-Test gegen den Alttext), `test_registry_metadata.py` (8);
  `test_m10_migrations.py` auf neuen Head geführt (Roundtrip +
  Row-Preservation).
- **Frontend neu:** `test/fix-queue.test.tsx` (7: Top-5, Priorität,
  Zählprefix, Deep-Links, Beispiele, Kappungshinweis, keine identischen
  Meldungen untereinander).
- Keine Tests deaktiviert, geskippt oder abgeschwächt (Diff-Prüfung).

## Verifikation (verify_all.ps1, wörtlich)

Hinweis zur Lauf-Historie (drei Läufe bis ALL GREEN):
1. Lauf kontaminiert durch ein noch laufendes Mess-Backend der F1-Messung
   (Port 8000 belegt, E2E gegen falsche DB); zusätzlich zeigte er die echte
   R2.5-Folge in `m10-2-ux` → mit `fdc75e7` ans neue Soll angepasst.
2. Lauf: `next build` scheiterte an einem OneDrive-Datei-Lock im `.next`-
   Cache (EPERM unlink, umgebungsbedingt; danach kaskadierend «servers not
   ready»), plus EIN Load-Timing-Flake in `test/draft-placeholder.test.tsx`
   (vorbestehend, Datei seit `8ad070c` unverändert; 3× isoliert grün
   nachgewiesen, P1-Follow-up notiert).
Massgeblich ist der folgende saubere Lauf.

Lauf vom 2026-07-07 (HEAD `fdc75e7`), Exit-Code 0. Backend-pytest komplett
grün (`s`-Marker = vorbestehende Conditional-Skips der Real-Provider-Smokes),
vitest 217/217 (50 Dateien), Playwright 31/31 (inkl. Status-Paritätstest und
angepasstem M10.2-Test), API-Smoke 18/18. Summary-Block wörtlich:

```text
================ M10 VERIFICATION SUMMARY ================
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass
build/typecheck/lint     : pass
Playwright               : pass
API smoke                : pass
export smoke             : pass   (test_m10_smoke.py::test_export_all_types)
no-raw-log               : pass   (test_m10_smoke.py::test_no_raw_log)
testdata markers         : pass   (scripts/check_testdata_markers.py)
legacy status guard      : pass   (scripts/check_legacy_status_paths.py)
evaluation summary       : C:\Users\karim\OneDrive - FHNW\Documents\Bachelorthesis\App\Reasearch-funding-app\backend\var\evaluation\EvaluationRunSummary.json
=========================================================
ALL GREEN
```

## Offene Punkte / Follow-ups

- **Migration-Review (R2.2):** Owner-Review der Migration `7b091c3d3e24`
  vor Merge/Push ausstehend (nur additiv, Downgrade vorhanden).
- **Gruppen-Titel** (`_FAMILY_TITLES` in `fix_queue.py`) sind UI-Anzeige-
  Labels (keine Regelaussagen); optionale Übernahme in den Message-Katalog
  als P2 möglich.
- `fix_recommendation` bleibt vorerst null (kein eindeutig ableitbarer
  Zusatz zu `recommended_next_action`); OpenIssue-Spalten sind angelegt,
  Befüllung folgt bei Bedarf.
- Baseline-Beobachtungen 2/4/5 (Stale-Sprünge, technische Feldlabels in
  Meldungstexten der checks.py-Findings, gerundete Budget-Meldungen) bleiben
  offen — Feldlabel-Texte kommen mit R4.2-Katalog bzw. R6.
- **P1 (vorbestehend):** `test/draft-placeholder.test.tsx` («cycles the
  selection») flakt unter Volllast (waitFor auf `selectionStart`); isoliert
  und in zwei Vollläufen grün. Stabilisierung als eigener Fix empfohlen.
- **P2 (Umgebung):** Repo liegt in OneDrive — Sync-Locks auf `.next` können
  `next build` mit EPERM brechen (2. Abschlusslauf). Empfehlung: `.next`
  vom OneDrive-Sync ausnehmen oder Repo ausserhalb OneDrive; alternativ
  `.next`-Cleanup in verify_all (Owner-Entscheid, Skript ist Do-not-touch).
- E-01 (PDF-Gate → R3/R3'), E-02 (Provider), R4.1-Mapping-Tabelle,
  `docs/security/*`-Vorlagen, Marker-Katalog: unverändert offen (Owner).
- **R4.4 (Browser-Storage-Security-P0)** bleibt der empfohlene nächste
  Slice (keine Owner-Abhängigkeiten).
- **Kein Push** von `repair-v2`/Tags ohne Owner-GO.

## Einordnung (ohne Überclaims)

R2 verändert die **Darstellung und Priorisierung** vorhandener Befunde —
es entstehen keine neuen Prüfregeln, keine KI-Inhalte und keine Aussagen zur
Förderfähigkeit. Die Zahl der offenen Findings bleibt gleich (72 am F1);
reduziert wird das Wiederholungsrauschen (7 Gruppen statt 72 Einzelzeilen)
und die Einstiegshürde (priorisierte Aufgabenliste). Kopieren bleibt
fail-open und wird nur protokolliert; menschliche Prüfung bleibt die finale
Instanz.
