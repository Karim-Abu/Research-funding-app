#!/usr/bin/env bash
# Abschlussgate — one-command verification (deterministisch, NUR Fake-Provider).
#
# Pflichtpfade (machen das Gate rot):
#   Backend-Tests · Migration · Frontend-Tests · lint/tsc/build ·
#   technischer Playwright-Pfad (Suite + Golden Path 2. Lauf) ·
#   funktionaler Import-Pfad (e2e/import-functional.spec.ts) ·
#   Review-Truth-Pfad (e2e/review-truth.spec.ts) · DOCX-Render-Smoke ·
#   API-Smoke · Testdaten-Marker · Legacy-Status-Guard.
#
# Opt-in-Kategorien (NIE Teil dieses Gates; werden nur als Status berichtet):
#   Live model evaluation (scripts/run_model_quality_eval.py),
#   Model selection (scripts/run_role_model_eval.py),
#   Live Firecrawl evaluation (scripts/run_live_research_smoke.py),
#   Provider-Preflight (scripts/run_provider_preflight.py),
#   Supervised live E2E (manuell, docs/demo/demo-runbook.md).
#
# Es gibt bewusst KEINE Pauschalaussage «ALL GREEN»: grün ist hier immer nur
# das technische, deterministische Gate mit Fake-Providern.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$BACKEND/.venv/bin/python"
[ -x "$PY" ] || PY="python"

# --- package manager detection (corr 1): corepack pnpm -> pnpm -> npm ----------
if command -v corepack >/dev/null 2>&1 && corepack pnpm --version >/dev/null 2>&1; then
  PM="corepack pnpm"; PM_KIND="pnpm"
elif command -v pnpm >/dev/null 2>&1; then
  PM="pnpm"; PM_KIND="pnpm"
else
  PM="npm"; PM_KIND="npm"
fi
pm_run()  { if [ "$PM_KIND" = "pnpm" ]; then $PM "$@"; else npm run "$@"; fi; }
pm_exec() { if [ "$PM_KIND" = "pnpm" ]; then $PM exec "$@"; else npx "$@"; fi; }

R_BACKEND="skip"; R_MIGRATION="skip"; R_FRONTEND="skip"; R_QUALITY="skip"
R_PLAYWRIGHT="skip"; R_GOLDEN2="skip"; R_FUNCTIONAL="skip"; R_REVIEWTRUTH="skip"
R_DOCX="skip"; R_APISMOKE="skip"; R_EXPORT="skip"; R_NORAWLOG="skip"
R_TESTDATA="skip"; R_LEGACYGUARD="skip"; EVAL_PATH="-"
BACKEND_PID=""; FRONTEND_PID=""
E2E_DB="$BACKEND/var/verify_e2e.db"
export E2E_EMAIL="${E2E_EMAIL:-anna.keller@example.test}"
export E2E_PASSWORD="${E2E_PASSWORD:-changeme-dev-lead}"

cleanup() {
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  # Best-effort port cleanup (children of next/uvicorn).
  for port in 3000 8000; do
    pid=$(netstat -ano 2>/dev/null | grep -E "LISTENING" | grep ":$port " | awk '{print $NF}' | head -1)
    [ -n "$pid" ] && taskkill //PID "$pid" //F >/dev/null 2>&1
  done
}
trap cleanup EXIT INT TERM

echo "== Abschlussgate (deterministisch, Fake-Provider) =="
echo "package manager: $PM"

# --- Testdaten-Marker-Check (R0.4) --------------------------------------------
echo "-- testdata marker check --"
"$PY" "$ROOT/scripts/check_testdata_markers.py" --root "$ROOT" \
  && R_TESTDATA="pass" || R_TESTDATA="FAIL"

# --- Legacy-Status-Guard (R1.4) ------------------------------------------------
echo "-- legacy status guard --"
"$PY" "$ROOT/scripts/check_legacy_status_paths.py" --root "$ROOT" \
  && R_LEGACYGUARD="pass" || R_LEGACYGUARD="FAIL"

# --- Backend: migration check + pytest ---------------------------------------
echo "-- backend: fresh-DB migration check --"
MIG_DB="$BACKEND/var/verify_migrate.db"
rm -f "$MIG_DB"
( cd "$BACKEND" && DATABASE_URL="sqlite:///./var/verify_migrate.db" APP_ENV=test \
  "$PY" -m alembic -c alembic.ini upgrade head ) && R_MIGRATION="pass" || R_MIGRATION="FAIL"
rm -f "$MIG_DB"

echo "-- backend: pytest (ohne DOCX-Render-Smoke — eigene Gate-Zeile) --"
( cd "$BACKEND" && "$PY" -m pytest -q -p no:warnings \
    --ignore=tests/test_docx_render_smoke.py ) \
  && R_BACKEND="pass" || R_BACKEND="FAIL"

echo "-- DOCX render smoke (benötigt Microsoft Word) --"
( cd "$BACKEND" && "$PY" -m pytest tests/test_docx_render_smoke.py -q -p no:warnings ) \
  && R_DOCX="pass" || R_DOCX="FAIL"

