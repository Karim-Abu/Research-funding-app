# Innosuisse-Antrag — Research-Funding-App

Feldbasierter Antragsassistent für Innosuisse-Innovationsprojekte. Ein
nichttechnischer Nutzer gelangt von der Projektidee oder einem vorhandenen
Innolink-PDF über Partner, Budget, freigegebene Recherche und KI-Analyse zu
feldbezogenen, editierbaren und kopierbaren Innolink-Textvorschlägen. Das System
**unterstützt die menschliche Prüfung** — es entscheidet weder über
Förderfähigkeit noch reicht es automatisch ein.

## Für Aussenstehende in 60 Sekunden

Dieses Repository zeigt eine vollständige, praxisnahe Produktumsetzung:

- Endnutzer-orientiertes Frontend mit klaren Formular- und Review-Flows
- API-zentriertes Backend mit reproduzierbarem Demo-Setup
- Nachvollziehbares Qualitätsgate aus Tests, Build und End-to-End-Demo

Wenn Sie das Projekt schnell beurteilen möchten:

1. Produktüberblick in `docs/SCHNELLSTART.md`
2. Bedienlogik und Nutzerfluss in `docs/BEDIENUNGSANLEITUNG.md`
3. Reproduzierbare Demo in `docs/demo/demo-runbook.md`

- Frontend: Next.js / TypeScript (Repo-Wurzel).
- Backend: FastAPI / SQLAlchemy (`backend/`), SQLite als Standard-DB.
- Verbindliche Projektregeln: [`.claude/CLAUDEX.md`](.claude/CLAUDEX.md).
- Zusammenarbeit: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Security-Meldungen: [`SECURITY.md`](SECURITY.md).

> **Sie wollen die App nur installieren und bedienen?** Die
> [Kurzanleitung `docs/SCHNELLSTART.md`](docs/SCHNELLSTART.md) führt ohne
> Vorkenntnisse durch Installation, Start und einen ersten Rundgang. Die
> vollständige Referenz ist die
> [Bedienungsanleitung](docs/BEDIENUNGSANLEITUNG.md). Der folgende Abschnitt
> ist die technische Kurzfassung.

## Schnellstart auf einem frischen Rechner

### 1. Voraussetzungen

- **Node** ≥ 20 mit corepack (`corepack enable`) → `pnpm`.
- **Python** ≥ 3.12.

### 2. Abhängigkeiten installieren

```bash
# Frontend (Repo-Wurzel)
corepack pnpm install

# Backend-venv + Abhängigkeiten
python -m venv backend/.venv
# Windows:
backend/.venv/Scripts/pip install -r backend/requirements.txt
# POSIX:
backend/.venv/bin/pip install -r backend/requirements.txt
```

### 3. Konfiguration (ohne Secrets)

```bash
cp backend/.env.demo.example backend/.env   # fertige Demo-Werte, Keys leer
cp .env.example .env.local                  # enthält APP_BACKEND_MODE + FASTAPI_BRIDGE_URL
```

Beide Vorlagen sind vollständig; für den Demo-Betrieb ist nichts zu editieren.
`.env.local` (Repo-Wurzel) enthält:

```env
APP_BACKEND_MODE=live
FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1
```

Ohne `APP_BACKEND_MODE=live` läuft das Frontend **ohne Fehlermeldung** im
Mock-Modus (Badge «Demo-Daten · keine echten Antragsdaten» in der Topbar).

`backend/.env.demo.example` setzt `AGENT_FAKE_PROVIDER=true`,
`WEB_RESEARCH_FAKE_PROVIDER=true`, `DEMO_DATA_ENABLED=true`, `AI_EVAL_MODE=off`
und `DATABASE_URL=sqlite:///./var/demo.db`. Die allgemeine Vorlage
`backend/.env.example` ist bewusst fail-closed (alle diese Schalter `false`) und
damit **kein** Demo-Setup — sie ist die Basis für eine bewusste Live-Einrichtung.

Provider-Keys gehören **ausschliesslich** in `backend/.env` (Server), nie in eine
`NEXT_PUBLIC_*`-Variable. Ohne Keys sind reale Provider-Routen schlicht nicht
verfügbar (kein Crash, kein stiller Fallback auf den Demo-Generator).

### 4. Datenbank: Migration + Seed

```bash
cd backend
# Windows PowerShell:
$env:APP_ENV="development"; $env:DEMO_DATA_ENABLED="true"; $env:DATABASE_URL="sqlite:///./var/demo.db"
# POSIX:  export APP_ENV=development DEMO_DATA_ENABLED=true DATABASE_URL="sqlite:///./var/demo.db"

python -m alembic -c alembic.ini upgrade head     # Schema (kein create_all zur Laufzeit)
python -m app.seed                                # Workspace + Förderprofil + 2 Nutzer
python -m app.demo.seed --reset --evaluation      # deterministischer Demo-Datensatz
```

