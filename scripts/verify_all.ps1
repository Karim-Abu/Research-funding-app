# Abschlussgate — one-command verification (Windows PowerShell; deterministisch,
# NUR Fake-Provider).
#
# Pflichtpfade (machen das Gate rot): Backend-Tests, Migration, Frontend-Tests,
# lint/tsc/build, technischer Playwright-Pfad (Suite + Golden Path 2. Lauf),
# funktionaler Import-Pfad, Review-Truth-Pfad, DOCX-Render-Smoke, API-Smoke,
# Testdaten-Marker, Legacy-Status-Guard.
#
# Opt-in-Kategorien (NIE Teil dieses Gates; nur Statusbericht): Live model
# evaluation, Model selection (scripts/run_role_model_eval.py), Live Firecrawl
# evaluation, Provider-Preflight, Supervised live E2E.
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

# Eigene Schluessel fuer Export-Smoke und No-Raw-Logging: beide werden separat
# ausgefuehrt und duerfen nicht laenger den Status der gesamten Backend-Suite
# spiegeln (frueher `$exportR = $R.backend`).
$R = @{ backend="skip"; migration="skip"; frontend="skip"; quality="skip";
        playwright="skip"; golden2="skip"; functional="skip"; reviewtruth="skip";
        docx="skip"; apismoke="skip"; testdata="skip"; legacyguard="skip";
        export="skip"; norawlog="skip"; evalpath="-" }
$e2eDb = Join-Path $backend "var\verify_e2e.db"

$pytestRunToken = '{0}-{1}' -f $PID, ([guid]::NewGuid().ToString('N').Substring(0, 8))
$pytestBase = '.pytest_cache\verify-all-' + $pytestRunToken
$pytestDocxBase = '.pytest_cache\verify-all-docx-' + $pytestRunToken
$pytestSmokeBase = '.pytest_cache\verify-all-smoke-' + $pytestRunToken

# --- Laufartefakte -----------------------------------------------------------
# Das Gate schrieb bisher nichts auf die Platte; jede "GRUEN"-Aussage war eine
# Abschrift. Jeder Lauf legt jetzt ein eigenes Verzeichnis mit Metadaten,
# JUnit-Dateien, Logs und einem maschinenlesbaren Gesamtergebnis an.
if (-not $env:VERIFY_RUN_ID) { $env:VERIFY_RUN_ID = "GATE-" + (Get-Date -Format "yyyyMMdd-HHmmss") }
$RunId  = $env:VERIFY_RUN_ID
$RunDir = Join-Path $root ("docs\evaluation\final\EVAL3-FINAL-01\runs\" + $RunId)
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$StartedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$GitCommit = (& git -C $root rev-parse HEAD 2>$null)
$GitBranch = (& git -C $root rev-parse --abbrev-ref HEAD 2>$null)
$GitDirty  = [bool]((& git -C $root status --porcelain 2>$null) | Where-Object { $_ -notmatch '^\?\? \.next' })
$ReadyTimeoutSec = if ($env:VERIFY_READY_TIMEOUT_SEC) { [int]$env:VERIFY_READY_TIMEOUT_SEC } else { 300 }
$ReadyState = "not-started"
$StartedPids = @()
$StoppedPids = @()

function Write-Utf8NoBom($path, $text) {
    [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding($false)))
}
Write-Utf8NoBom (Join-Path $RunDir "command.txt") "scripts\verify_all.ps1  (RUN_ID=$RunId, ReadyTimeoutSec=$ReadyTimeoutSec)"

# Cleanup ueber die tatsaechlich gestarteten PIDs. Der Port-Weg bleibt nur als
# Nachlauf fuer Kindprozesse — und beruehrt ausschliesslich die zwei Ports, die
# dieses Skript selbst belegt hat.
function Stop-Servers {
    foreach ($p in $script:StartedPids) {
        try {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; $script:StoppedPids += $p }
        } catch {}
    }
    foreach ($port in 3000, 8000) {
        try {
            # Get-NetTCPConnection nimmt einen typisierten Enum-Wert und ist
            # damit locale-unabhaengig (kein netstat/"LISTENING"-Parsing).
            $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            foreach ($x in $c) {
                Stop-Process -Id $x.OwningProcess -Force -ErrorAction SilentlyContinue
                $script:StoppedPids += $x.OwningProcess
            }
        } catch {}
    }
    $script:StoppedPids = $script:StoppedPids | Select-Object -Unique
}

