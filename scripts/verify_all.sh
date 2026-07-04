#!/usr/bin/env bash
# Milestone 10 — one-command verification (fake providers only; no real key required).
#
# Backend: fresh-DB alembic migration check + pytest.
# Frontend: vitest + eslint + tsc + build.
# E2E + smokes: throwaway migrated+seeded DB, starts backend + frontend, waits for
#   readiness, runs Playwright + the API smoke, generates the EvaluationRunSummary,
#   then always tears the servers down.
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
R_PLAYWRIGHT="skip"; R_APISMOKE="skip"; R_EXPORT="skip"; R_NORAWLOG="skip"; EVAL_PATH="-"
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

echo "== M10 verification =="
echo "package manager: $PM"

# --- Backend: migration check + pytest ---------------------------------------
echo "-- backend: fresh-DB migration check --"
MIG_DB="$BACKEND/var/verify_migrate.db"
rm -f "$MIG_DB"
( cd "$BACKEND" && DATABASE_URL="sqlite:///./var/verify_migrate.db" APP_ENV=test \
  "$PY" -m alembic -c alembic.ini upgrade head ) && R_MIGRATION="pass" || R_MIGRATION="FAIL"
rm -f "$MIG_DB"

echo "-- backend: pytest --"
( cd "$BACKEND" && "$PY" -m pytest -q -p no:warnings ) && R_BACKEND="pass" || R_BACKEND="FAIL"

# --- Frontend: vitest + lint + tsc + build -----------------------------------
echo "-- frontend: vitest --"
pm_run test && R_FRONTEND="pass" || R_FRONTEND="FAIL"

echo "-- frontend: lint + tsc + build --"
R_QUALITY="pass"
pm_run lint || R_QUALITY="FAIL"
pm_exec tsc --noEmit || R_QUALITY="FAIL"
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
  echo "-- Playwright --"
  pm_exec playwright test --workers=1 && R_PLAYWRIGHT="pass" || R_PLAYWRIGHT="FAIL"
  echo "-- API smoke --"
  "$PY" "$ROOT/scripts/smoke_api.py" && R_APISMOKE="pass" || R_APISMOKE="FAIL"
  echo "-- EvaluationRunSummary --"
  # Re-seed the evaluation dataset (demo-dataset.spec may have plain-reset it), then export.
  ( cd "$BACKEND" && "$PY" -m app.demo.seed --reset --evaluation \
    && "$PY" -m app.evaluation ) \
    && EVAL_PATH="$BACKEND/var/evaluation/EvaluationRunSummary.json"
else
  R_PLAYWRIGHT="FAIL(servers not ready)"; R_APISMOKE="FAIL(servers not ready)"
fi

# The export + no-raw-log smokes run as backend pytest cases (test_m10_smoke.py).
R_EXPORT="$R_BACKEND"; R_NORAWLOG="$R_BACKEND"

cleanup; trap - EXIT INT TERM
rm -f "$E2E_DB"

echo ""
echo "================ M10 VERIFICATION SUMMARY ================"
echo "backend tests            : $R_BACKEND"
echo "migration                : $R_MIGRATION"
echo "frontend tests (vitest)  : $R_FRONTEND"
echo "build/typecheck/lint     : $R_QUALITY"
echo "Playwright               : $R_PLAYWRIGHT"
echo "API smoke                : $R_APISMOKE"
echo "export smoke             : $R_EXPORT   (test_m10_smoke.py::test_export_all_types)"
echo "no-raw-log               : $R_NORAWLOG   (test_m10_smoke.py::test_no_raw_log)"
echo "evaluation summary       : $EVAL_PATH"
echo "========================================================="

for r in "$R_BACKEND" "$R_MIGRATION" "$R_FRONTEND" "$R_QUALITY" "$R_PLAYWRIGHT" "$R_APISMOKE"; do
  case "$r" in FAIL*) exit 1;; esac
done
echo "ALL GREEN"
