from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select

from app.agents import field_drafting
from app.db.models import DraftSuggestion, DraftVersion, SuggestionContextManifest
from app.db.session import SessionLocal
from tests.a2_helpers import (
    FIELD_ID, TARGET_SECTION, build_run_with_draft, fake_resolver,
    section_bundle, success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers


def _setup():
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(db)
        result = run.run_id, draft.draft_id, base
        db.commit()
        return result
    finally:
        db.close()


def _arm_fake(monkeypatch):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "ai_eval_mode", "off")
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    resolver = fake_resolver(success_fake(section_bundle()))
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", resolver)
    monkeypatch.setattr(
        field_drafting, "_default_resolver", lambda _config, _target_section=None: resolver
    )


def test_manifest_generate_and_accept_are_idempotent(client, monkeypatch):
    run_id, draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    path = f"/api/v1/runs/{run_id}/fields/{FIELD_ID}/redrafts"
    body = {
        "base_version_id": base,
        "target_section": TARGET_SECTION,
        "improvement_mode": "clearer",
        "selected_anchor_ids": [],
    }
    headers = {**unsafe_headers(csrf), "Idempotency-Key": "run3c-generate-key"}

    first = client.post(path, json=body, headers=headers)
    replay = client.post(path, json=body, headers=headers)
    assert first.status_code == replay.status_code == 202
    assert first.json()["operation_id"] == replay.json()["operation_id"]
    conflict = client.post(
        path, json={**body, "improvement_mode": "shorten"}, headers=headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"

    operation = client.get(
        f"/api/v1/operations/{first.json()['operation_id']}"
    ).json()
    assert operation["status"] == "succeeded"
    assert operation["result"]["accept_mode"] == "whole_suggestion_only"
    suggestion_id = operation["result"]["suggestion_id"]

    db = SessionLocal()
    try:
        suggestion = db.get(DraftSuggestion, suggestion_id)
        assert suggestion.manifest_id is not None
        manifest = db.get(SuggestionContextManifest, suggestion.manifest_id)
        assert manifest.schema_version == "SuggestionContextManifest@v1"
        assert manifest.component_hashes
        assert manifest.selected_anchor_ids == []
        before = db.scalar(select(func.count(DraftVersion.draft_version_id)).where(
            DraftVersion.draft_id == draft_id
        ))
    finally:
        db.close()

    accept_path = (
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}/suggestions/"
        f"{suggestion_id}/accept"
    )
    accept_headers = {
        **unsafe_headers(csrf), "Idempotency-Key": "run3c-accept-key"
    }
    barrier = Barrier(2)

    def accept_once():
        barrier.wait()
        return client.post(
            accept_path, json={"base_version_id": base}, headers=accept_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted, accepted_replay = list(
            pool.map(lambda _index: accept_once(), range(2))
        )
    assert accepted.status_code == accepted_replay.status_code == 200
    assert accepted.json()["draft_version_id"] == accepted_replay.json()["draft_version_id"]
    assert any(
        response.json()["idempotent_replay"]
        for response in (accepted, accepted_replay)
    )

    db = SessionLocal()
    try:
        after = db.scalar(select(func.count(DraftVersion.draft_version_id)).where(
            DraftVersion.draft_id == draft_id
        ))
        assert after == before + 1
    finally:
        db.close()


def test_manifest_suggestion_rejects_partial_legacy_patch(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    generated = client.post(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}/redrafts",
        json={"base_version_id": base, "target_section": TARGET_SECTION},
        headers={**unsafe_headers(csrf), "Idempotency-Key": "run3c-whole-key"},
    )
    operation_id = generated.json()["operation_id"]
    operation = client.get(f"/api/v1/operations/{operation_id}").json()
    response = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={
            "base_version_id": base,
            "text": "4.2 Nur ein Teil.",
            "source_operation_id": operation_id,
        },
        headers=unsafe_headers(csrf),
    )
    assert operation["status"] == "succeeded"
    assert response.status_code == 422
    assert response.json()["code"] == "whole_suggestion_required"


def test_run3c_runtime_openapi_exposes_additive_context_and_accept_contract(client):
    schema = client.get("/openapi.json").json()
    context_path = "/api/v1/runs/{run_id}/fields/{field_id}/suggestion-context-options"
    accept_path = (
        "/api/v1/runs/{run_id}/fields/{field_id}/suggestions/"
        "{suggestion_id}/accept"
    )
    assert "get" in schema["paths"][context_path]
    assert "post" in schema["paths"][accept_path]
    accept_parameters = schema["paths"][accept_path]["post"]["parameters"]
    key = next(item for item in accept_parameters if item["name"] == "Idempotency-Key")
    assert key["required"] is True
    redraft_parameters = schema["paths"][
        "/api/v1/runs/{run_id}/fields/{field_id}/redrafts"
    ]["post"]["parameters"]
    legacy_key = next(
        item for item in redraft_parameters if item["name"] == "Idempotency-Key"
    )
    assert legacy_key["required"] is False
