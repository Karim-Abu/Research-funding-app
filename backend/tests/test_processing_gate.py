"""Milestone 9D.2 — cloud-processing confirmation + run-creation gate + A2 availability.

Covers: member AND lead_admin may confirm; eligibility blocks (internal/confidential/
NDA) regardless of role; the one-run confirmation gates cloud run creation, freezes the
policy snapshot, and is consumed exactly once; every allow/block is audited; the cloud
mode is never silently converted; A2 availability requires an available provider/fake.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.agents import field_drafting
from app.config.settings import get_settings
from app.db.models import AnalysisRun, AuditEvent, ProcessingConfirmation, RunPolicySnapshot
from app.db.models import SourceVersion
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    TOBIAS_EMAIL,
    TOBIAS_PASSWORD,
    login,
    project_payload,
    unsafe_headers,
)

POLICY = "1.1.0"


def _classification(sensitivity="public", origin="synthetic", nda=False, mode="cloud_assisted"):
    return {
        "sensitivity": sensitivity, "origin": origin, "processing_mode": mode,
        "web_research_mode": "off", "nda_applies": nda,
    }


def _mut(csrf, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _make_project(client, csrf, classification, title="Cloud Project"):
    payload = project_payload(title)
    payload["data_classification"] = classification
    res = client.post("/api/v1/projects", json=payload, headers=_mut(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _text_source(client, project_id, csrf, classification):
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Src", "text": "Cloud gate source content.",
              "data_classification": classification},
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    return res.json()["current_source_version_id"]


def _confirm(client, project_id, csrf, svids, policy=POLICY):
    return client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={"processing_mode": "cloud_assisted", "source_version_ids": svids,
              "accepted_policy_version": policy, "purpose": "Textentwürfe vorbereiten",
              "expires_after_one_run": True},
        headers=_mut(csrf),
    )


def _run_body(mode, svids=None, confirmation_id=None):
    settings = {"processing_mode": mode, "max_cost_chf": 5, "max_llm_calls": 5,
                "max_web_calls": 0}
    if svids is not None:
        settings["source_version_ids"] = svids
    if confirmation_id is not None:
        settings["internal_cloud_confirmation_id"] = confirmation_id
    return {"settings": settings}


def _create_run(client, project_id, csrf, body):
    return client.post(f"/api/v1/projects/{project_id}/runs", json=body, headers=_mut(csrf))


def _run_classification(run_id):
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run is not None
        return run.effective_data_classification
    finally:
        db.close()


def _replace_source_classification(source_version_id, classification):
    db = SessionLocal()
    try:
        version = db.get(SourceVersion, source_version_id)
        assert version is not None
        version.data_classification = classification
        db.commit()
    finally:
        db.close()


def _public_project_with_source(client, csrf):
    cls = _classification()
    project_id = _make_project(client, csrf, cls)
    svid = _text_source(client, project_id, csrf, cls)
    return project_id, svid


# --- confirmation endpoint: role + eligibility -----------------------------


def test_member_can_create_confirmation_and_cloud_run(client):
    # member, not lead_admin
    csrf = login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    confirm = _confirm(client, project_id, csrf, [svid])
    assert confirm.status_code == 201, confirm.text
    body = confirm.json()
    assert body["status"] == "valid"
    assert body["created_by"]  # the confirming member
    run = _create_run(client, project_id, csrf,
                      _run_body("cloud_assisted", [svid], body["confirmation_id"]))
    assert run.status_code == 202, run.text


def test_lead_admin_can_create_confirmation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)  # lead_admin
    project_id, svid = _public_project_with_source(client, csrf)
    assert _confirm(client, project_id, csrf, [svid]).status_code == 201


def test_confirmation_blocked_for_internal(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _make_project(client, csrf, _classification("internal", "real_project",
                                                      mode="deterministic_only"))
    res = _confirm(client, pid, csrf, ["any"])
    assert res.status_code == 403
    assert res.json()["code"] == "cloud_not_eligible_for_classification"


def test_confirmation_blocked_for_confidential(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _make_project(client, csrf, _classification("confidential", "real_project",
                                                      mode="local_only"))
    assert _confirm(client, pid, csrf, ["any"]).status_code == 403


def test_confirmation_blocked_for_nda(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _make_project(client, csrf, _classification(nda=True))
    assert _confirm(client, pid, csrf, ["any"]).status_code == 403


def test_confirmation_rejects_policy_mismatch(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    res = _confirm(client, project_id, csrf, [svid], policy="9.9.9")
    assert res.status_code == 422
    assert res.json()["code"] == "policy_version_mismatch"


def test_confirmation_rejects_foreign_source(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, _ = _public_project_with_source(client, csrf)
    res = _confirm(client, project_id, csrf, ["not-a-real-version"])
    assert res.status_code == 422
    assert res.json()["code"] == "unknown_source_version"


# --- run-creation gate -----------------------------------------------------


def test_cloud_run_without_confirmation_blocked(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    res = _create_run(client, project_id, csrf,
                      _run_body("cloud_assisted", [svid]))
    assert res.status_code == 422
    assert res.json()["code"] == "cloud_confirmation_required"


def test_cloud_run_uses_snapshot_source_classification(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _make_project(
        client, csrf, _classification("public", "synthetic"))
    svid = _text_source(
        client,
        project_id,
        csrf,
        _classification("confidential", "real_project", mode="local_only"),
    )
    cid = _confirm(client, project_id, csrf, [svid]).json()["confirmation_id"]

    cloud = _create_run(client, project_id, csrf,
                        _run_body("cloud_assisted", [svid], cid))
    assert cloud.status_code == 403
    assert cloud.json()["code"] == "cloud_not_eligible_for_classification"

    deterministic = _create_run(
        client, project_id, csrf, _run_body("deterministic_only", [svid])
    )
    assert deterministic.status_code == 202, deterministic.text
    classification = _run_classification(deterministic.json()["resource_id"])
    assert classification["sensitivity"] == "confidential"


def test_confidential_project_with_public_source_never_relaxes(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _make_project(
        client,
        csrf,
        _classification("confidential", "real_project", mode="local_only"),
    )
    svid = _text_source(client, project_id, csrf,
                        _classification("public", "synthetic"))

    deterministic = _create_run(
        client, project_id, csrf, _run_body("deterministic_only", [svid])
    )
    assert deterministic.status_code == 202, deterministic.text
    classification = _run_classification(deterministic.json()["resource_id"])
    assert classification["sensitivity"] == "confidential"

    cloud = _create_run(client, project_id, csrf,
                        _run_body("cloud_assisted", [svid]))
    assert cloud.status_code == 403
    assert cloud.json()["code"] == "cloud_not_eligible_for_classification"


def test_missing_source_classification_fails_closed(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    _replace_source_classification(svid, {})

    run = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert run.status_code == 202, run.text
    classification = _run_classification(run.json()["resource_id"])
    assert classification["sensitivity"] == "confidential"
    assert classification["processing_mode"] == "deterministic_only"
    assert classification["web_research_mode"] == "off"
    assert classification["nda_applies"] is False


def test_run_classification_merge_flag_false_uses_project_only(client, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "run_classification_source_merge_enabled", False)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _make_project(
        client, csrf, _classification("public", "synthetic"))
    svid = _text_source(
        client,
        project_id,
        csrf,
        _classification("confidential", "real_project", mode="local_only"),
    )

    run = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert run.status_code == 202, run.text
    classification = _run_classification(run.json()["resource_id"])
    assert classification["sensitivity"] == "public"


def test_public_project_with_public_source_stays_public(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)

    run = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert run.status_code == 202, run.text
    classification = _run_classification(run.json()["resource_id"])
    assert classification["sensitivity"] == "public"


def test_cloud_run_freezes_policy_snapshot(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    cid = _confirm(client, project_id, csrf, [svid]).json()["confirmation_id"]
    run = _create_run(client, project_id, csrf,
                      _run_body("cloud_assisted", [svid], cid))
    assert run.status_code == 202, run.text
    run_id = run.json()["resource_id"]
    db = SessionLocal()
    try:
        snap = db.get(RunPolicySnapshot, run_id)
        assert snap.processing_mode == "cloud_assisted"
        assert snap.cloud_confirmation_id == cid
        assert snap.provider_route_class == "anthropic_direct"
        assert snap.allowed_routes == ["anthropic_direct"]
        assert snap.policy_version == POLICY
        confirmation = db.get(ProcessingConfirmation, cid)
        assert confirmation.status == "used"  # one-run consumed
        assert confirmation.used_by_run_id == run_id
    finally:
        db.close()


def test_confirmation_is_one_run_only(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    cid = _confirm(client, project_id, csrf, [svid]).json()["confirmation_id"]
    first = _create_run(client, project_id, csrf,
                        _run_body("cloud_assisted", [svid], cid))
    assert first.status_code == 202
    # Reusing a consumed confirmation is rejected (gate runs before the active-run check).
    second = _create_run(client, project_id, csrf,
                         _run_body("cloud_assisted", [svid], cid))
    assert second.status_code == 422
    assert second.json()["code"] == "cloud_confirmation_invalid"


def test_deterministic_run_needs_no_confirmation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    res = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert res.status_code == 202


def test_blocked_cloud_run_is_audited(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_project_with_source(client, csrf)
    res = _create_run(client, project_id, csrf,
                      _run_body("cloud_assisted", [svid]))
    assert res.status_code == 422
    db = SessionLocal()
    try:
        blocked = db.query(AuditEvent).filter(
            AuditEvent.target_id == project_id, AuditEvent.action == "cloud_run.blocked",
        ).all()
        assert blocked, "every block must be audited"
        assert blocked[-1].detail["reason"] == "cloud_confirmation_required"
    finally:
        db.close()


# --- A2 availability (provider check) --------------------------------------


def _fake_run(mode, sensitivity="public", origin="synthetic", nda=False):
    return SimpleNamespace(
        processing_mode=mode,
        effective_data_classification=_classification(
            sensitivity, origin, nda),
    )


def test_a2_availability_deterministic_unavailable(client):
    ok, reason = field_drafting.availability(
        _fake_run("deterministic_only"), "SOL.INNOVATION_SOLUTION.EDITOR")
    assert ok is False
    assert reason == "processing_mode_deterministic_only"


def test_a2_availability_cloud_with_fake_provider(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    ok, reason = field_drafting.availability(
        _fake_run("cloud_assisted"), "SOL.INNOVATION_SOLUTION.EDITOR")
    assert ok is True
    assert reason == "available"


def test_a2_availability_provider_unavailable_without_fake(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", False)
    ok, reason = field_drafting.availability(
        _fake_run("cloud_assisted"), "SOL.INNOVATION_SOLUTION.EDITOR")
    assert ok is False
    assert reason == "provider_unavailable"


def test_a2_availability_blocked_for_confidential(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    ok, _ = field_drafting.availability(_fake_run(
        "cloud_assisted", "confidential", "real_project"), "SOL.INNOVATION_SOLUTION.EDITOR")
    assert ok is False


# --- R4.3: lokaler KI-Opt-in (local_only + Bestaetigung, Owner 2026-07-08) ----

def _confirm_local(client, project_id, csrf, svids, policy=POLICY):
    return client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={"processing_mode": "local_only", "source_version_ids": svids,
              "accepted_policy_version": policy,
              "purpose": "KI-Vorschlaege (lokaler Pfad)",
              "expires_after_one_run": True},
        headers=_mut(csrf),
    )


def test_local_confirmation_allowed_for_internal_and_confidential(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    for sensitivity in ("internal", "confidential"):
        cls = _classification(sensitivity, "real_project", mode="local_only")
        pid = _make_project(client, csrf, cls, title=f"Local {sensitivity}")
        svid = _text_source(client, pid, csrf, cls)
        res = _confirm_local(client, pid, csrf, [svid])
        assert res.status_code == 201, res.text


def test_local_confirmation_blocked_for_public_and_nda(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid_public = _make_project(client, csrf, _classification(), title="Local pub")
    res = _confirm_local(client, pid_public, csrf, ["any"])
    assert res.status_code == 403
    assert res.json()["code"] == "local_ai_not_eligible_for_classification"
    pid_nda = _make_project(
        client, csrf,
        _classification("internal", "real_project", nda=True, mode="local_only"),
        title="Local nda")
    assert _confirm_local(client, pid_nda, csrf, ["any"]).status_code == 403


def test_local_run_with_confirmation_consumes_it(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    cls = _classification("internal", "real_project", mode="local_only")
    pid = _make_project(client, csrf, cls, title="Local run")
    svid = _text_source(client, pid, csrf, cls)
    cid = _confirm_local(client, pid, csrf, [svid]).json()["confirmation_id"]
    run = _create_run(client, pid, csrf, _run_body("local_only", [svid], cid))
    assert run.status_code == 202, run.text
    db = SessionLocal()
    try:
        confirmation = db.get(ProcessingConfirmation, cid)
        assert confirmation.status == "used"
        assert confirmation.used_by_run_id
        snapshot = db.get(RunPolicySnapshot, confirmation.used_by_run_id)
        assert snapshot.provider_route_class == "fake_local"
    finally:
        db.close()


def test_local_run_without_confirmation_stays_rule_based(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    cls = _classification("confidential", "real_project", mode="local_only")
    pid = _make_project(client, csrf, cls, title="Local plain")
    svid = _text_source(client, pid, csrf, cls)
    res = _create_run(client, pid, csrf, _run_body("local_only", [svid]))
    assert res.status_code == 202, res.text  # regelbasiert, keine Freigabe noetig


def test_local_run_blocked_for_public_project(client):
    # Cloud-Bestaetigung eines public-Projekts oeffnet den lokalen Pfad nicht.
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _make_project(client, csrf, _classification(), title="Pub local run")
    svid = _text_source(client, pid, csrf, _classification())
    cid = _confirm(client, pid, csrf, [svid]).json()["confirmation_id"]
    res = _create_run(client, pid, csrf, _run_body("local_only", [svid], cid))
    assert res.status_code == 403
    assert res.json()["code"] == "local_ai_not_eligible_for_classification"
