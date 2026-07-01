"""CLI: write an EvaluationRunSummary for a completed run.

    python -m app.evaluation [--run <run_id>] [--out var/evaluation]

Defaults to the evaluation demo run. Writes deterministic ``EvaluationRunSummary.json`` +
``.md`` to a git-ignored runtime dir (var/evaluation) — never to docs/ (corr 5).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.models import AnalysisRun
from app.db.session import SessionLocal
from app.demo.dataset import DEMO_PROJECTS
from app.evaluation.summary import build_evaluation_summary, render_markdown, to_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=None, help="Run id (default: the eval demo run).")
    parser.add_argument("--out", default="var/evaluation", help="Output directory.")
    parser.add_argument("--generated-at", default=None, help="Fixed timestamp (determinism).")
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)

    run_id = args.run or DEMO_PROJECTS[0].run_id
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if run is None:
            print(f"evaluation: run not found: {run_id}", file=sys.stderr)
            return 1
        summary = build_evaluation_summary(db, run, generated_at=args.generated_at)
    finally:
        db.close()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "EvaluationRunSummary.json"
    md_path = out / "EvaluationRunSummary.md"
    json_path.write_text(to_json(summary), encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    print(f"EvaluationRunSummary written: {json_path}")
    print(f"EvaluationRunSummary written: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
