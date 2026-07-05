"""End-to-end: run → deterministic requirement assessments + issues + staleness."""
from __future__ import annotations

import uuid

from app.db.models import RequirementAssessment, RuleResult
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)


def _mut(csrf, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _text_source(client, project_id, csrf):
    # The run just needs one processed source; M4 evaluates partner/project
    # structure, not source content. Non-ASCII text now ingests cleanly
    # (Unicode ingestion fix, Milestone 4.1).
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Notiz", "text": "Quelle für die Prüfung der Förderfähigkeit.",
              "data_classification": VALID_CLASSIFICATION},
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "processed", res.text


def _add_partner(client, project_id, csrf, **fields):
    res = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": fields.pop("name", "Partner"), **fields}, headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    return res.json()


def _start_run(client, project_id, csrf):
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only",
                           "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=_mut(csrf),
    )
    assert res.status_code == 202, res.text
    return res.json()["resource_id"], res.json()["operation_id"]


def _status_map(assessments):
    return {a["requirement_id"]: a["status"] for a in assessments}


def test_eligible_partners_produce_partial_assessments(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    _text_source(client, project_id, csrf)
    _add_partner(
        client, project_id, csrf, name="Industrie AG",
        partner_type="implementation_partner", country="CH",
        swiss_value_creation=True,
    )
    _add_partner(
        client, project_id, csrf, name="ETH Zürich",
        partner_type="research_partner", country="CH",
        research_partner_eligibility_status="eligible",
    )
    run_id, op_id = _start_run(client, project_id, csrf)

    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    assert client.get(f"/api/v1/operations/{op_id}").json()["status"] == "succeeded"

    res = client.get(f"/api/v1/runs/{run_id}/requirements")
    assert res.status_code == 200, res.text
    assessments = res.json()
    statuses = _status_map(assessments)

    # Partner eligibility satisfied at machine level + hybrid basis → partial.
    assert statuses["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"] == "partial"
    assert statuses["REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"] == "partial"
    # Budget inputs are not captured in M4 → honest needs_input (never guessed).
    assert statuses["REQ.INNO.BUDGET.CASH_MIN5"] == "needs_input"
    # MAX18 (applies only without an implementation partner) is omitted.
    assert "REQ.INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER" not in statuses
    # Every status is a contract enum value; basis is a contract enum value.
    for a in assessments:
        assert a["status"] in {"fulfilled", "partial", "open", "needs_input", "blocked"}
        assert a["basis"] in {"deterministic_rule", "semantic_assessment", "hybrid"}
        assert a["stale"] is False
    # Non-fulfilled requirements carry an OpenIssue with a recommended action.
    partial = next(
        a for a in assessments
        if a["requirement_id"] == "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"
    )
    assert partial["open_issues"]
    issue = partial["open_issues"][0]
    assert issue["target_type"] == "requirement"
    assert issue["recommended_next_action"]
    assert issue["status"] == "open"
    assert issue["severity"] in {"blocker", "warning", "info"}
    # Slice 4 (E4-A): assessments expose the registry-declared field scope.
    from app.registry import get_registry

    registry_reqs = get_registry().requirements
    for a in assessments:
        expected = list(registry_reqs[a["requirement_id"]].affected_field_ids)
        assert a["affected_field_ids"] == expected
    assert partial["affected_field_ids"] == ["ORG.CP.IMPLEMENTATION_PARTNERS"]


def test_missing_partners_block_eligibility(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    _text_source(client, project_id, csrf)
    run_id, _ = _start_run(client, project_id, csrf)

    statuses = _status_map(client.get(f"/api/v1/runs/{run_id}/requirements").json())
    assert statuses["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"] == "blocked"
    assert statuses["REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"] == "blocked"

    # A not_applicable rule persists a RuleResult but no assessment.
    db = SessionLocal()
    try:
        rule_statuses = {
            r.rule_id: r.status
            for r in db.query(RuleResult).filter(RuleResult.run_id == run_id)
        }
        assert rule_statuses["INNO.DURATION.TYPICAL_6_36"] == "not_applicable"
        # 12 rule results persisted, but the not_applicable ones are not assessments.
        assert len(rule_statuses) == 12
        assert db.query(RequirementAssessment).filter(
            RequirementAssessment.run_id == run_id
        ).count() < 12
    finally:
        db.close()


def test_assessments_go_stale_after_input_change(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    _text_source(client, project_id, csrf)
    _add_partner(
        client, project_id, csrf, partner_type="implementation_partner",
        swiss_value_creation=True,
    )
    run_id, _ = _start_run(client, project_id, csrf)

    fresh = client.get(f"/api/v1/runs/{run_id}/requirements").json()
    assert all(a["stale"] is False for a in fresh)

    # Change the structured inputs after the run was frozen.
    _add_partner(
        client, project_id, csrf, name="Neu",
        partner_type="research_partner", country="CH",
        research_partner_eligibility_status="eligible",
    )
    stale = client.get(f"/api/v1/runs/{run_id}/requirements").json()
    assert stale and all(a["stale"] is True for a in stale)


def test_list_requirements_workspace_isolation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    _text_source(client, project_id, csrf)
    run_id, _ = _start_run(client, project_id, csrf)

    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert client.get(f"/api/v1/runs/{run_id}/requirements").status_code == 404
