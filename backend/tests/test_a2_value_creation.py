"""Milestone 9E — A2 Value Creation (VC.BUSINESS_TARGETS_MODEL.EDITOR).

Activates exactly one new profile/field; SOL stays unchanged. Fake provider only.
Covers the registry-driven config (15000 limit, mandatory 3.1/3.2), createRedraft
gating, suggestion validation, accept → agent DraftVersion + recheck, and that no
other A2/A3 profile is invoked.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import a2_fields, field_drafting
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    DraftSuggestion,
    DraftVersion,
    PortalFieldDraft,
    ReviewApproval,
)
from app.db.session import SessionLocal
from tests.a2_helpers import (
    VC_FIELD_ID,
    VC_GOOD_TEXT,
    add_verified_anchor,
    bundle,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

SOL_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# --- registry-driven config ------------------------------------------------


def test_vc_config_resolves_from_registry():
    config = a2_fields.resolve_field_config(VC_FIELD_ID)
    assert config.profile_id == "A2.value_creation_market_logic"
    assert config.char_limit == 15000
    # Portal-Schema-Minimum: 3.3 (Impact) ist eine Editor-Hauptfrage.
    assert config.mandatory_markers == ("3.1", "3.2", "3.3")


def test_unsupported_field_has_no_config():
    assert a2_fields.resolve_field_config("INTRO.APP.ABSTRACT.EDITOR") is None


# --- orchestrator (fake provider) ------------------------------------------


def _vc_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=VC_FIELD_ID, character_limit=15000, field_name="Value Creation",
        draft_text=VC_GOOD_TEXT, **kw,
    )


def _run_vc(db, run, draft, base, provider, operation_id="op-vc"):
    return field_drafting.run_a2_field_drafting(
        db, run, field_id=VC_FIELD_ID, draft_id=draft.draft_id, base_version_id=base,
        operation_id=operation_id, target_section="3.2",
        provider_resolver=fake_resolver(provider),
    )


def _vc_bundle(**kw):
    kw.setdefault(
        "suggested_text",
        "3.2 Geschäftsmodell und Markt: Zielkunden und Differenzierung werden klarer beschrieben [unklar].",
    )
    return section_bundle(
        field_id=VC_FIELD_ID, target_section="3.2", **kw
    )


def test_valid_vc_suggestion_persists(db):
    run, draft, base = _vc_draft(db)
    out = _run_vc(db, run, draft, base, success_fake(_vc_bundle()))
    assert out.status == "succeeded"
    sug = db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id))
    assert sug.status == "proposed"
    assert sug.field_id == VC_FIELD_ID
    assert sug.profile_id == "A2.value_creation_market_logic"
    assert out.view["character_limit"] == 15000


def test_vc_over_limit_rejected(db):
    run, draft, base = _vc_draft(db)
    too_long = "3.2 " + ("x" * 15001)
    out = _run_vc(db, run, draft, base, success_fake(_vc_bundle(suggested_text=too_long)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"
    assert db.scalar(
        select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)
    ) is None


def test_vc_missing_mandatory_structure_rejected(db):
    run, draft, base = _vc_draft(db)
    # A section response must contain exactly the requested heading.
    out = _run_vc(db, run, draft, base, success_fake(_vc_bundle(suggested_text="3.1 nur eine Frage.")))
    assert out.status == "failed" and out.reason == "section_candidate_heading_invalid"


def test_vc_invented_evidence_anchor_rejected(db):
    run, draft, base = _vc_draft(db)
    out = _run_vc(db, run, draft, base,
                  success_fake(_vc_bundle(evidence_anchor_ids=["anchor-does-not-exist"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"


def test_vc_unknown_open_issue_rejected(db):
    run, draft, base = _vc_draft(db)
    out = _run_vc(db, run, draft, base,
                  success_fake(_vc_bundle(open_issue_ids=["issue-nope"])))
    assert out.status == "failed" and out.reason == "unknown_open_issue"


def test_vc_blocked_policy_makes_no_provider_call(db):
    run, draft, base = _vc_draft(db, sensitivity="confidential")
    provider = success_fake(_vc_bundle())
    out = _run_vc(db, run, draft, base, provider)
    assert out.status == "blocked" and provider.calls == 0


def test_vc_uses_verified_anchor(db):
    run, draft, base = _vc_draft(db)
    anchor_id = add_verified_anchor(db, run)
    out = _run_vc(db, run, draft, base,
                  success_fake(_vc_bundle(evidence_anchor_ids=[anchor_id])))
    assert out.status == "succeeded"


def test_only_value_creation_profile_invoked(db):
    run, draft, base = _vc_draft(db)
    _run_vc(db, run, draft, base, success_fake(_vc_bundle()))
    profiles = {i.profile_id for i in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id)
    )}
    # The VC profile is the only A2/A3 profile invoked — no SOL, no A3 critic.
    assert "A2.value_creation_market_logic" in profiles
    assert "A2.solution_innovation" not in profiles
    assert not any(p.startswith("A3") for p in profiles)


# --- createRedraft API (fake provider) -------------------------------------


def _setup(field_id=VC_FIELD_ID, processing_mode="cloud_assisted"):
    db = SessionLocal()
    try:
        if field_id == VC_FIELD_ID:
            run, draft, base = _vc_draft(db, processing_mode=processing_mode)
        else:
            run, draft, base = build_run_with_draft(db, processing_mode=processing_mode)
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm_vc(monkeypatch):
    monkeypatch.setattr(
        field_drafting, "_PROVIDER_RESOLVER", fake_resolver(success_fake(_vc_bundle())),
    )


def _create_redraft(client, csrf, run_id, field_id, base):
    target_section = "3.2" if field_id == VC_FIELD_ID else (
        "4.2" if field_id == SOL_FIELD_ID else None
    )
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base, "target_section": target_section},
        headers=unsafe_headers(csrf),
    )


def test_create_redraft_vc_async_then_result(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_vc(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, VC_FIELD_ID, base)
    assert res.status_code == 202
    op_id = res.json()["operation_id"]
    op = client.get(f"/api/v1/operations/{op_id}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["field_id"] == VC_FIELD_ID
    assert op["result"]["character_limit"] == 15000


def test_create_redraft_sol_still_works(client, monkeypatch):
    run_id, _draft_id, base = _setup(field_id=SOL_FIELD_ID)
    monkeypatch.setattr(
        field_drafting, "_PROVIDER_RESOLVER",
        fake_resolver(success_fake(section_bundle())),
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, SOL_FIELD_ID, base)
    assert res.status_code == 202


def test_create_redraft_unsupported_field_404(client):
    run_id, _draft_id, base = _setup()
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    # INTRO.APP.NAME is not in the A2 allow-list (Abstract/Exec Summary now are).
    res = _create_redraft(client, csrf, run_id, "INTRO.APP.NAME", base)
    assert res.status_code == 404


def test_create_redraft_deterministic_only_503(client, monkeypatch):
    run_id, _draft_id, base = _setup(processing_mode="deterministic_only")
    _arm_vc(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, VC_FIELD_ID, base)
    assert res.status_code == 503
    assert res.json()["code"] == "ai_unavailable"


def test_create_redraft_stale_base_409(client, monkeypatch):
    run_id, _draft_id, _base = _setup()
    _arm_vc(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, VC_FIELD_ID, "stale-version")
    assert res.status_code == 409


def test_accept_vc_creates_agent_draft_version(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_vc(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    op_id = _create_redraft(client, csrf, run_id, VC_FIELD_ID, base).json()["operation_id"]
    suggested = client.get(f"/api/v1/operations/{op_id}").json()["result"]["suggested_text"]

    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{VC_FIELD_ID}",
        json={"base_version_id": base, "text": suggested, "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "agent"

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run.recheck_required is True
        sug = db.scalar(select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id))
        assert sug.status == "accepted" and sug.accepted_draft_version_id
    finally:
        db.close()


def test_accept_vc_invalidates_approval(client, monkeypatch):
    run_id, draft_id, base = _setup()
    db = SessionLocal()
    try:
        db.add(ReviewApproval(
            approval_id="appr-vc", run_id=run_id, workspace_id="ws-demo", scope="run",
            scope_id=run_id, status="approved", approval_scope_hash="h",
            review_package_version="1",
        ))
        db.commit()
    finally:
        db.close()
    _arm_vc(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    op_id = _create_redraft(client, csrf, run_id, VC_FIELD_ID, base).json()["operation_id"]
    suggested = client.get(f"/api/v1/operations/{op_id}").json()["result"]["suggested_text"]
    client.patch(
        f"/api/v1/runs/{run_id}/fields/{VC_FIELD_ID}",
        json={"base_version_id": base, "text": suggested, "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    db = SessionLocal()
    try:
        appr = db.get(ReviewApproval, "appr-vc")
        assert appr.status != "approved"
    finally:
        db.close()
