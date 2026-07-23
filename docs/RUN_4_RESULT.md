# RUN 4 — Ergebnis (RUN 4B: Schreibassistent, visueller Diff, Browser-E2E)

Stand: 23. Juli 2026
Scope: Abschluss von RUN 4 (4A siehe `docs/RUN_4A_RESULT.md` +
`docs/RUN_4A_UI_REVIEW.md`; dieser Bericht deckt RUN 4B). Keine Provider-,
Rule-, Market-, Evidence- oder Datenarchitektur geändert; keine externen
Calls; Live-/Fake-Semantik unverändert.

## Statuswahrheit (unverändert)

```text
RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED
LIVE_WEB_CAPABILITY_VALIDATED
LIVE_LLM_CAPABILITY_VALIDATED
MARKET_SCOPE_OFFLINE_VALIDATED
COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT
```

Keine vollständige Live-Abnahme wird behauptet; HUMAN-01 bleibt `pending`.

## 1. Autorisierter additiver Versions-Slice (Owner-Entscheid A)

Einzige Contract-Erweiterung von RUN 4B — begründet, minimal, ohne Migration:

- **Backend:** `GET /runs/{id}/fields/{field}/versions` (read-only
  Metadaten-Liste über die bestehende append-only `draft_versions`-Tabelle;
  neueste zuerst; ohne Volltexte). Neue Pydantic-Modelle `DraftVersionSummary`
  + `DraftVersionList`; `_generation_kind_for` extrahiert, damit Liste und
  Einzelversion die Provenienz identisch ableiten. Kein DB-Modell-Change,
  keine Migration, kein neuer Mutations-Endpunkt.
- **Restore = client-orchestriert über den bestehenden Versionspfad:**
  Einzelversion lesen (bestehender Backend-GET, neu als BFF-Passthrough) →
  regulärer `updateField`-PATCH → neue `user`-Version. Dadurch gratis:
  409-Konfliktpfad, serverseitiger No-op bei identischem Text (keine
  redundante Version), unveränderte Audit-/Carry-over-Semantik.
- **Dokumentierte Grenzen:** kein dediziertes `version_restored`-Audit-Event
  (Audit zeigt den regulären Draft-Update); Restore einer Über-Limit-
  Altversion endet im bestehenden 422 mit verständlicher Meldung.
- Pytest: `backend/tests/test_draft_versions.py` (Reihenfolge/is_current,
  keine Volltexte, Scoping-404, Restore-Semantik inkl. No-op) — grün.

## 2. Problem-zu-Lösung-Matrix (RUN 4B)

