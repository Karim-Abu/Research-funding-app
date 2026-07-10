"""Integrated-Draft Demo-View-Router (DEMO.1).

Beide Routen sind eine **Demo-Ansicht** (code-only, wie das Market-Profil) — sie sind
nicht Teil des eingefrorenen OpenAPI-Contracts und ändern ihn nicht.

- ``POST /demo/integrated-draft``: erzeugt ein frisches synthetisches F1-Demo-
  DraftPackage über den unveränderten R5.9-Runner. **Nur Fake-Provider**: ohne
  ``settings.agent_fake_provider`` antwortet die Route 503 — ein UI-Klick kann
  strukturell nie einen echten OpenAI/Anthropic/Firecrawl-Call auslösen.
- ``GET /demo/integrated-draft/real``: Read-only-Ansicht bereits erzeugter
  R5.9-REAL-Artefakte. Liest je Envelope **ausschliesslich** den Whitelist-
  ``report``-Teil (Previews, Tokens, Status) — der ``artifact``-Teil (Rohtexte,
  Roh-Provider-Antworten) wird nie gesendet. Keine Artefakte ⇒ leere Antwort
  (Empty State, kein Fehler). Es wird nie ein neuer Provider-Call ausgeführt.
"""
from __future__ import annotations

import dataclasses
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import get_settings
from app.db.models import Project, ResearchResult, ResearchTask
from app.db.session import get_db
from app.evaluation import integrated_draft_real as idr
from app.integrated_draft.runner import run_integrated_draft
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Demo"])

# Verbatim from the F1 goldstandard case (docs/evaluation/cases/F1_synthetic_case.md).
_TITLE = "F1 QUALIMON — KI-gestützte Qualitätsüberwachung (Demo, synthetisch)"
_TITLE_EN = "QUALIMON — AI-based Quality Monitoring for Production Lines"
_D0_CLASSIFICATION = {
    "sensitivity": "public",
    "origin": "synthetic",
    "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public",
    "nda_applies": False,
}
_VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
_SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
_MARKET_PURPOSE = "market_comparison"
_PARTNER_PURPOSE = "partner_research_org_topic"


def _seed_research_context(actor_user_id: str):
    """Seed one advisory market/partner ResearchCandidate onto the VC/SOL child
    projects (mirror of the R5.9 F1-CLI seed — synthetic rows, no queries, no web)."""

    def _seed(db: Session, field_id: str, project: Project) -> None:
        purpose = {_VC_FIELD: _MARKET_PURPOSE, _SOL_FIELD: _PARTNER_PURPOSE}.get(field_id)
        if purpose is None:
            return
        task_id = "rt-" + uuid.uuid4().hex[:8]
        db.add(ResearchTask(
            research_task_id=task_id, project_id=project.project_id,
            workspace_id=project.workspace_id, created_by=actor_user_id,
            purpose=purpose, subject_type="topic",
            query_text="öffentliche Themen-/Organisationssuche",
            normalized_query_hash="qh", status="succeeded",
        ))
        db.add(ResearchResult(
            result_id="rr-" + uuid.uuid4().hex[:8], research_task_id=task_id,
            workspace_id=project.workspace_id,
            source_url="https://research.example.org/r/1",
            title="Öffentliche Quelle (synthetisch)",
            snippet="Öffentlich zugänglicher Auszug (Snippet ist kein Beleg).",
            provider_rank=1, status="candidate",
        ))
        db.flush()

    return _seed


@router.post("/demo/integrated-draft")
def create_demo_integrated_draft(
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> dict:
    """Synchronous fake-only demo run; returns the DraftPackage as JSON."""
    if not get_settings().agent_fake_provider:
        raise ProblemException(
            status=503, code="ai_unavailable", title="Demo mode not enabled",
            detail=(
                "Der Demo-Antragsentwurf ist nur im Fake-Provider-Modus verfügbar "
                "(AGENT_FAKE_PROVIDER=true). Es werden keine echten KI-Calls "
                "ausgeführt."
            ),
        )
    project = Project(
        project_id="demo-draft-" + uuid.uuid4().hex[:8],
        workspace_id=context.user.workspace_id,
        title=_TITLE,
        description="Synthetischer F1-Demo-Lauf für die Antragsentwurf-Ansicht (D0).",
        innovation_field="Industrial AI / Manufacturing Quality",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(_D0_CLASSIFICATION),
        created_by=context.user.id, status="draft",
    )
    db.add(project)
    db.flush()
    package = run_integrated_draft(
        db, base_project=project, actor_user_id=context.user.id, case_id="F1-DEMO",
        provider_mode="fake", data_mode="fake_test",
        seed_context=_seed_research_context(context.user.id), title_en=_TITLE_EN,
    )
    db.commit()
    return dataclasses.asdict(package)


@router.get("/demo/integrated-draft/real")
def get_real_run_artifacts(
    context: AuthContext = Depends(require_session),
) -> dict:
    """Whitelist-only read view over existing R5.9-REAL artifacts (never `artifact`)."""
    results = idr._load_results(idr._default_results_dir())
    return {
        "providers": {
            provider: entry["report"]
            for provider, entry in results.items()
            if "report" in entry
        }
    }
