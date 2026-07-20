"""End-to-end deterministic template drafts: run -> drafts -> edit -> links -> API."""
from __future__ import annotations

import hashlib
import uuid

from app.config.settings import get_settings
from app.db.models import AnalysisRun, DraftVersion, PortalFieldDraft, RequirementAssessment
from app.db.session import SessionLocal
from app.repositories import draft_suggestions as suggestions_repo
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
    # RUN 2A Slice 1: Hybrid-Pass ist fulfilled (Bestätigung = separate Dimension).
    assert statuses["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"] == "fulfilled"


# --- draft carry-over (Slice 2, Council E1-A) --------------------------------


def _start_second_run(client, csrf, project_id) -> str:
    """Start another run on the same project (the prior one is completed)."""
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only", "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=_mut(csrf),
    ).json()
    run_id = run["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return run_id


def _patch_abstract(client, csrf, run_id, text) -> dict:
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
        json={"base_version_id": draft["current_version"]["draft_version_id"], "text": text},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_carry_over_user_edit_into_next_run(client):
    """T1/T2: run1 edit → run2 carries the text; first run stays template."""
    csrf, project_id, run1 = _setup_run(client)
    first = client.get(f"/api/v1/runs/{run1}/fields/{ABSTRACT}").json()
    assert first["current_version"]["created_by"] == "template"  # T2 (Erst-Run)

    _patch_abstract(client, csrf, run1, "Kurzfassung aus Durchlauf eins.")
    run2 = _start_second_run(client, csrf, project_id)
    carried = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
    assert carried["current_version"]["text"] == "Kurzfassung aus Durchlauf eins."
    assert carried["current_version"]["created_by"] == "carried_over"
    assert carried["open_issue_count"] == 0  # no placeholder in the carried text


def test_carry_over_ignores_proposed_suggestions(client):
    """T3: a proposed A2 suggestion stays on the old run and is never carried."""
    csrf, project_id, run1 = _setup_run(client)
    _patch_abstract(client, csrf, run1, "Manueller Stand.")
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run1)
        draft = db.scalar(
            select(PortalFieldDraft).where(
                PortalFieldDraft.run_id == run1, PortalFieldDraft.field_id == ABSTRACT
            )
        )
        suggestions_repo.create(
            db, run, draft_id=draft.draft_id,
            base_version_id=draft.current_version_id, field_id=ABSTRACT,
            profile_id="M9D.field_drafting_suggestion",
                operation_id=str(uuid.uuid4()), agent_invocation_id=None,
                prompt_version=None, model_route=None, model_id=None,
                generation_kind="fake_demo", target_section=None,
                section_result_json=None,
                suggested_text="KI-Vorschlag, nie übernommen.", rationale=None,
            evidence_anchor_ids=[], open_issue_ids=[], placeholders=[],
            character_count=28,
        )
        db.commit()
    finally:
        db.close()

    run2 = _start_second_run(client, csrf, project_id)
    carried = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
    assert carried["current_version"]["text"] == "Manueller Stand."
    assert carried["current_version"]["created_by"] == "carried_over"

    db = SessionLocal()
    try:
        old_draft = db.scalar(
            select(PortalFieldDraft).where(
                PortalFieldDraft.run_id == run1, PortalFieldDraft.field_id == ABSTRACT
            )
        )
        suggestion = suggestions_repo.get_proposed_for(
            db, run1, old_draft.draft_id, old_draft.current_version_id
        )
        assert suggestion is not None  # stays proposed on the old run
    finally:
        db.close()


def test_carry_over_with_placeholder_sets_open_issue(client):
    """T4: a carried placeholder keeps the deterministic field issue open."""
    csrf, project_id, run1 = _setup_run(client)
    _patch_abstract(client, csrf, run1, "Kurzfassung. [[Angabe ergänzen: Marktzahlen]]")
    run2 = _start_second_run(client, csrf, project_id)
    carried = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
    assert carried["current_version"]["created_by"] == "carried_over"
    assert carried["open_issue_count"] == 1
    assert carried["open_issues"]


