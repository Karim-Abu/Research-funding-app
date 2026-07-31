"""Erst-Entwurf-Modus: Redrafts gelingen auch bei leerem/Platzhalter-Entwurf.

Bei leerem oder rein aus Vorlagen-Platzhaltern bestehendem Basistext enthält
der Grounding-Korpus keinen Anwendertext — ungegroundete konkrete Angaben
laufen dann über den bestehenden Warnkanal (unsupported_concrete_claim →
Prüfung nötig) statt hart mit failed_grounding_validation zu scheitern. Das
allowed_facts-Halluzinationsgate bleibt in jedem Modus hart.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.field_drafting_context import assemble_a2_context
from app.db.models import DraftSuggestion
from app.db.session import SessionLocal
from app.drafts.templates import is_placeholder_only, placeholder
from tests.a2_helpers import (
    FIELD_ID,
    GOOD_TEXT,
    TARGET_SECTION,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

EXEC_FIELD_ID = "INTRO.APP.EXECUTIVE_SUMMARY"

# SOL-Vorlage-Zustand: Marker vorhanden, 4.2-Körper nur Platzhalter.
PLACEHOLDER_SECTION_TEXT = "\n".join(
    f"{line.split(' ', 1)[0]}\n{placeholder('Antwort fachlich ergänzen')}"
    if line.startswith("4.2")
    else line
    for line in GOOD_TEXT.splitlines()
)
# "DATRIX" ist ein Akronym-Entity: das Grounding stuft es als ungegroundete
# Organisation ein; allowed_facts (Rechtsform-Suffix-Regex) schlägt nicht an.
# Länge über der Erst-Entwurf-Substanzschwelle (min(200, 40 % Budget)).
UNGROUNDED_SECTION_TEXT = (
    "4.2 Neuheit: Der Ansatz DATRIX grenzt sich klar vom bisherigen Vorgehen "
    "ab. Die Abgrenzung ergibt sich aus der Kombination bestehender Verfahren "
    "mit einer neuen Verankerungslogik, die im Projekt entwickelt und "
    "validiert wird. Offene fachliche Angaben bleiben als Klärungspunkte "
    "erfasst und werden nicht erfunden."
)


# --- Helper -----------------------------------------------------------------


def test_is_placeholder_only():
    assert is_placeholder_only("")
    assert is_placeholder_only("   \n")
    assert is_placeholder_only(placeholder("Executive summary"))
    assert is_placeholder_only(f"  {placeholder('A')}\n{placeholder('B')}  ")
    assert not is_placeholder_only(f"Echter Satz. {placeholder('A')}")
    assert not is_placeholder_only("Echter Satz.")


# --- Kontext-Erkennung (T4) -------------------------------------------------


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _sol_context(db, run, base):
    return assemble_a2_context(
        db, run, field_id=FIELD_ID, profile_id="A2.solution_innovation",
        target_section=TARGET_SECTION,
        section_markers=("4.1", "4.2", "4.3", "4.4", "4.5.1", "4.5.2",
                         "4.5.3", "4.5.4", "4.6"),
        base_version_id=base, manifest_mode=True,
    )


def test_context_detects_placeholder_section_as_initial_draft(db):
    run, _draft, base = build_run_with_draft(
        db, draft_text=PLACEHOLDER_SECTION_TEXT,
    )
    ctx = _sol_context(db, run, base)
    assert ctx.is_initial_draft is True
    assert '"draft_state": "initial"' in ctx.context_text


def test_context_keeps_substantive_section_out_of_initial_mode(db):
    """Hash-Stabilitäts-Pin: bei echtem Text bleibt der portal_requirement-
    Kontext byte-identisch — der draft_state-Schlüssel existiert dort nicht."""
    run, _draft, base = build_run_with_draft(db, draft_text=GOOD_TEXT)
    ctx = _sol_context(db, run, base)
    assert ctx.is_initial_draft is False
    assert "draft_state" not in ctx.context_text


def test_context_detects_registry_template_as_initial_draft(db):
    """Echter Vorlagenzustand: Registry-Fragelabels als Überschriften plus
    Platzhalter (build_template) gelten als Erst-Entwurf."""
    from app.drafts.templates import build_template
    from app.registry.loader import get_registry

    registry = get_registry()
    template = build_template(registry.portal_fields[FIELD_ID], registry)
    run, _draft, base = build_run_with_draft(db, draft_text=template)
    ctx = _sol_context(db, run, base)
    assert ctx.is_initial_draft is True
    assert '"draft_state": "initial"' in ctx.context_text


def test_context_detects_empty_narrative_field_as_initial_draft(db):
    run, _draft, base = build_run_with_draft(
        db, field_id=EXEC_FIELD_ID, character_limit=2000,
        field_name="Executive Summary",
        draft_text=placeholder("Executive summary (wird nicht in Aramis publiziert)"),
    )
    ctx = assemble_a2_context(
        db, run, field_id=EXEC_FIELD_ID,
        profile_id="A2.introduction_public_summary", target_section=None,
        section_markers=(), base_version_id=base, manifest_mode=True,
    )
    assert ctx.is_initial_draft is True
    assert '"draft_state": "initial"' in ctx.context_text


# --- Qualitäts-Slice: Anforderungsdefinitionen + Aufgaben-Direktiven --------


def test_context_carries_requirement_definitions(db):
    """Die Registry-Titel/-Beschreibungen der verlinkten Anforderungen stehen
    im Kontext; die alte draft_state_note existiert nicht mehr."""
    run, _draft, base = build_run_with_draft(db, draft_text=GOOD_TEXT)
    ctx = _sol_context(db, run, base)
    assert '"requirement_definitions"' in ctx.context_text
    # SOL-Editor ist mit REQ.PORTAL.SOL.CHARACTER_LIMIT verlinkt.
    assert "Innovation Solution character limit" in ctx.context_text
    assert "25'000 Zeichen" in ctx.context_text
    assert "draft_state_note" not in ctx.context_text


def test_org_context_carries_requirement_title_and_description(db):
    from app.agents.field_drafting_context import assemble_a2_context as assemble

    org_field = "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
    run, _draft, base = build_run_with_draft(
        db, field_id=org_field, character_limit=300,
        field_name="Explanations and Comments",
        draft_text=placeholder("Explanations and Comments (financial independence)"),
    )
    ctx = assemble(
        db, run, field_id=org_field, profile_id="A2.organisations_governance",
        target_section=None, section_markers=(), base_version_id=base,
        manifest_mode=True,
    )
    assert "Finanzielle Unabhängigkeit und 20-Prozent-Schwelle" in ctx.context_text
    assert "relevantes wirtschaftliches" in ctx.context_text


def test_task_directives_cover_budget_requirements_initial_and_mode(db):
    from app.agents.a2_fields import resolve_field_config

    config = resolve_field_config(FIELD_ID)
    run, _draft, base = build_run_with_draft(
        db, draft_text=PLACEHOLDER_SECTION_TEXT,
    )
    ctx = _sol_context(db, run, base)
    directives = field_drafting._task_directives(ctx, config)
    joined = "\n".join(directives)
    assert f"Zeichenbudget: {config.char_limit} Zeichen" in joined
    assert "requirement_definitions" in joined
    assert "Erst-Entwurf" in joined
    assert "Klarer formulieren" in joined  # Default-Modus «clearer»

    # Substanzieller Text: keine Erst-Entwurf-Direktive; Modus-Satz wechselt mit.
    run2, _draft2, base2 = build_run_with_draft(db, draft_text=GOOD_TEXT)
    ctx2 = _sol_context(db, run2, base2)
    ctx2.improvement_mode = "shorten"
    directives2 = field_drafting._task_directives(ctx2, config)
    joined2 = "\n".join(directives2)
    assert "Erst-Entwurf" not in joined2
    assert "Kürzen" in joined2


# --- API: manifest-mode Redraft (T1–T3, T5) ---------------------------------


def _setup(field_id=FIELD_ID, draft_text=PLACEHOLDER_SECTION_TEXT, **kw):
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(
            db, field_id=field_id, draft_text=draft_text, **kw,
        )
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm_fake(monkeypatch, payload):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "ai_eval_mode", "off")
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    resolver = fake_resolver(success_fake(payload))
    monkeypatch.setattr(field_drafting, "_PROVIDER_RESOLVER", resolver)
    monkeypatch.setattr(
        field_drafting, "_default_resolver",
        lambda _config, _target_section=None: resolver,
    )


def _create_manifest_redraft(client, csrf, run_id, field_id, base, *,
                             target_section=None):
    body = {"base_version_id": base}
    if target_section is not None:
        body["target_section"] = target_section
    headers = unsafe_headers(csrf)
    # Idempotency-Key ⇒ manifest_mode (wie der Editor, lib/redraft.ts).
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json=body, headers=headers,
    )


def _suggestion_for_run(run_id):
    db = SessionLocal()
    try:
        return db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.run_id == run_id)
        )
    finally:
        db.close()


def test_initial_draft_section_redraft_downgrades_grounding_to_warning(
    client, monkeypatch
):
    """T1: Platzhalter-Abschnitt + ungegroundete Angabe ⇒ Erfolg mit Warnung
    (Prüfung nötig) statt failed_grounding_validation."""
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch, section_bundle(suggested_text=UNGROUNDED_SECTION_TEXT))
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_manifest_redraft(
        client, csrf, run_id, FIELD_ID, base, target_section=TARGET_SECTION,
    )
    assert res.status_code == 202, res.text
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    output = op["result"]["section_result"]["field_suggestion_output_v1"]
    assert "unsupported_concrete_claim" in output["unsupported_claim_warnings"]
    suggestion = _suggestion_for_run(run_id)
    assert suggestion.quality_state == "completed_with_warnings"


def test_substantive_section_keeps_hard_grounding_gate(client, monkeypatch):
    """T2 (Regression-Pin): dieselbe ungegroundete Angabe gegen echten Text
    scheitert weiterhin hart — die Lockerung gilt nur im Erst-Entwurf."""
    run_id, _draft_id, base = _setup(draft_text=GOOD_TEXT)
    _arm_fake(monkeypatch, section_bundle(suggested_text=UNGROUNDED_SECTION_TEXT))
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_manifest_redraft(
        client, csrf, run_id, FIELD_ID, base, target_section=TARGET_SECTION,
    )
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["code"] == "failed_grounding_validation"


def test_initial_draft_narrative_field_redraft_succeeds(client, monkeypatch):
    """T3: Executive Summary im Vorlage-Zustand (nur Platzhalter) liefert
    einen Erst-Entwurf statt des generischen Fehlers."""
    from tests.a2_helpers import bundle

    run_id, _draft_id, base = _setup(
        field_id=EXEC_FIELD_ID, character_limit=2000,
        field_name="Executive Summary",
        draft_text=placeholder("Executive summary (wird nicht in Aramis publiziert)"),
    )
    _arm_fake(monkeypatch, bundle(
        field_id=EXEC_FIELD_ID,
        suggested_text=(
            "Zusammenfassung: Der Ansatz DATRIX verankert Datentransaktionen "
            "dezentral und ergänzt bestehende Systeme, ohne sie zu ersetzen. "
            "Forschungs- und Umsetzungspartner arbeiten dabei arbeitsteilig "
            "zusammen; der erwartete Nutzen liegt in höherer Nachvollziehbarkeit "
            "und Datensouveränität. Fehlende Kennzahlen und Baselines bleiben "
            "als Klärungspunkte markiert."
        ),
    ))
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_manifest_redraft(client, csrf, run_id, EXEC_FIELD_ID, base)
    assert res.status_code == 202, res.text
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["proposal"]["human_review_required"] is True
    suggestion = _suggestion_for_run(run_id)
    assert "unsupported_concrete_claim" in suggestion.unsupported_claim_warnings
    assert suggestion.quality_state == "completed_with_warnings"


def test_initial_draft_too_thin_is_rejected_with_clear_reason(client, monkeypatch):
    """Substanzschwelle: ein Nicht-Text wie «Keine zusätzlichen Erläuterungen.»
    wird als Erst-Entwurf verworfen und trägt einen klaren Grund."""
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch, section_bundle(
        suggested_text="4.2 Keine zusätzlichen Erläuterungen.",
    ))
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_manifest_redraft(
        client, csrf, run_id, FIELD_ID, base, target_section=TARGET_SECTION,
    )
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["code"] == "initial_draft_too_thin"


def test_initial_draft_keeps_hallucination_gate_hard(client, monkeypatch):
    """T5 (Ehrlichkeits-Pin): eine erfundene Patent-ID, die nirgends im
    sichtbaren Request steht, scheitert auch im Erst-Entwurf hart."""
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch, section_bundle(
        suggested_text="4.2 Neuheit: geschützt durch Patent EP1234567.",
    ))
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_manifest_redraft(
        client, csrf, run_id, FIELD_ID, base, target_section=TARGET_SECTION,
    )
    assert res.status_code == 202
    op = client.get(f"/api/v1/operations/{res.json()['operation_id']}").json()
    assert op["status"] == "failed"
    assert op["error"]["code"] == "invented_patent_identifier"
