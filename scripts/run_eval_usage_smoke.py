#!/usr/bin/env python
"""EVAL.1 — Wrapper für den Fake-Usage-Smoke (siehe app/evaluation/usage_smoke.py).

    python scripts/run_eval_usage_smoke.py --case F1 --provider fake

Setzt VOR dem ersten ``app.*``-Import eine frische Temp-SQLite-DB (nie die
Dev-DB, nie eine Datei im OneDrive-Repo) und delegiert an
``app.evaluation.usage_smoke.main``. Keine echten API-Calls, keine Secrets.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SMOKE_DB = Path(tempfile.gettempdir()) / "eval1_usage_smoke.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()  # frischer, deterministischer Zustand pro Lauf

os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.evaluation.usage_smoke import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
