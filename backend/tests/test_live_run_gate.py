"""Live-Lauf-Gate (Demo-Slice 2026-07-17): processing_mode=live + live-run-v1.

Öffentliche public_source-Projekte sowie synthetische/anonymisierte
Evaluationsfälle dürfen nach expliziter Live-Bestätigung einen Live-Lauf
erstellen; D1/D2/D3/Unknown bleiben blockiert; Demo-/Cloud-Bestätigungen
öffnen nie einen Live-Lauf (und umgekehrt); bestehende deterministische
Läufe werden von einem neuen Live-Lauf oder einem Klassifikationswechsel
nie mutiert.
"""
from __future__ import annotations

import uuid

from app.config.settings import get_settings
from app.db.models import AnalysisRun, ProcessingConfirmation, Project, RunPolicySnapshot
from app.db.session import SessionLocal
from app.runs.cloud_policy import (
    LIVE_RUN_CONFIRMATION_TEXT_VERSION,
    REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION,
    real_eval_confirmed,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, project_payload, unsafe_headers

POLICY = "1.1.0"


def _classification(sensitivity="public", origin="public_source", nda=False,
                    mode="cloud_assisted"):
    return {
        "sensitivity": sensitivity, "origin": origin, "processing_mode": mode,
        "web_research_mode": "off", "nda_applies": nda,
    }


def _mut(csrf, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _make_project(client, csrf, classification, title="Live Project"):
    payload = project_payload(title)
    payload["data_classification"] = classification
    res = client.post("/api/v1/projects", json=payload, headers=_mut(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _text_source(client, project_id, csrf, classification):
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Src", "text": "Live gate source content.",
              "data_classification": classification},
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    return res.json()["current_source_version_id"]


def _confirm(client, project_id, csrf, svids, mode="live", policy=POLICY):
    return client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={"processing_mode": mode, "source_version_ids": svids,
              "accepted_policy_version": policy,
              "purpose": "Live-KI-Vorschläge vorbereiten",
              "expires_after_one_run": True},
        headers=_mut(csrf),
    )


def _run_body(mode, svids, confirmation_id=None):
    settings = {"processing_mode": mode, "max_cost_chf": 5, "max_llm_calls": 5,
                "max_web_calls": 0, "source_version_ids": svids}
    if confirmation_id is not None:
        settings["internal_cloud_confirmation_id"] = confirmation_id
    return {"settings": settings}


def _create_run(client, project_id, csrf, body):
    return client.post(f"/api/v1/projects/{project_id}/runs", json=body,
                       headers=_mut(csrf))


def _public_source_project(client, csrf, title="Live public project"):
    cls = _classification()
    project_id = _make_project(client, csrf, cls, title=title)
    svid = _text_source(client, project_id, csrf, cls)
    return project_id, svid


def _arm_real_eval(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_eval_mode", "real")
    monkeypatch.setattr(get_settings(), "agent_fake_provider", False)


# --- Live-Bestätigung ---------------------------------------------------------


def test_live_confirmation_and_run_for_public_source(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf)

    confirm = _confirm(client, project_id, csrf, [svid])
    assert confirm.status_code == 201, confirm.text
    cid = confirm.json()["confirmation_id"]

    run = _create_run(client, project_id, csrf, _run_body("live", [svid], cid))
    assert run.status_code == 202, run.text
    run_id = run.json()["resource_id"]

    db = SessionLocal()
    try:
        row = db.get(AnalysisRun, run_id)
        assert row.processing_mode == "live"
        snap = db.get(RunPolicySnapshot, run_id)
        assert snap.processing_mode == "live"
        assert snap.cloud_confirmation_id == cid
        confirmation = db.get(ProcessingConfirmation, cid)
        assert confirmation.status == "used"
        assert confirmation.used_by_run_id == run_id
        assert confirmation.processing_mode == "live"
        assert (confirmation.confirmation_text_version
                == LIVE_RUN_CONFIRMATION_TEXT_VERSION)
        # Die Live-Bestätigung friert den Provider der Live-Primärroute (A2 =
        # Terra/OpenAI, provisorische Demo-Route) ein.
        assert confirmation.provider_route_class == "openai_direct"
    finally:
        db.close()


def test_live_confirmation_for_synthetic_project(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    cls = _classification(origin="synthetic")
    project_id = _make_project(client, csrf, cls, title="Live synthetic")
    svid = _text_source(client, project_id, csrf, cls)
    assert _confirm(client, project_id, csrf, [svid]).status_code == 201


def test_live_confirmation_blocked_without_real_eval(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_eval_mode", "off")
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf, "Live off")
    res = _confirm(client, project_id, csrf, [svid])
    assert res.status_code == 403
    assert res.json()["code"] == "live_mode_requires_real_eval"


def test_live_confirmation_blocked_for_restricted_classes(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    cases = [
        _classification("internal", "real_project", mode="deterministic_only"),
        _classification("confidential", "real_project", mode="local_only"),
        _classification(nda=True),
        # public + anonymized ⇒ UNKNOWN (deny-by-default) — bleibt blockiert.
        _classification("public", "anonymized"),
    ]
    for index, cls in enumerate(cases):
        pid = _make_project(client, csrf, cls, title=f"Live blocked {index}")
        res = _confirm(client, pid, csrf, ["any"])
        assert res.status_code == 403, res.text
        assert res.json()["code"] == "cloud_not_eligible_for_classification"


# --- Modus-exakter Bestätigungs-Match ----------------------------------------


def test_cloud_confirmation_never_opens_live_run(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf, "Cross demo→live")
    cloud_cid = _confirm(client, project_id, csrf, [svid],
                         mode="cloud_assisted").json()["confirmation_id"]
    res = _create_run(client, project_id, csrf,
                      _run_body("live", [svid], cloud_cid))
    assert res.status_code == 422
    assert res.json()["code"] == "cloud_confirmation_invalid"


def test_live_confirmation_never_opens_cloud_run(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf, "Cross live→demo")
    live_cid = _confirm(client, project_id, csrf, [svid]).json()["confirmation_id"]
    res = _create_run(client, project_id, csrf,
                      _run_body("cloud_assisted", [svid], live_cid))
    assert res.status_code == 422
    assert res.json()["code"] == "cloud_confirmation_invalid"


def test_live_run_without_confirmation_blocked(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf, "Live w/o confirm")
    res = _create_run(client, project_id, csrf, _run_body("live", [svid]))
    assert res.status_code == 422
    assert res.json()["code"] == "cloud_confirmation_required"


# --- Bestehende Läufe bleiben unverändert ------------------------------------


def test_live_run_leaves_existing_deterministic_run_untouched(client, monkeypatch):
    _arm_real_eval(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _public_source_project(client, csrf, "Det bleibt det")

    det = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert det.status_code == 202, det.text
    det_run_id = det.json()["resource_id"]

    cid = _confirm(client, project_id, csrf, [svid]).json()["confirmation_id"]
    live = _create_run(client, project_id, csrf, _run_body("live", [svid], cid))
    assert live.status_code == 202, live.text
    live_run_id = live.json()["resource_id"]

    db = SessionLocal()
    try:
        det_row = db.get(AnalysisRun, det_run_id)
        # Der alte Lauf bleibt als unveränderte Auditspur bestehen.
        assert det_row.processing_mode == "deterministic_only"
        live_row = db.get(AnalysisRun, live_run_id)
        assert live_row.processing_mode == "live"
        project = db.get(Project, project_id)
        # active_run_id zeigt nur nach erfolgreichem Abschluss auf den neuen
        # Lauf — nie auf einen bloss erstellten.
        if live_row.status == "completed":
            assert project.active_run_id == live_run_id
        else:
            assert project.active_run_id in (det_run_id, None)
    finally:
        db.close()


def test_classification_change_never_mutates_existing_run(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    cls = _classification("internal", "real_project", mode="deterministic_only")
    project_id = _make_project(client, csrf, cls, title="Cls switch")
    svid = _text_source(client, project_id, csrf, cls)
    run = _create_run(client, project_id, csrf,
                      _run_body("deterministic_only", [svid]))
    assert run.status_code == 202, run.text
    run_id = run.json()["resource_id"]

    db = SessionLocal()
    try:
        # Klassifikationswechsel (hier direkt persistiert — die API bietet
        # bewusst keinen Patch-Pfad) darf den bestehenden Lauf nie mutieren.
        project = db.get(Project, project_id)
        project.data_classification = _classification()
        db.commit()
        row = db.get(AnalysisRun, run_id)
        assert row.processing_mode == "deterministic_only"
        assert row.effective_data_classification["sensitivity"] == "internal"
    finally:
        db.close()


# --- real_eval_confirmed: Live-Zweig -----------------------------------------


def _persisted_live_run(db, *, text_version, confirmation_mode="live",
                        origin="public_source", sensitivity="public"):
    classification = _classification(sensitivity, origin, mode="cloud_assisted")
    pid = "live-proj-" + uuid.uuid4().hex[:8]
    db.add(Project(
        project_id=pid, workspace_id="ws-demo", title="Live gate unit",
        description="x",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=classification, created_by="user-anna", status="draft",
    ))
    rid = "live-run-" + uuid.uuid4().hex[:8]
    db.add(AnalysisRun(
        run_id=rid, project_id=pid, workspace_id="ws-demo", created_by="user-anna",
        status="completed", current_stage="finalize_run", progress_percent=100,
        processing_mode="live", effective_data_classification=classification,
        snapshot_versions={},
    ))
    db.add(ProcessingConfirmation(
        confirmation_id=str(uuid.uuid4()), project_id=pid, workspace_id="ws-demo",
        created_by="user-anna", status="used", processing_mode=confirmation_mode,
        source_version_ids=[], accepted_policy_version=POLICY,
        purpose="Live gate unit", provider_route_class="openai_direct",
        confirmation_text_version=text_version,
        data_classification_shown=classification, expires_after_one_run=True,
        used_by_run_id=rid,
    ))
    db.flush()
    return db.get(AnalysisRun, rid)


def test_real_eval_confirmed_accepts_live_confirmation(client):
    db = SessionLocal()
    try:
        run = _persisted_live_run(
            db, text_version=LIVE_RUN_CONFIRMATION_TEXT_VERSION)
        assert real_eval_confirmed(run) is True
    finally:
        db.rollback()
        db.close()


def test_real_eval_confirmed_rejects_wrong_text_version_for_live(client):
    db = SessionLocal()
    try:
        run = _persisted_live_run(
            db, text_version=REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION)
        assert real_eval_confirmed(run) is False
    finally:
        db.rollback()
        db.close()


def test_real_eval_confirmed_rejects_cloud_mode_confirmation_for_live(client):
    db = SessionLocal()
    try:
        run = _persisted_live_run(
            db, text_version=LIVE_RUN_CONFIRMATION_TEXT_VERSION,
            confirmation_mode="cloud_assisted")
        assert real_eval_confirmed(run) is False
    finally:
        db.rollback()
        db.close()


def test_real_eval_confirmed_rejects_internal_public_source_live_run(client):
    db = SessionLocal()
    try:
        run = _persisted_live_run(
            db, text_version=LIVE_RUN_CONFIRMATION_TEXT_VERSION,
            sensitivity="internal")
        assert real_eval_confirmed(run) is False
    finally:
        db.rollback()
        db.close()