def test_carry_over_does_not_carry_approvals(client):
    """T5: run2 starts unapproved; approval blockers stay fully effective."""
    csrf, project_id, run1 = _setup_run(client)
    _patch_abstract(client, csrf, run1, "Kurzfassung ohne Platzhalter.")
    pkg1 = client.get(f"/api/v1/runs/{run1}/review").json()
    client.post(
        f"/api/v1/runs/{run1}/rechecks",
        json={"expected_review_package_version": pkg1["review_package_version"], "changed_target_refs": []},
        headers=_mut(csrf),
    )
    pkg1 = client.get(f"/api/v1/runs/{run1}/review").json()
    approved = client.post(
        f"/api/v1/runs/{run1}/approvals",
        json={
            "scope": "field", "scope_id": ABSTRACT,
            "expected_approval_scope_hash": pkg1["current_approval_scope_hash"],
            "expected_review_package_version": pkg1["review_package_version"],
            "confirm_not_submission_approval": True,
        },
        headers=_mut(csrf),
    )
    assert approved.status_code == 201, approved.text

    run2 = _start_second_run(client, csrf, project_id)
    pkg2 = client.get(f"/api/v1/runs/{run2}/review").json()
    assert pkg2["approval_status"] != "approved"  # nothing carried
    # Run-scope approval on run2 is still blocked (other fields carry templates
    # with placeholders) — the blocker mechanics are untouched.
    blocked = client.post(
        f"/api/v1/runs/{run2}/approvals",
        json={
            "scope": "run", "scope_id": run2,
            "expected_approval_scope_hash": pkg2["current_approval_scope_hash"],
            "expected_review_package_version": pkg2["review_package_version"],
            "confirm_not_submission_approval": True,
        },
        headers=_mut(csrf),
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "approval_blocked"


def test_carry_over_flag_off_keeps_template_behavior(client, monkeypatch):
    """T6: draft_carry_over_enabled=false → exactly today's template path."""
    csrf, project_id, run1 = _setup_run(client)
    _patch_abstract(client, csrf, run1, "Wird bei Flag off nicht übernommen.")
    monkeypatch.setattr(get_settings(), "draft_carry_over_enabled", False)
    run2 = _start_second_run(client, csrf, project_id)
    draft = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
    assert draft["current_version"]["created_by"] == "template"
    assert "[[Angabe ergänzen:" in draft["current_version"]["text"]


def test_newer_template_only_run_does_not_displace_user_work(client, monkeypatch):
    """T7: a template-only run in between (flag off) must not shadow the older
    user edit — the newest *meaningful* version wins."""
    csrf, project_id, run1 = _setup_run(client)
    _patch_abstract(client, csrf, run1, "Nutzertext aus Durchlauf eins.")
    monkeypatch.setattr(get_settings(), "draft_carry_over_enabled", False)
    run2 = _start_second_run(client, csrf, project_id)
    assert (
        client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()["current_version"]["created_by"]
        == "template"
    )
    monkeypatch.setattr(get_settings(), "draft_carry_over_enabled", True)
    run3 = _start_second_run(client, csrf, project_id)
    third = client.get(f"/api/v1/runs/{run3}/fields/{ABSTRACT}").json()
    assert third["current_version"]["text"] == "Nutzertext aus Durchlauf eins."
    assert third["current_version"]["created_by"] == "carried_over"


def test_carry_over_over_limit_text_is_kept_and_blocks_review(client):
    """T8: over-limit legacy text is carried (never dropped); the existing
    draft_over_limit review blocker gates the new run."""
    csrf, project_id, run1 = _setup_run(client)
    long_text = "x" * 400  # ABSTRACT limit is 300
    db = SessionLocal()
    try:
        draft = db.scalar(
            select(PortalFieldDraft).where(
                PortalFieldDraft.run_id == run1, PortalFieldDraft.field_id == ABSTRACT
            )
        )
        # Simulate legacy data: an over-limit user version set directly (the
        # API guards edits, so this state can only pre-exist).
        version = DraftVersion(
            draft_version_id=str(uuid.uuid4()), draft_id=draft.draft_id,
            text=long_text, character_count=len(long_text), created_by="user",
            content_hash=hashlib.sha256(long_text.encode("utf-8")).hexdigest(),
            base_version_id=draft.current_version_id,
        )
        db.add(version)
        db.flush()
        draft.current_version_id = version.draft_version_id
        db.commit()
    finally:
        db.close()

    run2 = _start_second_run(client, csrf, project_id)
    carried = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
    assert carried["current_version"]["text"] == long_text
    assert carried["current_version"]["created_by"] == "carried_over"

    pkg = client.get(f"/api/v1/runs/{run2}/review").json()
    over_limit = [
        f for f in pkg["findings"]
        if f["field_id"] == ABSTRACT and f["severity"] == "blocker"
        and "Limit" in f["description"]
    ]
    assert over_limit, pkg["findings"]


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
