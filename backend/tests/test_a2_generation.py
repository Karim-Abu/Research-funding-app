"""A2 solution-innovation suggestion generation + validation (Milestone 9D)."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.agents import allowed_facts, field_drafting
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderResult, ProviderUsage
from app.config.settings import get_settings
from app.db.models import (
    ControlResult,
    DraftSuggestion,
    ProcessingConfirmation,
    Project,
)
from app.db.session import SessionLocal
from app.evaluation.preflight import persist_route_preflight, preflight_route
from app.evaluation import role_model_scoring as scoring
from app.runs.cloud_policy import REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION
from tests.a2_helpers import (
    GOOD_TEXT,
    VC_FIELD_ID,
    add_verified_anchor,
    bundle,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _run(db, run, draft, base, provider, *, operation_id="op-1"):
    return field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base, operation_id=operation_id,
        provider_resolver=fake_resolver(provider),
    )


def _suggestions(db, run):
    return db.scalars(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)).all()


def _attach_real_confirmation(db, run) -> None:
    if db.get(Project, run.project_id) is None:
        db.add(Project(
            project_id=run.project_id,
            workspace_id=run.workspace_id,
            title="Synthetic A2 live test",
            description="Synthetic evaluation fixture.",
            funding_instrument_profile_id=(
                "innosuisse_innovation_project_with_implementation_partner"
            ),
            data_classification=dict(run.effective_data_classification or {}),
            created_by="user-anna",
            status="draft",
        ))
    db.add(ProcessingConfirmation(
        confirmation_id=str(uuid.uuid4()),
        project_id=run.project_id,
        workspace_id=run.workspace_id,
        created_by="user-anna",
        status="used",
        processing_mode="cloud_assisted",
        source_version_ids=[],
        accepted_policy_version="1.1.0",
        purpose="Synthetic live evaluation",
        provider_route_class="anthropic_direct",
        confirmation_text_version=REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION,
        data_classification_shown=dict(run.effective_data_classification or {}),
        expires_after_one_run=True,
        used_by_run_id=run.run_id,
    ))
    db.flush()


# Provisorische Demo-Route (2026-07-17): A2-Primärroute ist GPT-5.6 Terra
# (openai_direct); die Hermetik-Adapter spiegeln deshalb den OpenAI-Weg.
class _PreflightEcho(FakeProvider):
    name = "openai_direct"

    def generate(self, request):
        return ProviderResult(
            raw_output='{"pong": true}',
            usage=ProviderUsage(1, 1),
            model="actual-hermetic-terra",
        )


class _LiveA2(FakeProvider):
    name = "openai_direct"

    def generate(self, request):
        self.calls += 1
        return ProviderResult(
            raw_output=json.dumps(bundle()),
            usage=ProviderUsage(40, 120),
            model="actual-hermetic-terra",
        )


def _arm_live_a2(db, run, monkeypatch) -> None:
    settings = get_settings()
    model_id = "requested-hermetic-terra"
    monkeypatch.setattr(settings, "ai_eval_mode", "real")
    monkeypatch.setattr(settings, "agent_fake_provider", False)
    monkeypatch.setattr(settings, "openai_api_key", "openai-hermetic")
    monkeypatch.setattr(settings, "agent_model_gpt_56_terra_id", model_id)
    monkeypatch.setattr(settings, "agent_model_pricing_chf_per_million", {
        model_id: {
            "input_chf_per_million": 1,
            "output_chf_per_million": 2,
            "price_version": "test-v1",
            "source_url": "https://prices.example.test",
            "checked_at": "2026-07-16",
        }
    })
    _attach_real_confirmation(db, run)
    result = preflight_route(
        "openai_gpt_56_terra_candidate",
        settings=settings,
        adapter=_PreflightEcho(),
        execute_live=True,
    )
    assert result.status == "pass"
    persist_route_preflight(db, result, settings=settings)
    db.flush()


def test_valid_suggestion_persists(db):
    run, draft, base = build_run_with_draft(db)
    anchor = add_verified_anchor(db, run)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=[anchor])))
    assert out.status == "succeeded" and out.suggestion_id
    s = _suggestions(db, run)[0]
    assert s.status == "proposed" and s.field_id == "SOL.INNOVATION_SOLUTION.EDITOR"
    assert s.suggested_text == GOOD_TEXT and s.evidence_anchor_ids == [anchor]
    assert s.agent_invocation_id and s.content_hash and s.operation_id == "op-1"
    # The operation-result view is available for the frontend.
    assert out.view["character_limit"] == 25000 and out.view["suggested_text"] == GOOD_TEXT


def test_over_character_limit_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="4.1 " + "x" * 26000)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"
    assert _suggestions(db, run) == []  # never persisted, never trimmed


def test_missing_mandatory_structure_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="Only 4.1 and 4.2 here.")))
    assert out.status == "failed" and out.reason == "mandatory_structure_missing"
    assert _suggestions(db, run) == []


def test_invented_evidence_anchor_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=["GHOST-ANCHOR"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert _suggestions(db, run) == []


def test_unknown_open_issue_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(open_issue_ids=["NO-SUCH-ISSUE"])))
    assert out.status == "failed" and out.reason == "unknown_open_issue"


def test_empty_text_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="   ")))
    assert out.status == "failed" and out.reason == "empty_suggested_text"


def test_new_claim_without_evidence_or_research_source_is_rejected(db):
    run, draft, base = build_run_with_draft(db)
    payload = section_bundle()
    payload["section_candidate"]["new_claims"] = [
        "The platform is externally proven to outperform all alternatives."
    ]

    out = field_drafting.run_a2_field_drafting(
        db,
        run,
        field_id="SOL.INNOVATION_SOLUTION.EDITOR",
        draft_id=draft.draft_id,
        base_version_id=base,
        operation_id="op-unsourced-new-claim",
        target_section="4.2",
        provider_resolver=fake_resolver(success_fake(payload)),
    )

    assert out.status == "failed"
    assert out.reason == "new_claim_without_source"


def test_missing_input_metadata_cannot_introduce_a_new_number(db):
    run, draft, base = build_run_with_draft(db)
    payload = section_bundle(
        missing_inputs=[{
            "label": "Customer validation",
            "reason": "Which 999 customers will validate the result?",
        }]
    )

    out = field_drafting.run_a2_field_drafting(
        db,
        run,
        field_id="SOL.INNOVATION_SOLUTION.EDITOR",
        draft_id=draft.draft_id,
        base_version_id=base,
        operation_id="op-invented-number-in-metadata",
        target_section="4.2",
        provider_resolver=fake_resolver(success_fake(payload)),
    )

    assert out.status == "failed"
    assert out.reason == "invented_numeric_token"


_SEDATE_VALUE_CREATION_SOURCE = """3.1 DRAFT - Work-in-Progress
Describe the value creation and market logic?
Reviewer note: resolve the contradictory market-share figures before submission.
Excel Vorlage: use 12% market share.
SEDATE targets industrial operators that currently rely on manual inspections every 14 days. The planning sheet states a 12% market share, while the reviewer note states 18%. A pilot is described for 3 sites and the applicant expects a 25% reduction in unplanned downtime. HelioSense AG is listed as the implementation partner. Revenue note: CHF 2.4 million? Confirm customer, price and adoption assumptions. Patent note EP123456?

