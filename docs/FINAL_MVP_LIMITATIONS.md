# Finale MVP-Limitationen

Stand: 23. Juli 2026 (Finale MVP-Abnahme).
Dieses Dokument bündelt alle zum MVP-Abschluss bekannten Einschränkungen.
Es ersetzt keine Fehleranalyse und beschönigt keine blockierten Gates.

## 1. Bekannte Live-Limitationen (unverändert aus RUN 3)

Übernommen aus `docs/KNOWN_LIVE_LIMITATIONS.md` — inhaltlich unverändert gültig:

1. **Externe Blockade:** Dem kombinierten Live-Lauf (LIVE-02B/LIVE-02C/LIVE-03)
   fehlt ein gültiger Ende-zu-Ende-Nachweis; die letzte bestätigte Live-Phase
   wurde durch einen externen Firecrawl-`provider_timeout` unterbrochen. Kein
   Produktfehler verifiziert. Status: `COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`.
2. **Humane Qualitätsbewertung:** nicht als vollständige Freigabe erfolgt;
   `HUMAN_QUALITY_REVIEW` bleibt `pending`. Der entkoppelte LLM-Spotcheck
   dieser Abnahme (Phase E) ergänzt Evidenz, ersetzt HUMAN-01 aber nicht.
3. **Browser-E2E:** Der deterministische Browser-E2E ist mit dieser Abnahme
   abgeschlossen (siehe FINAL_MVP_ACCEPTANCE_REPORT §Phase B); der
   *live*-gestützte End-to-End-Beobachtungsfluss bleibt ausständig.
4. **Datenmodell-/Architekturgrenzen:** Kein produktionsreifes automatisches
   «NDA-Enterprise»; externe Marktclaims ohne bestätigte Quelle werden nie
   automatisch abgeleitet (Missing Inputs statt Halluzination).
5. **Prozessgrenzen:** Keine neue Provider-/Markt-Architektur; Live-Retest der
   blockierten Gates ist separater Scope.
6. **Offene Freigaben:** Human Review bleibt für die Endfreigabe verpflichtend;
   kein fiktiver Produktionsstatus.

### Statuswahrheit (unverändert)

```text
RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED
LIVE_WEB_CAPABILITY_VALIDATED
LIVE_LLM_CAPABILITY_VALIDATED
MARKET_SCOPE_OFFLINE_VALIDATED
COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT
RUN_4_COMPLETE
```

LIVE-02B / LIVE-02C / LIVE-03 bleiben `blocked`; HUMAN-01 bleibt `pending`.
Keine Umdeutung durch diese Abnahme.

### Nachtrag 23.07.2026 — Live-Retest ausgeführt (neue Freigabe)

Der P0-Retest wurde am 23.07.2026 mit neuer Owner-Freigabe ausgeführt
(`docs/LIVE_RETEST_2026-07-23.md`). Ergebnis: Live-Web-E2E **passed**
(reale Firecrawl-Kette, kein Timeout); LIVE-02A einmal live bestanden
(akzeptierter echter A2-Vorschlag), über 3 Versuche nicht stabil;
LIVE-02B fail-closed am Exakt-Zitat-Gate. Der frühere externe Blocker
`provider_timeout` ist damit nachweislich behoben — der Status
`COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT` ist überholt und wird durch
`COMBINED_LIVE_E2E_PARTIAL_STRICT_GATES` ersetzt. HUMAN-01 bleibt `pending`.

## 2. Contract-Notizen (Stand nach dem Evidence-Read-Slice)

- **GESCHLOSSEN — Evidence-Read-Gap:** Der Read-Pfad für gespeicherte
  Vorschläge lieferte nur eine Beleg-Anzahl (`used_anchor_ids`), keine Details
  (Trigger `FINAL_ACCEPTANCE_BLOCKED_EVIDENCE_READ_CONTRACT`). Der autorisierte
  Read-only-Slice projiziert seither die zitierten `EvidenceAnchor`-Zeilen
  (Quelle, Seite/Abschnitt, Zitat, Verifikationsstatus) in
  `suggestion.evidence` — nur geprüfte Anker, Workspace-/Run-/Projekt-isoliert,
  keine Migration (Commit `39653a1`, Tests
  `backend/tests/test_suggestion_evidence_read.py`).
- `missing_inputs` trägt weiterhin kein `severity`-Feld — die UI zeigt alle
  fehlenden Angaben gleichrangig (ehrlich, keine erfundene Priorität).
