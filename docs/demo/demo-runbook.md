# Demo-Runbook — Innolink-Check Golden Path

Reproduzierbare, demonstrierbare End-to-End-Demo des Golden Path auf einer
frischen Demo-Datenbank, vollständig deterministisch (Fake-LLM + Fake-Web) und
ohne externe API-Schlüssel. Die ausführbare Fassung dieses Ablaufs ist
[`e2e/golden-path.spec.ts`](../../e2e/golden-path.spec.ts); dieses Runbook ist
die manuelle Entsprechung für eine Live-Vorführung.

> Regeln des Repos: [`.claude/CLAUDEX.md`](../../.claude/CLAUDEX.md). Der Fake-Provider
> ist der Demo-Default und wird in der UI **ehrlich** als Test-/Synthetik-Pfad
> gekennzeichnet — es wird nie über die Datenquelle getäuscht.

## 1. Voraussetzungen

- **Node** ≥ 20 mit **corepack** (`corepack enable`) → `pnpm`.
- **Python** ≥ 3.12 mit Backend-venv unter `backend/.venv`
  (`python -m venv backend/.venv`), Abhängigkeiten:
  `backend/.venv/Scripts/pip install -r backend/requirements.txt`.
- **Playwright-Browser** (nur für den automatisierten Nachweis):
  `corepack pnpm exec playwright install chromium`.
- Betriebssystem: Windows (PowerShell) oder POSIX (bash) — Befehle unten für beide.

## 2. .env-Werte (ohne Secrets)

Für die Demo werden **keine** echten Schlüssel benötigt. Vorlagen kopieren:

- `backend/.env` (aus `backend/.env.example`) — für die Demo relevant:
  ```env
  AGENT_FAKE_PROVIDER=true
  WEB_RESEARCH_ENABLED=true
  WEB_RESEARCH_FAKE_PROVIDER=true
  DEMO_DATA_ENABLED=true
  AI_EVAL_MODE=off
  # Provider-Keys bleiben leer — reale Routen sind dann schlicht nicht verfügbar (kein Crash):
  OPENAI_API_KEY=
  ANTHROPIC_API_KEY=
  FIRECRAWL_API_KEY=
  ```
- `.env.local` (Repo-Wurzel, aus `.env.example`):
  ```env
  APP_BACKEND_MODE=live
  FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1
  ```

Provider-Keys gehören **ausschliesslich** in `backend/.env` (Server), niemals in
eine `NEXT_PUBLIC_*`-Variable.

## 3. Startbefehle (frische Demo-DB)

### PowerShell (Windows)

```powershell
# 1) Frische, dedizierte Demo-DB bauen (aus backend/)
cd backend
$env:APP_ENV="development"; $env:DEMO_DATA_ENABLED="true"
$env:DATABASE_URL="sqlite:///./var/demo.db"
New-Item -ItemType Directory -Force .\var | Out-Null
Remove-Item .\var\demo.db -ErrorAction SilentlyContinue
python -m alembic -c alembic.ini upgrade head
python -m app.seed                       # Workspace + Förderprofil + 2 Nutzer
python -m app.demo.seed --reset --evaluation   # deterministischer Demo-Datensatz

# 2) Backend (Terminal 1, aus backend/) — Fake-Provider, SAME DATABASE_URL
$env:DATABASE_URL="sqlite:///./var/demo.db"; $env:APP_ENV="development"
$env:AGENT_FAKE_PROVIDER="true"; $env:WEB_RESEARCH_ENABLED="true"
$env:WEB_RESEARCH_FAKE_PROVIDER="true"; $env:DEMO_DATA_ENABLED="true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) Frontend (Terminal 2, aus Repo-Wurzel) — Live-Modus
$env:APP_BACKEND_MODE="live"; $env:FASTAPI_BRIDGE_URL="http://127.0.0.1:8000/api/v1"
Remove-Item .next -Recurse -Force -ErrorAction SilentlyContinue   # OneDrive-Lock vermeiden
corepack pnpm build; node node_modules/next/dist/bin/next start --port 3000
```

### bash (POSIX)

