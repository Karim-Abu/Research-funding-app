# Milestone 10 — one-command verification (Windows PowerShell; fake providers only).
# Backend migration check + pytest; frontend vitest/lint/tsc/build; then a throwaway
# migrated+seeded DB with backend + frontend started, Playwright + API smoke + the
# EvaluationRunSummary, with explicit teardown in a finally block.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# --- package manager detection (corr 1): corepack pnpm -> pnpm -> npm ---------
function Test-Cmd($cmd) { try { & $cmd --version *> $null; return $true } catch { return $false } }
if (Test-Cmd "corepack") { $PM = "corepack pnpm"; $PMKIND = "pnpm" }
elseif (Test-Cmd "pnpm") { $PM = "pnpm"; $PMKIND = "pnpm" }
else { $PM = "npm"; $PMKIND = "npm" }
function PmRun($script)  { if ($PMKIND -eq "pnpm") { iex "$PM $script" } else { npm run $script } }
function PmExec($cmdline){ if ($PMKIND -eq "pnpm") { iex "$PM exec $cmdline" } else { iex "npx $cmdline" } }

$env:E2E_EMAIL    = if ($env:E2E_EMAIL)    { $env:E2E_EMAIL }    else { "anna.keller@example.test" }
$env:E2E_PASSWORD = if ($env:E2E_PASSWORD) { $env:E2E_PASSWORD } else { "changeme-dev-lead" }

$R = @{ backend="skip"; migration="skip"; frontend="skip"; quality="skip";
        playwright="skip"; apismoke="skip"; testdata="skip"; legacyguard="skip";
        evalpath="-" }
$e2eDb = Join-Path $backend "var\verify_e2e.db"

