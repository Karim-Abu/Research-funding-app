"""Deterministic review checks (Milestone 7).

Pure, rule-based aggregation over already-persisted M4-M6 artifacts. Every
finding has a stable ``finding_code`` so re-running the checks is idempotent and
fixes clear the finding. This module NEVER judges market fit, novelty, business
quality or persuasiveness, and makes no LLM/network/provider call.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    OpenIssue,
    PortalFieldDraft,
    RequirementAssessment,
    RunProjectSnapshot,
)
from app.drafts import char_count, has_placeholder, is_empty
from app.drafts.charcount import within_limit
from app.registry import get_registry
from app.runs import project_snapshot


@dataclass(frozen=True)
class FindingSpec:
    """One deterministic finding candidate. ``finding_code`` is the idempotency
    key (unique per run+source)."""

    finding_code: str
    severity: str  # blocker | warning | info
    description: str
    target_type: str  # portal_field_draft | requirement_assessment | evidence_link
    target_id: str
    field_id: str | None = None
    requirement_id: str | None = None
    suggested_improvement: str | None = None
    recommended_next_action: str | None = None


def _latest_snapshot(db: Session, run_id: str) -> RunProjectSnapshot | None:
    return db.scalar(
        select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run_id)
    )


def compute_finding_specs(db: Session, run: AnalysisRun) -> list[FindingSpec]:
    """Deterministic review findings for a completed run, in stable order."""
    registry = get_registry()
    supported_field_ids = {f.field_id for f in registry.m6_draft_fields()}
    specs: list[FindingSpec] = []

    # 1. Open blocker OpenIssues (e.g. blocked requirements, missing eligible
    #    research partner). Field-level draft warnings are covered by the draft
    #    checks below and are excluded here to avoid duplicates.
    blocker_issues = db.scalars(
        select(OpenIssue)
        .where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.status == "open",
            OpenIssue.severity == "blocker",
        )
        .order_by(OpenIssue.created_at.asc(), OpenIssue.issue_id.asc())
    )
    for issue in blocker_issues:
        requirement_id = (
            issue.target_id
            if issue.target_type in ("requirement", "requirement_assessment")
            else None
        )
        specs.append(
            FindingSpec(
                finding_code=f"open_issue_blocker:{issue.issue_id}",
                severity="blocker",
                description=issue.description,
                target_type="requirement_assessment",
                target_id=issue.target_id,
                requirement_id=requirement_id,
                recommended_next_action=issue.recommended_next_action,
            )
        )

    # 2. Requirements awaiting human input (needs_input) → warning.
    snapshot = _latest_snapshot(db, run.run_id)
    snapshot_stale = snapshot is not None and project_snapshot.is_stale(db, snapshot)
    assessments = db.scalars(
        select(RequirementAssessment)
        .where(RequirementAssessment.run_id == run.run_id)
        .order_by(RequirementAssessment.created_at.asc())
    )
    for assessment in assessments:
        if assessment.status == "needs_input":
            # Der Anforderungstitel macht die sonst identischen Beispielzeilen in
            # der Fix-Queue unterscheidbar (reiner Anzeigetext, kein DTO-Feld).
            requirement = registry.requirements.get(assessment.requirement_id)
            if requirement is not None and requirement.title:
                needs_input_description = (
                    f"Anforderung «{requirement.title}» benötigt zusätzliche "
                    "Angaben, bevor sie abschliessend beurteilt werden kann."
                )
            else:
                needs_input_description = (
                    "Diese Anforderung benötigt zusätzliche Angaben, bevor sie "
                    "abschliessend beurteilt werden kann."
                )
            specs.append(
                FindingSpec(
                    finding_code=f"requirement_needs_input:{assessment.requirement_id}",
                    severity="warning",
                    description=needs_input_description,
                    target_type="requirement_assessment",
                    target_id=assessment.assessment_id,
                    requirement_id=assessment.requirement_id,
                )
            )
        # 3. Stale assessment: persisted snapshot drifted from current inputs.
        if snapshot_stale or assessment.stale:
            specs.append(
                FindingSpec(
                    finding_code=f"stale_assessment:{assessment.requirement_id}",
                    severity="warning",
                    description=(
                        "Die Beurteilung beruht auf einem veralteten Projekt-/"
                        "Partner-Snapshot. Eine erneute Prüfung wird empfohlen."
                    ),
                    target_type="requirement_assessment",
                    target_id=assessment.assessment_id,
                    requirement_id=assessment.requirement_id,
                )
            )

    # Draft checks. Active draft-version evidence links keyed by current version.
    drafts = list(
        db.scalars(
            select(PortalFieldDraft)
            .where(PortalFieldDraft.run_id == run.run_id)
            .order_by(PortalFieldDraft.field_id.asc())
        )
    )
    current_version_ids = [
        d.current_version_id for d in drafts if d.current_version_id
    ]
    links = list(
        db.scalars(
            select(EvidenceLink).where(
                EvidenceLink.run_id == run.run_id,
                EvidenceLink.target_type == "draft_version",
            )
        )
    )
    anchors = {
        a.anchor_id: a
        for a in db.scalars(
            select(EvidenceAnchor).where(EvidenceAnchor.run_id == run.run_id)
        )
    }
    has_verified_anchor = any(
        a.verification_status == "exact_verified" for a in anchors.values()
    )
    links_by_target: dict[str, list[EvidenceLink]] = {}
    for link in links:
        links_by_target.setdefault(link.target_id, []).append(link)

    for draft in drafts:
        version = (
            db.get(DraftVersion, draft.current_version_id)
            if draft.current_version_id
            else None
        )
        text = version.text if version else ""
        supported = draft.field_id in supported_field_ids

        # 4. Empty supported field → blocker.
        if supported and is_empty(text):
            specs.append(
                FindingSpec(
                    finding_code=f"draft_empty:{draft.field_id}",
                    severity="blocker",
                    description=(
                        f"Das Pflichtfeld „{draft.field_name}“ ist leer und muss "
                        "ausgefüllt werden."
                    ),
                    target_type="portal_field_draft",
                    target_id=draft.draft_id,
                    field_id=draft.field_id,
                    recommended_next_action="Feldinhalt fachlich ergänzen.",
                )
            )
        # 5. Visible placeholder in a supported mandatory field → blocker
        #    (deferred repeated-instance fields are not M6 draft fields → warning
        #    only, handled implicitly by `supported`).
        elif has_placeholder(text):
            specs.append(
                FindingSpec(
                    finding_code=f"draft_placeholder:{draft.field_id}",
                    severity="blocker" if supported else "warning",
                    description=(
                        f"Das Feld „{draft.field_name}“ enthält noch sichtbare "
                        "Platzhalter ([[Angabe ergänzen: …]])."
                    ),
                    target_type="portal_field_draft",
                    target_id=draft.draft_id,
                    field_id=draft.field_id,
                    recommended_next_action="Platzhalter durch konkrete Angaben ersetzen.",
                )
            )

        # 6. Over character limit → blocker (edits are guarded, but templates and
        #    legacy data are re-checked defensively).
        if (
            version
            and draft.character_limit is not None
            and not within_limit(text, draft.character_limit)
        ):
            specs.append(
                FindingSpec(
                    finding_code=f"draft_over_limit:{draft.field_id}",
                    severity="blocker",
                    description=(
                        f"Das Feld „{draft.field_name}“ überschreitet das Limit von "
                        f"{draft.character_limit} Zeichen ({char_count(text)})."
                    ),
                    target_type="portal_field_draft",
                    target_id=draft.draft_id,
                    field_id=draft.field_id,
                )
            )

        active_links = [
            link
            for link in links_by_target.get(draft.current_version_id or "", [])
            if link.status == "active"
        ]
        # 7. Stale draft evidence links on the current version → warning.
        for link in links_by_target.get(draft.current_version_id or "", []):
            if link.status == "stale":
                specs.append(
                    FindingSpec(
                        finding_code=f"stale_evidence_link:{link.evidence_link_id}",
                        severity="warning",
                        description=(
                            f"Für „{draft.field_name}“ besteht ein veralteter "
                            "Evidenz-Verweis. Bitte prüfen oder neu verknüpfen."
                        ),
                        target_type="evidence_link",
                        target_id=link.evidence_link_id,
                        field_id=draft.field_id,
                    )
                )
        # 8. Active link to a not-exact-verified anchor → warning.
        for link in active_links:
            anchor = anchors.get(link.anchor_id)
            if anchor is not None and anchor.verification_status != "exact_verified":
                specs.append(
                    FindingSpec(
                        finding_code=(
                            f"unverified_linked_evidence:{link.evidence_link_id}"
                        ),
                        severity="warning",
                        description=(
                            f"Für „{draft.field_name}“ ist eine nicht exakt "
                            "verifizierte Fundstelle verknüpft."
                        ),
                        target_type="evidence_link",
                        target_id=link.evidence_link_id,
                        field_id=draft.field_id,
                    )
                )
        # 9. User-edited field with no active evidence link although verified
        #    evidence exists in the run → warning.
        if (
            version is not None
            and version.created_by == "user"
            and not active_links
            and has_verified_anchor
            and not is_empty(text)
        ):
            specs.append(
                FindingSpec(
                    finding_code=f"missing_evidence_link:{draft.field_id}",
                    severity="warning",
                    description=(
                        f"Für „{draft.field_name}“ ist kein aktiver Evidenz-Verweis "
                        "hinterlegt, obwohl verifizierte Fundstellen vorliegen."
                    ),
                    target_type="portal_field_draft",
                    target_id=draft.draft_id,
                    field_id=draft.field_id,
                )
            )

    return specs
