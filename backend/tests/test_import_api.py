"""R3.2 — ImportCandidate-Persistenz + API (HITL-Entscheidungsfluss).

Fixtures: synthetisches Innolink-PDF (fiktives Projekt «SmartGrid Optimizer»).
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import AnalysisRun, AuditEvent, ImportCandidate, ReviewApproval
from app.db.session import SessionLocal
from app.security.redaction import detail_contains
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
)
from tests.review_helpers import (
    ABSTRACT,
    approve,
    clean_field,
    mut,
    run_recheck,
    setup_completed_run,
)

FIXTURES = Path(__file__).parent / "import_fixtures"
CLEAN_PDF = (FIXTURES / "innolink_sample.pdf").read_bytes()

NAME_EN = "INTRO.APP.NAME_EN"


def _upload_pdf(client, csrf, project_id: str) -> str:
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/files",
        files={"files": ("innolink_sample.pdf", CLEAN_PDF, "application/pdf")},
        data={"data_classification_json": json.dumps(VALID_CLASSIFICATION)},
        headers=mut(csrf),
    )
    assert res.status_code == 202, res.text
    return res.json()[0]["source_id"]


def _create_candidates(client, csrf, project_id: str, source_id: str):
    return client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": source_id},
        headers=mut(csrf),
    )


def _decide(client, csrf, candidate_id: str, **payload):
    with SessionLocal() as db:
        candidate = db.get(ImportCandidate, candidate_id)
        payload.setdefault("project_id", candidate.project_id if candidate else "missing")
        payload.setdefault("source_id", candidate.source_id if candidate else "missing")
        payload.setdefault(
            "expected_revision_id",
            candidate.current_revision_id if candidate else "missing",
        )
    return client.post(
        f"/api/v1/imports/{candidate_id}/decision", json=payload, headers=mut(csrf)
    )


def _setup_with_candidates(client):
    csrf, project_id, run_id = setup_completed_run(client, title="Import Project")
    source_id = _upload_pdf(client, csrf, project_id)
    res = _create_candidates(client, csrf, project_id, source_id)
    assert res.status_code == 201, res.text
    return csrf, project_id, run_id, source_id, {
        c["field_id"]: c for c in res.json()
    }


def _setup_without_run(client):
    """Projekt + Kandidaten OHNE Analyse-Lauf — der fachliche Normalfall des
    Antragsimports: erst prüfen und übernehmen, dann analysieren."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, "Import ohne Analyse")
    source_id = _upload_pdf(client, csrf, project_id)
    res = _create_candidates(client, csrf, project_id, source_id)
    assert res.status_code == 201, res.text
    return csrf, project_id, {c["field_id"]: c for c in res.json()}