function Stop-Servers {
    foreach ($port in 3000, 8000) {
        try {
            $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            foreach ($x in $c) { Stop-Process -Id $x.OwningProcess -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
}

Write-Host "== M10 verification ==  package manager: $PM"
try {
    # --- Testdaten-Marker-Check (R0.4) ---
    Write-Host "-- testdata marker check --"
    & $py (Join-Path $root "scripts\check_testdata_markers.py") --root $root
    $R.testdata = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    # --- Legacy-Status-Guard (R1.4) ---
    Write-Host "-- legacy status guard --"
    & $py (Join-Path $root "scripts\check_legacy_status_paths.py") --root $root
    $R.legacyguard = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    # --- Backend: migration check + pytest ---
    Write-Host "-- backend: fresh-DB migration check --"
    $migDb = Join-Path $backend "var\verify_migrate.db"
    Remove-Item $migDb -ErrorAction SilentlyContinue
    Push-Location $backend
    $env:DATABASE_URL = "sqlite:///./var/verify_migrate.db"; $env:APP_ENV = "test"
    & $py -m alembic -c alembic.ini upgrade head
    $R.migration = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Remove-Item $migDb -ErrorAction SilentlyContinue

    Write-Host "-- backend: pytest --"
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    & $py -m pytest -q -p no:warnings
    $R.backend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Pop-Location

    # --- Frontend: vitest + lint + tsc + build ---
    Write-Host "-- frontend: vitest --"
    PmRun "test"; $R.frontend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Write-Host "-- frontend: lint + tsc + build --"
    $R.quality = "pass"
    PmRun "lint";           if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    PmExec "tsc --noEmit";  if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    PmRun "build";          if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }

    # --- E2E + smokes ---
    Write-Host "-- e2e + smokes: preparing throwaway DB --"
    Remove-Item $e2eDb -ErrorAction SilentlyContinue
    Push-Location $backend
    $env:DATABASE_URL = "sqlite:///./var/verify_e2e.db"; $env:APP_ENV = "development"
    $env:DEMO_DATA_ENABLED = "true"
    & $py -m alembic -c alembic.ini upgrade head
    & $py -m app.demo.seed --reset --evaluation
    Pop-Location

    Write-Host "-- starting backend + frontend --"
    # Shared env so the servers AND Playwright's demo-seed subprocess use the SAME DB
    # (set only now, after the backend pytest section which uses its own conftest DB).
    $env:DATABASE_URL = "sqlite:///./var/verify_e2e.db"; $env:APP_ENV = "development"
    $env:AGENT_FAKE_PROVIDER = "true"; $env:WEB_RESEARCH_ENABLED = "true"
    $env:WEB_RESEARCH_FAKE_PROVIDER = "true"; $env:DEMO_DATA_ENABLED = "true"
    $beEnv = "`$env:DATABASE_URL='sqlite:///./var/verify_e2e.db';`$env:APP_ENV='development';" +
             "`$env:AGENT_FAKE_PROVIDER='true';`$env:WEB_RESEARCH_ENABLED='true';" +
             "`$env:WEB_RESEARCH_FAKE_PROVIDER='true';`$env:DEMO_DATA_ENABLED='true';" +
             "& '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList "-NoProfile","-Command",$beEnv -WorkingDirectory $backend -WindowStyle Hidden
    $feEnv = "`$env:APP_BACKEND_MODE='live';`$env:FASTAPI_BRIDGE_URL='http://127.0.0.1:8000/api/v1';" +
             "node node_modules/next/dist/bin/next start --port 3000"
    Start-Process powershell -ArgumentList "-NoProfile","-Command",$feEnv -WorkingDirectory $root -WindowStyle Hidden

    Write-Host "-- waiting for readiness --"
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $b = (Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 3).StatusCode
            $f = (Invoke-WebRequest "http://127.0.0.1:3000/login" -UseBasicParsing -TimeoutSec 3).StatusCode
            if ($b -eq 200 -and $f -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }

    if ($ready) {
        Write-Host "-- Playwright --"
        PmExec "playwright test --workers=1"
        $R.playwright = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- API smoke --"
        & $py (Join-Path $root "scripts\smoke_api.py")
        $R.apismoke = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- EvaluationRunSummary --"
        Push-Location $backend
        $env:DATABASE_URL = "sqlite:///./var/verify_e2e.db"; $env:APP_ENV = "development"
        # Re-seed the eval dataset (demo-dataset.spec may have plain-reset it), then export.
        & $py -m app.demo.seed --reset --evaluation
        & $py -m app.evaluation
        if ($LASTEXITCODE -eq 0) { $R.evalpath = (Join-Path $backend "var\evaluation\EvaluationRunSummary.json") }
        Pop-Location
    } else {
        $R.playwright = "FAIL(servers not ready)"; $R.apismoke = "FAIL(servers not ready)"
    }
}
finally {
    Stop-Servers
    Remove-Item $e2eDb -ErrorAction SilentlyContinue
}

$exportR = $R.backend; $norawR = $R.backend
Write-Host ""
Write-Host "================ M10 VERIFICATION SUMMARY ================"
Write-Host "backend tests            : $($R.backend)"
Write-Host "migration                : $($R.migration)"
Write-Host "frontend tests (vitest)  : $($R.frontend)"
Write-Host "build/typecheck/lint     : $($R.quality)"
Write-Host "Playwright               : $($R.playwright)"
Write-Host "API smoke                : $($R.apismoke)"
Write-Host "export smoke             : $exportR   (test_m10_smoke.py::test_export_all_types)"
Write-Host "no-raw-log               : $norawR   (test_m10_smoke.py::test_no_raw_log)"
Write-Host "testdata markers         : $($R.testdata)   (scripts/check_testdata_markers.py)"
Write-Host "legacy status guard      : $($R.legacyguard)   (scripts/check_legacy_status_paths.py)"
Write-Host "evaluation summary       : $($R.evalpath)"
Write-Host "========================================================="

$fail = @($R.backend, $R.migration, $R.frontend, $R.quality, $R.playwright, $R.apismoke, $R.testdata, $R.legacyguard) |
        Where-Object { $_ -like "FAIL*" }
if ($fail.Count -gt 0) { exit 1 }
Write-Host "ALL GREEN"
