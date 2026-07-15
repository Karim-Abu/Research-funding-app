# Abschlussgate — one-command verification (Windows PowerShell; deterministisch,
# NUR Fake-Provider).
#
# Pflichtpfade (machen das Gate rot): Backend-Tests, Migration, Frontend-Tests,
# lint/tsc/build, technischer Playwright-Pfad (Suite + Golden Path 2. Lauf),
# funktionaler Import-Pfad, Review-Truth-Pfad, DOCX-Render-Smoke, API-Smoke,
# Testdaten-Marker, Legacy-Status-Guard.
#
# Opt-in-Kategorien (NIE Teil dieses Gates; nur Statusbericht): Live model
# evaluation, Live Firecrawl evaluation, Provider-Preflight, Supervised live E2E.
# Es gibt bewusst KEINE Pauschalaussage «ALL GREEN».

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
        playwright="skip"; golden2="skip"; functional="skip"; reviewtruth="skip";
        docx="skip"; apismoke="skip"; testdata="skip"; legacyguard="skip"; evalpath="-" }
$e2eDb = Join-Path $backend "var\verify_e2e.db"

function Stop-Servers {
    foreach ($port in 3000, 8000) {
        try {
            $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            foreach ($x in $c) { Stop-Process -Id $x.OwningProcess -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
}

Write-Host "== Abschlussgate (deterministisch, Fake-Provider) ==  package manager: $PM"
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

    Write-Host "-- backend: pytest (ohne DOCX-Render-Smoke — eigene Gate-Zeile) --"
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    & $py -m pytest -q -p no:warnings --ignore=tests/test_docx_render_smoke.py
    $R.backend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    Write-Host "-- DOCX render smoke (benötigt Microsoft Word) --"
    & $py -m pytest tests/test_docx_render_smoke.py -q -p no:warnings
    $R.docx = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Pop-Location

    # --- Frontend: vitest + lint + tsc + build ---
    Write-Host "-- frontend: vitest --"
    PmRun "test"; $R.frontend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Write-Host "-- frontend: lint + tsc + build --"
    $R.quality = "pass"
    PmRun "lint";           if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    PmExec "tsc --noEmit";  if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    # OneDrive-Sync kann eine stale .next sperren (EPERM beim unlink) → vor dem
    # Build best-effort räumen. Kein Hänger; nur ein Lock auf Altbeständen.
    try { Remove-Item (Join-Path $root ".next") -Recurse -Force -ErrorAction Stop } catch {}
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
        Write-Host "-- Playwright (technischer Pfad, gesamte Suite) --"
        PmExec "playwright test --workers=1"
        $R.playwright = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        # Akzeptanz: der technische E2E läuft ZWEIMAL hintereinander auf der
        # frischen Demo-DB (die Suite oben ist Lauf 1; hier folgt Lauf 2).
        # Eindeutige Projekttitel machen den zweiten Lauf kollisionsfrei.
        Write-Host "-- technischer E2E (2. Lauf, frische Demo-DB) --"
        PmExec "playwright test e2e/golden-path.spec.ts --workers=1"
        $R.golden2 = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- funktionaler Import-Pfad (gezielter Lauf) --"
        PmExec "playwright test e2e/import-functional.spec.ts --workers=1"
        $R.functional = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- Review-Truth-Pfad (gezielter Lauf) --"
        PmExec "playwright test e2e/review-truth.spec.ts --workers=1"
        $R.reviewtruth = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
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
        $R.playwright = "FAIL(servers not ready)"; $R.golden2 = "FAIL(servers not ready)"
        $R.functional = "FAIL(servers not ready)"; $R.reviewtruth = "FAIL(servers not ready)"
        $R.apismoke = "FAIL(servers not ready)"
    }
}
finally {
    Stop-Servers
    Remove-Item $e2eDb -ErrorAction SilentlyContinue
}

$exportR = $R.backend; $norawR = $R.backend

# --- Opt-in-Kategorien: Status aus vorhandenen Artefakten (nie Gate-relevant) --
$mqJson = Join-Path $backend "var\evaluation\model_quality_summary.json"
if (Test-Path $mqJson) {
    try { $mqStatus = (Get-Content $mqJson -Raw -Encoding utf8 | ConvertFrom-Json).status }
    catch { $mqStatus = "Artefakt vorhanden" }
    $catModel = "$mqStatus — $mqJson"
} else {
    $catModel = "not_run (opt-in — scripts/run_model_quality_eval.py)"
}
$lrMd = Join-Path $backend "var\evaluation\live_research_smoke.md"
if (Test-Path $lrMd) {
    $lrLine = (Select-String -Path $lrMd -Pattern "Status: (\S+)" | Select-Object -First 1)
    $lrStatus = if ($lrLine) { $lrLine.Matches[0].Groups[1].Value.TrimEnd('*') } else { "Artefakt vorhanden" }
    $catFirecrawl = "$lrStatus — $lrMd"
} else {
    $catFirecrawl = "not_run (opt-in — scripts/run_live_research_smoke.py)"
}
$pfMd = Join-Path $backend "var\evaluation\provider_preflight.md"
$catPreflight = if (Test-Path $pfMd) { "Artefakt vorhanden — $pfMd" }
                else { "not_run (opt-in — scripts/run_provider_preflight.py)" }

$catTech   = if ($R.playwright -eq "pass" -and $R.golden2 -eq "pass") { "pass" } else { "FAIL" }
$catImport = if ($R.functional -eq "pass") { "pass" } else { "FAIL" }

Write-Host ""
Write-Host "=========== ABNAHME — FÜNF GETRENNTE KATEGORIEN ==========="
Write-Host "1. Technical deterministic E2E : $catTech   (Fake-Provider; Suite + 2. Lauf)"
Write-Host "2. Structured import E2E       : $catImport   (e2e/import-functional.spec.ts)"
Write-Host "3. Live model evaluation       : $catModel"
Write-Host "4. Live Firecrawl evaluation   : $catFirecrawl"
Write-Host "5. Supervised live E2E         : not_run (manuell — docs/demo/demo-runbook.md)"
Write-Host "Provider-Preflight (Ebene E)   : $catPreflight"
Write-Host "Private SEDATE-Acceptance      : manuell — scripts/run_private_innolink_acceptance.py"
Write-Host ""
Write-Host "=============== TECHNISCHE GATE-DETAILS ==================="
Write-Host "backend tests            : $($R.backend)"
Write-Host "migration                : $($R.migration)"
Write-Host "frontend tests (vitest)  : $($R.frontend)"
Write-Host "build/typecheck/lint     : $($R.quality)"
Write-Host "Playwright (Suite)       : $($R.playwright)"
Write-Host "technischer E2E (2. Lauf): $($R.golden2)   (e2e/golden-path.spec.ts)"
Write-Host "funktionaler Import      : $($R.functional)   (e2e/import-functional.spec.ts)"
Write-Host "review truth             : $($R.reviewtruth)   (e2e/review-truth.spec.ts)"
Write-Host "docx render smoke        : $($R.docx)   (tests/test_docx_render_smoke.py)"
Write-Host "API smoke                : $($R.apismoke)"
Write-Host "export smoke             : $exportR   (test_m10_smoke.py::test_export_all_types)"
Write-Host "no-raw-log               : $norawR   (test_m10_smoke.py::test_no_raw_log)"
Write-Host "testdata markers         : $($R.testdata)   (scripts/check_testdata_markers.py)"
Write-Host "legacy status guard      : $($R.legacyguard)   (scripts/check_legacy_status_paths.py)"
Write-Host "evaluation summary       : $($R.evalpath)"
Write-Host "==========================================================="

$fail = @($R.backend, $R.migration, $R.frontend, $R.quality, $R.playwright,
          $R.golden2, $R.functional, $R.reviewtruth, $R.docx, $R.apismoke,
          $R.testdata, $R.legacyguard) |
        Where-Object { $_ -like "FAIL*" }
if ($fail.Count -gt 0) {
    Write-Host "TECHNISCHES GATE (deterministisch, Fake-Provider): ROT"
    exit 1
}
Write-Host "TECHNISCHES GATE (deterministisch, Fake-Provider): GRÜN — Live-Kategorien siehe oben (not_run heisst nicht bestanden)."
