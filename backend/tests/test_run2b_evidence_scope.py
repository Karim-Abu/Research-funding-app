"""RUN 2B primary-application scope and typed evidence regressions."""
from __future__ import annotations

import uuid

import pytest

from app.agents.context import assemble_a1_context, assemble_evidence_mapping_context
from app.db.models import AnalysisRun, EvidenceCandidate, SourceDocument, SourceVersion
from app.db.session import SessionLocal
from app.evidence.discovery import discover_candidates
from app.evidence.eligibility import validate_requirement_quote
from app.evidence.scope_policy import formal_application_scope
from app.registry import get_registry
from tests.a1_mapping_helpers import build_run
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)


def _mut(csrf: str, key: str | None = None) -> dict[str, str]:
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _source(client, csrf: str, project_id: str, name: str, text: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": name,
            "text": text,
            "data_classification": VALID_CLASSIFICATION,
        },
        headers=_mut(csrf),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _select_primary(
    client,
    csrf: str,
    project_id: str,
    source_id: str,
    expected: str | None,
    *,
    key: str | None = None,
):
    return client.put(
        f"/api/v1/projects/{project_id}/primary-application",
        json={
            "source_id": source_id,
            "expected_primary_source_id": expected,
        },
        headers=_mut(csrf, key),
    )


def _start_run(client, csrf: str, project_id: str, versions=None):
    settings = {
        "processing_mode": "deterministic_only",
        "max_cost_chf": 0,
        "max_llm_calls": 0,
        "max_web_calls": 0,
    }
    if versions is not None:
        settings["source_version_ids"] = versions
    return client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": settings},
        headers=_mut(csrf),
    )


def test_primary_application_selection_is_scoped_idempotent_and_version_locked(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    source = _source(client, csrf, project_id, "Antrag", "Primärer Antrag.")
    supplementary = _source(client, csrf, project_id, "Beilage", "Beilage.")

    key = uuid.uuid4().hex
    selected = _select_primary(
        client, csrf, project_id, source["source_id"], None, key=key
    )
    replay = _select_primary(
        client, csrf, project_id, source["source_id"], None, key=key
    )
    assert selected.status_code == replay.status_code == 200
    assert selected.json()["primary_application_source_id"] == source["source_id"]
    assert replay.json()["primary_application_status"] == "configured"

    stale_expected = _select_primary(
        client, csrf, project_id, supplementary["source_id"], None
    )
    assert stale_expected.status_code == 409
    assert stale_expected.json()["code"] == "primary_application_conflict"

    other_project = create_project(client, csrf, "Other")
    cross_project = _select_primary(
        client,
        csrf,
        other_project,
        source["source_id"],
        None,
    )
    assert cross_project.status_code == 422
    assert cross_project.json()["code"] == "primary_application_source_invalid"

    excluded = _start_run(
        client,
        csrf,
        project_id,
        [supplementary["current_source_version_id"]],
    )
    assert excluded.status_code == 422
    assert excluded.json()["code"] == "primary_application_version_required"


def test_application_evidence_uses_only_primary_frozen_version(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    primary = _source(
        client,
        csrf,
        project_id,
        "Innolink Antrag",
        (
            "Industrie AG ist als Umsetzungspartner in der Schweiz "
            "wertschöpfend tätig. ETH Universität ist als Forschungspartner "
            "beitragsberechtigt."
        ),
    )
    supplementary = _source(
        client,
        csrf,
        project_id,
        "Begleitdokument",
        "Begleitdokument: Umsetzungspartner Beilage GmbH in der Schweiz.",
    )
    assert _select_primary(
        client, csrf, project_id, primary["source_id"], None
    ).status_code == 200

    response = _start_run(client, csrf, project_id)
    assert response.status_code == 202, response.text
    run_id = response.json()["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

    with SessionLocal() as db:
        run = db.get(AnalysisRun, run_id)
        candidates = list(
            db.query(EvidenceCandidate).filter(EvidenceCandidate.run_id == run_id)
        )
        assert candidates
        assert {candidate.source_id for candidate in candidates} == {
            primary["source_id"]
        }

        drafting = assemble_a1_context(db, run, max_fragments=80)
        formal = assemble_evidence_mapping_context(db, run, max_fragments=80)
        assert set(drafting.source_version_ids) == {
            primary["current_source_version_id"],
            supplementary["current_source_version_id"],
        }
        assert formal.source_version_ids == [primary["current_source_version_id"]]
        companion = next(
            block
            for block in drafting.fragment_blocks
            if block.source_version_id == supplementary["current_source_version_id"]
        )
        assert companion.scope == "drafting_context"
        assert companion.used_as_requirement_evidence is False

    assessments = client.get(f"/api/v1/runs/{run_id}/requirements").json()
    links = [link for item in assessments for link in item["evidence_links"]]
    assert links
    assert all(link["run_id"] == run_id for link in links)
    assert all(link["source_id"] == primary["source_id"] for link in links)
    assert all(link["scope"] == "application" for link in links)

    registry = get_registry()
    with_rules = next(item for item in assessments if item["rule_evidence"])
    for evidence in with_rules["rule_evidence"]:
        rule = registry.rules[evidence["rule_id"]]
        source = registry.sources[evidence["source_ref"]]
        assert evidence["evidence_quote"] == rule.description
        assert evidence["source_title"] == source.title
        assert evidence["source_url"] == source.url
        assert evidence["evidence_label"] == "Kuratierter Registry-Auszug"


def test_generated_or_review_sources_are_rejected_before_retrieval():
    db = SessionLocal()
    try:
        run, _fragments, version_id = build_run(
            db,
            fragments=["Acme AG ist Umsetzungspartner in der Schweiz."],
        )
        version = db.get(SourceVersion, version_id)
        document = db.get(SourceDocument, version.source_document_id)
        document.name = "Generated Output Review Package"
        db.flush()

        scope = formal_application_scope(db, run)
        assert scope.status == "rejected"
        assert scope.reason_code == "generated_or_review_content"
        assert discover_candidates(db, run) == []
        context = assemble_evidence_mapping_context(db, run, max_fragments=80)
        assert context.fragment_blocks == []
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize(
    ("requirement_id", "quote", "reason"),
    [
        (
            "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            "Der Anteil liegt im vorgesehenen Bereich.",
            "evidence_numeric_value_missing",
        ),
        (
            "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            "Zwischen 40 und 60 der Gesamtkosten.",
            "evidence_unit_missing",
        ),
        (
            "REQ.INNO.BUDGET.CASH_MIN5",
            "5 Prozent der Gesamtprojektkosten.",
            "evidence_operator_missing",
        ),
        (
            "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            "Zwischen 40 und 60 Prozent.",
            "evidence_denominator_missing",
        ),
        (
            "REQ.INNO.DURATION.TYPICAL_6_36",
            "Die Laufzeit ist angemessen.",
            "evidence_duration_missing",
        ),
        (
            "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH",
            "Ein Umsetzungspartner ist in der Schweiz.",
            "evidence_organization_not_concrete",
        ),
        (
            "REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE",
            "Acme AG ist Umsetzungspartner.",
            "evidence_research_role_mismatch",
        ),
        (
            "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH",
            "ETH Universität ist Forschungspartner.",
            "evidence_implementation_role_mismatch",
        ),
    ],
)
def test_typed_evidence_rejection_codes(requirement_id: str, quote: str, reason: str):
    assert validate_requirement_quote(requirement_id, quote) == reason
