# Finale MVP-Abnahme — Bericht

Stand: 23. Juli 2026 · Basis: `main` ab `a6ea22b` (RUN_4_COMPLETE) · Abnahme-Serie `39653a1…`
Rollen gemäss Mandat: Release Engineer, QA Lead, UX Reviewer, Accessibility Reviewer, AI Quality Reviewer (werkzeuggestützt).

## 1. Mandat & Scope

Finale MVP-Abnahme nach RUN 4B — kein Entwicklungs-Run. Nachweis, dass der
Innolink-Assistent im MVP-Scope funktioniert: Import, formale
Anforderungsprüfung, Evidenztrennung, öffentliche Recherche, Marktvergleich,
KI-Textverbesserung, Versionierung, Qualitätsübersicht, Export. Das Mandat
(«FINAL MVP ACCEPTANCE») wurde in-session übergeben; eine Datei
`FINAL_MVP_ACCEPTANCE_PROMPT.md` existiert im Repo nicht.

Owner-Entscheide dieser Abnahme (per Rückfrage eingeholt):

1. **Phase E freigegeben** — `RUN_FINAL_LLM_SPOTCHECK_APPROVED` (max. 2 echte
   LLM-Calls: complete + shorten, kein Firecrawl).
2. **Seed-Erweiterung freigegeben** — der `--evaluation`-Seed erhält einen
   gespeicherten Vorschlag, der den vorhandenen verifizierten Anker zitiert.

Autorisierter Produktcode-Change dieser Abnahme: ausschliesslich der
Phase-C-Read-only-Slice (§4) nach dokumentiertem Trigger. Keine neue
Provider-/Rule-/Markt-/Evidenz-Architektur, keine Migration, keine
Registry-Änderung, keine Bewilligungsprognose.

## 2. Phase A — Repository- und Testhygiene

Vorbedingungen: Working Tree sauber auf `a6ea22b`; `git diff --check` leer;
keine Secrets/DBs/Logs getrackt (nur `.env.example`-Dateien; `backend/.env`
untracked — Hygiene-Notiz dazu in `FINAL_MVP_LIMITATIONS.md` §3).

| Gate (über dem finalen Abnahme-Code) | Ergebnis |
|---|---|
| `corepack pnpm lint` | `pass` |
| `corepack pnpm exec tsc --noEmit` | `pass` |
| `corepack pnpm test` (Vitest) | `pass` — 76 Dateien / 562 Tests |
| `corepack pnpm build` | `pass` (frischer `.next`-Build) |
| `playwright test --workers=1` (volle Suite) | `pass` — 53 passed, 0 failed, 15 skipped (nur Opt-in-Specs) |
| `scripts/verify_all.ps1` (genau einmal, Vollregression) | `pass` — **TECHNISCHES GATE GRÜN**, alle 14 deterministischen Zeilen `pass` (diesmal inkl. `docx render smoke` mit lokalem Word); Live-Kategorien ehrlich getrennt: Live-Model-/Firecrawl-Evaluation mit RUN-3-Artefakten, Model-Selection + Supervised-Live-E2E `not_run` («not_run heisst nicht bestanden») |

Gezielte Backend-Regression während der Umsetzung: Suggestion-/Redraft-/A2-
Fläche 189 passed / 1 skipped; Seed-Tests (`test_demo_seed`,
`test_m10_eval_seed`, `test_evaluation_harness_smoke`) 15 passed inkl.
Doppel-Seed-Idempotenz.

Ehrliche Host-Infrastruktur-Klassifikation (kein Produktfehler; Belege in
`docs/RUN_4_RESULT.md` §6): OneDrive-`.pytest_cache`-EPERM (ESLint-Ignore seit
RUN 4A; `git status` zeigt nur die Permission-Warnung), `.next` muss vor Builds
vollständig gelöscht werden, `docx render smoke` benötigt lokal MS Word,
deutsche `netstat`-Locale («ABHÖREN») — Port-Bereinigung läuft
locale-unabhängig über PIDs (`Get-NetTCPConnection`).

Keine externen Calls in normalen Tests (Hermetik-Fixture `_no_real_provider_keys`
+ `RUN_REAL_PROVIDER_SMOKE`-Gate); kein Live→Fake-Fallback (E2E-EDITOR-04,
`test_live-editor-a2`); Working Tree nach den Tests sauber.

## 3. Phase B — Deterministischer Browser-E2E (B1–B10)