| Problem (Mandat) | Lösung | Dateien |
|---|---|---|
| §2.1 Kopf ohne originale Portalfrage | Portalfrage (Registry `label_or_question`) im Feldkopf, wenn sie mehr sagt als der Feldname | `draft-workspace-shell.tsx`, `live-editor.tsx` |
| §2.2 Modi-Copy technisch | «Fehlende Innolink-Punkte ergänzen» statt «Innolink-Anforderungen vervollständigen» | `live-editor.tsx` |
| §3 Diff ohne Screenreader-Zusammenfassung | `summarizeDiff` (Satzzählung je Änderungsart) als sr-only `aria-live`-Zeile im Sheet; Fokus beim Öffnen deterministisch auf dem Titel | `lib/diff.ts`, `suggestion-review-dialog.tsx` |
| §4 Stale nur als Roh-Code | Klartext für alle 9 kanonischen Staleness-Codes + Legacy + generischer Fallback; prominenter Hinweis mit nächster Aktion; Accept bleibt deaktiviert | `lib/redraft.ts` (`STALE_REASON_LABELS`), `suggestion-review-dialog.tsx` |
| §4 kein Pending-Zustand | «Vorschlag wird erzeugt … Ihr Entwurf bleibt unverändert …» mit `aria-live` | `live-editor.tsx` |
| §5 Missing Inputs nur als Chips/Listen | Primäre Sektion «Fehlende Angaben»: Titel, warum, Innolink-Punkt, nächste Aktion, Bleiben-sichtbar-Hinweis — nie Requirement-IDs | `suggestion-review-dialog.tsx` |
| §6 Belege ohne Hauptzeile; Read-Pfad leer | «Dieser Vorschlag verwendet N geprüfte Belege.» + aufklappbare Details (Quelle, Fundstelle, Zitat, Status); Read-Pfad-Zahl ehrlich aus `used_anchor_ids` mit Erklärtext statt 0-Claim | `suggestion-review-dialog.tsx` |
| §2.1 Manifest-Zeile im Hauptfluss | in «Technische Details» verlagert (nicht gelöscht) | `suggestion-review-dialog.tsx` |
| §7 kein benannter Regenerate | «Neuen Vorschlag erzeugen» im Sheet (bestehender idempotenter Redraft-Pfad) | `suggestion-review-dialog.tsx`, `live-editor.tsx` |
| §7 Replay unsichtbar | `idempotent_replay` → «Bereits übernommen — es wurde keine neue Version erstellt.» | `live-editor.tsx` |
| §7 Herkunft technisch | `versionOriginLabel`: «Aus KI-Vorschlag übernommen» nur bei verifizierter Provenienz; Generierungsart (Live-KI/Demo) als eigener Chip; Vorsichtstext bleibt für unverifizierte Herkunft | `lib/draft-viewmodel.ts`, `live-editor.tsx` |
| §9 Versionshistorie fehlte («Beta»-Hinweis) | echter Versionen-Tab: Herkunft/Zeit/Zeichen, «Aktuell», «Wiederherstellen» (gesperrt mit Begründung bei ungespeicherten Änderungen) | `assistant-panel.tsx`, `live-editor.tsx`, `lib/fields.ts` |
| §8 Markt-Card: 4 Findings, kein Quellen-Zähler, generischer Leerzustand | max. 3 Findings, deduplizierte «N geprüfte Quellen», limited-ohne-Items-Copy «Marktinformationen vorhanden, aber noch kein belastbarer Anbieter-/Alternativenvergleich.» | `live-market-comparison.tsx` |
| §10 Tabs ohne tabpanel | `role=tab/tabpanel` + `aria-controls`/`aria-labelledby` | `assistant-panel.tsx` |
| Screenshot-Review-Befund: Roh-Warncode `fake_demo_no_model` im Hauptfluss | Klartext-Label «Demo-Vorschlag ohne echtes KI-Modell — deterministischer Beispieltext …» | `suggestion-review-dialog.tsx` |
| Screenshot-Review-Befund: Badge «Streichung übernehmen» trotz Vollübernahme-Modus | Whole-only zeigt nur die Änderungsart «Streichung» (keine Einzelübernahme suggeriert) | `suggestion-review-dialog.tsx` |

Owner-Entscheid B (bestätigt): Die Legacy-Satz-/Teilübernahme bleibt — sie
nutzt den regulären Server-PATCH mit base_version-Concurrency und
`source_operation_id`-Provenienz (kein Manifest vorhanden, das umgangen werden
könnte); manifestgebundene Vorschläge bleiben server- und clientseitig strikt
Vollübernahme.

## 3. Geänderte Komponenten (Commit-Serie RUN 4B)

`c25125e` Backend-Versionsliste · `5b7028c` BFF/Client · `ff8aef7`
Versionen-Tab+Restore · `7ba1e9d` Feldkopf+Modi · `9fbf492` Diff-A11y ·
`e132c95` ehrliche Zustände · `bd77d0e` Missing-Inputs/Belege-Sektionen ·
`0e96e83` Aktionen/Herkunft · `3bcd1dd` Markt-Card · `5f29d5e` E2E-Spec+
golden-path — plus dieser Doku-/Visual-Commit.

## 4. Screens/States (visuelle Nachweise)

`docs/assets/run4b/` — erzeugt mit `e2e/run4b-visual.spec.ts` (opt-in
`RUN4B_VISUAL=1`, lokale Fake-Provider-Server, keine externen Calls):
Zwei-Spalten/gestapelt (1440×900, 768×1024, 390×844), Vorschlag mit Missing
Inputs + 2 Belegen, veralteter Vorschlag, Providerfehler ohne Demo-Fallback,
übernommene Version mit Historie, Markt limited ohne Items — jeweils
1440×900 / 1280×800 / 768×1024.

## 5. Accessibility (RUN 4B)

- Fokus beim Öffnen des Vorschlag-Sheets deterministisch auf dem Titel;
  Escape schliesst ohne zu verwerfen (unverändert).
