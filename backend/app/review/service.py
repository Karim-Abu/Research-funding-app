"""Review service: read model, human decisions/comments, approval gating.

All gates are deterministic and re-derived from raw persisted state, so a human
dismissing a derived finding can never bypass a hard gate (placeholders, blocker
open issues, stale links). No semantic judgement, no provider/LLM call.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.review import (
    HumanDecision as HumanDecisionContract,
)
from app.contracts.review import (
    ReviewApproval as ReviewApprovalContract,
)
from app.contracts.review import (
    ReviewFinding as ReviewFindingContract,
)
from app.contracts.review import ApprovalCreate, ReviewPackage, ReviewStatusView
from app.db.models import (
    AnalysisRun,
    DraftSuggestion,
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    HumanDecision,
    OpenIssue,
    PortalFieldDraft,
    RequirementAssessment,
    ReviewApproval,
    ReviewFinding,
    RunProjectSnapshot,
)
from app.drafts import has_placeholder, is_empty
from app.drafts.charcount import within_limit
from app.registry import get_registry
from app.repositories import audit, controls
from app.repositories import draft_suggestions as suggestions_repo
from app.repositories import drafts as drafts_repo
from app.repositories import requirements as requirements_repo
from app.review import package as review_package
from app.review.copy_readiness import copy_readiness_for_run
from app.runs import project_snapshot

_NOT_FOUND = "Resource not found"


# --- contract mappers ------------------------------------------------------


def _finding_to_contract(finding: ReviewFinding) -> ReviewFindingContract:
    return ReviewFindingContract(
        finding_id=finding.finding_id,
        profile_id=finding.profile_id,
        field_id=finding.field_id,
        target_section=finding.target_section,
        requirement_id=finding.requirement_id,
        severity=finding.severity,
        description=finding.description,
        suggested_improvement=finding.suggested_improvement,
        recommended_next_action=finding.recommended_next_action,
        status=finding.status,
        advisory=finding.advisory,
    )


def _decision_to_contract(decision: HumanDecision) -> HumanDecisionContract:
    return HumanDecisionContract(
        target_type=decision.target_type,
        target_id=decision.target_id,
        action=decision.action,
        comment=decision.comment,
        decision_id=decision.decision_id,
        user_id=decision.user_id,
        run_id=decision.run_id,
        created_at=decision.created_at,
    )


def _approval_to_contract(approval: ReviewApproval) -> ReviewApprovalContract:
    return ReviewApprovalContract(
        approval_id=approval.approval_id,
        run_id=approval.run_id,
        scope=approval.scope,
        status=approval.status,
        approval_scope_hash=approval.approval_scope_hash,
        approved_by=approval.approved_by,
        created_at=approval.created_at,
    )


# --- read model ------------------------------------------------------------


def _is_stale(db: Session, run: AnalysisRun) -> bool:
    snapshot = db.scalar(
        select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run.run_id)
    )
    return snapshot is not None and project_snapshot.is_stale(db, snapshot)


def read_review_package(db: Session, run: AnalysisRun) -> ReviewPackage:
    """Assemble the contract ReviewPackage. Pure read — never mutates."""
    scope_hash = review_package.compute_scope_hash(db, run)
    version = review_package.package_version(scope_hash)

    requirements = requirements_repo.to_contracts(
        db, run.run_id, stale=_is_stale(db, run)
    )
    fields = []
    readiness = copy_readiness_for_run(db, run)
    for field in get_registry().m6_draft_fields():
        draft = drafts_repo.get_draft(db, run.run_id, field.field_id)
        if draft is not None:
            fields.append(
                drafts_repo.to_contract(
                    db, draft, copy_readiness=readiness.get(field.field_id)
                )
            )

    findings = [
        _finding_to_contract(f)
        for f in db.scalars(
            select(ReviewFinding)
            .where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.status == "open",
            )
            .order_by(ReviewFinding.created_at.asc())
        )
    ]
    open_issues = [
        requirements_repo._issue_to_contract(i)
        for i in db.scalars(
            select(OpenIssue)
            .where(OpenIssue.run_id == run.run_id, OpenIssue.status == "open")
            .order_by(OpenIssue.created_at.asc())
        )
    ]
    blocker, warning, stale = review_package.counts(db, run)
    status = review_package.approval_status(db, run, scope_hash)

    return ReviewPackage(
        run_id=run.run_id,
        requirements=requirements,
        fields=fields,
        findings=findings,
        approval_status=status,
        blocker_count=blocker,
        warning_count=warning,
        open_issues=open_issues,
        review_package_version=version,
        current_approval_scope_hash=scope_hash,
        recheck_required=run.recheck_required,
        stale_finding_count=stale,
    )


def read_status_view(db: Session, run: AnalysisRun) -> ReviewStatusView:
    """R1.2 — kanonischer Status-View. Pure read, additive.

    Reuses the exact ReviewPackage primitives (``counts``/``approval_status``/
    ``package_version``) so every screen showing these numbers agrees with the
    Qualitätsprüfung. ``stale`` mirrors the user-facing «Prüfung nicht aktuell»:
    a draft edit sets ``recheck_required`` (scope hash outdated) or the project
    snapshot diverged.
    """
    scope_hash = review_package.compute_scope_hash(db, run)
    blocker, warning, _stale_findings = review_package.counts(db, run)
    status = review_package.approval_status(db, run, scope_hash)

    # RUN 2A Slice 1: offene menschliche Prüfungen/Bestätigungen kommen aus der
    # EINEN Zählquelle (offene Review-Issues minus menschlich bestätigte
    # Anforderungen) — nicht pauschal aus needs_input-Assessments. Ein
    # erfüllter Hybrid-Check mit offener Bestätigung zählt hier, bleibt aber in
    # allen Compliance-Zählern «fulfilled».
    from app.repositories.requirements import open_human_review_count

    human_review_count = open_human_review_count(db, run.run_id)

    per_area: dict[str, int] = {}
    for finding in db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.status == "open",
        )
    ):
        area = (finding.field_id or "").split(".")[0] or "general"
        per_area[area] = per_area.get(area, 0) + 1

    latest = review_package.latest_approval(db, run)
    # B7 — gruppierte Aufgaben-/Evidenzhinweis-Zähler aus der Fix Queue
    # (eine Quelle, keine parallele Zähllogik). Lazy Import: fix_queue wird
    # hier nur für die Zähler gebraucht.
    from app.review.fix_queue import build_fix_queue

    queue = build_fix_queue(db, run)
    return ReviewStatusView(
        run_id=run.run_id,
        blocker_count=blocker,
        warning_count=warning,
        human_review_count=human_review_count,
        stale=bool(run.recheck_required or _is_stale(db, run)),
        approval_status=status,
        review_package_version=review_package.package_version(scope_hash),
        per_area_counts=per_area,
        last_reviewed_at=latest.created_at if latest is not None else None,
        blocking_task_count=queue.blocking_task_count,
        evidence_note_count=queue.evidence_note_count,
    )


# --- human decisions / section comments ------------------------------------

_FINDING_ACTION_STATUS = {
    "dismiss": "dismissed",
    "override": "overridden",
    "confirm": "resolved",
    "request_changes": "open",
}


def _draft_for_target(db: Session, run: AnalysisRun, draft_id: str) -> PortalFieldDraft:
    draft = db.scalar(
        select(PortalFieldDraft).where(
            PortalFieldDraft.draft_id == draft_id,
            PortalFieldDraft.run_id == run.run_id,
        )
    )
    if draft is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Draft not found for this run.",
        )
    return draft


def _require_target(db: Session, run: AnalysisRun, target_type: str, target_id: str):
    if target_type == "review_finding":
        row = db.scalar(
            select(ReviewFinding).where(
                ReviewFinding.finding_id == target_id,
                ReviewFinding.run_id == run.run_id,
            )
        )
    elif target_type == "requirement_assessment":
        row = db.scalar(
            select(RequirementAssessment).where(
                RequirementAssessment.assessment_id == target_id,
                RequirementAssessment.run_id == run.run_id,
            )
        )
    elif target_type == "evidence_anchor":
        row = db.scalar(
            select(EvidenceAnchor).where(
                EvidenceAnchor.anchor_id == target_id,
                EvidenceAnchor.run_id == run.run_id,
            )
        )
    elif target_type == "portal_field_draft":
        row = _draft_for_target(db, run, target_id)
    elif target_type == "draft_suggestion":
        row = db.scalar(
            select(DraftSuggestion).where(
                DraftSuggestion.suggestion_id == target_id,
                DraftSuggestion.run_id == run.run_id,
            )
        )
    else:  # pragma: no cover - schema-validated
        row = None
    if row is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Decision target not found for this run.",
        )
    return row


def record_human_decision(
    db: Session, run: AnalysisRun, decision, actor_user_id: str
) -> HumanDecisionContract:
    target = _require_target(db, run, decision.target_type, decision.target_id)

    # C4 — nur ein noch offener Vorschlag ist ablehnbar (accepted/expired/
    # rejected sind bereits entschieden). Vor dem Insert prüfen (fail-closed).
    if decision.target_type == "draft_suggestion" and target.status != "proposed":
        raise ProblemException(
            status=409, code="suggestion_not_rejectable", title="Conflict",
            detail="Dieser Vorschlag ist bereits entschieden (übernommen, abgelaufen oder abgelehnt).",
        )

    record = HumanDecision(
        decision_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        user_id=actor_user_id,
        target_type=decision.target_type,
        target_id=decision.target_id,
        action=decision.action,
        comment=decision.comment,
    )
    db.add(record)
    db.flush()
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="review.decision_created", target_type="human_decision",
        target_id=record.decision_id,
        detail={"target_type": decision.target_type, "action": decision.action},
    )

    if decision.target_type == "review_finding":
        # Human review status only; the deterministic gate re-derives hard blocks.
        target.status = _FINDING_ACTION_STATUS[decision.action]
        target.updated_at = record.created_at
    elif decision.target_type == "portal_field_draft":
        _apply_comment(db, run, target, decision, actor_user_id)
    elif decision.target_type == "draft_suggestion":
        # C4 — Ablehnung persistieren; der Vorschlagstext bleibt erhalten,
        # das Audit trägt nur target_type/action/IDs (kein Rohtext).
        suggestions_repo.mark_rejected(db, target, decided_by=actor_user_id)
    # requirement_assessment / evidence_anchor decisions are review-level only:
    # recorded + audited, never mutating the deterministic assessment or the
    # technical EvidenceAnchor.verification_status (corr. #3).

    db.flush()
    return _decision_to_contract(record)


def _apply_comment(
    db: Session, run: AnalysisRun, draft: PortalFieldDraft, decision, actor_user_id: str
) -> None:
    """Section comments are represented as human ReviewFindings on the field."""
    registry = get_registry()
    if decision.action == "request_changes":
        text = (decision.comment or "").strip()
        if not text:
            raise ProblemException(
                status=422, code="comment_required", title="Unprocessable Entity",
                detail="A request_changes comment must include text.",
            )
        finding = ReviewFinding(
            finding_id=str(uuid.uuid4()),
            run_id=run.run_id,
            workspace_id=run.workspace_id,
            profile_id=registry.profile_id or "deterministic-review-1",
            field_id=draft.field_id,
            requirement_id=None,
            severity="warning",
            description=text,
            suggested_improvement=None,
            status="open",
            advisory=True,
            source="human",
            finding_code=f"comment:{uuid.uuid4()}",
            target_type="portal_field_draft",
            target_id=draft.draft_id,
            recommended_next_action=None,
        )
        db.add(finding)
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
            action="comment.created", target_type="review_finding",
            target_id=finding.finding_id, detail={"field_id": draft.field_id},
        )
    else:  # confirm → resolve the field's open human comments
        for finding in db.scalars(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.source == "human",
                ReviewFinding.field_id == draft.field_id,
                ReviewFinding.status == "open",
            )
        ):
            finding.status = "resolved"
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
                action="comment.resolved", target_type="review_finding",
                target_id=finding.finding_id,
            )


# --- approval gating -------------------------------------------------------


def _scope_drafts(
    db: Session, run: AnalysisRun, scope: str, scope_id: str
) -> list[PortalFieldDraft]:
    supported = {f.field_id for f in get_registry().m6_draft_fields()}
    if scope == "field":
        if scope_id not in supported:
            raise ProblemException(
                status=404, code="not_found", title=_NOT_FOUND,
                detail="Field is not a supported draft field.",
            )
        draft = drafts_repo.get_draft(db, run.run_id, scope_id)
        if draft is None:
            raise ProblemException(
                status=404, code="not_found", title=_NOT_FOUND,
                detail="Draft not found.",
            )
        return [draft]
    return [
        d
        for field_id in supported
        if (d := drafts_repo.get_draft(db, run.run_id, field_id)) is not None
    ]


def _draft_blockers(
    db: Session, run: AnalysisRun, draft: PortalFieldDraft
) -> list[str]:
    version = (
        db.get(DraftVersion, draft.current_version_id)
        if draft.current_version_id
        else None
    )
    if version is None:
        return [f"missing_version:{draft.field_id}"]
    reasons: list[str] = []
    text = version.text
    if is_empty(text):
        reasons.append(f"empty_field:{draft.field_id}")
    elif has_placeholder(text):
        reasons.append(f"placeholder:{draft.field_id}")
    if draft.character_limit is not None and not within_limit(
        text, draft.character_limit
    ):
        reasons.append(f"over_limit:{draft.field_id}")
    stale_link = db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.run_id == run.run_id,
            EvidenceLink.target_type == "draft_version",
            EvidenceLink.target_id == draft.current_version_id,
            EvidenceLink.status == "stale",
        )
    )
    if stale_link is not None:
        reasons.append(f"stale_evidence_link:{draft.field_id}")
    return reasons


def approval_blockers(
    db: Session, run: AnalysisRun, scope: str, scope_id: str
) -> list[str]:
    """Deterministic gate reasons (empty → approvable). Re-derived from raw state."""
    reasons: list[str] = []
    if run.recheck_required:
        reasons.append("recheck_required")

    drafts = _scope_drafts(db, run, scope, scope_id)
    field_ids = {d.field_id for d in drafts}
    for draft in drafts:
        reasons.extend(_draft_blockers(db, run, draft))

    # Blocker open issues: run scope → all; field scope → only those targeting
    # the approved field.
    blocker_issues = db.scalars(
        select(OpenIssue).where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.status == "open",
            OpenIssue.severity == "blocker",
        )
    )
    for issue in blocker_issues:
        if scope == "run" or (
            issue.target_type == "portal_field" and issue.target_id in field_ids
        ):
            reasons.append(f"blocker_issue:{issue.target_id}")

    # Milestone 9K: scope-bound reliability blockers (only for claims of the current,
    # non-stale RunQualitySummary — a stale summary never blocks). Lazy import avoids a
    # cycle; runs with no reliability pass yield no reasons, so behaviour is unchanged.
    from app.reliability import approval as reliability_approval

    reasons.extend(
        reliability_approval.reliability_blocker_reasons(
            db, run, field_ids=None if scope == "run" else field_ids
        )
    )
    return reasons


def create_approval(
    db: Session, run: AnalysisRun, payload: ApprovalCreate, actor_user_id: str
) -> ReviewApprovalContract:
    if run.status != "completed":
        raise ProblemException(
            status=409, code="run_not_reviewable", title="Conflict",
            detail="Review is available only after the run has completed.",
        )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="approval.attempted", target_type="run", target_id=run.run_id,
        detail={"scope": payload.scope, "scope_id": payload.scope_id},
    )

    scope_hash = review_package.compute_scope_hash(db, run)
    version = review_package.package_version(scope_hash)
    if (
        payload.expected_approval_scope_hash != scope_hash
        or payload.expected_review_package_version != version
    ):
        raise ProblemException(
            status=409, code="review_package_stale", title="Conflict",
            detail=(
                "The review changed since it was loaded. Reload the review and "
                "approve again."
            ),
        )

    reasons = approval_blockers(db, run, payload.scope, payload.scope_id)
    if reasons:
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
            action="approval.blocked", target_type="run", target_id=run.run_id,
            detail={"reasons": reasons},
        )
        raise ProblemException(
            status=409, code="approval_blocked", title="Conflict",
            detail="Approval is blocked: " + ", ".join(reasons),
        )

    approval = ReviewApproval(
        approval_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        scope=payload.scope,
        scope_id=payload.scope_id,
        status="approved",
        approval_scope_hash=scope_hash,
        review_package_version=version,
        approved_by=actor_user_id,
        invalidated_at=None,
    )
    db.add(approval)
    db.flush()
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.APPROVAL_GATE", status="passed",
        detail=f"scope={payload.scope} hash={scope_hash[:12]}",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="approval.succeeded", target_type="review_approval",
        target_id=approval.approval_id,
        detail={"scope": payload.scope, "scope_id": payload.scope_id},
    )
    return _approval_to_contract(approval)


# Re-exported for callers that already hold the full review service.
from app.review.invalidation import invalidate_approvals  # noqa: E402,F401
