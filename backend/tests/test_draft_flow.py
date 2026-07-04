"""End-to-end deterministic template drafts: run -> drafts -> edit -> links -> API."""
from __future__ import annotations

import uuid

from app.db.models import DraftVersion, RequirementAssessment
from app.db.session import SessionLocal
from sqlalchemy import select
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

SOURCE_TEXT = (
    "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. "
    "Ein beitragsberechtigter Schweizer Forschungspartner ist eingebunden."
)
ABSTRACT = "INTRO.APP.ABSTRACT"


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _setup_run(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Quelle", "text": SOURCE_TEXT, "data_classification": VALID_CLASSIFICATION},
        headers=_mut(csrf),
    )
    for partner in (
        {"name": "Industrie AG", "partner_type": "implementation_partner", "country": "CH", "swiss_value_creation": True},
        {"name": "ETH", "partner_type": "research_partner", "country": "CH", "research_partner_eligibility_status": "eligible"},
    ):
        client.post(f"/api/v1/projects/{project_id}/partners", json=partner, headers=_mut(csrf))
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only", "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=_mut(csrf),
    ).json()
    assert client.get(f"/api/v1/runs/{run['resource_id']}").json()["status"] == "completed"
    return csrf, project_id, run["resource_id"]


def test_listfields_returns_template_drafts_in_order(client):
    _csrf, _pid, run_id = _setup_run(client)
    res = client.get(f"/api/v1/runs/{run_id}/fields")
    assert res.status_code == 200
    drafts = res.json()
    assert [d["field_id"] for d in drafts] == [
        "INTRO.APP.NAME", "INTRO.APP.NAME_EN", "INTRO.APP.ABSTRACT",
        "INTRO.APP.EXECUTIVE_SUMMARY", "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
        "VC.BUSINESS_TARGETS_MODEL.EDITOR", "SOL.INNOVATION_SOLUTION.EDITOR",
        "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
    ]
    abstract = next(d for d in drafts if d["field_id"] == ABSTRACT)
    assert abstract["status"] == "needs_review"
    assert abstract["character_limit"] == 300
    assert abstract["current_version"]["created_by"] == "template"
    assert abstract["open_issue_count"] >= 1  # placeholder remains
    assert abstract["open_issues"]
    assert abstract["evidence_links"] == []
    assert abstract["character_count"] == len(abstract["current_version"]["text"])


def test_getfield_and_unsupported_404(client):
    _csrf, _pid, run_id = _setup_run(client)
    assert client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").status_code == 200
    # Repeated/non-supported field → 404.
    assert client.get(
        f"/api/v1/runs/{run_id}/fields/PS.WORK_PACKAGE.DESCRIPTION"
    ).status_code == 404


def test_updatefield_creates_user_version_and_sets_recheck(client):
    csrf, _pid, run_id = _setup_run(client)
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    base = draft["current_version"]["draft_version_id"]
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
        json={"base_version_id": base, "text": "Kurzfassung über Förderfähigkeit."},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["current_version"]["created_by"] == "user"
    assert body["current_version"]["draft_version_id"] != base
    assert body["current_version"]["text"] == "Kurzfassung über Förderfähigkeit."
    assert client.get(f"/api/v1/runs/{run_id}").json()["recheck_required"] is True


def test_updatefield_stale_base_returns_409_without_overwrite(client):
    csrf, _pid, run_id = _setup_run(client)
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    base = draft["current_version"]["draft_version_id"]
    client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                 json={"base_version_id": base, "text": "Erste Änderung."},
                 headers=unsafe_headers(csrf))
    # Re-use the now-stale base.
    conflict = client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                            json={"base_version_id": base, "text": "Zweite Änderung."},
                            headers=unsafe_headers(csrf))
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "stale_base_version"
    current = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    assert current["current_version"]["text"] == "Erste Änderung."  # not overwritten


def test_updatefield_over_limit_returns_422(client):
    csrf, _pid, run_id = _setup_run(client)
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    base = draft["current_version"]["draft_version_id"]
    res = client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                       json={"base_version_id": base, "text": "ä" * 301},
                       headers=unsafe_headers(csrf))
    assert res.status_code == 422
    assert res.json()["code"] == "character_limit_exceeded"


def test_identical_text_creates_no_new_version(client):
    csrf, _pid, run_id = _setup_run(client)
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    base = draft["current_version"]["draft_version_id"]
    text = draft["current_version"]["text"]
    res = client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                       json={"base_version_id": base, "text": text},
                       headers=unsafe_headers(csrf))
    assert res.status_code == 200
    assert res.json()["current_version"]["draft_version_id"] == base


