"""Shared setup for Milestone 9A agent tests (fake provider only)."""
from __future__ import annotations

import uuid

from app.agents.gateway import ModelRequest
from app.agents.providers import FakeProvider
from app.db.models import AnalysisRun, Project

WS = "ws-demo"


def fake_resolver(provider: FakeProvider):
    """A provider resolver that returns the same fake adapter for every route."""
    return lambda _route: provider


def per_route_resolver(by_provider: dict[str, FakeProvider]):
    """Resolve a distinct fake per provider name (for fallback tests)."""
    return lambda route: by_provider.get(route.provider)


def make_run(db, *, processing_mode="cloud_assisted", sensitivity="public") -> str:
    """Insert a minimal Project + completed AnalysisRun; returns the run_id."""
    pid = "agent-proj-" + uuid.uuid4().hex[:8]
    classification = {
        "sensitivity": sensitivity, "origin": "synthetic",
        "processing_mode": processing_mode, "web_research_mode": "off",
        "nda_applies": False,
    }
    db.add(
        Project(
            project_id=pid, workspace_id=WS, title="Agent Test", description="x",
            funding_instrument_profile_id=(
                "innosuisse_innovation_project_with_implementation_partner"
            ),
            data_classification=classification, created_by="user-anna", status="draft",
        )
    )
    rid = "agent-run-" + uuid.uuid4().hex[:8]
    db.add(
        AnalysisRun(
            run_id=rid, project_id=pid, workspace_id=WS, created_by="user-anna",
            status="completed", current_stage="finalize_run", progress_percent=100,
            processing_mode=processing_mode,
            effective_data_classification=classification, snapshot_versions={},
        )
    )
    db.flush()
    return rid


def base_request(**overrides) -> ModelRequest:
    defaults = dict(
        profile_id="A1.project_fact_extraction",
        workspace_id=WS,
        input_payload={
            "run_id": "r", "fragment_ids": ["frag-1"], "active_requirement_ids": [],
            "active_field_ids": [],
            "data_classification": {
                "sensitivity": "public", "origin": "synthetic",
                "processing_mode": "cloud_assisted",
            },
        },
        classification={"sensitivity": "public", "origin": "synthetic", "nda_applies": False},
        processing_mode="cloud_assisted",
        allowed_fragment_ids=frozenset({"frag-1"}),
    )
    defaults.update(overrides)
    return ModelRequest(**defaults)