function Test-PortFree($port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return (-not $c)
}

try { Start-Transcript -Path (Join-Path $RunDir "stdout.log") -Force | Out-Null } catch {}
Write-Host "== Abschlussgate (deterministisch, Fake-Provider) ==  package manager: $PM"
Write-Host "   RUN_ID=$RunId  commit=$GitCommit  branch=$GitBranch  dirty=$GitDirty"
Write-Host "   Artefakte: $RunDir"
try {
    # --- Testdaten-Marker-Check (R0.4) ---
    Write-Host "-- testdata marker check --"
    $markerOut = & $py (Join-Path $root "scripts\check_testdata_markers.py") --root $root 2>&1
    $markerExit = $LASTEXITCODE
    $markerOut | ForEach-Object { Write-Host $_ }
    # Ein gruener Lauf mit 0 Markern prueft faktisch nichts — das darf nicht
    # laenger als "pass" durchgehen (Katalog in docs/evaluation/testdata-policy.md
    # ist bewusst leer, TODO(Owner)).
    $markerCount = 0
    $m = ($markerOut | Out-String) -match '\((\d+)\s+Marker'
    if ($m) { $markerCount = [int]$Matches[1] }
    $R.testdata = if ($markerExit -ne 0) { "FAIL" }
                  elseif ($markerCount -gt 0) { "pass-with-verified-markers" }
                  else { "not-applicable-no-markers" }

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
    # Seit der Live-Aktivierung (23.07.2026) kann backend/.env AI_EVAL_MODE=real
    # setzen. Die Pflicht-Suite ist für die Fake-/CI-Umgebung spezifiziert
    # (docs/evaluation/Provider_Mode_Matrix.md); tests/conftest.py neutralisiert
    # zusätzlich hermetisch. (Hinweis: $env:X = "" LÖSCHT in PowerShell die
    # Variable — leere Strings lassen sich hier nicht setzen; deshalb werden
    # die Modell-Ids per Remove-Item entfernt, damit eine lokale backend/.env
    # nicht in den "deterministischen" Lauf leckt.)
    $env:AI_EVAL_MODE = "off"
    foreach ($v in "AGENT_MODEL_GPT_56_LUNA_ID","AGENT_MODEL_GPT_56_TERRA_ID",
                   "AGENT_MODEL_GPT_56_SOL_ID","AGENT_MODEL_CLAUDE_HAIKU_45_ID",
                   "AGENT_MODEL_CLAUDE_SONNET_5_ID","AGENT_MODEL_CLAUDE_FABLE_5_ID") {
        Remove-Item ("Env:\" + $v) -ErrorAction SilentlyContinue
    }
    # Export-Smoke und No-Raw-Logging laufen als eigene Gate-Zeilen (siehe
    # unten) und werden hier abgewaehlt, damit sie nicht doppelt laufen.
    & $py -m pytest -q -p no:warnings --basetemp=$pytestBase `
        --junitxml="$RunDir\backend-junit.xml" `
        --ignore=tests/test_docx_render_smoke.py `
        --deselect "tests/test_m10_smoke.py::test_export_all_types" `
        --deselect "tests/test_m10_smoke.py::test_no_raw_log"
    $R.backend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    # Eigenstaendige Ergebnisse: eigener Befehl, eigener Exit Code, eigenes
    # JUnit. Frueher spiegelten diese zwei Zeilen nur $R.backend und meldeten
    # FAIL, sobald irgendein anderer Test der Suite fiel.
    Write-Host "-- export smoke (eigene Zeile) --"
    & $py -m pytest "tests/test_m10_smoke.py::test_export_all_types" -q -p no:warnings `
        --basetemp="$pytestSmokeBase-export" --junitxml="$RunDir\export-smoke-junit.xml"
    $R.export = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    Write-Host "-- no-raw-log (eigene Zeile) --"
    & $py -m pytest "tests/test_m10_smoke.py::test_no_raw_log" -q -p no:warnings `
        --basetemp="$pytestSmokeBase-noraw" --junitxml="$RunDir\no-raw-log-junit.xml"
    $R.norawlog = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }

    Write-Host "-- DOCX render smoke (benötigt Microsoft Word) --"
    & $py -m pytest tests/test_docx_render_smoke.py -q -p no:warnings --basetemp=$pytestDocxBase `
        --junitxml="$RunDir\docx-junit.xml"
    $R.docx = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Pop-Location

    # --- Frontend: vitest + lint + tsc + build ---
    Write-Host "-- frontend: vitest --"
    PmRun "test" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "vitest.log")
    $R.frontend = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
    Write-Host "-- frontend: lint + tsc + build --"
    $R.quality = "pass"
    PmRun "lint" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "lint.log")
    if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    PmExec "tsc --noEmit" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "tsc.log")
    if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }
    # OneDrive-Sync kann eine stale .next sperren (EPERM beim unlink) → vor dem
    # Build best-effort räumen. Kein Hänger; nur ein Lock auf Altbeständen.
    try { Remove-Item (Join-Path $root ".next") -Recurse -Force -ErrorAction Stop } catch {}
    PmRun "build" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "build.log")
    if ($LASTEXITCODE -ne 0) { $R.quality = "FAIL" }

    # --- E2E + smokes ---
    Write-Host "-- e2e + smokes: preparing throwaway DB --"
    Remove-Item $e2eDb -ErrorAction SilentlyContinue
    Push-Location $backend
    $env:DATABASE_URL = "sqlite:///./var/verify_e2e.db"; $env:APP_ENV = "development"
    $env:DEMO_DATA_ENABLED = "true"
    & $py -m alembic -c alembic.ini upgrade head
    $seedPrep = ($LASTEXITCODE -eq 0)
    & $py -m app.demo.seed --reset --evaluation
    if ($LASTEXITCODE -ne 0) { $seedPrep = $false }
    Pop-Location
    if (-not $seedPrep) {
        # Ein fehlgeschlagener Seed lieferte frueher still eine kaputte E2E-DB.
        Write-Host "!! Seed/Migration fuer die E2E-DB fehlgeschlagen — E2E wird nicht ausgefuehrt."
        $R.playwright = "FAIL(seed)"; $R.golden2 = "FAIL(seed)"
        $R.functional = "FAIL(seed)"; $R.reviewtruth = "FAIL(seed)"; $R.apismoke = "FAIL(seed)"
    }

    Write-Host "-- starting backend + frontend --"
    foreach ($port in 3000, 8000) {
        if (-not (Test-PortFree $port)) {
            Write-Host "!! Port $port ist vor dem Start belegt — verwaister Listener aus einem frueheren Lauf?"
        }
    }
    # Shared env so the servers AND Playwright's demo-seed subprocess use the SAME DB
    # (set only now, after the backend pytest section which uses its own conftest DB).
    $env:DATABASE_URL = "sqlite:///./var/verify_e2e.db"; $env:APP_ENV = "development"
    $env:AGENT_FAKE_PROVIDER = "true"; $env:WEB_RESEARCH_ENABLED = "true"
    $env:WEB_RESEARCH_FAKE_PROVIDER = "true"; $env:DEMO_DATA_ENABLED = "true"
    # AI_EVAL_MODE=off verhindert live_fake_conflict, falls backend/.env live ist.
    $env:AI_EVAL_MODE = "off"
    $beEnv = "`$env:DATABASE_URL='sqlite:///./var/verify_e2e.db';`$env:APP_ENV='development';" +
             "`$env:AGENT_FAKE_PROVIDER='true';`$env:WEB_RESEARCH_ENABLED='true';" +
             "`$env:WEB_RESEARCH_FAKE_PROVIDER='true';`$env:DEMO_DATA_ENABLED='true';" +
             "`$env:AI_EVAL_MODE='off';" +
             "& '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    if (-not (Test-PortFree 8000)) { $ReadyState = "port-conflict"; Write-Host "!! Port 8000 belegt" }
    $beProc = Start-Process powershell -ArgumentList "-NoProfile","-Command",$beEnv -WorkingDirectory $backend -WindowStyle Hidden `
        -PassThru -RedirectStandardOutput (Join-Path $RunDir "backend-server.log") -RedirectStandardError (Join-Path $RunDir "backend-server.err")
    if ($beProc) { $StartedPids += $beProc.Id }
    $feEnv = "`$env:APP_BACKEND_MODE='live';`$env:FASTAPI_BRIDGE_URL='http://127.0.0.1:8000/api/v1';" +
             "node node_modules/next/dist/bin/next start --port 3000"
    if (-not (Test-PortFree 3000)) { $ReadyState = "port-conflict"; Write-Host "!! Port 3000 belegt" }
    $feProc = Start-Process powershell -ArgumentList "-NoProfile","-Command",$feEnv -WorkingDirectory $root -WindowStyle Hidden `
        -PassThru -RedirectStandardOutput (Join-Path $RunDir "frontend-server.log") -RedirectStandardError (Join-Path $RunDir "frontend-server.err")
    if ($feProc) { $StartedPids += $feProc.Id }

    Write-Host "-- waiting for readiness (timeout ${ReadyTimeoutSec}s) --"
    # Frueher: fixe 40x2s. Auf einem OneDrive-gebundenen Baum starteten die
    # Server regelmaessig spaeter, das Gate gab vorher auf und meldete
    # "servers not ready" ohne jede Diagnose. Jetzt: konfigurierbares Timeout,
    # getrennte Bereitschaft je Dienst und ein unterscheidbarer Ausgang.
    $ready = $false; $beReady = $false; $feReady = $false
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSec)
    while ((Get-Date) -lt $deadline) {
        # Ein belegter Port ist die Ursache, ein sofort beendeter Prozess nur die
        # Folge — der genauere Zustand darf nicht ueberschrieben werden.
        if ($beProc -and $beProc.HasExited) {
            if ($ReadyState -ne "port-conflict") { $ReadyState = "process-crash" }
            Write-Host "!! Backend-Prozess beendet (Exit $($beProc.ExitCode)) — Zustand: $ReadyState"; break
        }
        if ($feProc -and $feProc.HasExited) {
            if ($ReadyState -ne "port-conflict") { $ReadyState = "process-crash" }
            Write-Host "!! Frontend-Prozess beendet (Exit $($feProc.ExitCode)) — Zustand: $ReadyState"; break
        }
        if (-not $beReady) {
            try { if ((Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $beReady = $true; Write-Host "   backend bereit" } } catch {}
        }
        if (-not $feReady) {
            try { if ((Invoke-WebRequest "http://127.0.0.1:3000/login" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $feReady = $true; Write-Host "   frontend bereit" } } catch {}
        }
        if ($beReady -and $feReady) { $ready = $true; $ReadyState = "ready"; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready -and $ReadyState -notin @("process-crash","port-conflict")) {
        $ReadyState = if ($beReady -or $feReady) { "health-failure" } else { "startup-timeout" }
        Write-Host "!! Readiness fehlgeschlagen: $ReadyState (backend=$beReady frontend=$feReady)"
    }

    if ($ready) {
        Write-Host "-- Playwright (technischer Pfad, gesamte Suite) --"
        PmExec "playwright test --workers=1" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "pw-suite.log")
        $R.playwright = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        # Akzeptanz: der technische E2E läuft ZWEIMAL hintereinander auf der
        # frischen Demo-DB (die Suite oben ist Lauf 1; hier folgt Lauf 2).
        # Eindeutige Projekttitel machen den zweiten Lauf kollisionsfrei.
        Write-Host "-- technischer E2E (2. Lauf, frische Demo-DB) --"
        PmExec "playwright test e2e/golden-path.spec.ts --workers=1" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "pw-golden2.log")
        $R.golden2 = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- funktionaler Import-Pfad (gezielter Lauf) --"
        PmExec "playwright test e2e/import-functional.spec.ts --workers=1" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "pw-import.log")
        $R.functional = if ($LASTEXITCODE -eq 0) { "pass" } else { "FAIL" }
        Write-Host "-- Review-Truth-Pfad (gezielter Lauf) --"
        PmExec "playwright test e2e/review-truth.spec.ts --workers=1" *>&1 | Tee-Object -FilePath (Join-Path $RunDir "pw-reviewtruth.log")
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
        $R.playwright = "FAIL(servers not ready: $ReadyState)"; $R.golden2 = "FAIL(servers not ready: $ReadyState)"
        $R.functional = "FAIL(servers not ready: $ReadyState)"; $R.reviewtruth = "FAIL(servers not ready: $ReadyState)"
        $R.apismoke = "FAIL(servers not ready: $ReadyState)"
    }
}
finally {
    Stop-Servers
    Remove-Item $e2eDb -ErrorAction SilentlyContinue
}