Setup: frische Wegwerf-DB `backend/var/final_accept.db` (Alembic + Seed
`--reset --evaluation`), uvicorn :8000 mit `AGENT_FAKE_PROVIDER=true` +
`WEB_RESEARCH_FAKE_PROVIDER=true` + `DEMO_DATA_ENABLED=true`, `next start`
:3000 (`APP_BACKEND_MODE=live`). Alle Flüsse über die normale
Nutzeroberfläche; Fixtures nur wo der Fake-Backend einen Zustand nicht
herstellen kann und immer ehrlich `fake_demo`-gekennzeichnet
(RUN-4B-Methodik). Neuer Opt-in-Spec `e2e/final-acceptance.spec.ts`
(`FINAL_ACCEPT=1`, **9/9 passed**) schliesst genau die Lücken, die kein
Gate-/Opt-in-Spec abdeckte; `RUN4A_REVIEW=1` erneut ausgeführt (**4/4
passed**); volle Suite **53 passed / 0 failed**.

| Punkt | Ergebnis | Nachweis (Spec · Test) |
|---|---|---|
| B1 Projekt + Import: Upload, Werte prüfen, übernehmen, bearbeiten, PDF-Wert wiederherstellen, Übernahme zurücknehmen, erneut übernehmen | `passed` | golden-path (2× im Gate), import-functional (15 strukturierte Kandidaten, exakte Werte), import-flow, run4a-review §2 (Restore/Undo/Redo interaktiv, keine Roh-IDs) |
| B1 Primary Application | `passed` mit Limitation | final-acceptance B1: Erstimport weist die Primärquelle implizit zu; Gruppe «Primärer Innolink-Antrag» führt die Quelle. Kein explizites Picker-Control → Limitation §3/P1 |
| B1 Projektdauer abgeleitet, nicht direkt editierbar | `passed` | import-functional (18 Monate), final-acceptance B3-Screen «Abgeleitete Projektdauer 48 Monate — nicht separat bearbeitbar» |
| B2 Drei Zweck-Gruppen (Primär/Projektunterlagen/Öffentliche Recherche); Supporting nie Antragsquelle | `passed` | final-acceptance B2 (alle drei Gruppen mit Zweckbeschreibung; Marktquelle nur in Recherche-Gruppe, Arbeitsplan nur in Projektunterlagen); Backend-Scope `test_run2b_evidence_scope.py` |
| B3 Implementation-Partner-Beitrag **52 %** + Cash **5 %** beide «Erfüllt», Review nur sekundär | `passed` | final-acceptance B3: Budget-UI 100k/47k/5k → Precheck «52 %» + «5 %», «Erfüllt» ×2; API `IMPLEMENTATION_SHARE_40_60`=`fulfilled`, `CASH_MIN5`=`fulfilled` (keine Herabstufung); Sekundär-Chip «Maschinell geprüft · Bestätigung offen» |
| B3 Offizielle Innosuisse-Quelle, Fundstelle, Link | `passed` | final-acceptance B3 (/anforderungen: «Regelgrundlage», «Quelle: Innosuisse …», «Offizielle Regel öffnen» mit href, Registry 1.1.0 geprüft 2026-06-20); run4a-review §4/§5. Precheck-Karte zeigt Regelstand, aber `Quelle: —` → P2-Notiz |
| B3 Guidance nicht in Erfüllungsquote | `passed` | Sektion «Hinweise» («zählen in keiner Quote und blockieren nichts», `guidance-notes`); Aggregation `rules/aggregation.py` |
| B4 Statuskatalog: Erfüllt / Nicht erfüllt / Teilweise erfüllt / Nicht beurteilbar / Nicht geprüft / Hinweis | `passed` | final-acceptance B3/B4: Erfüllt+Teilweise erfüllt (52/5-Projekt, Dauer 48 Mte ausserhalb 6–36) + Hinweise; Projekt B «Nicht erfüllt» (fehlender Forschungspartner, aufgeklapptes Detail); Projekt A «Nicht beurteilbar»; «Nicht geprüft» als eigenes Segment nie grün (review-truth, im Gate) |
| B4 klare nächste Aktion, keine internen Rule-IDs, keine Bewilligungsprognose | `passed` | final-acceptance (negativ: kein `REQ.INNO.`/`INTRO.APP.`), m10-2-ux (Guidance-CTA), Copy «keine Aussage zur Förderwahrscheinlichkeit» sichtbar auf /review |
| B5 Evidenz-Scopes (Application nur aus Primärantrag; Rule aus Registry; External nur Markt/SOTA/Drafting) | `passed` | Backend-Gates `test_run2b_evidence_scope.py`, `evidence/eligibility.py`; UI: Regelquelle in «Regelgrundlage», External nur im Marktvergleich |
| B5 Belegstufen | `passed` mit Limitation | final-acceptance B5: «Textstelle gefunden – fachliche Prüfung offen» + «Stark gestützt» real; alle 5 Definitionen über «Was bedeuten die Belegstufen?»; «Teilweise gestützt»/«Widersprüchlich» als Datenzustand deterministisch nicht erreichbar → Limitation §3/P1 (nie gefaked) |
| B6 Recherche: Ziel/Region/4 Module/Suchbegriffe; Unicode-Roundtrip; Demo/Live getrennt | `passed` | final-acceptance B6: exakt `KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)` → «Entwurf speichern» → Reload → identisch; market-research-flow + public-web-research (Demo nie importierbar, 422 `demo_result_not_importable`); run4a-review §8 (eine Modul-Darstellung) |
| B7 Markt: ready mit belegtem Item | `passed` | final-acceptance B7 (Evaluation-Seed): «Referenzlösung Alpha (Demo)», «Fundstelle: exakt gefunden · Inhalt: Stützung ungeprüft», source_backed-Badge, unbelegte Zellen ehrlich «nicht öffentlich belegt»/«unbestätigt» |
| B7 limited mit/ohne Items, insufficient; keine leere Erfolgstabelle | `passed` | market-comparison.spec (ehrlich leer → `insufficient_external_evidence`), run4b-editor MARKET-01 (limited ohne Items: Hinweis-Copy; ready-Fixture: max. 3 Findings im Editor, keine zweite Analyse, «Marktvergleich öffnen» = selbes Artefakt) |
| B7 max. 5 Konsequenzen; keine erfundenen Anbieter/Preise/Anteile | `passed` | Cap doppelt: Backend `market/executor.py` (`[:5]`) + UI `slice(0,5)` mit Unit-Test (6.→ nicht gerendert); Seed-Vergleich ohne Konsequenzenliste (ehrlich annotiert) |
| B8 Schreibassistent komplett (Modus→Erzeugen→Vergleich→Diff→Limit→Missing Inputs→Belege→Whole Accept = 1 Version→Replay ohne 2. Version→Versionen→Restore→stale→Provider-Fehler ohne Demo-Fallback) | `passed` | run4b-editor.spec EDITOR-01…04 (real gegen Fake-Provider: Accept +1 Version, Replay `idempotent_replay`, Restore; stale fail-closed; 503 ehrlich) + golden-path Schritt 11a; ui-states (25'000-Limit) — alle im Gate |
| B9 Qualitätsübersicht: 4 Kategorien, Aufgaben mit Aktion, not_run nie 0 | `passed` | final-acceptance B9: «Formale Blocker / Fehlende Pflichtangaben / Wichtige Qualitätsrisiken / Offene menschliche Prüfungen»; Projekt B zeigt «Nicht geprüft» als Text; Aufgabenliste mit «Im Entwurf öffnen»-Aktionen (Kappung: 10 auf /review, 5 auf /anforderungen); review-truth (Ring-Parität, not_run eigenes Segment) |
| B10 Export: Blocker sichtbar, Erzeugung, Limits/Werte konsistent, keine Auditdaten im Antragsexport, keine Fremdquelle als Antragstext | `passed` | export.spec (ENTWURF-docx, approved-markdown, «Nicht zur Einreichung»), m10-acceptance (3 Typen; technischer Export ohne `claim_text`), status-parity (Blockerzahl identisch auf /export), portal-transfer (Kopieransicht exakt Feldtext); Scope-Gates backend |

## 4. Phase C — Evidenz-Nachvollziehbarkeit (hartes Produktgate)

**Trigger festgestellt und dokumentiert:**

```text
FINAL_ACCEPTANCE_BLOCKED_EVIDENCE_READ_CONTRACT
```

Befund: Der Read-Pfad für gespeicherte Vorschläge lieferte nur eine Zahl —
`proposed_suggestion_view` rief `_suggestion_view` ohne `evidence=` auf
(`"evidence": []`), die UI zeigte nur den `used_anchor_ids`-Zähler mit dem
ehrlichen Hinweis «Fundstellen-Details stehen für gespeicherte Vorschläge
nicht zur Verfügung» (vorbestehend dokumentiert in `RUN_4_RESULT.md` §8.3).
Zusätzlich zitiert der deterministische Fake-Provider nie Anker
(`evidence_anchor_ids: []` hartkodiert), sodass auch frische Demo-Vorschläge
keine Belegdetails trugen.

**Autorisierter Read-only-Slice (Commit `39653a1`):**

- `backend/app/repositories/evidence.py` → `list_anchors_by_ids(...)`:
  Workspace-Pflichtfilter + (Run ODER Projekt)-Scope, exakt die beiden
  legitimen Zitatquellen (Application-Evidence des Laufs, Projekt-Kontextanker).
- `backend/app/agents/field_drafting.py` `_suggestion_view`: Diskriminator
  `evidence is None` (nur Read-/Reuse-Pfad) → Projektion der zitierten
  `EvidenceAnchor`-Zeilen als `{anchor_id, quote, source_name,
  verification_status, page, section}`; **nur** `exact_verified`/`human_verified`
  (identisch zum Frischpfad-Filter, ehrlich zur Copy «geprüfte Belege»),
  Zitierreihenfolge erhalten. Frischpfad unverändert.
- `backend/app/contracts/draft.py`: test-only Contract-Validator
  `SuggestionEvidenceItem`; Response-Modell unverändert (`dict`).
- Keine neue Evidenzlogik, keine Migration, kein TS-/BFF-Change (Typ +
  Rendering existierten aus RUN 4B). Tests:
  `backend/tests/test_suggestion_evidence_read.py` (Projektion + Reihenfolge +
  Contract-Shape, Statusfilter mit ehrlicher `used_anchor_ids`-Divergenz,
  Workspace-/Scope-Isolation, ankerlose Regression, kein Leak von
  `normalized_text`/Prompts/Keys).

**C1-Nachweis im Browser (real, deterministisch, kein Fixture):**
final-acceptance «Phase C» (passed): Editor `INTRO.APP.EXECUTIVE_SUMMARY` →
gespeicherter Vorschlag (Owner-freigegebener Evaluation-Seed, Commits
`15a4889`/`b3222bc`, als `fake_demo` gekennzeichnet, zitiert den real
verifizierten Anker des Demo-Laufs) → Dialog: «Dieser Vorschlag verwendet 1
geprüften Beleg.» → «Belegdetails anzeigen» → **Quelle** «Demo A -
Projektüberblick.txt», **Fundstelle** «Abschnitt body», **Ausschnitt** (Zitat
der Passage), **Supportstatus** Badge «Fundstelle bestätigt» — echte
`EvidenceAnchor`-Daten über den echten Read-Pfad. Screenshot-Evidenz:
`docs/assets/final/beleg-details-gespeicherter-vorschlag-*.png` (3 Viewports).

**Grenze (nie erfunden):** Eine Claim-zu-Anker-Zuordnung («welcher Beleg stützt
welche Aussage») ist nicht gespeichert und bleibt dokumentierte Limitation
(`FINAL_MVP_LIMITATIONS.md` §2).

## 5. Phase D — UI-/UX-Abnahme (werkzeuggestützt, 3 Viewports)

Grundlage: 21 neue Screenshots `docs/assets/final/` (7 Screens × 1440×900 /
1280×800 / 768×1024) + bestehende Bestände `docs/assets/run4a/` (18) und
`docs/assets/run4b/` (18, inkl. 390×844 mobil) + interaktive A11y-Prüfung
(run4a-review §9: Dialog-Fokus, Escape+Fokus-Rückkehr, genau ein h1 pro Screen,
Tab-Reihenfolge erreicht interaktive Elemente, sichtbarer Fokus).

Bewertung 1–5 (5 = sehr gut), je über die drei Viewports:

| Kriterium | Note | Begründung (Kurz) |
|---|---:|---|
| Klarheit | 5 | Stepper mit ehrlichen Zuständen; eine Primäraktion pro Screen («Weiter zum Entwurf», «Budget speichern») |
| Orientierung | 5 | Konsistente Seitenstruktur, Projekt-Kontext in der Topbar, kanonische Blockerzahl überall identisch (status-parity) |
| Visuelle Ruhe | 4 | Karten/Abstände ruhig; Anforderungsliste bei vielen offenen Punkten dicht, aber gruppiert-kollabierbar |
| Scanbarkeit | 5 | Status-Kacheln, Bucket-Badges, «X / Y erfüllt» je Kategorie, Tabellen mit klaren Spalten |
| Verständlichkeit der Status | 5 | Klartext-Katalog (Erfüllt/Teilweise erfüllt/Prüfung nötig/Nicht beurteilbar/Nicht erfüllt) + Begründungssatz im Detail; «Nicht geprüft» nie 0/grün |
| Verständlichkeit von Belegen | 5 | «Dieser Vorschlag verwendet N geprüfte Belege» + aufklappbare Details (Quelle/Fundstelle/Zitat/Badge); Belegstufen-Definitionen an Ort |
| Verständlichkeit Missing Inputs | 5 | «Fehlende Angaben» primär mit Warum/Innolink-Punkt/nächster Aktion; Platzhalter statt erfundener Zahlen |
| Nutzbarkeit Marktvergleich | 4 | Ehrliche Zellen («nicht öffentlich belegt»), belegtes Zitat je Zeile; Tabelle bei 768 px horizontal scrollbar (akzeptabel) |
| Nutzbarkeit Schreibassistent | 5 | Drei Modi in Nutzersprache, Zwei-Spalten-Vergleich, Diff nie nur Farbe, Übernahme nur explizit |
| Vertrauen/Nachvollziehbarkeit | 5 | Demo-Kennzeichnung konsequent («kein echtes KI-Modell»), Regelgrundlage mit offizieller Quelle + Datum, «keine Aussage zur Förderwahrscheinlichkeit» |
| Accessibility | 4 | Fokusmanagement/aria-live/tabpanel belegt (RUN 4B + run4a-review §9); vollständiges AT-Audit (Screenreader-Durchlauf) bleibt offen |
| Responsive | 4 | 1440/1280 einwandfrei; 768 vollständig bedienbar; kosmetisch: Topbar-Projektauswahl überlappt bei sehr langem Titel leicht mit «Hilfe» (P2) |

```text
critical_confusion = no
main_action_obvious = yes
technical_overload = no
usable_for_nontechnical_applicant = yes
```

Kein kritischer UI-Blocker → kein `MVP_ACCEPTANCE_BLOCKED_UI_USABILITY`.
Kosmetische Funde (Topbar-Überlappung bei Langtiteln; «Abschnitt body» als
technischer Fundstellenname; Precheck `Quelle: —`) sind als P1/P2 im Backlog.

## 6. Phase E — Entkoppelter echter LLM-Spotcheck

Freigabe: `RUN_FINAL_LLM_SPOTCHECK_APPROVED` (Owner, 2026-07-23).
Ausführung: genau **2 echte LLM-Calls** über die bestehende Produktgrenze
`run_a2_field_drafting` → `gateway.invoke` (Muster + Guards des
R5.5-Harness: `RUN_REAL_PROVIDER_SMOKE=true`, `AI_EVAL_MODE=real`,
synthetisches D0-Setup, frische Wegwerf-DB, erzwungene Route, Adapter-Cap =
1 Call je Modus). **Kein Firecrawl, kein Providervergleich, kein Retryloop,
kein Fake-Fallback.** Feld `INTRO.APP.EXECUTIVE_SUMMARY`, Route
`openai_direct`, Modell `gpt-5.6-terra`. Artefakt:
`backend/var/evaluation/final_spotcheck.json` (git-ignoriert).

| | Call 1 `complete_innolink_requirements` | Call 2 `shorten` (Basistext 1023 Zeichen) |
|---|---|---|
| Status | `failed` — `no_candidate_for_field` | `failed` — `unknown_evidence_anchor` |
| Tokens (in/out) | 1750 / 284 | 1950 / 1562 |
| Latenz | 5.8 s | 28.2 s |
| Kosten (priced) | CHF 0.007 | CHF 0.023 |
| Metering | 1 UsageRecord | 1 UsageRecord |
| Persistiert | nichts | nichts |

**Ehrliche Einordnung:**

- **Call 2 ist ein echter Guardrail-Nachweis:** Der Kontext enthielt bewusst
  keine Beleg-Anker (das Spotcheck-Setup konfiguriert keine Primärquelle und
  keine Anker-Auswahl) — das Modell **erfand dennoch eine Beleg-Referenz**,
  und der serverseitige Halluzinations-Gate verwarf den Vorschlag fail-closed
  (`unknown_evidence_anchor`), ohne irgendetwas zu persistieren und ohne
  Demo-Fallback. Genau das Verhalten, das das Produktversprechen fordert.
- **Call 1:** Die Modellantwort enthielt keinen Kandidaten für das
  angeforderte Feld. Der Produktpfad hätte hier genau **einen** Reparatur-
  Versuch unternommen (`max_retries=1`); der Spotcheck-Cap (Mandatsbudget:
  max. 2 Calls gesamt) hat diesen produktüblichen Repair unterbunden —
  eine **Harness-Einschränkung, kein Produktfehler**.
- **E2-Akzeptanz nicht nachweisbar, E3 entfällt:** In den zwei bewilligten
  Calls entstand kein akzeptierter Vorschlag, den ein Mensch bewerten könnte.
  Der Spotcheck ist damit **durchgeführt** (nicht `NOT_RUN`, nicht
  `BLOCKED_BY_PROVIDER` — der Provider antwortete beide Male), Ergebnis:
  Fail-closed-Gates real belegt, Nutzwert-Bewertung offen.
- **Kein MVP-Blocker:** Der reale LLM-Qualitätsnachweis des MVP bleibt
  LIVE-02A (RUN 3: echter `model_generated`-Vorschlag mit Missing Inputs
  statt erfundener Marktgrösse, real validiert). HUMAN-01 bleibt unverändert
  `pending`. Ein erneuter Spotcheck mit produktgetreuem Repair-Budget und
  ausgewählten Belegen ist als P0-Backlog-Punkt dokumentiert und braucht eine
  neue Freigabe.

## 7. Statuswahrheit (unverändert übernommen)

```text
RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED
LIVE_WEB_CAPABILITY_VALIDATED
LIVE_LLM_CAPABILITY_VALIDATED
MARKET_SCOPE_OFFLINE_VALIDATED
COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT
RUN_4_COMPLETE
```

LIVE-02B / LIVE-02C / LIVE-03 bleiben `blocked` (externer Firecrawl-
`provider_timeout`, RUN 3); HUMAN-01 bleibt `pending`. Diese Abnahme deutet
keines dieser Gates um und behauptet keine vollständige Providerverfügbarkeit,
keine Enterprise-/NDA-Produktionsreife und keine Förderwahrscheinlichkeit.

## 8. Produktversprechen (zulässige Formulierung)

> Der MVP unterstützt die strukturierte Erstellung und Prüfung eines
> Innolink-Antrags, trennt formale Regeln und Evidenz, führt quellengebundene
> Recherche durch und erzeugt nachvollziehbare KI-Textvorschläge, die vor der
> Übernahme menschlich geprüft werden. Externe Providerverfügbarkeit und die
> endgültige fachliche Verantwortung bleiben ausserhalb der automatischen
> Entscheidung.

## 9. Endstatus

Alle Voraussetzungen des zulässigen Erfolgsstatus sind erfüllt:
deterministischer Browser-E2E bestanden (volle Suite 53/0, final-acceptance
9/9, run4a-review 4/4, verify_all GRÜN), UI-/UX-Review bestanden (kein
kritischer Blocker), Evidence-Details sichtbar (hartes Phase-C-Gate nach
autorisiertem Slice real belegt), Import/Regeln/Evidenz/Markt/Editor/
Qualität/Export bestanden, keine kritische Produktregression, bekannte
RUN-3-Live-Limitationen dokumentiert (`FINAL_MVP_LIMITATIONS.md`).

```text
MVP_ACCEPTED_WITH_KNOWN_LIVE_LIMITATIONS
```

Kein weiterer grosser Entwicklungs-Run. Offene Punkte ausschliesslich als
priorisierter Backlog in `FINAL_MVP_LIMITATIONS.md` §4 (P0: Live-Retest
LIVE-02B/-02C/-03, HUMAN-01, produktgetreuer Spotcheck-Re-Run; P1/P2 siehe
dort).

Abnahme-Commit-Serie: `39653a1` (Evidence-Read-Slice + Tests), `15a4889`
(Seed-Vorschlag mit verifiziertem Anker), `2e5bcad`/`e59a050`
(final-acceptance-Spec), `b3222bc` (Seed-Coverage-Stempel), plus dieser
Docs-/Assets-Commit.

```text
FINAL_MVP_ACCEPTANCE_COMPLETE
```
