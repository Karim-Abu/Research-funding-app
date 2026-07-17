"""R5.5 — A2 Introduction fields: Abstract + Executive Summary.

Activates INTRO.APP.ABSTRACT (limit 300) and INTRO.APP.EXECUTIVE_SUMMARY
(limit 2000), both served by the existing A2.introduction_public_summary profile.
Fake provider only — no real provider calls. Covers registry-driven config
(limits from the contract, no mandatory markers), a valid AIProposal per field,
anchor validation, missing_inputs, deterministic limit enforcement, no
auto-accept, UsageRecord linkage, and the createRedraft API.
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

ABSTRACT_FIELD_ID = "INTRO.APP.ABSTRACT"
EXEC_FIELD_ID = "INTRO.APP.EXECUTIVE_SUMMARY"
PROFILE_ID = "A2.introduction_public_summary"

# Public-safe, within-limit texts; no mandatory markers for these narrative fields.
ABSTRACT_TEXT = (
    "Kurzfassung des Projekts: Ziel ist eine neuartige Lösung für ein klar "
    "umrissenes Problem, mit erwartetem Nutzen für die beteiligten Organisationen. "
    "Konkrete Kennzahlen bleiben, wo Belege fehlen, als [Platzhalter] markiert."
)
EXEC_TEXT = (
    "Zusammenfassung: Ausgangslage, Innovationsziel und geplanter Nutzen des "
    "Projekts in allgemein verständlicher Form. Der Ansatz kombiniert bestehende "
    "Verfahren neu; fehlende Marktzahlen und Baselines bleiben als [Platzhalter] "
    "markiert statt erfunden."
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _abstract_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=ABSTRACT_FIELD_ID, character_limit=300, field_name="Abstract",
        draft_text="Aktueller Entwurf des Abstracts.", **kw,
    )


def _exec_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=EXEC_FIELD_ID, character_limit=2000, field_name="Executive Summary",
        draft_text="Aktueller Entwurf der Executive Summary.", **kw,
    )


def _run_field(db, run, draft, base, field_id, provider, operation_id="op-intro"):
    return field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft.draft_id, base_version_id=base,
        operation_id=operation_id, provider_resolver=fake_resolver(provider),
    )


# --- registry-driven config (Regel 1: Limits aus Registry) ------------------


def test_abstract_config_resolves_from_registry():
    config = a2_fields.resolve_field_config(ABSTRACT_FIELD_ID)
    assert config.profile_id == PROFILE_ID
    assert config.char_limit == 300  # from the portal-field registry, not hardcoded
    assert config.mandatory_markers == ()  # singleton narrative field, no sub-questions


def test_exec_summary_config_resolves_from_registry():
    config = a2_fields.resolve_field_config(EXEC_FIELD_ID)
    assert config.profile_id == PROFILE_ID
    assert config.char_limit == 2000
    assert config.mandatory_markers == ()


# --- valid AIProposal per field (fake provider) -----------------------------


def test_abstract_proposal_valid_and_advisory(db):
    run, draft, base = _abstract_draft(db)
    anchor = add_verified_anchor(db, run)
    out = _run_field(db, run, draft, base, ABSTRACT_FIELD_ID,
                     success_fake(bundle(field_id=ABSTRACT_FIELD_ID, suggested_text=ABSTRACT_TEXT,
                                         evidence_anchor_ids=[anchor])))
    assert out.status == "succeeded"
    sug = db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id))
    assert sug.status == "proposed" and sug.field_id == ABSTRACT_FIELD_ID
    assert sug.profile_id == PROFILE_ID
    assert out.view["character_limit"] == 300
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.generation_kind == "fake_demo"
    assert proposal.suggestion_text == ABSTRACT_TEXT
    assert proposal.human_review_required is True  # Regel 5: kein Auto-Accept
    assert proposal.used_anchor_ids == [anchor]
    assert proposal.profile_id == PROFILE_ID
    assert proposal.prompt_version is None  # kein Modellaufruf: technische Modellmetadaten verborgen


def test_exec_summary_proposal_valid(db):
    run, draft, base = _exec_draft(db)
    out = _run_field(db, run, draft, base, EXEC_FIELD_ID,
                     success_fake(bundle(field_id=EXEC_FIELD_ID, suggested_text=EXEC_TEXT)))
    assert out.status == "succeeded"
    assert out.view["character_limit"] == 2000
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.suggestion_text == EXEC_TEXT
    assert proposal.human_review_required is True
    assert proposal.used_anchor_ids == []


# --- used_anchor_ids validated ----------------------------------------------


def test_invented_anchor_rejected(db):
    run, draft, base = _abstract_draft(db)
    out = _run_field(db, run, draft, base, ABSTRACT_FIELD_ID,
                     success_fake(bundle(field_id=ABSTRACT_FIELD_ID, suggested_text=ABSTRACT_TEXT,
                                         evidence_anchor_ids=["anchor-ghost"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert out.view is None
    assert db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)) is None


# --- fehlende Daten ⇒ missing_inputs (Regel 3) ------------------------------


def test_missing_inputs_from_placeholders(db):
    run, draft, base = _exec_draft(db)
    out = _run_field(db, run, draft, base, EXEC_FIELD_ID,
                     success_fake(bundle(field_id=EXEC_FIELD_ID, suggested_text=EXEC_TEXT,
                                         placeholders=[{"label": "[Marktgrösse fehlt]",
                                                        "reason": "missing_market_data"}])))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs[0].label == "[Marktgrösse fehlt]"
    assert proposal.missing_inputs[0].reason == "missing_market_data"
    assert "contains_placeholders" in proposal.safety_notes


# --- Limit deterministisch (Regel 4: kontrollierte Ablehnung, kein Trim) ----


def test_abstract_over_limit_rejected(db):
    run, draft, base = _abstract_draft(db)
    too_long = "A" * 301
    out = _run_field(db, run, draft, base, ABSTRACT_FIELD_ID,
                     success_fake(bundle(field_id=ABSTRACT_FIELD_ID, suggested_text=too_long)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"
    assert db.scalar(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)) is None


# --- UsageRecord-Verknüpfung ------------------------------------------------


def test_usage_record_linkage(db):
    run, draft, base = _abstract_draft(db)
    out = _run_field(db, run, draft, base, ABSTRACT_FIELD_ID,
                     success_fake(bundle(field_id=ABSTRACT_FIELD_ID, suggested_text=ABSTRACT_TEXT)))
    assert out.status == "succeeded"
    inv = db.get(AgentInvocation, out.invocation_id)
    assert inv.usage_record_id  # EVAL.1 metering fired for the fake model call
    assert out.view["proposal"]["usage_record_id"] is None
    assert out.view["ai_proposal"] is None


def test_only_introduction_profile_invoked(db):
    run, draft, base = _abstract_draft(db)
    _run_field(db, run, draft, base, ABSTRACT_FIELD_ID,
               success_fake(bundle(field_id=ABSTRACT_FIELD_ID, suggested_text=ABSTRACT_TEXT)))
    profiles = {i.profile_id for i in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id)
    )}
    assert profiles == {PROFILE_ID}  # no SOL/VC, no A3 critic
    assert not any(p.startswith("A3") for p in profiles)


# --- createRedraft API (fake provider) --------------------------------------


def _setup(field_id):
    db = SessionLocal()
    try:
        if field_id == ABSTRACT_FIELD_ID:
            run, draft, base = _abstract_draft(db)
        else:
            run, draft, base = _exec_draft(db)
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm(monkeypatch, field_id, text):
    from app.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_eval_mode", "off")
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    resolver = fake_resolver(
        success_fake(bundle(field_id=field_id, suggested_text=text))
    )
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", resolver)
    monkeypatch.setattr(
        field_drafting,
        "_default_resolver",
        lambda _config, _target_section=None: resolver,
    )


def _create_redraft(client, csrf, run_id, field_id, base):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base}, headers=unsafe_headers(csrf),
    )


@pytest.mark.parametrize(
    "field_id, text, limit",
    [(ABSTRACT_FIELD_ID, ABSTRACT_TEXT, 300), (EXEC_FIELD_ID, EXEC_TEXT, 2000)],
)
def test_create_redraft_intro_async_then_result(client, monkeypatch, field_id, text, limit):
    run_id, _draft_id, base = _setup(field_id)
    _arm(monkeypatch, field_id, text)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, field_id, base)
    assert res.status_code == 202
    op_id = res.json()["operation_id"]
    op = client.get(f"/api/v1/operations/{op_id}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["field_id"] == field_id
    assert op["result"]["character_limit"] == limit
    assert op["result"]["proposal"]["human_review_required"] is True
    assert op["result"]["proposal"]["generation_kind"] == "fake_demo"
    assert op["result"]["ai_proposal"] is None
