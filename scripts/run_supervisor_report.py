"""EVAL.4 — CLI-Wrapper für den Supervisor Evaluation Report.

Reine Dateiaggregation über bestehende R5.9-REAL-Artefakte
(``backend/var/evaluation/r5_9_real/*.json``) — kein Provider-Call, keine DB, kein Netz.

Usage:
  python scripts/run_supervisor_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from app.evaluation.supervisor_report import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
