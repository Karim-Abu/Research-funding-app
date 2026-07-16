"""Regression tests for the additive, versioned role/skill contracts."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.critic_review import A3Finding, _group_similar_findings
from app.agents.gateway import ModelRequest, _safe_input_artifact_refs
from app.agents.prompt_assets import role_skill_instructions_for
from app.agents.role_skills import RoleSkillRegistryError, get_role_skill_registry
from app.agents.schemas import validate_payload


def test_required_roles_and_all_a2_subsection_skills_are_registered():
    registry = get_role_skill_registry()
    assert set(registry.roles) == {
        "A1_FACT_EVIDENCE_ANALYST",
        "A2_INNOSUISSE_PROPOSAL_WRITER",
        "A3_INNOSUISSE_CRITICAL_REVIEWER",
        "RESEARCH_QUERY_PLANNER",
        "RESEARCH_EVIDENCE_SYNTHESIZER",
        "EVIDENCE_SUPPORT_VERIFIER",
    }
    expected = {
        ("INTRO.APP.EXECUTIVE_SUMMARY", None): "a2.executive_summary",
        ("VC.BUSINESS_TARGETS_MODEL.EDITOR", "3.1"): "a2.value_creation_3_1",
        ("VC.BUSINESS_TARGETS_MODEL.EDITOR", "3.2"): "a2.market_access_3_2",
        ("VC.BUSINESS_TARGETS_MODEL.EDITOR", "3.3"): "a2.impact_3_3",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.1"): "a2.state_of_the_art_4_1",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.2"): "a2.novelty_4_2",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.3"): "a2.quantifiable_goals_4_3",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.4"): "a2.preliminary_work_4_4",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.5.1"): "a2.ipr_4_5_1_to_4_5_4",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.5.2"): "a2.ipr_4_5_1_to_4_5_4",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.5.3"): "a2.ipr_4_5_1_to_4_5_4",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.5.4"): "a2.ipr_4_5_1_to_4_5_4",
        ("SOL.INNOVATION_SOLUTION.EDITOR", "4.6"): "a2.partner_suitability_4_6",
    }
    assert {
        binding: registry.skill_for_a2(*binding).skill_id for binding in expected
    } == expected


def test_role_and_skill_assets_are_independently_versioned():
    registry = get_role_skill_registry()
    root = Path(__file__).resolve().parents[1] / "app" / "agents"
    for role in registry.roles.values():
        assert (root / role.prompt_asset).stem == role.version
    for skill in registry.skills.values():
        assert (root / skill.prompt_asset).stem == skill.version
    prompt = role_skill_instructions_for(
        "A2.solution_innovation", "a2.quantifiable_goals_4_3"
    )
    assert prompt is not None
    assert "spezialisierter Redaktor" in prompt
    assert "Baseline" in prompt


def test_profile_cannot_select_a_skill_from_another_professional_role():
    with pytest.raises(RoleSkillRegistryError, match="not compatible"):
        get_role_skill_registry().resolve(
            "A1.project_fact_extraction", "a3.critical_review"
        )


def test_v2_a2_contract_requires_true_human_review_and_valid_character_count():
    payload = {
        "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
        "section_id": "3.1",
        "proposed_text": "Klarer Nutzen.",
        "character_count": len("Klarer Nutzen."),
        "character_limit": 15000,
        "confidence": "low",
        "requires_human_review": True,
    }
    assert validate_payload("ProposalSectionSuggestion@v2", payload).requires_human_review


def test_input_artifact_persistence_excludes_raw_values():
    request = ModelRequest(
        profile_id="A1.project_fact_extraction",
        workspace_id="ws",
        input_payload={},
        classification={},
        processing_mode="cloud_assisted",
        run_id="run-1",
        context_hash="safehash",
        allowed_fragment_ids=frozenset({"fragment-1"}),
        input_artifact_refs=(
            {
                "kind": "source",
                "source_id": "source-1",
                "raw_query": "vertraulicher Rohtext",
                "draft_text": "nicht speichern",
            },
        ),
    )
    refs = _safe_input_artifact_refs(request)
    assert refs[0] == {"kind": "source", "source_id": "source-1"}
    assert "vertraulicher Rohtext" not in str(refs)
    assert "nicht speichern" not in str(refs)


def test_a3_groups_a_large_set_of_identical_evidence_symptoms():
    findings = [
        A3Finding(
            origin_profile_id="A3.evidence_consistency",
            severity="warning",
            status="open",
            field_id="SOL.INNOVATION_SOLUTION.EDITOR",
            target_section="4.2",
            description="Marktclaim 123 benötigt einen Beleg.",
            recommended_next_action="Beleg ergänzen.",
        )
        for _ in range(100)
    ]
    grouped = _group_similar_findings(findings)
    assert len(grouped) == 1
    assert "100 ähnliche Hinweise" in grouped[0].description