```bash
cd backend
export APP_ENV=development DEMO_DATA_ENABLED=true DATABASE_URL="sqlite:///./var/demo.db"
mkdir -p var && rm -f var/demo.db
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m app.seed
.venv/bin/python -m app.demo.seed --reset --evaluation
AGENT_FAKE_PROVIDER=true WEB_RESEARCH_ENABLED=true WEB_RESEARCH_FAKE_PROVIDER=true \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
# Repo-Wurzel, zweites Terminal:
rm -rf .next
APP_BACKEND_MODE=live FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1 \
  corepack pnpm build && node node_modules/next/dist/bin/next start --port 3000
```

**Backend und Frontend müssen dieselbe `DATABASE_URL` verwenden.**

Anmeldung (Seed-Nutzer): `anna.keller@example.test` / `changeme-dev-lead`
(Lead/Admin) oder `tobias.frei@example.test` / `changeme-dev-member`.

## 4. Health-Check

- Backend: `GET http://127.0.0.1:8000/api/v1/health` → `200`.
- Frontend: `http://localhost:3000/login` → `200`.
- Nach Login zeigt das Dashboard **nur** die geseedeten Demo-Projekte. Erscheint
  ein altes E2E-/Testprojekt, läuft der Server auf einer verunreinigten DB →
  Schritt 3.1 mit frischer `demo.db` wiederholen.

## 5. Zehnminütiger Demoablauf (Golden Path) mit erwartetem Ergebnis je Schritt

