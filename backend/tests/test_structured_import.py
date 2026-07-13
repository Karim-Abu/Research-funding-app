"""Deterministischer strukturierter PDF-Import mit menschlicher Übernahme."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from app.db.models import (
    AnalysisRun,
    AuditEvent,
    RunProjectSnapshot,
    StructuredImportCandidate,
)
from app.db.session import SessionLocal
from app.imports.mapping import (
    STRUCTURED_MAPPING_VERSION,
    map_document,
    map_parse_result,
)
from app.ingestion.parsers import ParsedBlock, ParseResult
from app.rules.inputs import inputs_from_snapshot
from app.runs import project_snapshot
from app.security.redaction import detail_contains
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
)
from tests.review_helpers import mut
from tests.structured_import_fixture import (
    CONTACT_MARKER,
    GOLDEN_STRUCTURED_PDF,
)


EXPECTED_BUDGET = {
    "project.direct_total_project_costs_excluding_overhead": 309734,
    "project.implementation_own_contribution": 142680,
    "project.cash_contribution": 20000,
    "project.total_requested_funding": 147054,
    "project.total_requested_funding_including_overhead": 171560,
}


def _by_target(document=GOLDEN_STRUCTURED_PDF):
    result = map_document("pdf", document)
    return result, {item.target_key: item for item in result.structured_candidates}


def _upload(client, csrf: str, project_id: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/sources/files",
        files={"files": ("synthetic-golden.pdf", GOLDEN_STRUCTURED_PDF, "application/pdf")},
        data={"data_classification_json": json.dumps(VALID_CLASSIFICATION)},
        headers=mut(csrf),
    )
    assert response.status_code == 202, response.text
    return response.json()[0]["source_id"]


def _setup(client, *, title: str = "Empty import target"):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, title)
    source_id = _upload(client, csrf, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": source_id},
        headers=mut(csrf),
    )
    assert response.status_code == 201, response.text
    structured = client.get(
        f"/api/v1/projects/{project_id}/structured-imports"
    )
    assert structured.status_code == 200, structured.text
    return csrf, project_id, source_id, {
        item["target_key"]: item for item in structured.json()
    }


def _decide(client, csrf: str, candidate: dict, **overrides):
    payload = {"decision": "accepted", **overrides}
    return client.post(
        f"/api/v1/structured-imports/{candidate['candidate_id']}/decision",
        json=payload,
        headers=mut(csrf),
    )


class TestStructuredMapping:
    def test_golden_values_and_no_contact_pii(self):
        result, candidates = _by_target()

        assert result.needs_manual_input is False
        assert len(candidates) == 15
        assert all(
            item.mapping_version == STRUCTURED_MAPPING_VERSION
            for item in candidates.values()
        )
        assert candidates["project.title"].payload_json == {"title": "ORBIT"}
        assert candidates["project.title"].confidence == "uncertain"
        assert candidates["project.title_en"].payload_json == {
            "title_en": "ORBIT Synthetic Collaboration"
        }
        assert candidates["project.start_date"].payload_json == {
            "start_date": "2026-01-01"
        }
        assert candidates["project.end_date"].payload_json == {
            "end_date": "2027-06-30"
        }
        assert candidates["project.duration_months"].payload_json == {
            "duration_months": 18
        }
        for target, value in EXPECTED_BUDGET.items():
            field = target.removeprefix("project.")
            assert candidates[target].payload_json == {field: value}

        partners = [
            item for item in candidates.values() if item.candidate_kind == "partner"
        ]
        assert [item.target_key for item in partners] == [
            "partner.research.01",
            "partner.implementation.01",
            "partner.implementation.02",
        ]
        assert all(item.confidence == "found" for item in partners)
        assert all(
            item.payload_json["personnel_independence_status"] == "confirmed"
            and item.payload_json["financial_independence_status"] == "confirmed"
            for item in partners
        )
        assert partners[0].payload_json["country"] == "CH"
        assert partners[0].payload_json["swiss_value_creation"] is None
        assert CONTACT_MARKER not in json.dumps(
            [item.payload_json for item in candidates.values()]
        )

        assert candidates["answer.scientific_integrity"].payload_json == {
            "sanction_answer": False,
            "comment": None,
        }
        assert candidates["answer.management_hours"].payload_json == {
            "management_hours": 0,
            "total_project_hours": 4700,
        }
        explanation = next(
            item
            for item in result.fields
            if item.field_id == "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"
        )
        assert explanation.confidence == "uncertain"
        assert explanation.extracted_text == (
            "No project-management hours are planned (0 of 4700 hours)."
        )

    @pytest.mark.parametrize(
        ("line", "target"),
        [
            ("Project Start Date: 2026/31/12", "project.start_date"),
            ("Cash Contribution: EUR 20'000", "project.cash_contribution"),
        ],
    )
    def test_invalid_dates_and_currency_stay_uncertain(self, line, target):
        from tests.fixtures import make_text_pages_pdf

        result = map_document("pdf", make_text_pages_pdf([[line]]))
        item = next(candidate for candidate in result.structured_candidates if candidate.target_key == target)
        assert item.confidence == "uncertain"
        assert next(iter(item.payload_json.values())) is None

    def test_legacy_layout_table_is_segmented_without_contact_column(self):
        layout = "\n".join(
            [
                "2. Organisations and People",
                "Research Partners",
                "Contract Party                 Research Center       Department          Organisation               Contact",
                "                               Type                                      Representative",
                "Synthetic Research Lab         University             Applied Systems     Robin Example              contact-marker@example.test",
                "Implementation Partners",
                "Contract Party             Start-up          Total     Industry          Organisation               Contact",
                "                           Company           FTE       Sector            Representative",
                "Synthetic Devices AG       No                10        Electronics       Morgan Sample              hidden@example.test",
                "Synthetic Services GmbH    No                25        Services          Taylor Fixture             hidden2@example.test",
                "Main Contacts",
            ]
        )
        text = "\n".join(
            [
                "2. Organisations and People",
                "Research Partners",
                "Implementation Partners",
                "Are any of the employees involved in the project on the part of a research partner also an employee of an implementation partner?",
                "No",
                "Are any of the employees involved in the project on the part of the research partners a member of an involved implementation partner's executive board, supervisory board or scientific committee?",
                "No",
                "Have any of the employees involved in the project on the part of the research partners been commissioned by an involved implementation partner to perform another role?",
                "No",
                "☒ None of the employees involved in the project on the part of the research partners holds more than 20% shares in an involved implementation partner",
                "☒ None of the research partners (legal person) holds more than 20% shares in an involved implementation partner",
                "Main Contacts",
                "contact-marker@example.test",
            ]
        )
        result = map_parse_result(
            ParseResult(
                blocks=[
                    ParsedBlock(
                        text=text,
                        layout_text=layout,
                        page=3,
                        section="body",
                    )
                ]
            ),
            include_structured=True,
        )
        partners = [
            item
            for item in result.structured_candidates
            if item.candidate_kind == "partner"
        ]
        assert [item.target_key for item in partners] == [
            "partner.research.01",
            "partner.implementation.01",
            "partner.implementation.02",
        ]
        assert all(item.confidence == "uncertain" for item in partners)
        assert all(
            item.payload_json["personnel_independence_status"] == "confirmed"
            and item.payload_json["financial_independence_status"] == "confirmed"
            for item in partners
        )
        assert "example.test" not in json.dumps(
            [item.payload_json for item in partners]
        )


class TestStructuredApi:
    def test_creation_is_idempotent_and_summary_is_safe(self, client):
        csrf, project_id, source_id, by_target = _setup(client)
        assert len(by_target) == 15

        second = client.post(
            f"/api/v1/projects/{project_id}/imports",
            json={"source_id": source_id},
            headers=mut(csrf),
        )
        assert second.status_code == 201, second.text
        with SessionLocal() as db:
            count = db.scalar(
                select(func.count()).select_from(StructuredImportCandidate).where(
                    StructuredImportCandidate.project_id == project_id
                )
            )
        assert count == 15

        summary = client.get(
            f"/api/v1/projects/{project_id}/structured-imports/summary"
        ).json()
        assert summary == {
            "partners": {"detected": 3, "reviewed": 0, "unchecked": 3},
            "budget": {"detected": 5, "reviewed": 0, "unchecked": 5},
            "provenance": [],
        }
        assert CONTACT_MARKER not in json.dumps(summary)

    def test_uncertain_requires_edit_and_project_conflict_requires_confirmation(self, client):
        csrf, project_id, _, by_target = _setup(client, title="Existing title")
        title = by_target["project.title"]
        response = _decide(client, csrf, title)
        assert response.status_code == 422
        assert response.json()["code"] == "structured_import_manual_edit_required"

        edit = {"title": "ORBIT"}
        response = _decide(client, csrf, title, edited_payload_json=edit)
        assert response.status_code == 409
        assert response.json()["code"] == "structured_import_conflict"

        response = _decide(
            client,
            csrf,
            title,
            edited_payload_json=edit,
            confirm_overwrite=True,
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "accepted"
        assert client.get(f"/api/v1/projects/{project_id}").json()["title"] == "ORBIT"

    def test_exact_partner_match_requires_confirmation_then_merges(self, client):
        csrf, project_id, _, by_target = _setup(client)
        candidate = by_target["partner.research.01"]
        detected = candidate["payload_json"]
        created = client.post(
            f"/api/v1/projects/{project_id}/partners",
            json={
                "name": detected["name"],
                "partner_type": "research_partner",
                "department": "Existing Department",
            },
            headers=mut(csrf),
        )
        assert created.status_code == 201, created.text

        conflict = _decide(client, csrf, candidate)
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "structured_import_conflict"
        accepted = _decide(client, csrf, candidate, confirm_overwrite=True)
        assert accepted.status_code == 200, accepted.text

        partners = client.get(f"/api/v1/projects/{project_id}/partners").json()
        assert len(partners) == 1
        assert partners[0]["partner_id"] == created.json()["partner_id"]
        assert partners[0]["department"] == detected["department"]

    def test_multiple_exact_partner_matches_stay_blocked(self, client):
        csrf, project_id, _, by_target = _setup(client)
        candidate = by_target["partner.implementation.01"]
        name = candidate["payload_json"]["name"]
        for index in range(2):
            response = client.post(
                f"/api/v1/projects/{project_id}/partners",
                json={
                    "name": name,
                    "partner_type": "implementation_partner",
                    "department": f"Department {index}",
                },
                headers=mut(csrf),
            )
            assert response.status_code == 201, response.text

        response = _decide(client, csrf, candidate)
        assert response.status_code == 409
        assert response.json()["code"] == "structured_import_partner_ambiguous"
        response = _decide(client, csrf, candidate, confirm_overwrite=True)
        assert response.status_code == 409
        assert response.json()["code"] == "structured_import_partner_ambiguous"

    def test_contact_pii_is_rejected_from_edited_partner_payload(self, client):
        csrf, _, _, by_target = _setup(client)
        candidate = by_target["partner.research.01"]
        edited = dict(candidate["payload_json"])
        marker = "private-contact-marker@example.test"
        edited["official_representative"] = {"display_name": marker}
        response = _decide(
            client,
            csrf,
            candidate,
            edited_payload_json=edited,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "structured_import_contact_pii_not_allowed"
        assert marker not in response.text

    def test_ignored_decision_is_terminal(self, client):
        csrf, _, _, by_target = _setup(client)
        candidate = by_target["project.title_en"]
        ignored = _decide(client, csrf, candidate, decision="ignored")
        assert ignored.status_code == 200
        assert ignored.json()["decision"] == "ignored"
        repeated = _decide(client, csrf, candidate)
        assert repeated.status_code == 409
        assert repeated.json()["code"] == "structured_import_already_decided"

    def test_golden_acceptance_persists_existing_models_and_new_snapshot(self, client):
        csrf, project_id, _, by_target = _setup(client)
        accepted_targets = [
            *EXPECTED_BUDGET,
            "project.duration_months",
            "partner.research.01",
            "partner.implementation.01",
            "partner.implementation.02",
            "answer.scientific_integrity",
            "answer.management_hours",
        ]
        for target in accepted_targets:
            response = _decide(client, csrf, by_target[target])
            assert response.status_code == 200, (target, response.text)

        project = client.get(f"/api/v1/projects/{project_id}").json()
        assert project["duration_months"] == 18
        assert project["direct_total_project_costs_excluding_overhead"] == 309734
        assert project["implementation_own_contribution"] == 142680
        assert project["cash_contribution"] == 20000
        assert project["total_requested_funding"] == 147054
        assert project["total_requested_funding_including_overhead"] == 171560

        partners = client.get(f"/api/v1/projects/{project_id}/partners").json()
        assert len(partners) == 3
        assert {item["partner_type"] for item in partners} == {
            "research_partner",
            "implementation_partner",
        }
        assert all("department" in item for item in partners)
        assert CONTACT_MARKER not in json.dumps(partners)

        precheck = client.get(
            f"/api/v1/projects/{project_id}/budget/precheck"
        ).json()
        assert precheck["figures"]["implementation_share_percent"] == 52.52
        assert precheck["figures"]["cash_share_percent"] == 6.46
        assert all(item["status"] == "fulfilled" for item in precheck["checks"])

        run_response = client.post(
            f"/api/v1/projects/{project_id}/runs",
            json={
                "settings": {
                    "processing_mode": "deterministic_only",
                    "max_cost_chf": 0,
                    "max_llm_calls": 0,
                    "max_web_calls": 0,
                }
            },
            headers=mut(csrf),
        )
        assert run_response.status_code == 202, run_response.text
        run_id = run_response.json()["resource_id"]
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

        with SessionLocal() as db:
            snapshot = db.get(RunProjectSnapshot, run_id)
            assert snapshot is not None
            assert len(snapshot.partners_json) == 3
            assert snapshot.project_json["total_requested_funding"] == 147054
            inputs = inputs_from_snapshot(
                profile_id=snapshot.project_json.get("funding_instrument_profile_id"),
                partner_dicts=list(snapshot.partners_json),
                project_dict=dict(snapshot.project_json),
            )
        assert inputs.sanction_answer is False
        assert inputs.human_decision_present is True
        assert inputs.management_hours == 0
        assert inputs.total_project_hours == 4700

        summary = client.get(
            f"/api/v1/projects/{project_id}/structured-imports/summary"
        ).json()
        assert summary["partners"] == {"detected": 3, "reviewed": 3, "unchecked": 0}
        assert summary["budget"] == {"detected": 5, "reviewed": 5, "unchecked": 0}
        assert len(summary["provenance"]) == 8

    def test_acceptance_marks_existing_run_stale_without_mutating_snapshot(self, client):
        csrf, project_id, _, by_target = _setup(client)
        run_response = client.post(
            f"/api/v1/projects/{project_id}/runs",
            json={
                "settings": {
                    "processing_mode": "deterministic_only",
                    "max_cost_chf": 0,
                    "max_llm_calls": 0,
                    "max_web_calls": 0,
                }
            },
            headers=mut(csrf),
        )
        run_id = run_response.json()["resource_id"]
        with SessionLocal() as db:
            snapshot = db.get(RunProjectSnapshot, run_id)
            before = dict(snapshot.project_json)

        response = _decide(
            client,
            csrf,
            by_target["project.cash_contribution"],
        )
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            snapshot = db.get(RunProjectSnapshot, run_id)
            assert run.recheck_required is True
            assert snapshot.project_json == before
            assert project_snapshot.is_stale(db, snapshot) is True

    def test_audit_and_summary_never_contain_payload_values(self, client):
        csrf, project_id, _, by_target = _setup(client)
        partner = by_target["partner.research.01"]
        marker = partner["payload_json"]["name"]
        response = _decide(client, csrf, partner)
        assert response.status_code == 200, response.text
        summary = client.get(
            f"/api/v1/projects/{project_id}/structured-imports/summary"
        ).json()
        assert marker not in json.dumps(summary)
        with SessionLocal() as db:
            audits = list(db.scalars(select(AuditEvent)))
        assert not detail_contains([item.detail for item in audits], marker)
        assert not detail_contains([item.detail for item in audits], CONTACT_MARKER)
