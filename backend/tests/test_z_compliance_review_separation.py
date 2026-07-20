"""RUN 2A Slice 1 — Compliance-Status und Human Review sind getrennte Dimensionen.

Owner-Entscheide: 52 % im Band 40–60 % und exakt 5 % Barbeitrag sind
``fulfilled``; die offene menschliche Bestätigung läuft separat
(``review_status`` / ``human_review_count``) und stuft die Compliance nie
herab. Guidance-Anforderungen (Registry: severity == "info") zählen in keiner
Quote und erscheinen nie als offen. Precheck, Anforderungsscreen und
Status-View zeigen dieselbe Wahrheit.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import RuleResult
from app.db.session import SessionLocal
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project, login, unsafe_headers
from tests.review_helpers import _IMPL_PARTNER, _RESEARCH_PARTNER, mut

SHARE_REQ = "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60"
CASH_REQ = "REQ.INNO.BUDGET.CASH_MIN5"
GUIDANCE_REQ = "REQ.INNO.BUDGET.NO_FINANCIAL_CAP"

# 52 % Umsetzungspartner-Anteil (47'000 + 5'000 von 100'000), exakt 5 % Cash.
BUDGET_52_5 = {
    "direct_total_project_costs_excluding_overhead": 100000,
    "implementation_own_contribution": 47000,
    "cash_contribution": 5000,
    "total_requested_funding": 48000,
    "duration_months": 24,
}


def _setup_run_with_budget(client, budget: dict = BUDGET_52_5):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, f"Compliance {uuid.uuid4().hex[:6]}")
    res = client.patch(
        f"/api/v1/projects/{project_id}", json=budget, headers=unsafe_headers(csrf)
    )
    assert res.status_code == 200, res.text
    for partner in (_IMPL_PARTNER, _RESEARCH_PARTNER):
        assert client.post(
            f"/api/v1/projects/{project_id}/partners", json=partner,
            headers=mut(csrf),
        ).status_code == 201
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {
            "processing_mode": "deterministic_only",
            "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0,
        }},
        headers=mut(csrf),
    ).json()
    run_id = run["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return csrf, project_id, run_id


def _assessments_by_id(client, run_id) -> dict:
    res = client.get(f"/api/v1/runs/{run_id}/requirements")
    assert res.status_code == 200, res.text
    return {a["requirement_id"]: a for a in res.json()}


def test_52_percent_and_exact_5_percent_are_fulfilled_with_open_review(client):
    csrf, project_id, run_id = _setup_run_with_budget(client)
    by_id = _assessments_by_id(client, run_id)

    for req_id in (SHARE_REQ, CASH_REQ):
        assessment = by_id[req_id]
        # Compliance: maschinell bestanden ⇒ fulfilled — nie «Teilweise erfüllt».
        assert assessment["status"] == "fulfilled", assessment
        assert assessment["basis"] == "hybrid"
        # Human Review: separate Dimension, offen.
        assert assessment["review_status"] == "required"
        assert assessment["display_mode"] == "requirement"
        issue_types = {i["issue_type"] for i in assessment["open_issues"]}
        assert "human_confirmation_pending" in issue_types

    # Konsistenz (Mandats-Test 9): der Budget-Precheck zeigt dieselbe Wahrheit.
    precheck = client.get(f"/api/v1/projects/{project_id}/budget/precheck").json()
    by_rule = {c["rule_id"]: c for c in precheck["checks"]}
    assert by_rule["INNO.BUDGET.IMPLEMENTATION_SHARE_40_60"]["status"] == "fulfilled"
    assert by_rule["INNO.BUDGET.CASH_MIN5"]["status"] == "fulfilled"


def test_fulfilled_with_open_review_counts_only_in_human_review(client):
    _, _, run_id = _setup_run_with_budget(client)
    by_id = _assessments_by_id(client, run_id)
    status_view = client.get(f"/api/v1/runs/{run_id}/review/status").json()

    # Die EINE Zählquelle: offene Review-Issues ⇔ review_status == required.
    required = [a for a in by_id.values() if a["review_status"] == "required"]
    assert status_view["human_review_count"] == len(required)
    assert status_view["human_review_count"] >= 2  # beide Budget-Hybride offen

    # fulfilled bleibt fulfilled in den Compliance-Zählern: keine offene
    # Bestätigung erzeugt einen Blocker/Warning-Zähler (Issue-Severity info).
    for a in required:
        if a["status"] == "fulfilled":
            for issue in a["open_issues"]:
                if issue["issue_type"] == "human_confirmation_pending":
                    assert issue["severity"] == "info"


def test_exact_40_60_boundaries_stay_fulfilled(client):
    boundary = dict(BUDGET_52_5)
    boundary.update({"implementation_own_contribution": 35000})  # 40.0 %
    _, _, run_id = _setup_run_with_budget(client, boundary)
    assert _assessments_by_id(client, run_id)[SHARE_REQ]["status"] == "fulfilled"

    boundary.update({"implementation_own_contribution": 55000})  # 60.0 %
    _, _, run_id = _setup_run_with_budget(client, boundary)
    assert _assessments_by_id(client, run_id)[SHARE_REQ]["status"] == "fulfilled"


def test_below_5_percent_cash_is_blocked_not_fulfilled(client):
    below = dict(BUDGET_52_5)
    below.update({"cash_contribution": 4990, "implementation_own_contribution": 47010})
    _, _, run_id = _setup_run_with_budget(client, below)
    cash = _assessments_by_id(client, run_id)[CASH_REQ]
    assert cash["status"] == "blocked"  # Severity blocker ⇒ blocked, nie fulfilled.


def test_confirmation_changes_only_review_status(client):
    csrf, _, run_id = _setup_run_with_budget(client)
    share = _assessments_by_id(client, run_id)[SHARE_REQ]
    assert share["status"] == "fulfilled"
    assert share["review_status"] == "required"
    before_count = client.get(
        f"/api/v1/runs/{run_id}/review/status"
    ).json()["human_review_count"]

    res = client.post(
        f"/api/v1/runs/{run_id}/human-decisions",
        json={
            "target_type": "requirement_assessment",
            "target_id": share["assessment_id"],
            "action": "confirm",
        },
        headers=mut(csrf),
    )
    assert res.status_code == 201, res.text

    after = _assessments_by_id(client, run_id)[SHARE_REQ]
    assert after["review_status"] == "confirmed"
    # Compliance-Status und deterministisches RuleResult bleiben unverändert.
    assert after["status"] == "fulfilled"
    with SessionLocal() as db:
        rule_result = db.scalar(
            select(RuleResult).where(
                RuleResult.run_id == run_id,
                RuleResult.rule_id == "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            )
        )
        assert rule_result.status == "passed"
    # Die Bestätigung reduziert die offene Review-Zählung um genau eins.
    after_count = client.get(
        f"/api/v1/runs/{run_id}/review/status"
    ).json()["human_review_count"]
    assert after_count == before_count - 1


def test_guidance_no_financial_cap_counts_nowhere(client):
    _, _, run_id = _setup_run_with_budget(client)
    by_id = _assessments_by_id(client, run_id)

    guidance = by_id[GUIDANCE_REQ]
    assert guidance["display_mode"] == "guidance"
    # Nie offen/blockiert, keine Issues, keine Review-Pflicht.
    assert guidance["status"] == "fulfilled"
    assert guidance["review_status"] == "not_required"
    assert guidance["open_issues"] == []

    # Guidance erhöht keine Zähler (Blocker/Warnung/Human Review).
    status_view = client.get(f"/api/v1/runs/{run_id}/review/status").json()
    required_non_guidance = [
        a for a in by_id.values()
        if a["review_status"] == "required" and a["display_mode"] == "requirement"
    ]
    assert status_view["human_review_count"] == len(required_non_guidance)


def test_guidance_without_data_is_omitted_not_needs_input(client):
    no_funding = dict(BUDGET_52_5)
    no_funding.pop("total_requested_funding")
    _, _, run_id = _setup_run_with_budget(client, no_funding)
    by_id = _assessments_by_id(client, run_id)
    # Ohne auswertbare Angabe erscheint der Hinweis gar nicht — insbesondere
    # nie als needs_input/open in der Anforderungsliste.
    assert GUIDANCE_REQ not in by_id