# --- Frontend: vitest + lint + tsc + build -----------------------------------
echo "-- frontend: vitest --"
pm_run test && R_FRONTEND="pass" || R_FRONTEND="FAIL"

echo "-- frontend: lint + tsc + build --"
R_QUALITY="pass"
pm_run lint || R_QUALITY="FAIL"
pm_exec tsc --noEmit || R_QUALITY="FAIL"
# OneDrive-Sync kann eine stale .next sperren (EPERM beim unlink) → vor dem Build
# best-effort räumen. Kein Hänger; nur ein Lock auf Altbeständen (siehe README).
rm -rf "$ROOT/.next" 2>/dev/null || true
pm_run build || R_QUALITY="FAIL"

# --- E2E + smokes: start servers, run, tear down ------------------------------
echo "-- e2e + smokes: preparing throwaway DB --"
rm -f "$E2E_DB"
( cd "$BACKEND" && DATABASE_URL="sqlite:///./var/verify_e2e.db" APP_ENV=development \
    DEMO_DATA_ENABLED=true "$PY" -m alembic -c alembic.ini upgrade head \
  && DATABASE_URL="sqlite:///./var/verify_e2e.db" APP_ENV=development DEMO_DATA_ENABLED=true \
    "$PY" -m app.demo.seed --reset --evaluation )

echo "-- starting backend + frontend --"
# Shared env so the servers AND Playwright's demo-seed subprocess use the SAME DB.
# (Exported only now, AFTER the backend pytest section, which uses its own conftest DB.)
export DATABASE_URL="sqlite:///./var/verify_e2e.db" APP_ENV=development \
  AGENT_FAKE_PROVIDER=true WEB_RESEARCH_ENABLED=true WEB_RESEARCH_FAKE_PROVIDER=true \
  DEMO_DATA_ENABLED=true
( cd "$BACKEND" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ) &
BACKEND_PID=$!
( APP_BACKEND_MODE=live FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1 \
  node node_modules/next/dist/bin/next start --port 3000 ) &
FRONTEND_PID=$!

echo "-- waiting for readiness --"
READY="no"
for _ in $(seq 1 40); do
  b=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/health 2>/dev/null)
  f=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/login 2>/dev/null)
  if [ "$b" = "200" ] && [ "$f" = "200" ]; then READY="yes"; break; fi
  sleep 2
done

if [ "$READY" = "yes" ]; then
  echo "-- Playwright (technischer Pfad, gesamte Suite) --"
  pm_exec playwright test --workers=1 && R_PLAYWRIGHT="pass" || R_PLAYWRIGHT="FAIL"
  # Akzeptanz: der technische E2E läuft ZWEIMAL hintereinander auf der frischen
  # Demo-DB (die Playwright-Suite oben ist Lauf 1; hier folgt Lauf 2). Eindeutige
  # Projekttitel machen den zweiten Lauf kollisionsfrei.
  echo "-- technischer E2E (2. Lauf, frische Demo-DB) --"
  pm_exec playwright test e2e/golden-path.spec.ts --workers=1 \
    && R_GOLDEN2="pass" || R_GOLDEN2="FAIL"
  echo "-- funktionaler Import-Pfad (gezielter Lauf) --"
  pm_exec playwright test e2e/import-functional.spec.ts --workers=1 \
    && R_FUNCTIONAL="pass" || R_FUNCTIONAL="FAIL"
  echo "-- Review-Truth-Pfad (gezielter Lauf) --"
  pm_exec playwright test e2e/review-truth.spec.ts --workers=1 \
    && R_REVIEWTRUTH="pass" || R_REVIEWTRUTH="FAIL"
  echo "-- API smoke --"
  "$PY" "$ROOT/scripts/smoke_api.py" && R_APISMOKE="pass" || R_APISMOKE="FAIL"
  echo "-- EvaluationRunSummary --"
  # Re-seed the evaluation dataset (demo-dataset.spec may have plain-reset it), then export.
  ( cd "$BACKEND" && "$PY" -m app.demo.seed --reset --evaluation \
    && "$PY" -m app.evaluation ) \
    && EVAL_PATH="$BACKEND/var/evaluation/EvaluationRunSummary.json"
else
  R_PLAYWRIGHT="FAIL(servers not ready)"; R_GOLDEN2="FAIL(servers not ready)"
  R_FUNCTIONAL="FAIL(servers not ready)"; R_REVIEWTRUTH="FAIL(servers not ready)"
  R_APISMOKE="FAIL(servers not ready)"
fi

# The export + no-raw-log smokes run as backend pytest cases (test_m10_smoke.py).
R_EXPORT="$R_BACKEND"; R_NORAWLOG="$R_BACKEND"

cleanup; trap - EXIT INT TERM
rm -f "$E2E_DB"

