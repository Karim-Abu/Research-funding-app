"""Unsupported-claim gate + reliability-finding persistence (Milestone 9K, STEP 5).

Maps (claim strength × lineage × sufficiency) onto advisory/blocker findings, persisted as
``ReviewFinding`` rows reusing ``source="agent"`` + ``profile_id="M9K.reliability_assurance"``
(binding correction 1 — no new source enum, no migration). Findings target the DraftClaim
(``target_type="draft_claim"``, ``target_id=claim_id``). No draft mutation, no claim deletion,
no auto-approve. Wording is an "evidence sufficiency check", never "verified as true" (corr 4).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, ReviewFinding
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability.extract import ExtractedClaim, is_quantified
from app.reliability.lineage import LineageResult
from app.reliability import sufficiency as suff
from app.repositories import audit


@dataclass(frozen=True)
class ReliabilityFindingSpec:
    finding_code: str
    severity: str  # blocker | warning | info
    description: str
    field_id: str
    target_type: str = "draft_claim"  # draft_claim | portal_field_draft
    target_id: str = ""  # claim_id (draft_claim) or field_id (portal_field_draft)


def _claim_spec(code: str, severity: str, description: str, claim) -> ReliabilityFindingSpec:
    return ReliabilityFindingSpec(
        code, severity, description, claim.field_id, "draft_claim", claim.claim_id
    )


def _sev_for_strength(strong: bool) -> str:
    return "blocker" if strong else "warning"


def gate_claim(claim: ExtractedClaim, lineage: LineageResult) -> list[ReliabilityFindingSpec]:
    """Findings for one claim. Only claims that require evidence are gated."""
    if not claim.requires_evidence:
        return []
    specs: list[ReliabilityFindingSpec] = []
    strong = claim.strength == "strong"
    ls, ss = lineage.lineage_status, lineage.sufficiency_status

    if ls == "conflicting_evidence":
        specs.append(_claim_spec(
            f"reliability:conflict:{claim.claim_id}", _sev_for_strength(strong),
            "Konfliktende Belege: die verknüpfte Quelle scheint dieser Aussage unter den "
            "definierten Kriterien zu widersprechen. Menschliche Prüfung nötig.", claim,
        ))
    elif ls == "no_evidence":
        specs.append(_claim_spec(
            f"reliability:unsupported:{claim.claim_id}", _sev_for_strength(strong),
            "Nicht belegte Aussage: für diese Aussage wurde keine verknüpfte Quelle "
            "gefunden (Beleg-Suffizienzprüfung). Bitte belegen oder abschwächen.", claim,
        ))
    elif not lineage.supported:
        # weak / indirect / insufficient support → needs review (warning).
        specs.append(_claim_spec(
            f"reliability:weak:{claim.claim_id}", "warning",
            "Schwach belegte Aussage: die Quelle scheint die Aussage unter den definierten "
            "Kriterien nur teilweise zu stützen. Menschliche Prüfung empfohlen.", claim,
        ))

    # Quantified claim without a matching number in the evidence.
    if is_quantified(claim) and ss == suff.INSUFFICIENT and not lineage.supported:
        specs.append(_claim_spec(
            f"reliability:quantified:{claim.claim_id}", _sev_for_strength(strong),
            "Quantifizierte Aussage ohne passende Zahl im Beleg (Beleg-Suffizienzprüfung).",
            claim,
        ))

    # Market/competitor claim without a source-backed comparison or supporting anchor.
    if claim.claim_type == "market" and not lineage.market_backed and not lineage.supported:
        specs.append(_claim_spec(
            f"reliability:market:{claim.claim_id}", "warning",
            "Marktaussage ohne quellenbelegte Markt-/Konkurrenzangabe.", claim,
        ))

    # Proposed-only A1 fact stated as certain.
    if lineage.proposed_fact_as_certain and not lineage.supported:
        specs.append(_claim_spec(
            f"reliability:proposed_fact:{claim.claim_id}", _sev_for_strength(strong),
            "Vorgeschlagene (nicht bestätigte) A1-Angabe wird als sichere Aussage "
            "verwendet. Bitte bestätigen oder als offen kennzeichnen.", claim,
        ))
    return specs


def apply_reliability_findings(
    db: Session, run: AnalysisRun, specs: list[ReliabilityFindingSpec]
) -> tuple[int, int]:
    """Idempotently upsert M9K reliability findings (source=agent, profile=reliability) and
    resolve reliability findings no longer emitted. NEVER touches deterministic/human/A3 rows.
    Returns (blocker_count, warning_count) among the currently-open reliability findings."""
    existing = {
        f.finding_code: f
        for f in db.scalars(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.source == "agent",
                ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            )
        )
    }
    seen: set[str] = set()
    for spec in specs:
        seen.add(spec.finding_code)
        advisory = spec.severity != "blocker"
        row = existing.get(spec.finding_code)
        if row is None:
            row = ReviewFinding(
                finding_id=str(uuid.uuid4()), run_id=run.run_id,
                workspace_id=run.workspace_id, profile_id=RELIABILITY_PROFILE_ID,
                field_id=spec.field_id, requirement_id=None,
                severity=spec.severity, description=spec.description,
                suggested_improvement=None, status="open", advisory=advisory,
                source="agent", finding_code=spec.finding_code,
                target_type=spec.target_type, target_id=spec.target_id,
                recommended_next_action=None,
            )
            db.add(row)
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="reliability.finding_created", target_type="review_finding",
                target_id=row.finding_id,
                detail={"code": spec.finding_code, "severity": spec.severity},
            )
        else:
            row.severity = spec.severity
            row.description = spec.description
            row.field_id = spec.field_id
            row.target_type = spec.target_type
            row.target_id = spec.target_id
            row.advisory = advisory
            if row.status == "resolved":
                row.status = "open"

    blocker = warning = 0
    for code, row in existing.items():
        if code not in seen and row.status == "open":
            row.status = "resolved"
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="reliability.finding_updated", target_type="review_finding",
                target_id=row.finding_id, detail={"status": "resolved"},
            )
    for spec in specs:
        if spec.severity == "blocker":
            blocker += 1
        elif spec.severity == "warning":
            warning += 1
    db.flush()
    return blocker, warning