def _start_run(client, csrf, project_id: str) -> str:
    run = client.post(
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
    ).json()
    run_id = run["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return run_id


class TestCreateCandidates:
    def test_upload_and_map_creates_pending_candidates(self, client):
        _, project_id, _, source_id, by_field = _setup_with_candidates(client)
        assert len(by_field) == 8
        assert all(c["decision"] == "pending" for c in by_field.values())
        abstract = by_field[ABSTRACT]
        assert abstract.get("label") == "Abstract (wird in Aramis publiziert)"
        assert abstract["extracted_text"].startswith("Das Projekt entwickelt")
        assert abstract["confidence"] == "found"
        assert abstract["source_location"].startswith("Seite ")
        assert abstract["mapping_version"] == "innolink-narrative-v2"
        assert abstract["mapping_status"] == "content_detected"
        assert abstract["section_metadata"][0]["candidate_text"].startswith(
            "Das Projekt entwickelt"
        )
        assert abstract["section_metadata"][0]["original_excerpt"].startswith(
            "Abstract"
        )
        project = client.get(f"/api/v1/projects/{project_id}").json()
        assert project["primary_application_source_id"] == source_id
        assert project["primary_application_status"] == "configured"

    def test_recreate_is_idempotent_no_duplicate_rows(self, client):
        csrf, project_id, _, source_id, by_field = _setup_with_candidates(client)
        res = _create_candidates(client, csrf, project_id, source_id)
        assert res.status_code == 201
        assert len(res.json()) == len(by_field)
        with SessionLocal() as db:
            rows = db.scalars(
                select(ImportCandidate).where(
                    ImportCandidate.project_id == project_id
                )
            ).all()
        assert len(rows) == len(by_field)

    def test_open_legacy_candidates_are_remapped_to_current_version(self, client):
        csrf, project_id, _, source_id, by_field = _setup_with_candidates(client)
        old_ids = {candidate["import_candidate_id"] for candidate in by_field.values()}
        with SessionLocal() as db:
            rows = db.scalars(
                select(ImportCandidate).where(ImportCandidate.project_id == project_id)
            ).all()
            for row in rows:
                row.mapping_version = "legacy-anchor-v1"
            db.commit()

        res = _create_candidates(client, csrf, project_id, source_id)
        assert res.status_code == 201, res.text
        assert {item["mapping_version"] for item in res.json()} == {
            "innolink-narrative-v2"
        }
        assert not old_ids.intersection(
            item["import_candidate_id"] for item in res.json()
        )

    def test_decided_legacy_candidates_are_never_silently_remapped(self, client):
        csrf, project_id, _, source_id, by_field = _setup_with_candidates(client)
        assert _decide(
            client,
            csrf,
            by_field[ABSTRACT]["import_candidate_id"],
            decision="ignored",
        ).status_code == 200
        with SessionLocal() as db:
            rows = db.scalars(
                select(ImportCandidate).where(ImportCandidate.project_id == project_id)
            ).all()
            for row in rows:
                row.mapping_version = "legacy-anchor-v1"
            db.commit()

        res = _create_candidates(client, csrf, project_id, source_id)
        assert res.status_code == 409
        assert res.json()["code"] == "import_mapping_outdated_decided"

    def test_listing_is_read_only_and_scoped(self, client):
        csrf, project_id, _, _, by_field = _setup_with_candidates(client)
        res = client.get(f"/api/v1/projects/{project_id}/imports")
        assert res.status_code == 200
        assert {c["field_id"] for c in res.json()} == set(by_field)


class TestDecisions:
    def test_uncertain_without_decision_stays_pending(self, client):
        # HITL-Zwang: der leere/unsichere Kandidat bleibt pending, egal was
        # mit anderen Kandidaten passiert.
        csrf, project_id, _, _, by_field = _setup_with_candidates(client)
        assert by_field[NAME_EN]["confidence"] == "uncertain"
        _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                decision="ignored")
        listed = client.get(f"/api/v1/projects/{project_id}/imports").json()
        name_en = next(c for c in listed if c["field_id"] == NAME_EN)
        assert name_en["decision"] == "pending"

    def test_ignored_and_saved_as_source_are_recorded(self, client):
        csrf, project_id, _, _, by_field = _setup_with_candidates(client)
        res = _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                      decision="ignored")
        assert res.status_code == 200
        assert res.json()["decision"] == "ignored"
        res = _decide(
            client, csrf,
            by_field["INTRO.APP.EXECUTIVE_SUMMARY"]["import_candidate_id"],
            decision="saved_as_source",
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "saved_as_source"
        assert res.json()["decided_at"] is not None

    def test_post_stays_initial_only_and_patch_creates_revision(self, client):
        csrf, project_id, _, _, by_field = _setup_with_candidates(client)
        candidate = by_field[ABSTRACT]
        cid = candidate["import_candidate_id"]
        first = _decide(client, csrf, cid, decision="ignored")
        assert first.status_code == 200
        res = _decide(client, csrf, cid, decision="saved_as_source")
        assert res.status_code == 409
        assert res.json()["code"] == "import_already_decided"
        revised = client.patch(
            f"/api/v1/imports/{cid}/decision",
            json={
                "decision": "saved_as_source",
                "project_id": project_id,
                "source_id": candidate["source_id"],
                "expected_revision_id": first.json()["current_revision_id"],
            },
            headers=mut(csrf),
        )
        assert revised.status_code == 200, revised.text
        assert revised.json()["revision_number"] == first.json()["revision_number"] + 1

    def test_accept_without_run_stages_the_decision(self, client):
        # Fachliche Korrektur: «zuerst Analyse starten» ist KEINE Voraussetzung
        # mehr. Ohne run_id wird die Übernahme vorgemerkt (kein Draft-Write,
        # accepted_draft_version_id bleibt leer bis zum Konsum im Lauf).
        csrf, _, by_field = _setup_without_run(client)
        res = _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                      decision="accepted")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["decision"] == "accepted"
        assert body["decided_at"] is not None
        assert body["accepted_draft_version_id"] is None

    def test_edited_text_requires_accept_decision(self, client):
        csrf, _, by_field = _setup_without_run(client)
        res = _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                      decision="ignored", edited_text="Editiert")
        assert res.status_code == 422
        assert res.json()["code"] == "edited_text_not_allowed"

    def test_accept_with_blank_edited_text_is_rejected(self, client):
        csrf, _, by_field = _setup_without_run(client)
        res = _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                      decision="accepted", edited_text="   ")
        assert res.status_code == 422
        assert res.json()["code"] == "import_candidate_empty"

    def test_accept_of_empty_candidate_is_rejected(self, client):
        csrf, _, run_id, _, by_field = _setup_with_candidates(client)
        res = _decide(client, csrf, by_field[NAME_EN]["import_candidate_id"],
                      decision="accepted", run_id=run_id)
        assert res.status_code == 422
        assert res.json()["code"] == "import_candidate_empty"

    def test_ambiguous_legacy_section_requires_edited_text(self, client):
        csrf, _, by_field = _setup_without_run(client)
        candidate = by_field["SOL.INNOVATION_SOLUTION.EDITOR"]
        with SessionLocal() as db:
            row = db.get(ImportCandidate, candidate["import_candidate_id"])
            row.section_metadata = [
                {
                    "target_sections": ["4.5.2", "4.5.3"],
                    "source_location": "Seite 3",
                    "status": "uncertain",
                    "candidate_text": "Synthetische Altangabe",
                    "original_excerpt": "Synthetische Portalfrage und Antwort",
                    "migration_version": "innolink-intro-ip-to-solution-v1",
                    "requires_manual_assignment": True,
                    "review_note": "Fachlich zuordnen.",
                }
            ]
            db.commit()

        res = _decide(
            client, csrf, candidate["import_candidate_id"], decision="accepted"
        )
        assert res.status_code == 422
        assert res.json()["code"] == "import_manual_assignment_required"
        edited = candidate["extracted_text"] + "\n4.5.3\nSynthetisch eingeordnet."
        res = _decide(
            client,
            csrf,
            candidate["import_candidate_id"],
            decision="accepted",
            edited_text=edited,
        )
        assert res.status_code == 200, res.text
        assert res.json()["edited_text"] == edited

    def test_unknown_candidate_is_404(self, client):
        csrf, _, _, _, _ = _setup_with_candidates(client)
        res = _decide(client, csrf, "does-not-exist", decision="ignored")
        assert res.status_code == 404