| # | Aktion | Erwartetes Ergebnis |
|---|--------|---------------------|
| 1 | Anmelden (`/login`) | Weiterleitung auf das Dashboard. |
| 2 | Neues Projekt: Titel + Projektidee eingeben **und** ein Innolink-PDF hochladen (`/intake`), Klassifikation «Öffentlich» | Nach «Projekt erstellen und weiter» öffnet sich die Import-Review (`/import`). |
| 3 | Importkandidaten prüfen, «Abstract» übernehmen | 8 Kandidaten sichtbar, unsichere Felder markiert; nach Klick zeigt die Zeile «Übernommen». |
| 4 | Partner ergänzen (`/partner`) | Zwei Partner erscheinen in der Liste. |
| 5 | Budget erfassen (100'000 / 45'000 / 5'000 / 24) und speichern | «Budgetangaben gespeichert.»; die «Formale Vorprüfung» zeigt zweimal «Erfüllt» (50 % Umsetzung + 5 % Cash). |
| 6 | Recherchebrief (`/quellen`, Panel «Öffentliche Recherche»): «Recherchebrief vorschlagen», Pflichtfelder public-safe ergänzen (Anwendungsdomäne, Technologieklasse, Zielkundensegmente, Kompetenzen), «Public-safe Brief freigeben» | «Brief v1 freigegeben» — Queries entstehen nur aus dem geprüften Brief. |
| 7 | Analyse starten (`/quellen`), öffentliche Webrecherche einschalten, geplante Query freigeben, «Demo-Generator für diesen Durchlauf aktivieren» bestätigen, starten | Der Dialog zeigt jede geplante Suchanfrage; Analyse läuft und schliesst ab (Fake-Provider, schnell). |
| 8 | Im Recherche-Panel «Queries erzeugen», die offene Query freigeben, «Freigegebene Queries ausführen» | Ergebnisse erscheinen klar als «Demo» markiert; **kein** «Übernehmen»-Knopf (Demo-Ergebnisse werden nie zu Quellen). «Vergleich erstellen» weist die Evidenzlücke ehrlich aus: kein fabrizierter Marktvergleich ohne echte Webquellen. |
| 9 | Editor öffnen (`/editor`): A2-Vorschlag (Modus «Vorschläge») und A3-Hinweis (Modus «Prüfen» → «Schwächen») ansehen | Vorschlag aus der Analyse sichtbar (nie automatisch übernommen); A3-Hinweis zu unbelegten Aussagen im Feld «Lösung & Innovation». |
| 10 | Ein Feld bearbeiten (Abstract), speichern | «Die erneute Prüfung ist vor der Freigabe erforderlich.» |
| 11 | Qualitätsprüfung (`/review`): «Gesamte Prüfung erneut ausführen» | KI-gestützte Hinweise sichtbar; erneute Prüfung schliesst ab. |
| 12 | Zurück im Editor, Modus «Prüfen» → «Kommentare» → «Abschnitt freigeben» | «Abschnitt freigegeben.» |
| 13 | Innolink-Kopieransicht (`/export` → Tab): Feld kopieren | «Kopiert am …»; die Zwischenablage enthält exakt den Feldtext. |
| 14 | Browser neu laden | Zustand bleibt erhalten: der bearbeitete Abschnitt ist weiterhin im Editor vorhanden. |

> **Hinweis «Prüfen»-Modus:** Die Assistenz-Tabs und die Aktion «Abschnitt
> freigeben» sind bewusst nur im Editor-Modus **«Prüfen»** sichtbar (ruhiger
> Schreibmodus als Default). In den Modi «Bearbeiten»/«Vorschläge» ist das
> Kontextpanel eingeklappt.

## 5a. Funktionaler Import-Pfad (Ebene B — Structured import E2E)

Beweist fachlich, dass ein unfertiger Antrag im **älteren** Innolink-Schema
korrekt ausgelesen wird (Fixture `spike/fixtures/innolink_structured.pdf`,
rein synthetisches Projekt «TERRAFLUX»):

| Schritt | Erwartetes Ergebnis |
|---|---|
| PDF im Intake hochladen | 8 Antragstexte + 15 strukturierte Kandidaten in der Import-Review. |
| Executive Summary | Badge «Leer»; «Übernehmen» deaktiviert — erbt nie Folgeinhalte. |
| «Innovation & Lösung» → Abschnittsdetails | «Altstruktur migriert»: IPR → 4.5.1–4.5.4, alt-4.5 → 4.6; mehrdeutige Altangabe verlangt fachliche Zuordnung. |
| Strukturierte Kandidaten übernehmen (HITL, je Zeile) | Titelkonflikt verlangt «Geprüft überschreiben»; nichts wird still übernommen. |
| `/partner` | 3 Partner (1 Forschungs-, 2 Umsetzungspartner) **ohne** manuelle Neuanlage, Herkunft «Aus PDF übernommen»; Budgetformular vorbefüllt (200'000/105'000/13'000/18), Vorprüfung 2× «Erfüllt». |

Automatisiert als `e2e/import-functional.spec.ts` (Pflichtteil des Gates) und
`backend/tests/test_import_functional_fixture.py`.

## 5b. Review-Truth-Pfad (Statuswahrheit)

Automatisiert als `e2e/review-truth.spec.ts` (Pflichtteil des Gates) +
`backend/tests/test_review_truth.py`:

- «Bearbeitungs- und Prüfstand» zeigt exakt die Zahlen des autoritativen
  Check-Status-Views; **«Nicht geprüft» ist nie grün**.
- Nach einer Feldänderung ist die Prüfung veraltet: 0/9 «Bestanden», Badge
  «Stand veraltet».
- Evidenz-Leiter: «Textstelle gefunden» (exakt verifizierte Fundstelle ohne
  inhaltliches Stützurteil) ist Abdeckung, keine fachliche Stützung.
- Massen-Findings derselben Familie erzeugen EINE gruppierte Hauptaufgabe;
  die Zahl «blockierende Aufgaben» ist auf Review/Export/Dashboard identisch
  (zusätzlich `e2e/status-parity.spec.ts`).

## 6. Fallback bei Firecrawl-/Provider-Ausfall

- **Demo-Default ist der Fake-Provider** (`AGENT_FAKE_PROVIDER=true`,
  `WEB_RESEARCH_FAKE_PROVIDER=true`). Er ist deterministisch, benötigt keine
  Schlüssel und ist in der UI als Test-/Synthetik-Pfad gekennzeichnet. Ein
  externer Provider-Ausfall betrifft die Demo daher nicht.
- Fällt in einem realen Modus ein Provider aus, bleibt der manuelle Ausweg
  erhalten: Quellen lassen sich unter «Quellen» jederzeit per URL oder Datei
  hinzufügen; KI-Vorschläge sind optional und nie Pflicht.
- Reale Provider-Erreichbarkeit lässt sich **separat** und opt-in prüfen (kein
  Teil des Gates, macht nichts rot):
  ```powershell
  $env:RUN_REAL_PROVIDER_SMOKE="true"; $env:AI_EVAL_MODE="real"
  backend\.venv\Scripts\python.exe scripts\run_provider_availability_smoke.py
  ```
  Bericht: `backend/var/evaluation/provider_availability_summary.md`. Ohne
  Opt-in/Keys erscheinen alle Provider als «übersprungen».

## 6a. Opt-in Live-Evaluationen (nie Teil des Gates)

Alle Live-Läufe sind explizit opt-in, machen das Gate nie rot und berichten
nicht Durchgeführtes wörtlich als `not_run` (nie als bestanden):

```powershell
# Provider-Preflight (Ebene E): Key → Erreichbarkeit → Modell-Echo →
# strukturierte Ausgabe → verständliche 429-Klassifikation; ohne Antragsinhalt.
$env:RUN_REAL_PROVIDER_SMOKE = "true"
backend\.venv\Scripts\python.exe scripts\run_provider_preflight.py
# → backend/var/evaluation/provider_preflight.{md,json}

# Live model evaluation (Ebene C): gleicher F1/D0-Eingabetext, gleiche Rubrik,
# OpenAI UND Anthropic über den produktiven Gateway-Pfad + Qualitätsmetriken.
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
backend\.venv\Scripts\python.exe scripts\run_model_quality_eval.py
# → backend/var/evaluation/model_quality_summary.{md,json}
#   (Human-Rubric Nützlichkeit/Struktur/Präzision manuell ergänzen)

# Live Firecrawl evaluation (Ebene D): public-safe Brief-Query durch die
# Query-Firewall (Canaries bleiben aus Query/Log/Audit), dann echte Suche.
$env:RUN_REAL_PROVIDER_SMOKE = "true"
$env:WEB_RESEARCH_ENABLED = "true"; $env:WEB_RESEARCH_FAKE_PROVIDER = "false"
backend\.venv\Scripts\python.exe scripts\run_live_research_smoke.py
# → backend/var/evaluation/live_research_smoke.md (echte URL, nie example.org)

# Rollen-Modell-Evaluation (Model Selection): Kandidatenvergleich je Agentenrolle
# (A1/A2/A3) auf F1/F2 (Dev) + H1 (Holdout), ≥2 Wiederholungen, Blindbogen.
# VORAUSSETZUNGEN: Keys in backend/.env, AGENT_MODEL_*_ID für alle Kandidaten
# gesetzt UND AGENT_MODEL_PRICING_CHF_PER_MILLION mit verifizierten Preisen je
# Modell-ID gefüllt — ohne Preis blockiert das Gateway die Route
# (price_unknown_for_cost_guard); Ceiling-Routen (fable-5, gpt-5.6-sol)
# brauchen zusätzlich AGENT_QUALITY_CEILING_ENABLED=true.
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a1
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a3
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py blind --role a2
# → Blindbogen menschlich ausfüllen (docs/evaluation/blind_rubric_a2.md), dann:
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py ingest --role a2 `
  --scores backend/var/evaluation/role_model_eval/blind/a2/a2_scoring_sheet.csv
# Holdout erst NACH dem Blind-Scoring der Dev-Läufe (identischer Prompt-SHA):
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2 `
  --cases H1 --allow-holdout
# → backend/var/evaluation/role_model_eval/summary.{md,json}
# Kostenloser Probelauf des gesamten Zyklus (keine Keys nötig): «run --fake …»
# — Samples sind unübersehbar als fake_dryrun markiert, nie eine Live-Aussage.
```

## 6b. Supervised live E2E (manuelles Protokoll)

Ein begleiteter Live-Durchlauf (reale Provider) wird nur mit
Owner-Freigabe und ausschliesslich synthetischen/anonymisierten Inhalten
durchgeführt:

1. Preflight (oben) muss für den gewünschten Provider `bestanden` melden.
2. Backend mit `AI_EVAL_MODE=real`, `AGENT_FAKE_PROVIDER=false` starten;
   Projekt mit Herkunft «synthetisch» anlegen. Die Capabilities zeigen dann
   «KI-Unterstützung für Evaluationsfälle verfügbar»; ist Live konfiguriert,
   aber kein Key vorhanden, zeigt die UI ausdrücklich den Zustand
   `live_unavailable` — es erscheint **nie** ein Demo-Ergebnis als Ersatz.
3. Die Modellrouten je Rolle sind die im
   [`model-selection-report`](../evaluation/model-selection-report.md)
   dokumentierten Sieger (gesetzt über `AGENT_MODEL_*_ID` in `backend/.env`);
   A3 läuft über einen anderen Provider als A2 — die Warnung
   `same_provider_a2_a3` in «Technische Details» muss fehlen.
4. Golden-Path-Schritte 1–14 begleitet durchführen; jede Query-Freigabe und
   jede Übernahme bleibt menschlich. Externe Störungen führen zu einem ehrlich
   ausgewiesenen `partial_live` mit Begründung — nie zu einem stillen Fallback.
5. **Zweimal-Regel:** ein vollständiger Lauf auf Demo-Projekt 1 **plus** ein
   gezielter Wiederholungslauf der kritischen Provider-/Research-Schritte
   (Preflight → A1 → Query-Freigabe → Firecrawl → Quelle übernehmen → A2 → A3)
   auf Demo-Projekt 2 — oder alternativ zwei vollständige Läufe.
6. Evidenz archivieren unter `backend/var/evaluation/supervised_live/<datum>/`:
   Technical-Evidence-Export (Provider, Modell, Skill, Tokens, Kosten, Latenz,
   Quellen), Preflight-Artefakte, Run-/Projekt-IDs.
7. Ergebnis (Datum, Provider, tatsächliche Modell-IDs aus dem Technical
   Evidence, Beobachtungen) im Acceptance-Report unter «Supervised live E2E»
   eintragen; ohne Durchführung bleibt dort `not_run` stehen.

## 6c. Private SEDATE-Acceptance (lokal, gitignoriert)

```powershell
backend\.venv\Scripts\python.exe scripts\run_private_innolink_acceptance.py
```

Prüft das lokale echte Innolink-PDF (`private_inputs/`, gitignoriert) mit der
produktiven Mapping-/Regel-Pipeline; Ausgabe enthält nur Feldnamen, Zählwerte
und Pass/Fail — keine Antragstexte, keine PII.

## 7. Vorbereiteter synthetischer Backup-Run

Der Seed `python -m app.demo.seed --reset --evaluation` legt zwei vollständige,
synthetische Demo-Projekte mit abgeschlossenem deterministischem Lauf an
(siehe [`Demo_Walkthrough.md`](Demo_Walkthrough.md) und
[`Demo_Data_Dictionary.md`](Demo_Data_Dictionary.md)). Falls die Live-Vorführung
klemmt, kann direkt eines dieser Projekte gezeigt werden (Dashboard → Projekt →
`/review` → `/export`). Zwischen zwei Teilnehmenden den Datensatz mit demselben
Befehl zurücksetzen.

## 8. Bekannte Limitationen

- **PDF-Titel wird nie automatisch übernommen:** Der Innolink-Export führt den
  Haupttitel ohne Label; das Feld `INTRO.APP.NAME` bleibt manuell (dokumentiert
  in [`../evaluation/pdf-import-gate-report.md`](../evaluation/pdf-import-gate-report.md)).
- **PDF-Import-Quote:** Auf dem echten Portal-Export sind 5 von 8 Feldern
  automatisch nutzbar; 2 leere Felder werden korrekt als «unsicher» markiert,
  nie falsch befüllt (n = 1 Export gemessen).
- **OneDrive-Sync:** Ein stale `.next`-Verzeichnis kann beim Build ein `EPERM`
  (Datei-Lock) auslösen — kein Programm-Hänger. Abhilfe: `.next` vor dem Build
  löschen (in den `verify_all`-Skripten automatisiert) oder Sync kurz pausieren.
- **SQLite Single-Writer:** Die E2E-/Demo-DB ist SQLite; parallele Läufe werden
  bewusst mit `--workers=1` serialisiert.
- **Kein Portal-Writeback:** Die App bereitet Feldtexte nur zum manuellen
  Kopieren vor; es gibt keine automatische Innolink-Übermittlung.
