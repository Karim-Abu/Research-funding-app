"""End-to-end deterministic evidence: run -> candidates -> anchors -> links -> API."""
from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select

from app.db.models import EvidenceCandidate, RunSourceSnapshot
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

# Source text whose sentences lexically overlap requirement titles/descriptions.
SOURCE_TEXT = (
    "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. "
    "Ein beitragsberechtigter Schweizer Forschungspartner ist eingebunden. "
    "Das Gesuch ist vollständig und inhaltlich nachvollziehbar ausgefüllt."
)


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _source(client, project_id, csrf):
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Quelle", "text": SOURCE_TEXT, "data_classification": VALID_CLASSIFICATION},
        headers=_mut(csrf),
    )
    assert res.status_code == 201 and res.json()["status"] == "processed", res.text
    return res.json()["source_id"]


def _partner(client, project_id, csrf, **fields):
    res = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": fields.pop("name", "P"), **fields}, headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text


def _start_run(client, project_id, csrf):
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only",
                           "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=_mut(csrf),
    )
    assert res.status_code == 202, res.text
    return res.json()["resource_id"], res.json()["operation_id"]


def _setup_and_run(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    source_id = _source(client, project_id, csrf)
    selected = client.put(
        f"/api/v1/projects/{project_id}/primary-application",
        json={"source_id": source_id, "expected_primary_source_id": None},
        headers=_mut(csrf),
    )
    assert selected.status_code == 200, selected.text
    _partner(client, project_id, csrf, name="Industrie AG",
             partner_type="implementation_partner", country="CH", swiss_value_creation=True)
    _partner(client, project_id, csrf, name="ETH Zürich",
             partner_type="research_partner", country="CH",
             research_partner_eligibility_status="eligible")
    run_id, op_id = _start_run(client, project_id, csrf)
    assert client.get(f"/api/v1/operations/{op_id}").json()["status"] == "succeeded"
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return csrf, project_id, run_id


def test_listevidence_returns_exact_verified_anchors(client):
    _csrf, _pid, run_id = _setup_and_run(client)
    res = client.get(f"/api/v1/runs/{run_id}/evidence")
    assert res.status_code == 200
    anchors = res.json()
    assert anchors
    verified = [a for a in anchors if a["verification_status"] == "exact_verified"]
    assert verified
    anchor = verified[0]
    for key in (
        "anchor_id", "source_version_id", "fragment_id", "quote",
        "verification_status", "source_id", "source_name", "source_type",
        "normalizer_version",
    ):
        assert anchor.get(key), key
    assert anchor["match_type"] == "exact_normalized"
    assert anchor["match_score"] is None and anchor["coverage"] is None
    assert anchor["human_checked_by"] is None and anchor["human_checked_at"] is None
    assert anchor["verification_status"] != "human_verified"
    # exact span copied from the source (no paraphrase / no full document)
    assert anchor["quote"] in SOURCE_TEXT
    assert anchor["quote"] != SOURCE_TEXT


def test_requirements_return_active_evidence_links(client):
    _csrf, _pid, run_id = _setup_and_run(client)
    assessments = client.get(f"/api/v1/runs/{run_id}/requirements").json()
    linked = [a for a in assessments if a["evidence_links"]]
    assert linked
    link = linked[0]["evidence_links"][0]
    assert link["target_type"] == "requirement_assessment"
    assert link["status"] == "active"
    anchor_ids = {
        a["anchor_id"] for a in client.get(f"/api/v1/runs/{run_id}/evidence").json()
    }
    assert link["anchor_id"] in anchor_ids


def test_evidence_does_not_change_m4_statuses(client):
    _csrf, _pid, run_id = _setup_and_run(client)
    statuses = {
        a["requirement_id"]: a["status"]
        for a in client.get(f"/api/v1/runs/{run_id}/requirements").json()
    }
    # Deterministic M4 results preserved — evidence is supplementary.
    # RUN 2A Slice 1: Hybrid-Pass ist fulfilled (Bestätigung = separate Dimension).
    assert statuses["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"] == "fulfilled"
    assert statuses["REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"] == "fulfilled"


def test_reproducible_across_runs(client):
    csrf, project_id, run_id = _setup_and_run(client)
    quotes1 = sorted(
        a["quote"] for a in client.get(f"/api/v1/runs/{run_id}/evidence").json()
    )
    run2, op2 = _start_run(client, project_id, csrf)
    assert client.get(f"/api/v1/operations/{op2}").json()["status"] == "succeeded"
    quotes2 = sorted(
        a["quote"] for a in client.get(f"/api/v1/runs/{run2}/evidence").json()
    )
    assert quotes1 and quotes1 == quotes2


def test_candidates_in_snapshot_deduped_and_capped(client):
    _csrf, _pid, run_id = _setup_and_run(client)
    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(
                select(EvidenceCandidate).where(EvidenceCandidate.run_id == run_id)
            )
        )
        assert candidates
        snapshot_versions = set(
            db.scalars(
                select(RunSourceSnapshot.source_version_id).where(
                    RunSourceSnapshot.run_id == run_id
                )
            )
        )
        # no candidate outside the run snapshot
        assert all(c.source_version_id in snapshot_versions for c in candidates)
        # dedup by (target, fragment, quote_hash)
        keys = [(c.target_requirement_id, c.fragment_id, c.quote_hash) for c in candidates]
        assert len(keys) == len(set(keys))
        # max candidates per requirement respected
        per_req = Counter(c.target_requirement_id for c in candidates)
        assert all(count <= 3 for count in per_req.values())
        # quotes are exact substrings (never rewritten)
        assert all(c.proposed_quote in SOURCE_TEXT for c in candidates)
    finally:
        db.close()


def test_zero_candidate_run_succeeds(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    # No lexical overlap with the German requirement vocabulary.
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "X", "text": "Lorem ipsum dolor sit amet consectetur elit.",
              "data_classification": VALID_CLASSIFICATION},
        headers=_mut(csrf),
    )
    assert res.json()["status"] == "processed"
    run_id, op_id = _start_run(client, project_id, csrf)
    assert client.get(f"/api/v1/operations/{op_id}").json()["status"] == "succeeded"
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["current_stage"] == "finalize_run"
    assert run["progress_percent"] == 100
    # Empty evidence is safe; the run is not failed because no evidence was found.
    evidence = client.get(f"/api/v1/runs/{run_id}/evidence")
    assert evidence.status_code == 200
    # M4 deterministic assessments are still produced.
    assert client.get(f"/api/v1/runs/{run_id}/requirements").json()


def test_listevidence_unauthenticated_401(client):
    assert client.get(f"/api/v1/runs/{uuid.uuid4()}/evidence").status_code == 401


def test_listevidence_workspace_isolation_404(client):
    _csrf, _pid, run_id = _setup_and_run(client)
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert client.get(f"/api/v1/runs/{run_id}/evidence").status_code == 404