# --- Opt-in-Kategorien: Status aus vorhandenen Artefakten (nie Gate-relevant) --
MQ_JSON="$BACKEND/var/evaluation/model_quality_summary.json"
if [ -f "$MQ_JSON" ]; then
  MQ_STATUS="$("$PY" -c "import json;print(json.load(open(r'$MQ_JSON',encoding='utf-8'))['status'])" 2>/dev/null || echo "Artefakt vorhanden")"
  CAT_MODEL="$MQ_STATUS — $MQ_JSON"
else
  CAT_MODEL="not_run (opt-in — scripts/run_model_quality_eval.py)"
fi
RME_JSON="$BACKEND/var/evaluation/role_model_eval/summary.json"
if [ -f "$RME_JSON" ]; then
  RME_STATUS="$("$PY" -c "import json;print(json.load(open(r'$RME_JSON',encoding='utf-8'))['status'])" 2>/dev/null || echo "Artefakt vorhanden")"
  CAT_ROLE_EVAL="$RME_STATUS — $RME_JSON"
else
  CAT_ROLE_EVAL="not_run (opt-in — scripts/run_role_model_eval.py)"
fi
LR_MD="$BACKEND/var/evaluation/live_research_smoke.md"
if [ -f "$LR_MD" ]; then
  LR_STATUS="$(grep -m1 -o 'Status: [a-zA-Zü_]*' "$LR_MD" | head -1 | cut -d' ' -f2)"
  CAT_FIRECRAWL="${LR_STATUS:-Artefakt vorhanden} — $LR_MD"
else
  CAT_FIRECRAWL="not_run (opt-in — scripts/run_live_research_smoke.py)"
fi
PF_MD="$BACKEND/var/evaluation/provider_preflight.md"
if [ -f "$PF_MD" ]; then
  CAT_PREFLIGHT="Artefakt vorhanden — $PF_MD"
else
  CAT_PREFLIGHT="not_run (opt-in — scripts/run_provider_preflight.py)"
fi

CAT_TECH="FAIL"; case "$R_PLAYWRIGHT$R_GOLDEN2" in passpass) CAT_TECH="pass";; esac
CAT_IMPORT="FAIL"; case "$R_FUNCTIONAL" in pass) CAT_IMPORT="pass";; esac

echo ""
echo "=========== ABNAHME — SECHS GETRENNTE KATEGORIEN ==========="
echo "1. Technical deterministic E2E : $CAT_TECH   (Fake-Provider; Suite + 2. Lauf)"
echo "2. Structured import E2E       : $CAT_IMPORT   (e2e/import-functional.spec.ts)"
echo "3. Live model evaluation       : $CAT_MODEL"
echo "4. Model selection (A1/A2/A3)  : $CAT_ROLE_EVAL"
echo "5. Live Firecrawl evaluation   : $CAT_FIRECRAWL"
echo "6. Supervised live E2E         : not_run (manuell — docs/demo/demo-runbook.md)"
echo "Provider-Preflight (Ebene E)   : $CAT_PREFLIGHT"
echo "Private SEDATE-Acceptance      : manuell — scripts/run_private_innolink_acceptance.py"
echo ""
echo "=============== TECHNISCHE GATE-DETAILS ==================="
echo "backend tests            : $R_BACKEND"
echo "migration                : $R_MIGRATION"
echo "frontend tests (vitest)  : $R_FRONTEND"
echo "build/typecheck/lint     : $R_QUALITY"
echo "Playwright (Suite)       : $R_PLAYWRIGHT"
echo "technischer E2E (2. Lauf): $R_GOLDEN2   (e2e/golden-path.spec.ts)"
echo "funktionaler Import      : $R_FUNCTIONAL   (e2e/import-functional.spec.ts)"
echo "review truth             : $R_REVIEWTRUTH   (e2e/review-truth.spec.ts)"
echo "docx render smoke        : $R_DOCX   (tests/test_docx_render_smoke.py)"
echo "API smoke                : $R_APISMOKE"
echo "export smoke             : $R_EXPORT   (test_m10_smoke.py::test_export_all_types)"
echo "no-raw-log               : $R_NORAWLOG   (test_m10_smoke.py::test_no_raw_log)"
echo "testdata markers         : $R_TESTDATA   (scripts/check_testdata_markers.py)"
echo "legacy status guard      : $R_LEGACYGUARD   (scripts/check_legacy_status_paths.py)"
echo "evaluation summary       : $EVAL_PATH"
echo "==========================================================="

for r in "$R_BACKEND" "$R_MIGRATION" "$R_FRONTEND" "$R_QUALITY" "$R_PLAYWRIGHT" \
         "$R_GOLDEN2" "$R_FUNCTIONAL" "$R_REVIEWTRUTH" "$R_DOCX" "$R_APISMOKE" \
         "$R_TESTDATA" "$R_LEGACYGUARD"; do
  case "$r" in FAIL*)
    echo "TECHNISCHES GATE (deterministisch, Fake-Provider): ROT"
    exit 1;;
  esac
done
echo "TECHNISCHES GATE (deterministisch, Fake-Provider): GRÜN — Live-Kategorien siehe oben (not_run heisst nicht bestanden)."
