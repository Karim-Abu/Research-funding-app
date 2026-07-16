"""Milestone 9K — MAS reliability & value assurance (deterministic, no provider).

Covers the 10 synthetic regression fixtures + claim extraction, lineage, evidence
sufficiency (exact_verified ≠ supports), the unsupported-claim gate + scope-bound approval
blocking, false-consensus, semantic drift, RunQualitySummary metrics, idempotency/stale,
no-draft-mutation, no-claim_text-in-audit and workspace isolation.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.db.models import (
    AuditEvent,
    ClaimLineage,
    DraftClaim,
    DraftVersion,
    ReviewApproval,
    ReviewFinding,
    RunQualitySummary,
)
from app.db.session import SessionLocal
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability import approval as rapproval
from app.reliability.executor import run_reliability_pass
from app.review import service as review_service
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, OUTSIDER_EMAIL, OUTSIDER_PASSWORD, login
from tests.reliability_fixtures.builders import (
    add_a3_finding,
    add_fact,
    add_source_backed_market_item,
    completed_run_with_draft,
    link_anchor_to_draft,
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _pass(db, run):
    summary = run_reliability_pass(db, run)
    db.commit()
    return summary


def _codes(db, run) -> set[str]:
    rows = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            ReviewFinding.status == "open",
        )
    )
    return {r.finding_code.rsplit(":", 1)[0] if ":drift:" not in r.finding_code
            else "reliability:drift" for r in rows}


def _lineage(db, run):
    return {lin.claim_id: lin for lin in db.scalars(
        select(ClaimLineage).where(ClaimLineage.run_id == run.run_id))}


# --- 1. unsupported market claim -------------------------------------------

def test_unsupported_market_claim(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik ist riesig und die Kunden wachsen stark.")
    _pass(db, run)
    assert "reliability:unsupported" in _codes(db, run)
    summary = rapproval.latest_summary(db, run)
    assert summary.unsupported_claims >= 1


# --- 2. wrong evidence quote (exact_verified but does NOT support) ----------

def test_wrong_evidence_quote_does_not_support(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Der Markt für Logistik-Robotik wächst und Kunden zahlen.")
    link_anchor_to_draft(db, run, v, quote="Das Wetter war gestern sonnig und warm.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    # exact_verified anchor exists, yet it does not support the claim.
    assert lin.sufficiency_status in ("does_not_support_claim", "insufficient_evidence")
    assert lin.lineage_status in ("no_evidence", "weak_evidence")


# --- 3. generic evidence not supporting a specific claim -------------------

def test_generic_evidence_weakly_supports(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht im Prototyp eine sehr hohe Zuverlässigkeit.")
    link_anchor_to_draft(db, run, v, quote="Das Verfahren wird im Bericht beschrieben.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.sufficiency_status in ("weakly_supports_claim", "insufficient_evidence")
    assert "reliability:weak" in _codes(db, run)


# --- 4. quantified claim with missing number -------------------------------

def test_quantified_claim_missing_number(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht eine Genauigkeit von 95 Prozent.")
    link_anchor_to_draft(db, run, v, quote="Die Genauigkeit des Verfahrens ist hoch.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.sufficiency_status == "insufficient_evidence"
    assert "reliability:quantified" in _codes(db, run)


# --- 5. A1 proposed fact used as a confirmed statement ---------------------

def test_proposed_a1_fact_used_as_certain(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Das Team verfügt über umfangreiche Erfahrung mit Logistik-Robotik.")
    add_fact(db, run, statement="Das Team verfügt über Erfahrung mit Logistik-Robotik.",
             status="proposed")
    _pass(db, run)
    assert "reliability:proposed_fact" in _codes(db, run)


# --- 6/7. A2 invented competitor + A3 silence → false consensus ------------

def test_false_consensus_when_a3_silent(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Wettbewerber Foobar AG hat keinen vergleichbaren Marktanteil.",
        created_by="agent")
    _pass(db, run)
    assert "reliability:false_consensus" in _codes(db, run)


def test_a3_finding_prevents_false_consensus_but_not_missing_evidence(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Wettbewerber Foobar AG hat keinen vergleichbaren Marktanteil.",
        created_by="agent")
    add_a3_finding(db, run, field_id="SOL.INNOVATION_SOLUTION.EDITOR")
    _pass(db, run)
    codes = _codes(db, run)
    assert "reliability:false_consensus" not in codes  # A3 flagged → not silent
    # ... but the missing-evidence finding still stands (A3 agreement ≠ evidence).
    assert "reliability:unsupported" in codes or "reliability:market" in codes


# --- 8. semantic drift: exact_verified = approved --------------------------

def test_semantic_drift_detected(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Die Quelle wurde exact_verified und ist damit fachlich genehmigt.")
    _pass(db, run)
    assert "reliability:drift" in _codes(db, run)
    assert rapproval.latest_summary(db, run).semantic_drift_count >= 1


# --- 9. conflicting fragments ---------------------------------------------

def test_conflicting_evidence(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht eine Genauigkeit von 95 Prozent.")
    link_anchor_to_draft(db, run, v, quote="Die Genauigkeit betrug 40 Prozent im Test.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.lineage_status == "conflicting_evidence"
    assert rapproval.latest_summary(db, run).conflicting_claims >= 1


# --- 10. strong claim with proper exact evidence → supported --------------

def test_supported_strong_claim(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht eine Genauigkeit von 95 Prozent.")
    link_anchor_to_draft(
        db, run, v,
        quote="Die gemessene Genauigkeit des Verfahrens betrug 95 Prozent im Test.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.sufficiency_status == "supports_claim"
    assert lin.lineage_status == "direct_evidence"
    summary = rapproval.latest_summary(db, run)
    assert summary.supported_claims >= 1
    # No unsupported finding for a supported claim.
    assert "reliability:unsupported" not in _codes(db, run)


# --- trivial anchors do not count (Teil C4) --------------------------------

def test_trivial_word_anchor_does_not_count_as_coverage(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Der Overhead sinkt deutlich im neuen Verfahren.")
    link_anchor_to_draft(db, run, v, quote="Overhead")
    summary = _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.lineage_status == "no_evidence"
    assert summary.evidence_coverage == 0.0


def test_trivial_numeric_anchor_does_not_count_as_coverage(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Wir erreichen 18 von 26 Punkten im Benchmark.")
    link_anchor_to_draft(db, run, v, quote="18/26")
    summary = _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    assert lin.lineage_status == "no_evidence"
    assert summary.evidence_coverage == 0.0


# --- coverage ≠ correctness (metric discipline) ---------------------------

def test_coverage_distinct_from_sufficiency(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik wächst und die Kunden sind zahlungsbereit.")
    # Evidence linked (coverage > 0) but it does NOT support the claim.
    link_anchor_to_draft(db, run, v, quote="Ein völlig anderes Thema ohne Bezug.")
    summary = _pass(db, run)
    assert summary.evidence_coverage > 0
    assert summary.evidence_correctness_sample_pass_rate < 1.0
    assert summary.quality_flag == "risky"


# --- market claim supported by a source-backed comparison -----------------

def test_market_claim_source_backed(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Wettbewerber Acme dominiert den Robotik-Markt der Kunden.")
    add_source_backed_market_item(
        db, run, name="Acme",
        quote="Acme ist ein Wettbewerber im Robotik-Markt mit vielen Kunden.")
    _pass(db, run)
    lin = next(iter(_lineage(db, run).values()))
    # The source-backed market item is recorded in the claim lineage provenance.
    assert lin.provenance.get("market_item_ids")


# --- idempotency + no draft mutation --------------------------------------

def test_idempotent_and_no_draft_mutation(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik ist riesig und wächst.")
    before = db.get(DraftVersion, v).text
    s1 = _pass(db, run)
    claims1 = db.scalars(select(DraftClaim).where(DraftClaim.run_id == run.run_id)).all()
    s2 = _pass(db, run)
    claims2 = db.scalars(select(DraftClaim).where(DraftClaim.run_id == run.run_id)).all()
    assert s1.summary_id == s2.summary_id  # same scope → reused
    assert len(claims1) == len(claims2)
    assert db.get(DraftVersion, v).text == before  # draft never mutated


def test_changed_draft_marks_summary_stale(db):
    run, draft, v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik ist riesig und wächst.")
    _pass(db, run)
    assert not rapproval.is_stale(db, run)
    # Edit the draft: a new current version → scope changes.
    new_v = "ver-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=new_v, draft_id=draft.draft_id,
        text="Ein ganz neuer, anderer Entwurfstext ohne Marktaussage hier.",
        character_count=10, created_by="user", content_hash="h" + new_v))
    draft.current_version_id = new_v
    db.commit()
    assert rapproval.is_stale(db, run)
    # A stale summary's claim-bound blockers must not govern approval (corr 3/13); since
    # M10.1 (F3) the staleness itself yields a single run-level reason instead, so approval
    # requires a fresh pass.
    reasons = rapproval.reliability_blocker_reasons(db, run)
    assert not any(r.startswith("reliability_blocker:") for r in reasons)
    assert reasons == [f"reliability_stale:{run.run_id}"]


# --- Blockerdisziplin (B5) + Primary-Cause-Dedup (B6) ----------------------

def _open_claim_findings(db, run) -> list[ReviewFinding]:
    return db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            ReviewFinding.status == "open",
            ReviewFinding.target_type == "draft_claim",
        )
    ).all()


def test_strong_unsupported_claim_is_reviewer_risk_until_field_ready(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Wir sind der weltweit erste Anbieter im Markt der Kunden.")
    _pass(db, run)
    # B5 — unbelegte starke Aussage ist standardmässig Reviewer-Risiko
    # (warning), kein Blocker; ohne Feld-Freigabe blockiert nichts.
    findings = _open_claim_findings(db, run)
    assert findings and all(f.severity == "warning" for f in findings)
    reasons = review_service.approval_blockers(db, run, "run", run.run_id)
    assert not any(r.startswith("reliability_blocker:") for r in reasons)


def test_field_approval_escalates_strong_unsupported_claim(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Wir sind der weltweit erste Anbieter im Markt der Kunden.")
    _pass(db, run)
    claim = db.scalar(select(DraftClaim).where(DraftClaim.run_id == run.run_id))
    assert claim.strength == "strong"
    # Nutzer markiert das Feld als bereit (gültige Feld-Freigabe).
    db.add(ReviewApproval(
        approval_id="app-" + uuid.uuid4().hex[:10], run_id=run.run_id,
        workspace_id=run.workspace_id, scope="field", scope_id=claim.field_id,
        status="approved", approval_scope_hash="hash-x",
        review_package_version="rpv-x", approved_by="user-anna"))
    db.flush()
    # Eskalation wirkt in BEIDEN Blocker-Pfaden (Anzeige + hartes Gate).
    reasons = rapproval.reliability_blocker_reasons(db, run)
    assert any(r.startswith("reliability_blocker:") for r in reasons)
    gate_reasons = review_service.approval_blockers(db, run, "run", run.run_id)
    assert any(r.startswith("reliability_blocker:") for r in gate_reasons)


def test_conflicting_evidence_stays_blocker(db):
    run, _d, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht eine Genauigkeit von 95 Prozent.")
    link_anchor_to_draft(db, run, v, quote="Die Genauigkeit betrug 40 Prozent im Test.")
    _pass(db, run)
    findings = _open_claim_findings(db, run)
    conflict = [f for f in findings if f.finding_code.startswith("reliability:conflict:")]
    assert conflict and all(f.severity == "blocker" for f in conflict)
    # Widerspruch mit verknüpfter Quelle blockiert ohne Feld-Freigabe.
    reasons = review_service.approval_blockers(db, run, "run", run.run_id)
    assert any(r.startswith("reliability_blocker:") for r in reasons)


def test_one_primary_finding_per_claim(db):
    # Markt + quantifiziert + stark + unbelegt: früher 3 Findings pro Claim
    # (unsupported/quantified/market), jetzt genau die primäre Ursache.
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik wächst um 12 Prozent pro Jahr.")
    _pass(db, run)
    claims = db.scalars(select(DraftClaim).where(DraftClaim.run_id == run.run_id)).all()
    assert claims
    findings = _open_claim_findings(db, run)
    per_claim: dict[str, int] = {}
    for f in findings:
        per_claim[f.target_id] = per_claim.get(f.target_id, 0) + 1
    assert per_claim and all(count == 1 for count in per_claim.values())
    assert any(f.finding_code.startswith("reliability:unsupported:") for f in findings)


# --- no claim_text in audit ------------------------------------------------

def test_no_claim_text_in_audit(db):
    secret_sentence = "Der geheime Wettbewerber Zebra dominiert den Markt vollständig."
    run, _d, _v = completed_run_with_draft(db, draft_text=secret_sentence)
    _pass(db, run)
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.workspace_id == run.workspace_id)).all()
    blob = json.dumps([e.detail for e in events], ensure_ascii=False, default=str)
    assert "Zebra" not in blob and secret_sentence not in blob


# --- endpoint + workspace isolation ---------------------------------------

def test_export_block_has_summary_without_claim_text(db):
    import json as _json

    from app.exports.snapshot import _reliability_block

    secret = "Der geheime Wettbewerber Zebra dominiert den Markt vollständig."
    run, _d, _v = completed_run_with_draft(db, draft_text=secret)
    _pass(db, run)
    block = _reliability_block(db, run)
    assert block["available"] is True
    assert block["quality_summary"]["claim_count"] >= 1
    assert block["claim_lineage_summary"]  # at least one claim row
    for row in block["claim_lineage_summary"]:
        assert "claim_hash" in row and "claim_text" not in row
    # The raw claim text never appears in the export block.
    assert "Zebra" not in _json.dumps(block, ensure_ascii=False)


def test_reliability_endpoint_and_isolation(client, db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik ist riesig und wächst stark.")
    _pass(db, run)

    anna = login(client, ANNA_EMAIL, ANNA_PASSWORD)  # noqa: F841 (cookie set on client)
    res = client.get(f"/api/v1/runs/{run.run_id}/reliability")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True and body["summary"]["claim_count"] >= 1

    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    denied = client.get(f"/api/v1/runs/{run.run_id}/reliability")
    assert denied.status_code == 404