Seed-Nutzer (Dev-Defaults, in jeder echten Umgebung überschreiben):

| Rolle | E-Mail | Passwort |
|-------|--------|----------|
| Lead/Admin | `anna.keller@example.test` | `changeme-dev-lead` |
| Member | `tobias.frei@example.test` | `changeme-dev-member` |

### 5. Live-Modus starten (zwei Terminals)

```powershell
# Terminal 1 — Backend (aus backend/), SAME DATABASE_URL, Fake-Provider
$env:DATABASE_URL="sqlite:///./var/demo.db"; $env:APP_ENV="development"
$env:AGENT_FAKE_PROVIDER="true"; $env:WEB_RESEARCH_ENABLED="true"
$env:WEB_RESEARCH_FAKE_PROVIDER="true"; $env:DEMO_DATA_ENABLED="true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend (aus Repo-Wurzel), Live-Modus
$env:APP_BACKEND_MODE="live"; $env:FASTAPI_BRIDGE_URL="http://127.0.0.1:8000/api/v1"
Remove-Item .next -Recurse -Force -ErrorAction SilentlyContinue   # OneDrive-Lock vermeiden
corepack pnpm build; node node_modules/next/dist/bin/next start --port 3000
```

App: <http://localhost:3000> · Backend-Health: <http://127.0.0.1:8000/api/v1/health>.
**Backend und Frontend müssen dieselbe `DATABASE_URL` nutzen.** Für die
schnelle Entwicklung genügt `corepack pnpm dev` statt build/start.

## Demo

[Kurzanleitung für Aussenstehende](docs/SCHNELLSTART.md) ·
[Bedienungsanleitung](docs/BEDIENUNGSANLEITUNG.md) ·
[Verifikationsbericht](docs/VERIFIKATIONSBERICHT_BEDIENUNGSANLEITUNG.md) ·
[GitHub-Profilvorlage (DE)](docs/GITHUB_PROFIL_VORLAGE.md)

Die reproduzierbare End-to-End-Demo (Golden Path) ist in
[`docs/demo/demo-runbook.md`](docs/demo/demo-runbook.md) beschrieben; die
ausführbare Fassung ist [`e2e/golden-path.spec.ts`](e2e/golden-path.spec.ts).
Abnahmestatus: [`docs/demo/demo-acceptance-report.md`](docs/demo/demo-acceptance-report.md).

## Tests & Abschlussgate

```bash
# Backend
cd backend && .venv/Scripts/python.exe -m pytest -q      # POSIX: .venv/bin/python

# Frontend
corepack pnpm test          # vitest
corepack pnpm lint
corepack pnpm exec tsc --noEmit
corepack pnpm build

# End-to-End (Server müssen laufen, s. oben)
corepack pnpm exec playwright test --workers=1
```

Ein-Kommando-Gate (frische DB, startet Server, Playwright inkl. Golden-Path-
Doppellauf, API-Smoke, Evaluation, Teardown):

```powershell
.\scripts\verify_all.ps1     # Windows
```
```bash
scripts/verify_all.sh        # POSIX
```

Das Gate endet mit `ALL GREEN`, wenn alle Prüfungen bestehen.

Reale Provider-Erreichbarkeit (OpenAI/Anthropic/Firecrawl) ist **opt-in** und
nicht Teil des Gates (ein Ausfall macht nichts rot):

```powershell
$env:RUN_REAL_PROVIDER_SMOKE="true"; $env:AI_EVAL_MODE="real"
backend\.venv\Scripts\python.exe scripts\run_provider_availability_smoke.py
```

## Bekannte Limitationen

- **OneDrive-Sync** kann ein stale `.next`-Verzeichnis sperren (`EPERM` beim
  Build — kein Hänger). Abhilfe: `.next` vor dem Build löschen (in den
  `verify_all`-Skripten automatisiert) oder Sync kurz pausieren.
- **PDF-Import:** layoutabhängig und unvollständig; der Innolink-Export führt den
  Haupttitel ohne Label → das Feld bleibt manuell. Gemessene Erkennungsquoten:
  [`docs/evaluation/pdf-import-gate-report.md`](docs/evaluation/pdf-import-gate-report.md).
- **Kein Portal-Writeback:** Feldtexte werden nur zum manuellen Kopieren
  vorbereitet; keine automatische Innolink-Übermittlung.

## Verzeichnisstruktur (Auszug)

- `app/`, `components/`, `lib/` — Next.js-Frontend.
- `e2e/` — Playwright-Specs (Golden Path, UI-Zustände, Milestones).
- `backend/app/` — FastAPI-Backend (Import, Agents, Review, Research, Exports).
- `scripts/` — `verify_all.*`, Smokes, Guards.
- `docs/` — Repair-Roadmap, Evaluation, Demo.
