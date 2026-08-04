# PoC-Demo-Start (opt-in) — baut eine frische Demo-DB mit 4 kuratierten
# Demo-Projekten (A 72% blockiert, B 45% blockiert, C 25% Analyse starten,
# D 12% Quellen hochladen) und startet das Backend darauf.
#
# Session-only Umgebungsvariablen: backend\.env und backend\app.db bleiben
# unveraendert (OS-Env hat Pydantic-Vorrang vor .env). Ctrl+C beendet das
# Backend; die Overrides sterben mit diesem Prozess.
#
# Frontend separat starten (zweites Terminal, Repo-Wurzel): npm run dev
#
# -Evaluation: zusaetzlich die M10-Evaluationsanreicherung seeden (veraendert
# Projekt A und damit die Dashboard-Zahlen; Standard ist der reine Demo-Seed).

param([switch]$Evaluation)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "FEHLER: backend\.venv fehlt ($py) — bitte zuerst das Backend-venv einrichten."
    exit 1
}
$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host ("FEHLER: Port 8000 ist belegt (PID {0}) — laufendes Backend zuerst beenden." -f $busy[0].OwningProcess)
    exit 1
}

# Session-Env: gilt nur fuer diesen Prozess. Neutralisiert den Live-Modus aus
# backend\.env — der Demo-Seed laeuft deterministisch mit Fake-Providern,
# es finden keine externen Aufrufe statt.
$env:APP_ENV = "development"
$env:DEMO_DATA_ENABLED = "true"
$env:DATABASE_URL = "sqlite:///./var/demo.db"
$env:AGENT_FAKE_PROVIDER = "true"
$env:WEB_RESEARCH_ENABLED = "true"
$env:WEB_RESEARCH_FAKE_PROVIDER = "true"
$env:AI_EVAL_MODE = "off"

Push-Location $backend
try {
    New-Item -ItemType Directory -Force -Path .\var | Out-Null
    if (Test-Path .\var\demo.db) { Remove-Item .\var\demo.db -Force }

    & $py -m alembic -c alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER: Migration fehlgeschlagen."; exit 1 }
    & $py -m app.seed
    if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER: Basis-Seed fehlgeschlagen."; exit 1 }
    if ($Evaluation) {
        & $py -m app.demo.seed --reset --evaluation
    } else {
        & $py -m app.demo.seed --reset
    }
    if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER: Demo-Seed fehlgeschlagen."; exit 1 }

    Write-Host ""
    Write-Host "Demo-DB bereit: backend\var\demo.db (4 Demo-Projekte)."
    Write-Host "Frontend im zweiten Terminal starten (Repo-Wurzel): npm run dev"
    Write-Host "Login: anna.keller@example.test / changeme-dev-lead"
    Write-Host "Beenden: Ctrl+C — backend\.env und backend\app.db wurden nicht veraendert."
    Write-Host ""
    & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