- sr-only-Diff-Zusammenfassung mit `aria-live="polite"`; Pending-/Replay-/
  Fehlerzustände als `role="status"`/`alert`.
- Assistent-Tabs mit `tabpanel`-Verknüpfung; Versionsliste mit erklärt
  deaktiviertem «Wiederherstellen» bei ungespeicherten Änderungen.
- Status nie nur über Farbe (Text-Badges im Diff, Herkunfts-Chips).
- Responsive: Zwei-Spalten ab `lg`, gestapelt darunter; Sheet 85vw mit
  scrollbarem Inhalt; Nachweise bei 1440/1280/768 (+390 mobil).

## 6. Tests und Gates

Vitest/Component (neu bzw. erweitert, alle grün): `fields-versions`,
`live-editor-versions`, `live-editor` (Portalfrage), `diff` (summarizeDiff),
`suggestion-review-dialog` (sr-Summary, Missing-Inputs-Sektion, Beleg-Zeile,
Read-Pfad, Regenerate, Stale-Klartext), `redraft` (staleReasonLabel),
`live-market-comparison`, `live-editor-context` (Versionen-Tab + tabpanel).
Backend-Pytest: `test_draft_versions.py` (+ Regression `test_draft_flow.py`,
`test_a2_redraft_api.py`).

```text
corepack pnpm lint             → pass
corepack pnpm exec tsc --noEmit → pass
corepack pnpm test             → pass (76 Dateien / 561 Tests)
corepack pnpm build            → pass
playwright test --workers=1    → pass (53 passed, 5 skipped [opt-in-Specs], 0 failed)
scripts/verify_all.ps1 (einmal) → {{VERIFY_ALL_RESULT}}
```

Browser-E2E: `e2e/run4b-editor.spec.ts` — 5/5 grün (EDITOR-01..04,
MARKET-01; Methodik-Mix real/Fixture siehe Spec-Kopf); golden-path inkl.
neuem Versionshistorie-Schritt grün (E2E-FLOW-01).

Host-Infrastruktur (ehrlich, kein Produktfehler): Beim E2E-Setup wurden zwei
verwaiste Serverprozesse einer früheren Session entdeckt, die Port 3000/8000
hielten und einen gelöschten Build aus dem Speicher servierten (CSS-500).
Ursache der wirkungslosen Port-Bereinigung: deutsche `netstat`-Ausgabe
(«ABHÖREN» statt «LISTENING») — die Prozessbereinigung wurde auf
locale-unabhängige PID-Ermittlung umgestellt. Zusätzlich bleibt
`.pytest_cache/` unter OneDrive zeitweise gesperrt (seit RUN 4A im
ESLint-Ignore) und `.next` muss vor Builds vollständig entfernt werden
(bestehendes verify_all-Verhalten).

## 7. Bekannte RUN-3-Limitationen (unverändert übernommen)

`docs/KNOWN_LIVE_LIMITATIONS.md` gilt fort: LIVE-02B/-02C/-03 `blocked`
(externer `provider_timeout`), humane Qualitätsbewertung `pending`, kein
produktionsreifes NDA-Enterprise-System, Human Review bleibt Pflicht.

## 8. Offene Final-Acceptance-Punkte

1. Live-Retest der blockierten Gates (separat autorisieren; nicht Teil RUN 4).
2. HUMAN-01 humane Qualitätsbewertung.
3. Contract-Notizen (kein Blocker, ehrlich in der UI behandelt):
   `severity` fehlt in `missing_inputs`; Read-Pfad ohne Beleg-Details für
   gespeicherte Vorschläge; Claim-zu-Beleg-Zuordnung («welche Aussage wird
   gestützt») ist im Vertrag nicht je Anker vorhanden — die UI zeigt das
   wörtliche Zitat der Fundstelle.
4. P2-Reste aus RUN 4A (`RUN_4A_RESULT.md` §6): Mock-Divergenz,
   Editor-Read-only-Markttabellen-Redesign, Demo-Seed-Intake-Banner.

## 9. Abschluss

```text
RUN_4_COMPLETE
READY_FOR_FINAL_ACCEPTANCE
```

Keine finale Produktfreigabe wird behauptet; es folgt der separate
Final-Acceptance-Lauf.
