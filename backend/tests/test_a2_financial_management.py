"""R5.6 — A2 fields: Financial Independence + Management Hours.

Activates ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS (limit 300, profile
A2.organisations_governance) and PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION (limit
1000, profile A2.project_setup_workplan). Fake provider only — no real provider
calls. Covers registry-driven config, a valid advisory AIProposal per field,
missing_inputs from placeholders (unknown independence / missing hour distribution),
anchor validation, deterministic limit enforcement, no auto-accept, UsageRecord
linkage, per-field profile isolation, and the createRedraft API.

The content-level rules (no "financial independence confirmed" without evidence, no
invented percentages / hour values) are enforced by the versioned prompts and gated
by the injection suite; these unit tests lock in the *structural* invariants
(missing_inputs, HITL, char limits, anchor subset, metering).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import a2_fields, field_drafting
from app.agents.proposal import DraftProposal
from app.db.models import AgentInvocation, DraftSuggestion
from app.db.session import SessionLocal
from tests.a2_helpers import (
    add_verified_anchor,
    bundle,
    build_run_with_draft,
    fake_resolver,
    success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

FIN_FIELD_ID = "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
FIN_PROFILE_ID = "A2.organisations_governance"
FIN_PROMPT = "a2_organisations_governance_v1"
MGMT_FIELD_ID = "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"
MGMT_PROFILE_ID = "A2.project_setup_workplan"
MGMT_PROMPT = "a2_project_setup_workplan_v1"

# Cautious, within-limit texts; no confirmed independence, no invented numbers.
FIN_TEXT = (
    "Erläuterung zur finanziellen Unabhängigkeit der Partner nach den vorliegenden "
    "Angaben. Eigentumsverhältnisse sind noch zu belegen [Platzhalter]. Eine "
    "abschliessende Prüfung ist vor der Einreichung erforderlich."
)
MGMT_TEXT = (
    "Die Management-Stunden decken Projektkoordination, Reporting, Review-Meetings "
    "und Partnerabstimmung ab. Die konkrete Stundenverteilung ist noch zu ergänzen "
    "[Platzhalter]; ohne Grundlage werden keine Zahlen genannt."
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _fin_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=FIN_FIELD_ID, character_limit=300,
        field_name="Financial independence comment",
        draft_text="Aktueller Entwurf der Erläuterung.", **kw,
    )


def _mgmt_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=MGMT_FIELD_ID, character_limit=1000,
        field_name="Management hours explanation",
        draft_text="Aktueller Entwurf der Erklärung.", **kw,
    )


def _run_field(db, run, draft, base, field_id, provider, operation_id="op-r56"):
    return field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft.draft_id, base_version_id=base,
        operation_id=operation_id, provider_resolver=fake_resolver(provider),
    )


# --- registry-driven config (Limits aus Registry) --------------------------


def test_financial_config_resolves_from_registry():
    config = a2_fields.resolve_field_config(FIN_FIELD_ID)
    assert config.profile_id == FIN_PROFILE_ID
    assert config.char_limit == 300  # portal-field registry, not hardcoded
    assert config.mandatory_markers == ()  # singleton narrative field


def test_management_config_resolves_from_registry():
    config = a2_fields.resolve_field_config(MGMT_FIELD_ID)
    assert config.profile_id == MGMT_PROFILE_ID
    assert config.char_limit == 1000
    assert config.mandatory_markers == ()


def test_unrelated_field_stays_unresolved():
    # A structured (agent_writable: false) confirmation field is NOT A2-enabled.
    assert a2_fields.resolve_field_config(
        "ORG.INDEPENDENCE.FINANCIAL.EMPLOYEE_OWNERSHIP_CONFIRMATION"
    ) is None


# --- Financial Independence -------------------------------------------------


def test_financial_proposal_valid_and_advisory(db):
    run, draft, base = _fin_draft(db)
    anchor = add_verified_anchor(db, run)
    out = _run_field(db, run, draft, base, FIN_FIELD_ID,
                     success_fake(bundle(field_id=FIN_FIELD_ID, suggested_text=FIN_TEXT,
                                         evidence_anchor_ids=[anchor])))
    assert out.status == "succeeded"
    sug = db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id))
    assert sug.status == "proposed" and sug.field_id == FIN_FIELD_ID
    assert sug.profile_id == FIN_PROFILE_ID
    assert out.view["character_limit"] == 300
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.suggestion_text == FIN_TEXT
    assert proposal.human_review_required is True  # kein Auto-Accept
    assert proposal.used_anchor_ids == [anchor]
    assert proposal.profile_id == FIN_PROFILE_ID
    assert proposal.prompt_version is None  # Fake-Demo ist kein Modellaufruf
    assert proposal.data_mode  # data_mode present


def test_financial_unknown_independence_becomes_missing_inputs(db):
    # No ownership/dependency evidence ⇒ the gap is a missing input, not a claim.
    run, draft, base = _fin_draft(db)
    out = _run_field(db, run, draft, base, FIN_FIELD_ID,
                     success_fake(bundle(field_id=FIN_FIELD_ID, suggested_text=FIN_TEXT,
                                         placeholders=[{"label": "[Eigentumsverhältnisse fehlen]",
                                                        "reason": "missing_ownership_data"}])))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs[0].label == "[Eigentumsverhältnisse fehlen]"
    assert proposal.missing_inputs[0].reason == "missing_ownership_data"
    assert proposal.human_review_required is True
    assert "contains_placeholders" in proposal.safety_notes


def test_financial_invented_anchor_rejected(db):
    run, draft, base = _fin_draft(db)
    out = _run_field(db, run, draft, base, FIN_FIELD_ID,
                     success_fake(bundle(field_id=FIN_FIELD_ID, suggested_text=FIN_TEXT,
                                         evidence_anchor_ids=["anchor-ghost"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)) is None


def test_financial_over_limit_rejected(db):
    run, draft, base = _fin_draft(db)
    out = _run_field(db, run, draft, base, FIN_FIELD_ID,
                     success_fake(bundle(field_id=FIN_FIELD_ID, suggested_text="A" * 301)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"
    assert db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)) is None


def test_only_governance_profile_invoked(db):
    run, draft, base = _fin_draft(db)
    _run_field(db, run, draft, base, FIN_FIELD_ID,
               success_fake(bundle(field_id=FIN_FIELD_ID, suggested_text=FIN_TEXT)))
    profiles = {i.profile_id for i in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id)
    )}
    assert profiles == {FIN_PROFILE_ID}  # no SOL/VC/intro/PS, no A3 critic
    assert not any(p.startswith("A3") for p in profiles)


# --- Management Hours -------------------------------------------------------


def test_management_proposal_valid_and_advisory(db):
    run, draft, base = _mgmt_draft(db)
    out = _run_field(db, run, draft, base, MGMT_FIELD_ID,
                     success_fake(bundle(field_id=MGMT_FIELD_ID, suggested_text=MGMT_TEXT)))
    assert out.status == "succeeded"
    sug = db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id))
    assert sug.profile_id == MGMT_PROFILE_ID
    assert out.view["character_limit"] == 1000
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.suggestion_text == MGMT_TEXT
    assert proposal.human_review_required is True
    assert proposal.profile_id == MGMT_PROFILE_ID
    assert proposal.prompt_version is None  # Fake-Demo ist kein Modellaufruf


def test_management_missing_distribution_becomes_missing_inputs(db):
    run, draft, base = _mgmt_draft(db)
    out = _run_field(db, run, draft, base, MGMT_FIELD_ID,
                     success_fake(bundle(field_id=MGMT_FIELD_ID, suggested_text=MGMT_TEXT,
                                         placeholders=[{"label": "[Stundenverteilung fehlt]",
                                                        "reason": "missing_hour_distribution"}])))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs[0].label == "[Stundenverteilung fehlt]"
    assert proposal.human_review_required is True


def test_management_over_limit_rejected(db):
    run, draft, base = _mgmt_draft(db)
    out = _run_field(db, run, draft, base, MGMT_FIELD_ID,
                     success_fake(bundle(field_id=MGMT_FIELD_ID, suggested_text="A" * 1001)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"


def test_management_usage_record_linkage(db):
    run, draft, base = _mgmt_draft(db)
    out = _run_field(db, run, draft, base, MGMT_FIELD_ID,
                     success_fake(bundle(field_id=MGMT_FIELD_ID, suggested_text=MGMT_TEXT)))
    assert out.status == "succeeded"
    inv = db.get(AgentInvocation, out.invocation_id)
    assert inv.usage_record_id  # EVAL.1 metering fired for the fake model call
    assert out.view["proposal"]["usage_record_id"] is None
    assert out.view["ai_proposal"] is None


# --- createRedraft API (fake provider) --------------------------------------


def _setup(field_id):
    db = SessionLocal()
    try:
        if field_id == FIN_FIELD_ID:
            run, draft, base = _fin_draft(db)
        else:
            run, draft, base = _mgmt_draft(db)
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm_fake(monkeypatch, payload):
    from app.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_eval_mode", "off")
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    resolver = fake_resolver(success_fake(payload))
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", resolver)
    monkeypatch.setattr(
        field_drafting,
        "_default_resolver",
        lambda _config, _target_section=None: resolver,
    )


@pytest.mark.parametrize(
    "field_id, text, limit",
    [(FIN_FIELD_ID, FIN_TEXT, 300), (MGMT_FIELD_ID, MGMT_TEXT, 1000)],
)
def test_create_redraft_async_then_result(client, monkeypatch, field_id, text, limit):
    run_id, _draft_id, base = _setup(field_id)
    _arm_fake(
        monkeypatch, bundle(field_id=field_id, suggested_text=text)
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base}, headers=unsafe_headers(csrf),
    )
    assert res.status_code == 202
    op_id = res.json()["operation_id"]
    op = client.get(f"/api/v1/operations/{op_id}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["field_id"] == field_id
    assert op["result"]["character_limit"] == limit
    assert op["result"]["proposal"]["human_review_required"] is True
    assert op["result"]["proposal"]["generation_kind"] == "fake_demo"
    assert op["result"]["ai_proposal"] is None
