"""Run orchestration: createRun/lifecycle/async/LangGraph/cancel/recovery/security."""
from __future__ import annotations

import os
import sqlite3
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver

from app.db.models import AnalysisRun, AsyncOperation, UsageRecord
from app.db.session import SessionLocal
from app.runs.executor import recover_interrupted_runs, run_executor
from app.runs.graph import get_graph
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    ORIGIN,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)


def _run_body(processing_mode="deterministic_only", source_version_ids=None):
    settings = {
        "processing_mode": processing_mode,
        "max_cost_chf": 0,
        "max_llm_calls": 0,
        "max_web_calls": 0,
    }
    if source_version_ids is not None:
        settings["source_version_ids"] = source_version_ids
    return {"settings": settings}


def _create_run(client, project_id, csrf, body=None, key=None):
    return client.post(
        f"/api/v1/projects/{project_id}/runs", json=body or _run_body(),
        headers=_mut_headers(csrf, key),
    )


def _mut_headers(csrf, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _text_source(client, project_id, csrf, name="Src", text="Run source content."):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": name, "text": text, "data_classification": VALID_CLASSIFICATION},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _setup(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    source = _text_source(client, project_id, csrf)
    return csrf, project_id, source


def _insert_run(project_id, workspace_id, status="running", op_status="running"):
    db = SessionLocal()
    try:
        run_id = str(uuid.uuid4())
        op_id = str(uuid.uuid4())
        db.add(
            AnalysisRun(
                run_id=run_id, project_id=project_id, workspace_id=workspace_id,
                created_by="user-anna", status=status, current_stage="initialize",
                progress_percent=0, processing_mode="deterministic_only",
                effective_data_classification=VALID_CLASSIFICATION,
                snapshot_versions={}, recheck_required=False,
                semantic_findings_stale=False,
            )
        )
        db.add(
            AsyncOperation(
                operation_id=op_id, workspace_id=workspace_id, project_id=project_id,
                resource_type="run", resource_id=run_id, status=op_status,
            )
        )
        db.commit()
        return run_id, op_id
    finally:
        db.close()


# --- creation -------------------------------------------------------------


def test_create_run_returns_202_async_accepted(client):
    csrf, project_id, _ = _setup(client)
    res = _create_run(client, project_id, csrf)
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["resource_type"] == "run"
    assert body["status"] in ("queued", "running")
    assert body["operation_id"] and body["resource_id"]
    assert body["poll_url"] == f"/api/v1/operations/{body['operation_id']}"

    # TestClient runs the background task → run reaches a terminal technical state.
    run = client.get(f"/api/v1/runs/{body['resource_id']}").json()
    assert run["status"] == "completed"
    assert run["current_stage"] == "finalize_run"
    assert run["progress_percent"] == 100
    op = client.get(body["poll_url"]).json()
    assert op["status"] == "succeeded"


def test_no_valid_source_rejected(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)  # no sources
    res = _create_run(client, project_id, csrf)
    assert res.status_code == 422
    assert res.json()["code"] == "no_valid_sources"


def test_snapshot_excludes_foreign_and_invalid_versions(client):
    csrf, project_id, source = _setup(client)
    res = _create_run(
        client, project_id, csrf,
        body=_run_body(source_version_ids=["does-not-exist"]),
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_source_version"


def test_idempotent_replay_and_conflict(client):
    csrf, project_id, _ = _setup(client)
    key = uuid.uuid4().hex
    first = _create_run(client, project_id, csrf, key=key)
    assert first.status_code == 202
    # Wait for the first run to finish so the project is not active.
    second = _create_run(client, project_id, csrf, key=key)
    assert second.json()["operation_id"] == first.json()["operation_id"]
    conflict = _create_run(
        client, project_id, csrf, body=_run_body(processing_mode="local_only"),
        key=key,
    )
    assert conflict.status_code == 409


def test_active_run_blocks_second(client):
    csrf, project_id, _ = _setup(client)
    _insert_run(project_id, "ws-demo", status="running")
    res = _create_run(client, project_id, csrf)
    assert res.status_code == 409
    assert res.json()["code"] == "active_run_exists"


def test_processing_mode_cloud_rejected(client):
    csrf, project_id, _ = _setup(client)
    res = _create_run(client, project_id, csrf, body=_run_body("cloud_assisted"))
    assert res.status_code == 403
    assert res.json()["code"] == "cloud_processing_unavailable"


# --- lifecycle / cancel / resume -----------------------------------------


def test_list_and_get_run(client):
    csrf, project_id, _ = _setup(client)
    run_id = _create_run(client, project_id, csrf).json()["resource_id"]
    listing = client.get(f"/api/v1/projects/{project_id}/runs")
    assert listing.status_code == 200
    assert any(r["run_id"] == run_id for r in listing.json()["items"])


def test_cancel_running_run(client):
    csrf, project_id, _ = _setup(client)
    run_id, op_id = _insert_run(project_id, "ws-demo", status="running")
    res = client.post(f"/api/v1/runs/{run_id}/cancel", headers=_mut_headers(csrf))
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/operations/{op_id}").json()["status"] == "cancelled"


def test_cancel_terminal_run_rejected(client):
    csrf, project_id, _ = _setup(client)
    run_id = _create_run(client, project_id, csrf).json()["resource_id"]  # completed
    res = client.post(f"/api/v1/runs/{run_id}/cancel", headers=_mut_headers(csrf))
    assert res.status_code == 409


def test_resume_not_resumable(client):
    csrf, project_id, _ = _setup(client)
    run_id = _create_run(client, project_id, csrf).json()["resource_id"]
    res = client.post(
        f"/api/v1/runs/{run_id}/resume",
        json={
            "approval_id": "a", "expected_checkpoint_version": "c",
            "expected_review_package_version": "r",
        },
        headers=_mut_headers(csrf),
    )
    assert res.status_code == 409
    assert res.json()["code"] == "run_not_resumable"


# --- LangGraph / recovery -------------------------------------------------


def test_checkpoint_persists_and_survives_reopen(client):
    csrf, project_id, _ = _setup(client)
    run_id = _create_run(client, project_id, csrf).json()["resource_id"]
    # In-process checkpoint.
    snapshot = get_graph().get_state({"configurable": {"thread_id": run_id}})
    assert snapshot.values.get("run_id") == run_id
    # Re-open the checkpoint DB from disk (simulates a restart).
    conn = sqlite3.connect(os.environ["CHECKPOINT_DB_PATH"], check_same_thread=False)
    reopened = SqliteSaver(conn)
    tup = reopened.get_tuple({"configurable": {"thread_id": run_id}})
    conn.close()
    assert tup is not None


def test_finalize_never_overwrites_cancelled(client):
    _setup(client)
    run_id, _ = _insert_run("p-x", "ws-demo", status="cancelled")
    # Running the graph on a cancelled run must not complete it.
    get_graph().invoke(
        {"run_id": run_id, "project_id": "p-x", "workspace_id": "ws-demo", "cancelled": False},
        config={"configurable": {"thread_id": run_id}},
    )
    db = SessionLocal()
    try:
        assert db.get(AnalysisRun, run_id).status == "cancelled"
    finally:
        db.close()


def test_startup_recovery_marks_interrupted_failed(client):
    _setup(client)
    run_id, op_id = _insert_run("p-y", "ws-demo", status="running", op_status="running")
    recovered = recover_interrupted_runs()
    assert recovered >= 1
    db = SessionLocal()
    try:
        assert db.get(AnalysisRun, run_id).status == "failed"
        op = db.get(AsyncOperation, op_id)
        assert op.status == "failed"
        assert op.last_error_code == "OPERATION_INTERRUPTED"
    finally:
        db.close()


def test_usage_record_zero(client):
    csrf, project_id, _ = _setup(client)
    run_id = _create_run(client, project_id, csrf).json()["resource_id"]
    db = SessionLocal()
    try:
        usage = db.query(UsageRecord).filter(UsageRecord.run_id == run_id).first()
        assert usage is not None
        assert usage.provider is None and usage.cost_chf == 0
    finally:
        db.close()


# --- source deletion guard / security ------------------------------------


def test_source_delete_in_use_409(client):
    csrf, project_id, source = _setup(client)
    _create_run(client, project_id, csrf)  # freezes the source snapshot
    res = client.delete(
        f"/api/v1/sources/{source['source_id']}", headers=unsafe_headers(csrf)
    )
    assert res.status_code == 409
    assert res.json()["code"] == "SOURCE_IN_USE"


def test_create_run_requires_csrf(client):
    csrf, project_id, _ = _setup(client)
    res = client.post(
        f"/api/v1/projects/{project_id}/runs", json=_run_body(),
        headers={"Origin": ORIGIN, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert res.status_code == 403


def test_run_unauthenticated(client):
    assert client.get("/api/v1/runs/anything").status_code == 401


def test_operation_workspace_isolation(client):
    csrf, project_id, _ = _setup(client)
    op_id = _create_run(client, project_id, csrf).json()["operation_id"]
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert client.get(f"/api/v1/operations/{op_id}").status_code == 404
