#!/usr/bin/env python
"""EVAL.2 — Wrapper für den manuellen Real-Provider-Smoke.

    $env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
    python scripts/run_real_provider_smoke.py --case F1 --provider openai
    python scripts/run_real_provider_smoke.py --case F1 --provider anthropic
    python scripts/run_real_provider_smoke.py --case F1 --provider firecrawl

Setzt VOR dem ersten ``app.*``-Import eine frische Temp-SQLite-DB (nie die
Dev-DB, nie eine Datei im OneDrive-Repo) und wechselt nach ``backend/``,
damit pydantic-settings die API-Keys aus ``backend/.env`` lädt (die
``DATABASE_URL``-Env-Var übersteuert den .env-Wert). Alle Manual-Mode-Guards
liegen in ``app.evaluation.real_smoke`` — ohne explizites Opt-in bricht der
Runner ab, in CI immer.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SMOKE_DB = Path(tempfile.gettempdir()) / "eval2_real_smoke.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()  # frischer Zustand pro Lauf

os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
os.chdir(_BACKEND)  # env_file=".env" ist CWD-relativ → backend/.env (Keys)
sys.path.insert(0, str(_BACKEND))

from app.evaluation.real_smoke import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
