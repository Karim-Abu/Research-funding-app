"""R2.4 — Gruppierungs-API + Fix Queue (read-only View über offenen Findings)."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import AnalysisRun, ReviewFinding
from app.db.session import SessionLocal
from app.review.fingerprint import compute_finding_fingerprint
from app.review.fix_queue import build_fix_queue
from tests.review_helpers import get_review, setup_completed_run

_CLAIMS = (
    "Der Markt wächst um 40 Prozent pro Jahr.",
    "Die Ausschussquote sinkt um 15 Prozent.",
    "Die Latenz liegt unter 250 Millisekunden.",
    "Der Energieverbrauch sinkt um 30 Prozent.",
)


_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
_QUANT_KEY = f"evidence_risk|reliability:quantified|{_FIELD.lower()}"


def _add_reliability_finding(
    db, run, claim_text: str, index: int, field_id: str = _FIELD
) -> None:
    db.add(
        ReviewFinding(
            finding_id=str(uuid.uuid4()),
            run_id=run.run_id,
            workspace_id=run.workspace_id,
            profile_id="M9K.reliability_assurance",
            field_id=field_id,
            requirement_id=None,
            severity="warning",
            description=(
                "Quantifizierte Aussage ohne passende Zahl im Beleg "
                "(Beleg-Suffizienzprüfung)."
            ),
            suggested_improvement=None,
            status="open",
            advisory=True,
            source="agent",
            finding_code=f"reliability:quantified:claim-{index}",
            target_type="draft_claim",
            target_id=f"claim-{index}",
            recommended_next_action=None,
            fingerprint=compute_finding_fingerprint(
                "reliability:quantified",
                field_id,
                claim_core=claim_text,
            ),
            severity_class="evidence_risk",
        )
    )


def _build(run_id: str):
    with SessionLocal() as db:
        run = db.get(AnalysisRun, run_id)
        return build_fix_queue(db, run)


class TestGrouping:
    def test_four_same_family_different_claims_one_group(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            for i, claim in enumerate(_CLAIMS):
                _add_reliability_finding(db, run, claim, i)
            db.commit()

        view = _build(run_id)
        quant = [
            g for g in view.grouped_findings if g.group_key == _QUANT_KEY
        ]
        assert len(quant) == 1, "vier gleichartige Findings ⇒ genau EINE Gruppe"
        group = quant[0]
        assert group.count == 4
        # Feldbewusster Titel: «<Feld-Label>: <Familientitel>».
        assert group.title.endswith("Quantifizierte Aussage ohne passenden Zahlenbeleg")
        assert group.target_field_id == _FIELD
        assert group.area == "evidenz_suffizienz"
        # Die Einzel-Claims bleiben als Beispiele sichtbar (max 5).
        assert len(group.examples) == 4
        assert {e.target_id for e in group.examples} == {
            "claim-0", "claim-1", "claim-2", "claim-3",
        }
        # Unterschiedliche Claims ⇒ unterschiedliche fingerprints (Row-Ebene).
        with SessionLocal() as db:
            fps = {
                f.fingerprint
                for f in db.scalars(
                    select(ReviewFinding).where(
                        ReviewFinding.run_id == run_id,
                        ReviewFinding.finding_code.like("reliability:quantified:%"),
                    )
                )
            }
        assert len(fps) == 4

    def test_group_key_contains_no_claim_text(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            _add_reliability_finding(
                db, run, "PROJECT_SECRET_MARKER_123 wächst um 40 Prozent.", 0
            )
            db.commit()
        view = _build(run_id)
        for group in view.grouped_findings:
            assert "PROJECT_SECRET_MARKER_123" not in group.group_key
            assert "40" not in group.group_key


class TestPriorities:
    def test_placeholder_before_evidence_risk(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            _add_reliability_finding(db, run, _CLAIMS[0], 0)
            db.commit()
        view = _build(run_id)
        keys = [g.group_key for g in view.next_actions]
        placeholder = next(
            i for i, k in enumerate(keys) if "|draft_placeholder" in k
        )
        evidence = next(i for i, k in enumerate(keys) if k == _QUANT_KEY)
        assert placeholder < evidence, "export_blocker (Platzhalter) vor evidence_risk"

    def test_research_partner_blocker_before_reviewer_risk(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(
            client, with_research_partner=False, title="FQ ohne Forschungspartner"
        )
        get_review(client, run_id)
        # Synthetisches reviewer_risk-Finding (Rubric existiert erst ab R6.4).
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            db.add(
                ReviewFinding(
                    finding_id=str(uuid.uuid4()), run_id=run.run_id,
                    workspace_id=run.workspace_id, profile_id="rubric-test",
                    field_id="SOL.INNOVATION_SOLUTION.EDITOR", requirement_id=None,
                    severity="warning", description="Test-Rubric-Hinweis.",
                    suggested_improvement=None, status="open", advisory=True,
                    source="agent", finding_code="rubric:test:1",
                    target_type="portal_field_draft", target_id="x",
                    recommended_next_action=None, severity_class="reviewer_risk",
                )
            )
            db.commit()
        view = _build(run_id)
        keys = [(g.severity_class, i) for i, g in enumerate(view.next_actions)]
        eligibility = next(i for c, i in keys if c == "eligibility_blocker")
        reviewer = next(i for c, i in keys if c == "reviewer_risk")
        assert eligibility < reviewer, "Research-Partner-Blocker vor Reviewer-Risk"


class TestAggregation:
    def test_hundred_similar_claim_findings_one_task(self, client) -> None:
        """B2/B3 — 100 gleichartige claimweise Probleme im selben Feld sind
        EINE gruppierte Aufgabe (count 100, max 5 Beispiele), kein Blocker-Berg."""
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            for i in range(100):
                _add_reliability_finding(db, run, f"Aussage {i} mit Zahl {i}.", i)
            db.commit()

        view = _build(run_id)
        quant = [g for g in view.grouped_findings if g.group_key == _QUANT_KEY]
        assert len(quant) == 1
        assert quant[0].count == 100
        assert len(quant[0].examples) == 5
        # Die 100 Claim-Warnings erzeugen KEINE blockierende Aufgabe — die
        # blockierenden Aufgaben stammen nur aus den formalen Blocker-Gruppen
        # (Template-Platzhalter der Fixture); die technische Claim-Zahl bleibt
        # getrennt sichtbar.
        blocker_groups = [g for g in view.grouped_findings if g.severity == "blocker"]
        assert view.blocking_task_count == len(blocker_groups)
        assert all("reliability" not in g.group_key for g in blocker_groups)
        assert view.evidence_note_count == 100

    def test_same_family_different_fields_split_into_groups(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            _add_reliability_finding(db, run, _CLAIMS[0], 0)
            _add_reliability_finding(
                db, run, _CLAIMS[1], 1, field_id="SOL.INNOVATION_SOLUTION.EDITOR"
            )
            db.commit()
        view = _build(run_id)
        quant = [
            g for g in view.grouped_findings
            if "|reliability:quantified|" in g.group_key
        ]
        assert len(quant) == 2, "verschiedene Felder ⇒ getrennte Aufgaben"
        assert {g.target_field_id for g in quant} == {
            _FIELD, "SOL.INNOVATION_SOLUTION.EDITOR",
        }

    def test_teil_d_family_rank_within_reviewer_risk(self, client) -> None:
        """Teil D — KPI-Kette vor Risiko-Framing innerhalb reviewer_risk."""
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            for code, field in (
                ("rubric:risk_scope:f1", "SOL.INNOVATION_SOLUTION.EDITOR"),
                ("rubric:kpi_chain:f2", "VC.BUSINESS_TARGETS_MODEL.EDITOR"),
            ):
                db.add(ReviewFinding(
                    finding_id=str(uuid.uuid4()), run_id=run.run_id,
                    workspace_id=run.workspace_id, profile_id="R6.rubric_v0",
                    field_id=field, requirement_id=None, severity="warning",
                    description="Rubric-Hinweis.", suggested_improvement=None,
                    status="open", advisory=True, source="deterministic_review",
                    finding_code=code, target_type="portal_field_draft",
                    target_id=field, recommended_next_action=None,
                    severity_class="reviewer_risk",
                ))
            db.commit()
        view = _build(run_id)
        keys = [g.group_key for g in view.next_actions]
        kpi = next(i for i, k in enumerate(keys) if "rubric:kpi_chain" in k)
        risk = next(i for i, k in enumerate(keys) if "rubric:risk_scope" in k)
        assert kpi < risk


class TestApi:
    def test_endpoint_returns_view(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        res = client.get(f"/api/v1/runs/{run_id}/review/fix-queue")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["run_id"] == run_id
        assert body["total_open_findings"] >= 1
        assert body["grouped_findings"]
        assert body["next_actions"][0]["severity_class"] == "export_blocker"
        # Gruppen decken alle offenen Findings ab (Summe der counts).
        assert sum(g["count"] for g in body["grouped_findings"]) == body[
            "total_open_findings"
        ]
        # B7 — additive Zähler sind vorhanden und konsistent zur Gruppierung.
        assert body["blocking_task_count"] == sum(
            1 for g in body["grouped_findings"] if g["severity"] == "blocker"
        )
        assert body["evidence_note_count"] >= 0

    def test_endpoint_view_is_read_only(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        with SessionLocal() as db:
            before = {
                (f.finding_id, f.status)
                for f in db.scalars(
                    select(ReviewFinding).where(ReviewFinding.run_id == run_id)
                )
            }
        assert client.get(f"/api/v1/runs/{run_id}/review/fix-queue").status_code == 200
        with SessionLocal() as db:
            after = {
                (f.finding_id, f.status)
                for f in db.scalars(
                    select(ReviewFinding).where(ReviewFinding.run_id == run_id)
                )
            }
        assert before == after