def test_updatefield_requires_csrf(client):
    _csrf, _pid, run_id = _setup_run(client)
    base = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()["current_version"]["draft_version_id"]
    res = client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                       json={"base_version_id": base, "text": "x"})
    assert res.status_code == 403


def test_workspace_isolation(client):
    _csrf, _pid, run_id = _setup_run(client)
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert client.get(f"/api/v1/runs/{run_id}/fields").status_code == 404
    assert client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").status_code == 404


def test_listfields_unauthenticated_401(client):
    assert client.get(f"/api/v1/runs/{uuid.uuid4()}/fields").status_code == 401


# --- draft evidence links --------------------------------------------------


def _an_anchor(client, run_id):
    anchors = client.get(f"/api/v1/runs/{run_id}/evidence").json()
    verified = [a for a in anchors if a["verification_status"] == "exact_verified"]
    assert verified
    return verified[0]["anchor_id"]


def test_evidence_link_lifecycle(client):
    csrf, _pid, run_id = _setup_run(client)
    anchor_id = _an_anchor(client, run_id)
    base = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()["current_version"]["draft_version_id"]

    # create
    created = client.post(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/evidence-links",
        json={"anchor_id": anchor_id, "base_version_id": base}, headers=_mut(csrf),
    )
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["target_type"] == "draft_version"
    assert link["target_id"] == base
    assert link["status"] == "active"

    # idempotent replay (same anchor+base) → same link
    replay = client.post(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/evidence-links",
        json={"anchor_id": anchor_id, "base_version_id": base}, headers=_mut(csrf),
    )
    assert replay.status_code == 201
    assert replay.json()["evidence_link_id"] == link["evidence_link_id"]

    # edit text → prior link becomes stale
    client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                 json={"base_version_id": base, "text": "Neuer Abstract."},
                 headers=unsafe_headers(csrf))
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    stale = [li for li in draft["evidence_links"] if li["evidence_link_id"] == link["evidence_link_id"]]
    assert stale and stale[0]["status"] == "stale"

    # delete link → 204 + removed
    deleted = client.delete(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/evidence-links/{link['evidence_link_id']}",
        headers=unsafe_headers(csrf),
    )
    assert deleted.status_code == 204
    draft2 = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    removed = [li for li in draft2["evidence_links"] if li["evidence_link_id"] == link["evidence_link_id"]]
    assert removed and removed[0]["status"] == "removed"


def test_evidence_link_foreign_anchor_404_and_stale_base_409(client):
    csrf, _pid, run_id = _setup_run(client)
    base = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()["current_version"]["draft_version_id"]
    # foreign anchor
    assert client.post(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/evidence-links",
        json={"anchor_id": str(uuid.uuid4()), "base_version_id": base}, headers=_mut(csrf),
    ).status_code == 404
    # stale base
    anchor_id = _an_anchor(client, run_id)
    assert client.post(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/evidence-links",
        json={"anchor_id": anchor_id, "base_version_id": str(uuid.uuid4())}, headers=_mut(csrf),
    ).status_code == 409


def test_graph_drafts_do_not_change_m4_assessments(client):
    _csrf, _pid, run_id = _setup_run(client)
    statuses = {a["requirement_id"]: a["status"] for a in client.get(f"/api/v1/runs/{run_id}/requirements").json()}
    assert statuses["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"] == "partial"


def test_initial_versions_are_template_never_agent(client):
    csrf, _pid, run_id = _setup_run(client)
    # Initial versions are templates.
    base = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()["current_version"]["draft_version_id"]
    # A user edit produces created_by=user; never agent.
    client.patch(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
                 json={"base_version_id": base, "text": "Bearbeitet."},
                 headers=unsafe_headers(csrf))
    db = SessionLocal()
    try:
        # Scope to this run's drafts: other tests (M9D A2 accept) create agent
        # versions in the shared test DB; this deterministic M6 run never does.
        from app.db.models import PortalFieldDraft

        draft_ids = [
            d.draft_id for d in db.scalars(
                select(PortalFieldDraft).where(PortalFieldDraft.run_id == run_id)
            )
        ]
        versions = list(
            db.scalars(select(DraftVersion).where(DraftVersion.draft_id.in_(draft_ids)))
        )
        assert versions
        kinds = {v.created_by for v in versions}
        assert kinds <= {"template", "user"}
        assert "agent" not in kinds
    finally:
        db.close()