3.2 Market access: SEDATE plans direct pilot access through HelioSense AG.
3.3 Impact: the applicant expects fewer unplanned interruptions, but the measurement basis is open."""

_SEDATE_VALUE_CREATION_PROPOSAL = """3.1 SEDATE addresses industrial operators that currently depend on manual inspections every 14 days to identify emerging equipment issues. The proposed monitoring approach is intended to give operators earlier, operationally usable information, while HelioSense AG contributes the implementation path needed to integrate the result into customer workflows.

The initial value-creation logic is a pilot-led transition from manual inspection to a repeatable monitoring service. The stated pilot scope of 3 sites and the applicant-stated 25% reduction in unplanned downtime remain project claims that must be validated during implementation. Their relevance is practical: fewer unexpected interruptions would improve planning for operators and provide the implementation partner with a serviceable offer rather than a stand-alone technology component.

The available material contains conflicting market-share estimates of 12% and 18%; neither figure is treated as validated. The customer, pricing and adoption assumptions behind the CHF 2.4 million revenue note are not available and therefore remain open. Until these inputs are confirmed, the proposal can explain the commercial mechanism but cannot present a secured market share or revenue forecast.

Swiss value creation would arise through the implementation and validation capability retained by the project partners and through a reusable service for the stated target users. The precise segment boundary, validated market basis and revenue assumptions require applicant confirmation before submission."""


def _normalized_matches(pattern, text: str) -> set[str]:
    return {" ".join(value.split()).casefold() for value in pattern.findall(text)}


def test_sedate_like_31_regression_produces_clean_english_reviewable_prose(db):
    run, draft, base = build_run_with_draft(
        db,
        field_id=VC_FIELD_ID,
        draft_text=_SEDATE_VALUE_CREATION_SOURCE,
        character_limit=15000,
        field_name="Value Creation",
    )
    payload = {
        "section_candidate": {
            "field_id": VC_FIELD_ID,
            "target_section": "3.1",
            "suggested_text": _SEDATE_VALUE_CREATION_PROPOSAL,
            "rationale": (
                "Reordered the applicant material into customer problem, value "
                "mechanism, business logic and Swiss value creation."
            ),
            "preserved_facts": [
                "SEDATE targets industrial operators using manual inspections every 14 days.",
                "The pilot scope is 3 sites and the applicant states a 25% reduction in unplanned downtime.",
                "HelioSense AG is the implementation partner.",
            ],
            "removed_or_reframed_claims": [
                "The 12% and 18% market-share estimates conflict and were reframed as unvalidated.",
                "The CHF 2.4 million revenue note was not presented as a secured forecast.",
            ],
            "new_claims": [],
            "missing_inputs": [
                {
                    "label": "Validated market-share basis",
                    "reason": (
                        "Which market-share estimate, 12% or 18%, applies to "
                        "which segment and reference year?"
                    ),
                },
                {
                    "label": "Revenue assumptions",
                    "reason": (
                        "Which customer, pricing and adoption assumptions support "
                        "the CHF 2.4 million revenue note?"
                    ),
                },
            ],
            "evidence_anchor_ids": [],
            "research_source_ids": [],
            "open_issue_ids": [],
        },
        "warnings": [],
    }

    out = field_drafting.run_a2_field_drafting(
        db,
        run,
        field_id=VC_FIELD_ID,
        draft_id=draft.draft_id,
        base_version_id=base,
        operation_id="op-sedate-value-creation",
        target_section="3.1",
        provider_resolver=fake_resolver(success_fake(payload)),
    )

    assert out.status == "succeeded"
    text = out.view["suggested_text"]
    for banned in (
        "Reviewer note",
        "DRAFT",
        "Work-in-Progress",
        "Excel Vorlage",
        "Describe the value creation",
        "Patent note",
    ):
        assert banned not in text
    assert "12%" in text and "18%" in text and "conflicting" in text
    assert "market share is 12%" not in text.casefold()
    assert len(text.split()) > 150
    assert sum(1 for line in text.splitlines() if line.lstrip().startswith(("-", "*"))) == 0
    assert text.count(".") >= 8
    assert out.view["character_count"] <= out.view["character_limit"]

    # Der Vorschlag führt keine Zahl/Patent/Organisation ein, die der
    # Quelltext nicht trägt (Detektoren seit 2026-07-17 in allowed_facts).
    assert _normalized_matches(
        allowed_facts._NUMBER_RE, text
    ) <= _normalized_matches(allowed_facts._NUMBER_RE, _SEDATE_VALUE_CREATION_SOURCE)
    assert _normalized_matches(
        allowed_facts._PATENT_RE, text
    ) <= _normalized_matches(allowed_facts._PATENT_RE, _SEDATE_VALUE_CREATION_SOURCE)
    assert _normalized_matches(
        allowed_facts._ORG_RE, text
    ) <= _normalized_matches(allowed_facts._ORG_RE, _SEDATE_VALUE_CREATION_SOURCE)

    section = out.view["section_result"]
    assert section["new_claims"] == []
    assert section["research_source_ids"] == []
    assert section["preserved_facts"] == payload["section_candidate"]["preserved_facts"]
    assert section["removed_or_reframed_claims"] == (
        payload["section_candidate"]["removed_or_reframed_claims"]
    )
    assert section["missing_inputs"] == payload["section_candidate"]["missing_inputs"]
    assert all(
        item["reason"].endswith("?") for item in section["missing_inputs"]
    )
    assert section["role_skill_contract_v2"]["requires_human_review"] is True

    gates = scoring.a2_gate_results(
        text,
        schema_valid=True,
        required_terms=("SEDATE",),
        expected_markers=("3.1",),
        char_limit=out.view["character_limit"],
        manifest=allowed_facts.build_manifest([
            ("current_field_text", _SEDATE_VALUE_CREATION_SOURCE),
        ]),
        missing_inputs_count=len(section["missing_inputs"]),
        human_review_required=out.view["proposal"]["human_review_required"],
        expected_language="en",
    )
    assert scoring.gates_passed(gates), gates


def test_malformed_output_safe_failure(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, FakeProvider(mode="malformed"))
    assert out.status in ("failed", "timed_out") and _suggestions(db, run) == []


def test_timeout_safe_failure(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, FakeProvider(mode="timeout"))
    assert out.status in ("failed", "timed_out") and _suggestions(db, run) == []


def test_deterministic_only_skips(db):
    run, draft, base = build_run_with_draft(db, processing_mode="deterministic_only")
    provider = success_fake(bundle())
    out = _run(db, run, draft, base, provider)
    assert out.status == "skipped" and provider.calls == 0 and _suggestions(db, run) == []


def test_confidential_blocked(db):
    run, draft, base = build_run_with_draft(db, sensitivity="confidential")
    provider = success_fake(bundle())
    out = _run(db, run, draft, base, provider)
    assert out.status == "blocked" and provider.calls == 0


def test_availability_no_mode_upgrade(db):
    run, _d, _b = build_run_with_draft(db, processing_mode="deterministic_only")
    available, reason = field_drafting.availability(
        run, "SOL.INNOVATION_SOLUTION.EDITOR"
    )
    assert available is False and reason == "processing_mode_deterministic_only"
    # The run's mode is unchanged (never upgraded).
    assert run.processing_mode == "deterministic_only"


def test_replay_reuses_existing_suggestion(db):
    run, draft, base = build_run_with_draft(db)
    first = _run(db, run, draft, base, success_fake(bundle()), operation_id="op-a")
    assert first.status == "succeeded"
    second_provider = success_fake(bundle())
    second = _run(db, run, draft, base, second_provider, operation_id="op-b")
    assert second.status == "reused" and second_provider.calls == 0
    assert len(_suggestions(db, run)) == 1


def test_fake_provider_flag_drives_default_resolver(db, monkeypatch):
    # With agent_fake_provider on and no explicit resolver, the orchestrator uses
    # the deterministic fake (dev/test affordance) and produces a valid suggestion.
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    monkeypatch.setattr(get_settings(), "ai_eval_mode", "off")
    run, draft, base = build_run_with_draft(db)
    out = field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base, operation_id="op-fake",
    )
    assert out.status == "succeeded" and out.suggestion_id
    assert "4.5" in out.view["suggested_text"]


def test_real_mode_with_fake_flag_never_generates_fake_a2(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_eval_mode", "real")
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    run, draft, base = build_run_with_draft(db)
    provider = success_fake(bundle())

    out = _run(db, run, draft, base, provider, operation_id="op-live-conflict")

    assert out.status == "blocked"
    assert out.reason == "live_fake_conflict"
    assert provider.calls == 0
    assert _suggestions(db, run) == []


def test_live_without_model_id_is_unavailable_and_never_demo(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_eval_mode", "real")
    monkeypatch.setattr(settings, "agent_fake_provider", False)
    monkeypatch.setattr(settings, "anthropic_api_key", "anthropic-hermetic")
    monkeypatch.setattr(settings, "agent_model_claude_sonnet_5_id", None)
    monkeypatch.setattr(settings, "agent_model_gpt_56_terra_id", None)
    run, _draft, _base = build_run_with_draft(db)
    _attach_real_confirmation(db, run)

    available, reason = field_drafting.availability(
        run, "SOL.INNOVATION_SOLUTION.EDITOR"
    )

    assert available is False
    assert reason == "live_model_id_missing"


def test_preflighted_synthetic_live_a2_is_truthfully_model_generated(
    db, monkeypatch
):
    run, draft, base = build_run_with_draft(db)
    _arm_live_a2(db, run, monkeypatch)
    available, reason = field_drafting.availability(
        run, "SOL.INNOVATION_SOLUTION.EDITOR"
    )
    assert (available, reason) == (True, "available")
    provider = _LiveA2()

    out = _run(db, run, draft, base, provider, operation_id="op-live-model")

    assert out.status == "succeeded"
    assert provider.calls == 1
    assert out.view["generation_kind"] == "model_generated"
    assert out.view["execution_mode"] == "live"
    assert out.view["ai_proposal"]["generation_kind"] == "model_generated"
    assert out.view["proposal"]["human_review_required"] is True


def test_evidence_requirement_control_recorded(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle()))
    ctrl = db.scalars(
        select(ControlResult).where(
            ControlResult.agent_invocation_id == out.invocation_id,
            ControlResult.control_id == "CTRL.EVIDENCE_REQUIREMENT",
        )
    ).all()
    assert ctrl and ctrl[0].status == "passed"
