"""createRedraft endpoint + accept/reject flow (Milestone 9D)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.providers import FakeProvider
from app.db.models import (
    AnalysisRun,
    DraftSuggestion,
    DraftVersion,
    PortalFieldDraft,
    ReviewApproval,
)
from app.db.session import SessionLocal
from tests.a2_helpers import (
    FIELD_ID,
    GOOD_TEXT,
    SECTION_GOOD_TEXT,
    TARGET_SECTION,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers


def _setup(processing_mode="cloud_assisted"):
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(db, processing_mode=processing_mode)
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm_fake(monkeypatch, payload=None):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "ai_eval_mode", "off")
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    resolver = fake_resolver(success_fake(payload or section_bundle()))
    monkeypatch.setattr(
        field_drafting, "_PROVIDER_RESOLVER", resolver,
    )
    monkeypatch.setattr(
        field_drafting, "_default_resolver",
        lambda _config, _target_section=None: resolver,
    )


def _create_redraft(client, csrf, run_id, field_id, base):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base, "target_section": TARGET_SECTION},
        headers=unsafe_headers(csrf),
    )


def test_create_redraft_async_then_result(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op_id = res.json()["operation_id"]
    op = client.get(f"/api/v1/operations/{op_id}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["suggested_text"] == SECTION_GOOD_TEXT
    assert op["result"]["target_section"] == TARGET_SECTION
    assert op["result"]["generation_kind"] == "fake_demo"
    assert op["result"]["ai_proposal"] is None
    assert op["result"]["character_limit"] == 25000


def test_redraft_missing_target_marker_reports_specific_422(client, monkeypatch):
    """Regression 2026-07-24 («section_marker_missing:4.5.2»): deterministische
    Abschnittsfehler tragen den spezifischen Code, Status 422 und deutschen
    Klartext mit benanntem Marker — und bieten keinen Alternativ-Retry an."""
    db = SessionLocal()
    try:
        text = "\n".join(
            line for line in GOOD_TEXT.splitlines() if not line.startswith("4.2")
        )
        run, _draft, base = build_run_with_draft(db, draft_text=text)
        run_id = run.run_id
        db.commit()
    finally:
        db.close()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["code"] == "section_marker_missing:4.2"
    assert op["error"]["status"] == 422
    assert "«4.2»" in op["error"]["detail"]
    # Der Operations-Lesecontract serialisiert das Feld immer — entscheidend
    # ist, dass es für deterministische Fehler nicht gesetzt/true ist.
    assert not op["error"].get("retry_with_alternative_model")


def test_redraft_tolerates_missing_non_target_marker(client, monkeypatch):
    """Gegenprobe zur Toleranz: fehlt ein NICHT-Ziel-Marker (4.5.2), gelingt
    der Redraft des vorhandenen Zielabschnitts trotzdem."""
    db = SessionLocal()
    try:
        text = "\n".join(
            line for line in GOOD_TEXT.splitlines() if not line.startswith("4.5.2")
        )
        run, _draft, base = build_run_with_draft(db, draft_text=text)
        run_id = run.run_id
        db.commit()
    finally:
        db.close()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["target_section"] == TARGET_SECTION


def test_explicit_second_redraft_replaces_proposed_suggestion(client, monkeypatch):
    """Expliziter Editor-Redraft erzeugt wirklich neu: der bisherige
    proposed-Vorschlag derselben Basis wird «superseded», nicht wiederverwendet
    (sonst käme nach «Neuen Vorschlag erzeugen» immer derselbe Text zurück)."""
    from app.db.models import DraftSuggestion as _DS

    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    first = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert first.status_code == 202
    op1 = client.get(f"/api/v1/operations/{first.json()['operation_id']}").json()
    assert op1["status"] == "succeeded"
    first_id = op1["result"]["suggestion_id"]

    second = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert second.status_code == 202
    op2 = client.get(f"/api/v1/operations/{second.json()['operation_id']}").json()
    assert op2["status"] == "succeeded"
    second_id = op2["result"]["suggestion_id"]
    assert second_id != first_id

    db = SessionLocal()
    try:
        assert db.get(_DS, first_id).status == "superseded"
        assert db.get(_DS, second_id).status == "proposed"
    finally:
        db.close()
    # Der Lese-Endpoint liefert den neuen Vorschlag.
    read = client.get(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}/suggestion",
        params={"target_section": TARGET_SECTION},
    ).json()
    assert read["suggestion"]["suggestion_id"] == second_id


def test_cost_guard_block_reports_call_limit_reason(client, monkeypatch):
    """CostGuard-Block (Profil-/Run-Limit) trägt den Katalog-Reason
    ai_call_limit_reached mit deutschem Klartext statt des Generiktexts."""
    from app.agents import cost_guard

    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    monkeypatch.setattr(
        cost_guard, "pre_check",
        lambda *args, **kwargs: cost_guard.CostDecision(
            False, "max_invocations_per_run(2)"
        ),
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["code"] == "cost_guard_blocked"
    assert op["error"]["status"] == 503
    assert op["error"]["reason_code"] == "ai_call_limit_reached"
    assert "Limit für KI-Aufrufe" in op["error"]["detail"]
    assert not op["error"].get("retry_with_alternative_model")


def test_redraft_result_exposes_concrete_change_metadata_for_review(
    client, monkeypatch
):
    payload = section_bundle()
    payload["section_candidate"].update({
        "preserved_facts": [
            "Der synthetische Projektbegriff bleibt erhalten.",
        ],
        "removed_or_reframed_claims": [
            "Die pauschale Überlegenheitsbehauptung wurde entfernt.",
        ],
        "new_claims": [],
        "missing_inputs": [{
            "label": "Vergleichsbasis",
            "reason": "Welcher bestehende Ansatz ist die freigegebene Vergleichsbasis?",
        }],
        "research_source_ids": [],
    })
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch, payload)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)

    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)

    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    section = op["result"]["section_result"]
    assert section["preserved_facts"] == payload["section_candidate"]["preserved_facts"]
    assert section["removed_or_reframed_claims"] == (
        payload["section_candidate"]["removed_or_reframed_claims"]
    )
    assert section["new_claims"] == []
    assert section["missing_inputs"] == payload["section_candidate"]["missing_inputs"]
    assert section["research_source_ids"] == []
    assert section["role_skill_contract_v2"]["requires_human_review"] is True
    assert op["result"]["proposal"]["human_review_required"] is True


def _create_redraft_with_preference(client, csrf, run_id, field_id, base, preference):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base, "target_section": TARGET_SECTION,
              "model_preference": preference},
        headers=unsafe_headers(csrf),
    )


def test_redraft_accepts_explicit_alternative_model(client, monkeypatch):
    """§4 Demo-Slice: die Alternativroute läuft nur auf expliziten Wunsch."""
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft_with_preference(
        client, csrf, run_id, FIELD_ID, base, "alternative")
    assert res.status_code == 202, res.text
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["suggested_text"] == SECTION_GOOD_TEXT


def test_transient_primary_failure_offers_alternative_retry(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    resolver = fake_resolver(success_fake(section_bundle()))
    # Primärroute transient nicht erreichbar (Timeout) — Policy/Schema wären
    # ausgeschlossen.
    timeout_resolver = fake_resolver(FakeProvider(mode="timeout"))
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", timeout_resolver)
    monkeypatch.setattr(
        field_drafting, "_default_resolver",
        lambda _config, _target_section=None: timeout_resolver,
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["retry_with_alternative_model"] is True
    # Der explizite Alternativ-Versuch mit funktionierendem Provider gelingt.
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", resolver)
    monkeypatch.setattr(
        field_drafting, "_default_resolver",
        lambda _config, _target_section=None: resolver,
    )
    retry = _create_redraft_with_preference(
        client, csrf, run_id, FIELD_ID, base, "alternative")
    assert retry.status_code == 202
    retry_op = client.get(
        f"/api/v1/operations/{retry.json()['operation_id']}").json()
    assert retry_op["status"] == "succeeded"


def test_schema_failure_never_offers_alternative(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    malformed = fake_resolver(FakeProvider(mode="malformed"))
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", malformed)
    monkeypatch.setattr(
        field_drafting, "_default_resolver",
        lambda _config, _target_section=None: malformed,
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert (op["error"] or {}).get("retry_with_alternative_model") is not True


def test_redraft_other_field_404(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    # INTRO.APP.NAME is outside the A2 allow-list (Abstract/Exec Summary now in).
    res = _create_redraft(client, csrf, run_id, "INTRO.APP.NAME", base)
    assert res.status_code == 404


def test_redraft_stale_base_409(client, monkeypatch):
    run_id, _draft_id, _base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, "not-current")
    assert res.status_code == 409
    assert res.json()["code"] == "stale_base_version"


def test_redraft_deterministic_only_503(client, monkeypatch):
    run_id, _draft_id, base = _setup(processing_mode="deterministic_only")
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "ai_unavailable"
    # R4.2: konkreter, maschinenlesbarer Grund + freigegebener deutscher Text.
    assert body["reason_code"] == "mode_deterministic_only"
    assert body["detail"] == (
        "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt."
    )
    assert "Datenklasse oder Umgebung" not in body["detail"]


def test_redraft_live_fake_conflict_is_503_without_demo_operation(
    client, monkeypatch
):
    from app.config.settings import get_settings

    settings = get_settings()
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    monkeypatch.setattr(settings, "ai_eval_mode", "real")
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)

    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)

    assert res.status_code == 503
    assert res.json()["reason_code"] == "live_fake_conflict"
    assert "operation_id" not in res.json()


# --- Kein vorgetäuschter lokaler KI-Pfad ------------------------------------

def _setup_local(sensitivity: str = "confidential", nda: bool = False):
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(
            db, processing_mode="local_only", sensitivity=sensitivity,
            origin="real_project", nda=nda,
        )
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _attach_local_confirmation(run_id: str) -> None:
    """Simuliert den beim Run-Start verbrauchten Local-AI-Opt-in."""
    import uuid as _uuid

    from app.db.models import ProcessingConfirmation

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        db.add(ProcessingConfirmation(
            confirmation_id=str(_uuid.uuid4()), project_id=run.project_id,
            workspace_id=run.workspace_id, created_by="test-user", status="used",
            processing_mode="local_only", source_version_ids=[],
            accepted_policy_version="1.1.0", purpose="KI-Vorschläge (lokal)",
            provider_route_class="fake_local",
            confirmation_text_version="local-ai-confirm-v1",
            data_classification_shown={}, expires_after_one_run=True,
            used_by_run_id=run_id,
        ))
        db.commit()
    finally:
        db.close()


def test_redraft_local_only_without_opt_in_503(client, monkeypatch):
    run_id, _draft_id, base = _setup_local()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    assert res.json()["reason_code"] == "provider_unavailable"


def test_redraft_local_only_with_legacy_opt_in_stays_unavailable(client, monkeypatch):
    """Auch eine alte Bestätigung darf keinen nicht existierenden Adapter erzeugen."""
    run_id, _draft_id, base = _setup_local()
    _attach_local_confirmation(run_id)
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503, res.text
    assert res.json()["reason_code"] == "provider_unavailable"


def test_redraft_local_only_nda_stays_blocked(client, monkeypatch):
    """D3 bleibt blockiert — auch mit (fälschlich) vorhandenem Opt-in."""
    run_id, _draft_id, base = _setup_local(nda=True)
    _attach_local_confirmation(run_id)
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    assert res.json()["reason_code"] == "provider_unavailable"


def _generate(client, monkeypatch, run_id, base) -> str:
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    op_id = _create_redraft(client, csrf, run_id, FIELD_ID, base).json()["operation_id"]
    return csrf, op_id


def test_accept_creates_agent_draft_version(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "agent"
    assert SECTION_GOOD_TEXT in res.json()["current_version"]["text"]
    assert "4.1 Stand der Technik" in res.json()["current_version"]["text"]
    assert "4.3 Ziele" in res.json()["current_version"]["text"]

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run.recheck_required is True
        suggestion = db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id)
        )
        assert suggestion.status == "accepted" and suggestion.accepted_draft_version_id
    finally:
        db.close()


def test_accept_stale_base_409(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": "stale", "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 409


def test_accept_invalidates_existing_approval(client, monkeypatch):
    run_id, draft_id, base = _setup()
    # Seed an approved review approval on the run.
    db = SessionLocal()
    try:
        db.add(ReviewApproval(
            approval_id="appr-1", run_id=run_id, workspace_id="ws-demo", scope="run",
            scope_id=run_id, status="approved", approval_scope_hash="h",
            review_package_version="1",
        ))
        db.commit()
    finally:
        db.close()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    db = SessionLocal()
    try:
        appr = db.get(ReviewApproval, "appr-1")
        assert appr.status == "stale"
    finally:
        db.close()


def test_edited_text_not_marked_agent(client, monkeypatch):
    # A human-edited proposal is merged only into its target section and keeps
    # user provenance, while the reviewed proposal becomes terminally accepted.
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": "4.2 Menschlich bearbeitete Neuheit.",
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "user"
    assert "4.2 Menschlich bearbeitete Neuheit." in res.json()["current_version"]["text"]
    assert "4.1 Stand der Technik" in res.json()["current_version"]["text"]
    assert "4.3 Ziele" in res.json()["current_version"]["text"]
    db = SessionLocal()
    try:
        suggestion = db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id)
        )
        assert suggestion.status == "accepted"
    finally:
        db.close()


def test_reject_creates_no_version(client, monkeypatch):
    # "Reject" is a client-side dismiss — no backend call → no new version.
    run_id, draft_id, base = _setup()
    _generate(client, monkeypatch, run_id, base)
    db = SessionLocal()
    try:
        draft = db.get(PortalFieldDraft, draft_id)
        versions = db.scalars(
            select(DraftVersion).where(DraftVersion.draft_id == draft_id)
        ).all()
        assert len(versions) == 1 and draft.current_version_id == base
    finally:
        db.close()


# --- C4: Ablehnung als persistierte HumanDecision ---------------------------


def _reject(client, csrf, run_id, suggestion_id, comment=None):
    from tests.review_helpers import mut

    return client.post(
        f"/api/v1/runs/{run_id}/human-decisions",
        json={
            "target_type": "draft_suggestion",
            "target_id": suggestion_id,
            "action": "reject",
            "comment": comment,
        },
        headers=mut(csrf),
    )


def _created_suggestion_id(client, csrf, run_id, base) -> str:
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202, res.text
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    return op["result"]["suggestion_id"]


def _complete_run(run_id: str) -> None:
    """Human decisions (Ablehnung) laufen in der Review-Phase — Run abschliessen."""
    db = SessionLocal()
    try:
        db.get(AnalysisRun, run_id).status = "completed"
        db.commit()
    finally:
        db.close()


def test_reject_suggestion_persists_decision_and_status(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    suggestion_id = _created_suggestion_id(client, csrf, run_id, base)
    _complete_run(run_id)

    res = _reject(client, csrf, run_id, suggestion_id, "Eigene Formulierung bevorzugt")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["target_type"] == "draft_suggestion"
    assert body["action"] == "reject"

    db = SessionLocal()
    try:
        suggestion = db.get(DraftSuggestion, suggestion_id)
        assert suggestion.status == "rejected"
        assert suggestion.decided_by is not None
        assert suggestion.decided_at is not None
        # Der Vorschlagstext bleibt unverändert erhalten (nur der Entscheid).
        assert suggestion.suggested_text == SECTION_GOOD_TEXT
    finally:
        db.close()

    # Bereits entschieden ⇒ 409, kein stiller Doppel-Reject.
    again = _reject(client, csrf, run_id, suggestion_id)
    assert again.status_code == 409
    assert again.json()["code"] == "suggestion_not_rejectable"


def test_reject_unknown_or_foreign_suggestion_404(client, monkeypatch):
    run_id, _draft_id, _base = _setup()
    _arm_fake(monkeypatch)
    _complete_run(run_id)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _reject(client, csrf, run_id, "sug-does-not-exist")
    assert res.status_code == 404


def test_reject_audit_carries_no_raw_text(client, monkeypatch):
    from app.db.models import AuditEvent

    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    suggestion_id = _created_suggestion_id(client, csrf, run_id, base)
    _complete_run(run_id)
    reason = "Der geheime Grund mit Zebra-Marker."
    assert _reject(client, csrf, run_id, suggestion_id, reason).status_code == 201

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        events = db.execute(
            select(AuditEvent).where(AuditEvent.workspace_id == run.workspace_id)
        ).scalars().all()
        blob = json.dumps(
            [e.detail for e in events], ensure_ascii=False, default=str
        )
        # Audit trägt nur IDs/Action — weder Grund noch Vorschlagstext.
        assert "Zebra-Marker" not in blob
        assert SECTION_GOOD_TEXT not in blob
        assert any(
            (e.detail or {}).get("target_type") == "draft_suggestion"
            for e in events
            if e.action == "review.decision_created"
        )
    finally:
        db.close()
