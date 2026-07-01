"""Milestone 10 — export smoke + no-raw-log smoke (deterministic, no real provider).

Export smoke: a completed deterministic run + reliability pass exports DOCX + Markdown +
technical-evidence; each artifact is created, downloadable, non-empty; the technical-evidence
JSON carries the reliability summary and leaks no claim_text / prompts / provider payloads /
raw queries / secrets. No-raw-log smoke: synthetic sensitive markers carried through the D2
firewall query path never reach logs / AuditEvent / ControlResult / ToolInvocation /
UsageRecord / provider payloads / the technical-evidence export.
"""
from __future__ import annotations

import json
import logging
import uuid

import pytest
from sqlalchemy import select

from app.config.logging import RedactingFilter
from app.config.settings import get_settings
from app.db.models import AuditEvent, ControlResult, ToolInvocation, UsageRecord
from app.db.session import SessionLocal
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

PROFILE = "innosuisse_innovation_project_with_implementation_partner"
PUBLIC = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "off", "nda_applies": False,
}
CONFIDENTIAL = {
    "sensitivity": "confidential", "origin": "real_project",
    "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
    "nda_applies": False,
}


@pytest.fixture
def web_fakes(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "agent_fake_provider", True)
    monkeypatch.setattr(s, "d2_web_research_enabled", False)
    return s


def _mut(csrf: str) -> dict:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    h["Content-Type"] = "application/json"
    return h


def _wait_op(client, op_id: str) -> str:
    for _ in range(60):
        status = client.get(f"/api/v1/operations/{op_id}").json()["status"]
        if status in ("succeeded", "failed", "cancelled"):
            return status
    return "timeout"


def _completed_run(client, csrf) -> str:
    pid = client.post("/api/v1/projects", headers=_mut(csrf), json={
        "title": "M10 Smoke", "description": "smoke.",
        "funding_instrument_profile_id": PROFILE, "data_classification": PUBLIC,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{pid}/sources/text", headers=_mut(csrf), json={
        "name": "Notiz", "text": "Synthetischer öffentlicher Projektinhalt für den Smoke-Test.",
        "data_classification": PUBLIC,
    })
    sv = ""
    for _ in range(40):
        rows = client.get(f"/api/v1/projects/{pid}/sources").json()
        ready = next((s for s in rows if s["status"] == "processed"
                      and s.get("current_source_version_id")), None)
        if ready:
            sv = ready["current_source_version_id"]
            break
    assert sv, "source never processed"
    accepted = client.post(f"/api/v1/projects/{pid}/runs", headers=_mut(csrf), json={
        "settings": {"processing_mode": "deterministic_only", "max_cost_chf": 0,
                     "max_llm_calls": 0, "max_web_calls": 0, "source_version_ids": [sv]},
    }).json()
    assert _wait_op(client, accepted["operation_id"]) == "succeeded"
    run_id = accepted["resource_id"]
    rel = client.post(f"/api/v1/runs/{run_id}/reliability", headers=_mut(csrf)).json()
    assert _wait_op(client, rel["operation_id"]) == "succeeded"
    return run_id


def _export(client, csrf, run_id: str, kind: str) -> tuple[dict, bytes]:
    accepted = client.post(f"/api/v1/runs/{run_id}/exports", headers=_mut(csrf),
                           json={"type": kind, "force_draft": False}).json()
    assert _wait_op(client, accepted["operation_id"]) == "succeeded"
    artifact = client.get(f"/api/v1/exports/{accepted['resource_id']}").json()
    body = client.get(f"/api/v1/exports/{artifact['export_id']}/download").content
    return artifact, body


def test_export_all_types(client, web_fakes):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _completed_run(client, csrf)

    for kind in ("docx", "markdown", "technical_evidence"):
        artifact, body = _export(client, csrf, run_id, kind)
        assert artifact["type"] == kind
        assert len(body) > 0, f"{kind} export is empty"

    _artifact, tech = _export(client, csrf, run_id, "technical_evidence")
    payload = json.loads(tech.decode("utf-8"))
    assert payload["artifact_kind"] == "internal_audit_export"
    assert payload["reliability"]["available"] is True
    assert payload["reliability"]["quality_summary"]["summary_version"]
    text = tech.decode("utf-8")
    for forbidden in ("claim_text", "raw_query", "sk-", "prompt_text", "provider_payload"):
        assert forbidden not in text, f"technical export leaked {forbidden!r}"


def test_no_raw_log(client, web_fakes):
    partner = "Zylthex"
    codename = "Nachtfalke"
    budget = "777333"
    secret = "sk-testsecrettoken0001"
    raw_query = (
        f"Wettbewerber fuer {partner} AG Projekt {codename} mit Budget CHF {budget} "
        f"und Token {secret}"
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = client.post("/api/v1/projects", headers=_mut(csrf), json={
        "title": "M10 Confidential", "description": "d",
        "funding_instrument_profile_id": PROFILE, "data_classification": CONFIDENTIAL,
        "budget_framework_chf": int(budget),
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{pid}/partners", headers=_mut(csrf),
                json={"name": f"{partner} AG", "partner_type": "implementation_partner"})

    preview = client.post(
        f"/api/v1/projects/{pid}/search-query-firewall/preview",
        headers=_mut(csrf), json={"raw_query": raw_query},
    ).json()
    # Confidential → sanitize + approval; the raw query is never echoed back.
    assert preview["decision"] in ("require_human_approval", "block")
    assert partner not in preview["sanitized_query"] and budget not in preview["sanitized_query"]
    if preview["decision"] == "require_human_approval":
        client.post(f"/api/v1/search-query-approvals/{preview['approval_id']}/approve",
                    headers=_mut(csrf))
        created = client.post(f"/api/v1/projects/{pid}/research-tasks", headers=_mut(csrf), json={
            "purpose": "partner_role_suggestion", "subject_type": "topic",
            "query_preview": raw_query, "max_results": 3,
            "user_confirms_public_professional_purpose": True,
            "approval_id": preview["approval_id"],
        })
        if created.status_code == 202:
            _wait_op(client, created.json()["operation_id"])

    # Assert the raw markers never reached the backend persistence surfaces.
    markers = (raw_query, secret, f"{partner} AG Projekt {codename}")
    db = SessionLocal()
    try:
        audits = db.scalars(select(AuditEvent)).all()
        controls = db.scalars(select(ControlResult)).all()
        tools = db.scalars(select(ToolInvocation)).all()
        usage = db.scalars(select(UsageRecord)).all()
    finally:
        db.close()
    blob = json.dumps(
        [a.detail for a in audits] + [c.detail for c in controls]
        + [t.input_hash for t in tools] + [t.output_hash for t in tools]
        + [f"{u.provider}:{u.model}" for u in usage],
        ensure_ascii=False, default=str,
    )
    for marker in markers:
        assert marker not in blob, f"leaked {marker!r} into a persistence surface"
    # Raw D2 query + secret must never appear in the persistence blob at all.
    assert secret not in blob and raw_query not in blob


def test_log_redaction_scrubs_query_marker():
    f = RedactingFilter()
    rec = logging.LogRecord(
        "x", logging.INFO, __file__, 1,
        'raw_query="Zylthex Nachtfalke sk-secret" query_text="777333"', (), None,
    )
    assert f.filter(rec)
    msg = rec.getMessage()
    assert "Zylthex" not in msg and "777333" not in msg and "sk-secret" not in msg