class TestAccept:
    def test_accept_writes_draft_version_and_invalidates_review(self, client):
        csrf, _, run_id, _, by_field = _setup_with_candidates(client)
        # Ein Feld-Approve auf einem ANDEREN Feld (Muster test_review_approval):
        # die Übernahme in ABSTRACT muss ihn stale machen.
        clean_field(client, csrf, run_id, "INTRO.APP.NAME", "Projekt Alpha.")
        assert run_recheck(client, csrf, run_id).status_code == 202
        assert approve(
            client, csrf, run_id, scope="field", scope_id="INTRO.APP.NAME"
        ).status_code == 201

        candidate = by_field[ABSTRACT]
        res = _decide(client, csrf, candidate["import_candidate_id"],
                      decision="accepted", run_id=run_id)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["decision"] == "accepted"
        assert body["accepted_draft_version_id"]

        draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
        assert draft["current_version"]["text"] == candidate["extracted_text"]
        # Herkunft «import»: die UI zeigt daraus «Aus PDF übernommen – Prüfung
        # nötig» — importierte Texte werden nie als final markiert.
        assert draft["current_version"]["created_by"] == "import"
        assert draft["status"] == "needs_review"

        # Stale-Verhalten kommt aus dem bestehenden Draft-Mechanismus:
        # Approval wird stale, Re-Check wird verlangt (nichts nachgebaut).
        with SessionLocal() as db:
            approval = db.scalar(
                select(ReviewApproval).where(ReviewApproval.run_id == run_id)
            )
            assert approval.status == "stale"
            assert db.get(AnalysisRun, run_id).recheck_required is True

    def test_accept_on_edited_draft_requires_explicit_confirmation(self, client):
        csrf, project_id, run_id, _, by_field = _setup_with_candidates(client)
        clean_field(
            client, csrf, run_id, ABSTRACT,
            "Manuell bearbeiteter Abstract ohne offene Angaben.",
        )
        candidate = by_field[ABSTRACT]

        res = _decide(client, csrf, candidate["import_candidate_id"],
                      decision="accepted", run_id=run_id)
        assert res.status_code == 409
        assert res.json()["code"] == "import_conflict"
        listed = client.get(f"/api/v1/projects/{project_id}/imports").json()
        marked = next(c for c in listed if c["field_id"] == ABSTRACT)
        assert marked["decision"] == "conflict"

        res = _decide(client, csrf, candidate["import_candidate_id"],
                      decision="accepted", run_id=run_id, confirm_overwrite=True)
        assert res.status_code == 200, res.text
        draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
        assert draft["current_version"]["text"] == candidate["extracted_text"]


