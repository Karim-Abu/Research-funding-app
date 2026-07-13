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
| 6 | Analyse starten (`/quellen`), öffentliche Webrecherche einschalten | Der Dialog zeigt jede geplante Suchanfrage. |
| 7 | Sichere Research-Queries genehmigen (2 freigeben, 1 ablehnen), Cloud-KI bestätigen, starten | Analyse läuft und schliesst ab (Fake-Provider, schnell). |
| 8 | Öffentliche Recherche durchführen, ein Ergebnis als Quelle übernehmen; Markt-/Konkurrenzvergleich erstellen | «Als Quelle gespeichert»; Vergleichstabelle erscheint; eine Zeile «Übernehmen» → «Inhaltlich geprüft». |
| 9 | Editor öffnen (`/editor`): A2-Vorschlag (KI-Assist) und A3-Hinweis (Modus «Prüfen» → «Schwächen») ansehen | Vorschlag aus der Analyse sichtbar (nie automatisch übernommen); A3-Hinweis zu unbelegten Aussagen im Feld «Lösung & Innovation». |
| 10 | Ein Feld bearbeiten (Abstract), speichern | «Die erneute Prüfung ist vor der Freigabe erforderlich.» |
| 11 | Qualitätsprüfung (`/review`): «Gesamte Prüfung erneut ausführen» | KI-gestützte Hinweise sichtbar; erneute Prüfung schliesst ab. |
| 12 | Zurück im Editor, Modus «Prüfen» → «Kommentare» → «Abschnitt freigeben» | «Abschnitt freigegeben.» |
| 13 | Innolink-Kopieransicht (`/export` → Tab): Feld kopieren | «Kopiert am …»; die Zwischenablage enthält exakt den Feldtext. |
| 14 | Browser neu laden | Zustand bleibt erhalten: der bearbeitete Abschnitt ist weiterhin im Editor vorhanden. |

> **Hinweis «Prüfen»-Modus:** Die Assistenz-Tabs und die Aktion «Abschnitt
> freigeben» sind bewusst nur im Editor-Modus **«Prüfen»** sichtbar (ruhiger
> Schreibmodus als Default). In den Modi «Bearbeiten»/«KI-Assist» ist das
> Kontextpanel eingeklappt.

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