- **Keine Claim-zu-Anker-Zuordnung gespeichert:** Welcher Beleg welche
  einzelne Aussage stützt, ist nicht persistiert und wird nie erfunden; sichtbar
  sind die je Vorschlag verwendeten Belege als Menge.
- Frisch- vs. Read-Shape: Der Frischpfad trägt pro Beleg Zusatzfelder
  (`support_status`, `context_kind`); der Read-Pfad liefert die sechs
  Kernfelder. Die UI nutzt nur die Kernfelder.

## 3. In dieser Abnahme festgestellte Produkt-/Daten-Limitationen

- **Kein explizites Primärquellen-Control:** Die Primärquelle wird beim
  Erstimport implizit zugewiesen (`backend/app/imports/service.py`); bei
  mehreren Kandidaten zeigt die UI nur einen Hinweis, ohne Auswahlaktion.
- **Belegstufen «Teilweise gestützt» / «Widersprüchlich/unklar»:** Als
  Datenzustand deterministisch nicht erreichbar — es gibt kein UI-Control zum
  Verwerfen/Bestätigen einzelner Anker. Die Stufen sind über die
  Definitionsliste und Unit-Tests (`lib/evidence-ladder.ts`) abgedeckt.
- **Fake-Provider zitiert keine Anker:** Deterministische A2-Vorschläge tragen
  `evidence_anchor_ids: []`; Beleg-Details erscheinen im Demo-Betrieb nur am
  geseedeten Vorschlag (Evaluation-Seed) bzw. künftig an echten Modell-Läufen.
- **Technischer Abschnittsname:** Text-Quellen liefern als Fundstelle den
  Chunker-Abschnitt («Abschnitt body») — korrekt, aber nicht nutzersprachlich.
- **Seed-Marktvergleich ohne Konsequenzenliste:** Der Cap (max. 5) ist durch
  Backend (`market/executor.py`, `[:5]`) und Unit-Test belegt; der geseedete
  Vergleich selbst führt keine Konsequenzen.
- **`backend/.env`-Hygiene:** Eine versehentliche Zeile (`m,n.p0`) steht in der
  lokalen `.env`; sie ist wirkungslos, sollte aber vom Owner entfernt werden
  (Datei ist untracked, wird hier bewusst nicht angefasst).

## 4. Priorisierter Backlog

### P0 — Release-Blocker für eine Live-/Produktionsfreigabe (nicht MVP)

- Live-Retest der blockierten Gates LIVE-02B / LIVE-02C / LIVE-03 (separat zu
  autorisieren; externer Provider-Timeout war die Ursache, kein Produktfehler).
  **Ausgeführt 23.07.2026** mit neuer Freigabe — Ergebnis teilweise: Web-E2E
  passed, LIVE-02A live bestanden (nicht stabil), 02B fail-closed am
  Exakt-Zitat-Gate; Details `docs/LIVE_RETEST_2026-07-23.md`. Restpunkt neu:
  robustere Zitat-Lokalisierung + produktgetreues Repair-Budget im Harness (P1).
- HUMAN-01: menschlicher Qualitäts-Finalentscheid über echte LLM-Outputs.
- Spotcheck-Re-Run mit produktgetreuem Repair-Budget (1+max_retries je Modus)
  und ausgewählten Belegen: Der Phase-E-Spotcheck dieser Abnahme (2 Calls,
  `gpt-5.6-terra`) belegte die Fail-closed-Gates real (inkl. verworfener
  erfundener Beleg-Referenz), lieferte aber keinen akzeptierten Vorschlag für
  die E3-Humanbewertung (Details: FINAL_MVP_ACCEPTANCE_REPORT §6). Neue
  Freigabe erforderlich.

### P1 — nach dem MVP sinnvoll

- Explizites UI-Control «Als primären Innolink-Antrag festlegen» (deckt den
  `needs_selection`-Fall ab).
- Anker-Verifikations-UI (bestätigen/verwerfen) — macht die Belegstufen
  «Teilweise gestützt»/«Widersprüchlich» real erreichbar.
- Nutzersprachliche Fundstellen für Text-Quellen (statt «Abschnitt body»).
- Konsequenzen im Evaluation-Seed-Marktvergleich ergänzen.

### P2 — dokumentierte Restpunkte

- Aus `RUN_4A_RESULT.md` §6: Mock-/Demo-Datenpfad-Divergenz, Redesign der
  read-only Markt-Tabellen im Editor, Demo-Seed-Intake-Banner.
- `backend/.env`-Zeile `m,n.p0` entfernen (Owner).
- Weitere Post-M10-Punkte gemäss `docs/audits/` (P2-Einträge der
  Frontend-Contract-Audits).
