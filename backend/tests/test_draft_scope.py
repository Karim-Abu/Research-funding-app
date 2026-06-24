"""M6 field scope (registry-driven) + deterministic template catalogue units."""
from __future__ import annotations

from app.drafts import build_template, char_count, has_placeholder
from app.drafts.charcount import within_limit
from app.registry import get_registry

reg = get_registry()

SUPPORTED_ORDER = [
    "INTRO.APP.NAME",
    "INTRO.APP.NAME_EN",
    "INTRO.APP.ABSTRACT",
    "INTRO.APP.EXECUTIVE_SUMMARY",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR",
    "SOL.INNOVATION_SOLUTION.EDITOR",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
]


def test_scope_is_exactly_the_supported_singletons_in_registry_order():
    assert [f.field_id for f in reg.m6_draft_fields()] == SUPPORTED_ORDER


def test_repeated_instance_fields_are_deferred():
    ids = {f.field_id for f in reg.m6_draft_fields()}
    for deferred in (
        "PS.WORK_PACKAGE.DESCRIPTION",
        "PS.WORK_PACKAGE.ACTIVITIES",
        "PS.MILESTONE.DESCRIPTION",
        "PS.MATERIAL_POSITION.RESEARCH_PARTNER.EXPLANATION",
        "PS.CASH_CONTRIBUTION.SALARY.PROJECT_TASKS",
    ):
        assert deferred not in ids


def test_non_writable_or_non_draft_fields_excluded():
    ids = {f.field_id for f in reg.m6_draft_fields()}
    assert "INTRO.APP.COMMUNICATION_LANGUAGE" not in ids  # action_only
    assert "INTRO.APP.NAME_EN_SAME_AS_ABOVE" not in ids  # structured_input
    assert "VC.BUSINESS_TARGETS_MODEL.CHARACTER_LIMIT" not in ids  # information


def test_template_deterministic_placeholdered_within_limit():
    for field in reg.m6_draft_fields():
        first = build_template(field, reg)
        second = build_template(field, reg)
        assert first == second  # deterministic
        assert has_placeholder(first)  # safe visible placeholder
        assert within_limit(first, field.character_limit)


def test_composite_editors_use_exact_registered_questions():
    sol = build_template(reg.portal_fields["SOL.INNOVATION_SOLUTION.EDITOR"], reg)
    assert "4.1 Describe the state of the art that you intend to advance" in sol
    assert "4.5 Please describe how the selected partners are suited" in sol
    vc = build_template(reg.portal_fields["VC.BUSINESS_TARGETS_MODEL.EDITOR"], reg)
    assert "3.1 Describe the business targets and the business model" in vc
    assert "3.2 Describe potential customers" in vc


def test_english_name_is_placeholder_only_not_translated():
    template = build_template(reg.portal_fields["INTRO.APP.NAME_EN"], reg)
    assert has_placeholder(template)
    assert template.startswith("[[Angabe ergänzen:")


def test_char_count_counts_unicode_code_points():
    assert char_count("äöüÄÖÜß") == 7
    assert char_count("") == 0
    assert char_count("Müller & Söhne") == 14
