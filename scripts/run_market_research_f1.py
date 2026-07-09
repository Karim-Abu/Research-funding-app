"""RESEARCH.1a — F1 market research runner (Backend + Report).

Default: deterministic **FakeWebProvider**, a fresh temp SQLite DB, an F1-synthetic D0
project; generates ``docs/evaluation/research1_market_report_F1.md``. No network.

Real Firecrawl is opt-in and never runs in CI:
``RUN_REAL_FIRECRAWL=true`` + a ``FIRECRAWL_API_KEY`` in ``backend/.env`` switches to the
live provider (D0/public F1 synthetic only — never real D2 data).

Usage:
  python scripts/run_market_research_f1.py            # fake provider (default)
  RUN_REAL_FIRECRAWL=true python scripts/run_market_research_f1.py   # manual live run
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_SMOKE_DB = Path(tempfile.gettempdir()) / "market_research_f1.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
os.chdir(_BACKEND)  # env_file=".env" is CWD-relative → backend/.env (Firecrawl key)
sys.path.insert(0, str(_BACKEND))

from app.config.settings import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Project  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.evaluation.usage_smoke import (  # noqa: E402
    ACTOR,
    F1_SMOKE_CLASSIFICATION,
    WS,
    _ensure_base_rows,
)
from app.market_research.planner import MarketTopic  # noqa: E402
from app.market_research.report import render_report  # noqa: E402
from app.market_research.runner import run_market_research  # noqa: E402

CASE_ID = "F1"
# F1/QUALIMON public, synthetic-safe topic descriptors (no confidential idea/partners).
F1_TOPIC = MarketTopic(
    application_domain="manufacturing quality assurance",
    technology_area="industrial AI anomaly detection",
    target_customers="manufacturing SMEs",
    region="Switzerland",
)
_REPORT = _BACKEND.parent / "docs" / "evaluation" / "research1_market_report_F1.md"


def _seed_project(db) -> Project:
    _ensure_base_rows(db)
    project = Project(
        project_id="market-f1-synthetic",
        workspace_id=WS,
        title="F1 QUALIMON (RESEARCH.1a, synthetisch)",
        description="Synthetischer F1-abgeleiteter Market-Research-MVP (D0/public).",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(F1_SMOKE_CLASSIFICATION),
        created_by=ACTOR,
        status="draft",
    )
    db.add(project)
    db.commit()
    return db.get(Project, "market-f1-synthetic")


def main() -> int:
    settings = get_settings()
    real = os.environ.get("RUN_REAL_FIRECRAWL") == "true"
    if os.environ.get("CI") and real:
        print("market-research: real Firecrawl is never allowed in CI.", file=sys.stderr)
        return 2
    settings.web_research_enabled = True
    settings.web_research_fake_provider = not real
    data_mode = "synthetic_eval" if real else "fake_test"
    if real and not settings.firecrawl_api_key:
        print("market-research: RUN_REAL_FIRECRAWL set but no FIRECRAWL_API_KEY.",
              file=sys.stderr)
        return 2

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        project = _seed_project(db)
        outcome = run_market_research(
            db, project=project, actor_user_id=ACTOR, topic=F1_TOPIC,
            case_id=CASE_ID, data_mode=data_mode, max_results=3,
        )
    finally:
        db.close()

    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(
        render_report(outcome, generated_at=datetime.now(timezone.utc).date().isoformat()),
        encoding="utf-8",
    )
    print(
        f"market-research: provider={outcome.provider} queries={len(outcome.queries)} "
        f"results={outcome.result_count} tools={outcome.tool_invocation_count} "
        f"candidates={len(outcome.candidates)} -> {_REPORT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
