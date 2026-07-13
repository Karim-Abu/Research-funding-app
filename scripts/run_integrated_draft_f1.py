"""R5.9 — F1 integrated draft run (DraftPackage + Report).

Default: FAKE provider (``settings.agent_fake_provider=True``), a fresh temp SQLite DB, an
F1-synthetic D0 project + one cloud-assisted run; generates
``docs/evaluation/r5_9_integrated_draft_run_report.md``. No network, no real provider, no
Firecrawl, no new queries.

Real provider is intentionally NOT supported here — it is a separate R5.9-REAL ticket.

Usage:
  python scripts/run_integrated_draft_f1.py --provider fake
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SMOKE_DB = Path(tempfile.gettempdir()) / "integrated_draft_f1.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
os.chdir(_BACKEND)
sys.path.insert(0, str(_BACKEND))

from app.config.settings import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    Project,
    ResearchResult,
    ResearchTask,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.db.session import SessionLocal, engine  # noqa: E402
from app.evaluation.usage_smoke import (  # noqa: E402
    ACTOR,
    F1_SMOKE_CLASSIFICATION,
    WS,
    _ensure_base_rows,
)
from app.integrated_draft.report import render_report  # noqa: E402
from app.integrated_draft.runner import run_integrated_draft  # noqa: E402

CASE_ID = "F1"
_PROJECT_ID = "integrated-f1-synthetic"
_REPORT = _BACKEND.parent / "docs" / "evaluation" / "r5_9_integrated_draft_run_report.md"
_MARKET_PURPOSE = "market_comparison"
_PARTNER_PURPOSE = "partner_research_org_topic"
# Verbatim from the F1 goldstandard case (docs/evaluation/cases/F1_synthetic_case.md,
# "2. INTRO.APP.NAME_EN", status: present) — not invented, not translated here.
_TITLE_EN = "QUALIMON — AI-based Quality Monitoring for Production Lines"


def _seed_project(db):
    _ensure_base_rows(db)
    project = Project(
        project_id=_PROJECT_ID, workspace_id=WS,
        title="F1 QUALIMON — KI-gestützte Qualitätsüberwachung (synthetisch)",
        description="Synthetischer F1-abgeleiteter Integrated-Draft-Lauf (D0/public).",
        innovation_field="Industrial AI / Manufacturing Quality",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(F1_SMOKE_CLASSIFICATION), created_by=ACTOR, status="draft",
    )
    db.add(project)
    db.commit()
    return db.get(Project, _PROJECT_ID)


def _add_candidate(db, project, *, purpose, title):
    task_id = "rt-" + uuid.uuid4().hex[:8]
    db.add(ResearchTask(
        research_task_id=task_id, project_id=project.project_id,
        workspace_id=project.workspace_id, created_by=ACTOR, purpose=purpose,
        subject_type="topic", query_text="öffentliche Themen-/Organisationssuche",
        normalized_query_hash="qh", status="succeeded",
    ))
    db.add(ResearchResult(
        result_id="rr-" + uuid.uuid4().hex[:8], research_task_id=task_id,
        workspace_id=project.workspace_id, source_url="https://research.example.org/r/1",
        title=title, snippet="Öffentlich zugänglicher Auszug (Snippet ist kein Beleg).",
        provider_rank=1, status="candidate",
    ))


def _add_imported_source(db, project):
    src_id, ver_id = "src-" + uuid.uuid4().hex[:8], "sv-" + uuid.uuid4().hex[:8]
    dc = {"sensitivity": "public", "origin": "public_source",
          "processing_mode": "deterministic_only", "web_research_mode": "validated_public",
          "nda_applies": False}
    text = "Der Markt für Anbieter und Wettbewerber im Bereich Qualitätsüberwachung wächst."
    db.add(SourceDocument(
        source_id=src_id, project_id=project.project_id, workspace_id=project.workspace_id,
        name="Marktbericht (öffentlich)", type="url", status="processed",
        data_classification=dc, current_source_version_id=ver_id, created_by=ACTOR,
    ))
    db.add(SourceVersion(
        source_version_id=ver_id, source_document_id=src_id, version_number=1,
        original_content_hash="h", normalized_content_hash="h2", normalized_text=text,
        parser_version="parser-1", normalizer_version="normalizer-1",
        chunker_version="chunker-1", processing_status="processed", data_classification=dc,
        storage_ref="b" * 32, original_filename="market.html", byte_size=len(text),
        mime_type="text/html",
    ))
    db.add(SourceFragment(
        fragment_id="frag-" + uuid.uuid4().hex[:8], source_version_id=ver_id, ordinal=0,
        original_text=text, normalized_text=text, start_offset=0, end_offset=len(text),
        content_hash="fh",
    ))


def _seed_context(db, field_id, project):
    """Seed advisory research context onto the VC/SOL child projects (R5.7 integration).
    Direct synthetic rows — no queries, no Firecrawl."""
    if field_id == "VC.BUSINESS_TARGETS_MODEL.EDITOR":
        _add_candidate(db, project, purpose=_MARKET_PURPOSE,
                       title="Öffentliche Marktquelle: Anbieter & Wettbewerber")
        _add_imported_source(db, project)
    elif field_id == "SOL.INNOVATION_SOLUTION.EDITOR":
        _add_candidate(db, project, purpose=_PARTNER_PURPOSE,
                       title="Öffentliche Partnerquelle: Forschungslabor Schweiz")
    db.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["fake"], default="fake",
                        help="Only 'fake' is supported; real provider is a separate "
                             "R5.9-REAL ticket.")
    args = parser.parse_args()
    if args.provider != "fake":
        print("integrated-draft: real provider is a separate R5.9-REAL ticket.",
              file=sys.stderr)
        return 2

    settings = get_settings()
    settings.agent_fake_provider = True  # built-in per-field fake texts, no keys, no network

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        project = _seed_project(db)
        package = run_integrated_draft(
            db, base_project=project, actor_user_id=ACTOR, case_id=CASE_ID,
            provider_mode="fake", data_mode="fake_test", seed_context=_seed_context,
            title_en=_TITLE_EN,
        )
        db.commit()
    finally:
        db.close()

    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(
        render_report(package, generated_at=datetime.now(timezone.utc).date().isoformat()),
        encoding="utf-8",
    )
    statuses = {}
    for f in package.fields:
        statuses[f.status] = statuses.get(f.status, 0) + 1
    print(
        f"integrated-draft: fields={len(package.fields)} statuses={statuses} "
        f"tokens={package.usage_summary.get('total_tokens', 0)} -> {_REPORT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