# --- Opt-in-Kategorien: Status aus vorhandenen Artefakten (nie Gate-relevant) --
$mqJson = Join-Path $backend "var\evaluation\model_quality_summary.json"
if (Test-Path $mqJson) {
    try { $mqStatus = (Get-Content $mqJson -Raw -Encoding utf8 | ConvertFrom-Json).status }
    catch { $mqStatus = "Artefakt vorhanden" }
    $catModel = "$mqStatus — $mqJson"
} else {
    $catModel = "not_run (opt-in — scripts/run_model_quality_eval.py)"
}
# Zeigte frueher auf var\evaluation\role_model_eval\summary.json — dieser Pfad
# wird von keinem Codepfad je erzeugt, die Kategorie stand daher dauerhaft auf
# not_run. Der Pilot schreibt pilot_summary.json.
$rmeJson = Join-Path $backend "var\evaluation\role_model_eval_pilot\pilot_summary.json"
if (Test-Path $rmeJson) {
    try { $rmeStatus = (Get-Content $rmeJson -Raw -Encoding utf8 | ConvertFrom-Json).status }
    catch { $rmeStatus = "Artefakt vorhanden" }
    $catRoleEval = "$rmeStatus — $rmeJson"
} else {
    $catRoleEval = "not_run (opt-in — scripts/run_role_model_eval.py)"
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
Write-Host "=========== ABNAHME — SECHS GETRENNTE KATEGORIEN ==========="
Write-Host "1. Technical deterministic E2E : $catTech   (Fake-Provider; Suite + 2. Lauf)"
Write-Host "2. Structured import E2E       : $catImport   (e2e/import-functional.spec.ts)"
Write-Host "3. Live model evaluation       : $catModel"
Write-Host "4. Model selection (A1/A2/A3)  : $catRoleEval"
Write-Host "5. Live Firecrawl evaluation   : $catFirecrawl"
Write-Host "6. Supervised live E2E         : not_run (manuell — docs/demo/demo-runbook.md)"
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
Write-Host "export smoke             : $($R.export)   (test_m10_smoke.py::test_export_all_types)"
Write-Host "no-raw-log               : $($R.norawlog)   (test_m10_smoke.py::test_no_raw_log)"
Write-Host "testdata markers         : $($R.testdata)   (scripts/check_testdata_markers.py)"
Write-Host "legacy status guard      : $($R.legacyguard)   (scripts/check_legacy_status_paths.py)"
Write-Host "evaluation summary       : $($R.evalpath)"
Write-Host "==========================================================="

$gateKeys = @("backend","migration","frontend","quality","playwright","golden2",
              "functional","reviewtruth","docx","apismoke","export","norawlog",
              "testdata","legacyguard")
# "skip" bedeutet: die Zeile lief nie (z. B. Abbruch im try-Block). Das galt
# frueher als bestanden — jetzt faerbt es das Gate rot.
$fail = @($gateKeys | Where-Object { $R[$_] -like "FAIL*" -or $R[$_] -eq "skip" })
$overall = if ($fail.Count -gt 0) { "ROT" } else { "GRÜN" }
$FinishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# --- Maschinenlesbares Gesamtergebnis ---------------------------------------
$result = [ordered]@{
    run_id       = $RunId
    commit       = $GitCommit
    branch       = $GitBranch
    dirty        = $GitDirty
    started_at   = $StartedAt
    finished_at  = $FinishedAt
    duration_seconds = [int]((Get-Date $FinishedAt) - (Get-Date $StartedAt)).TotalSeconds
    overall_status = $overall
    readiness_state = $ReadyState
    ready_timeout_sec = $ReadyTimeoutSec
    environment  = [ordered]@{
        os = [string]$PSVersionTable.OS
        powershell = [string]$PSVersionTable.PSVersion
        package_manager = $PM
        python = (& $py --version 2>&1 | Out-String).Trim()
        provider_mode = "deterministic/fake (AI_EVAL_MODE=off)"
        real_providers_enabled = $false
    }
    categories   = ($gateKeys | ForEach-Object { [ordered]@{ name = $_; status = $R[$_] } })
    failed_tests = $fail
    blocked_tests = @(
        "backend/tests/test_a1_real_provider_smoke.py (RUN_REAL_PROVIDER_SMOKE)",
        "backend/tests/test_a1_mapping_real_provider_smoke.py (RUN_REAL_PROVIDER_SMOKE)",
        "backend/tests/test_agent_real_provider_smoke.py (RUN_REAL_PROVIDER_SMOKE)",
        "backend/tests/test_role_routing_real_e2e.py (RUN_REAL_PROVIDER_SMOKE)"
    )
    not_executed = @(
        "Live model evaluation (opt-in)",
        "Model selection A1/A2/A3 (opt-in)",
        "Live Firecrawl evaluation (opt-in)",
        "Supervised live E2E (manuell)",
        "Opt-in Playwright-Specs: RUN4A_VISUAL, RUN4A_REVIEW, RUN4B_VISUAL, FINAL_ACCEPT"
    )
    known_limitations = @(
        "64 Portal-Quality-Gates (QG.*) sind contract-only — nicht implementiert",
        "Keine parallelen, auswaehlbaren KI-Textvarianten",
        "Testdaten-Marker-Katalog ist leer (TODO Owner) — Guard meldet not-applicable-no-markers",
        "F-25 Dashboard-Flake: not-reproduced, Rest-Risiko dokumentiert",
        "Evaluation_Dataset.md weicht in 5 Kennzahlen von der Messung ab"
    )
    artifacts = [ordered]@{
        stdout = "stdout.log"
        backend_junit = "backend-junit.xml"
        export_junit = "export-smoke-junit.xml"
        no_raw_log_junit = "no-raw-log-junit.xml"
        docx_junit = "docx-junit.xml"
        evaluation_summary = $R.evalpath
    }
    cleanup = [ordered]@{
        started_pids = @($StartedPids)
        stopped_pids = @($StoppedPids)
        remaining_listeners = @(
            @(3000, 8000) | ForEach-Object {
                $c = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
                if ($c) { "port $_ still listening (pid $($c[0].OwningProcess))" }
            } | Where-Object { $_ }
        )
        removed_files = @("backend/var/verify_e2e.db", "backend/var/verify_migrate.db")
    }
}
Write-Utf8NoBom (Join-Path $RunDir "EvaluationGateResult.json") ($result | ConvertTo-Json -Depth 6)
Write-Host ""
Write-Host "Maschinenlesbares Ergebnis: $RunDir\EvaluationGateResult.json"

if ($fail.Count -gt 0) {
    Write-Host "TECHNISCHES GATE (deterministisch, Fake-Provider): ROT — $($fail -join ', ')"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Host "TECHNISCHES GATE (deterministisch, Fake-Provider): GRÜN — Live-Kategorien siehe oben (not_run heisst nicht bestanden)."
try { Stop-Transcript | Out-Null } catch {}
# Ohne explizites exit 0 fiel der Exit Code auf $LASTEXITCODE des letzten
# nativen Befehls zurueck — ein gruener Lauf konnte so ungleich 0 enden.
exit 0