class TestStagedAccept:
    """Übernahme VOR dem ersten Analyse-Lauf: der spätere Lauf konsumiert die
    akzeptierten Kandidaten als Entwurfsbasis (create_initial_draft)."""

    def test_staged_accept_seeds_next_run_draft_baseline(self, client):
        csrf, project_id, by_field = _setup_without_run(client)
        candidate = by_field[ABSTRACT]
        assert _decide(client, csrf, candidate["import_candidate_id"],
                       decision="accepted").status_code == 200

        run_id = _start_run(client, csrf, project_id)
        draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
        assert draft["current_version"]["text"] == candidate["extracted_text"]
        assert draft["current_version"]["created_by"] == "import"
        assert draft["status"] == "needs_review"  # nie automatisch final

        # Konsum-Markierung: die Vormerkung zeigt auf die erzeugte Version.
        listed = client.get(f"/api/v1/projects/{project_id}/imports").json()
        consumed = next(c for c in listed if c["field_id"] == ABSTRACT)
        assert (
            consumed["accepted_draft_version_id"]
            == draft["current_version"]["draft_version_id"]
        )

        # Zweiter Lauf: carry-over statt Doppel-Konsum — Text bleibt erhalten.
        run2 = _start_run(client, csrf, project_id)
        draft2 = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
        assert draft2["current_version"]["text"] == candidate["extracted_text"]
        assert draft2["current_version"]["created_by"] == "carried_over"

    def test_staged_accept_with_edited_text_keeps_original_excerpt(self, client):
        csrf, project_id, by_field = _setup_without_run(client)
        candidate = by_field[ABSTRACT]
        edited = "Bearbeitete Fassung des Abstracts für die Übernahme."
        res = _decide(client, csrf, candidate["import_candidate_id"],
                      decision="accepted", edited_text=edited)
        assert res.status_code == 200, res.text
        body = res.json()
        # «Bearbeitet übernommen»: edited_text gesetzt, Original unverändert.
        assert body["edited_text"] == edited
        assert body["extracted_text"] == candidate["extracted_text"]

        run_id = _start_run(client, csrf, project_id)
        draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
        assert draft["current_version"]["text"] == edited
        assert draft["current_version"]["created_by"] == "import"

    def test_staged_accept_never_overwrites_user_carry_over(self, client):
        # Nutzerarbeit hat Vorrang: existiert ein carry-over-fähiger User-Text
        # aus einem früheren Lauf, wird die Vormerkung NICHT konsumiert.
        csrf, project_id, run_id, _, by_field = _setup_with_candidates(client)
        clean_field(
            client, csrf, run_id, ABSTRACT,
            "Vom Menschen formulierter Abstract ohne offene Angaben.",
        )
        candidate = by_field[ABSTRACT]
        assert _decide(client, csrf, candidate["import_candidate_id"],
                       decision="accepted").status_code == 200

        run2 = _start_run(client, csrf, project_id)
        draft2 = client.get(f"/api/v1/runs/{run2}/fields/{ABSTRACT}").json()
        assert (
            draft2["current_version"]["text"]
            == "Vom Menschen formulierter Abstract ohne offene Angaben."
        )
        assert draft2["current_version"]["created_by"] == "carried_over"
        listed = client.get(f"/api/v1/projects/{project_id}/imports").json()
        staged = next(c for c in listed if c["field_id"] == ABSTRACT)
        assert staged["accepted_draft_version_id"] is None  # nicht konsumiert

    def test_accepted_draft_contains_no_portal_noise(self, client):
        # Portal-Hilfetexte/Chrome sind kein Antragsinhalt: der übernommene
        # Draft darf keine «Please note»/«Open Editor»/Zeichenzähler enthalten.
        csrf, project_id, by_field = _setup_without_run(client)
        assert _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                       decision="accepted").status_code == 200
        run_id = _start_run(client, csrf, project_id)
        text = client.get(
            f"/api/v1/runs/{run_id}/fields/{ABSTRACT}"
        ).json()["current_version"]["text"].lower()
        for noise in ("please note", "open editor", "characters:",
                      "innosuisse innolink"):
            assert noise not in text, f"Portal-Rauschen im Draft: {noise}"


class TestAuditHygiene:
    def test_no_candidate_text_in_audit_details(self, client):
        csrf, project_id, run_id, _, by_field = _setup_with_candidates(client)
        _decide(client, csrf, by_field[ABSTRACT]["import_candidate_id"],
                decision="accepted", run_id=run_id)
        _decide(client, csrf, by_field["INTRO.APP.NAME"]["import_candidate_id"],
                decision="ignored")
        # Markante Fixture-Passagen dürfen in keinem Audit-Detail auftauchen.
        sensitive = ("SmartGrid Optimizer", "Lastprognose", "Netzwerk Stadt AG")
        with SessionLocal() as db:
            events = db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action.like("import.%")
                )
            ).all()
            assert events, "Import-Audit-Events erwartet"
            for event in events:
                assert not detail_contains(event.detail, sensitive)
