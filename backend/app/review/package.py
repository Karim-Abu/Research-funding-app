"""ReviewPackage assembly, approval-scope hashing and finding persistence.

Everything here is a deterministic function of already-persisted state. The
approval scope hash binds a run's drafts, evidence links, assessments, open
issues, findings and registry versions; any later edit changes it, which is how
an approval becomes stale.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    EvidenceLink,
    OpenIssue,
    PortalFieldDraft,
    RequirementAssessment,
    ReviewApproval,
    ReviewFinding,
    ReviewPackage,
)
from app.registry import get_registry
from app.repositories import audit
from app.review import REVIEW_PROFILE_VERSION
from app.review.checks import compute_finding_specs
from app.review.fingerprint import (
    classify_severity_class,
    compute_finding_fingerprint,
    finding_code_family,
)

DETERMINISTIC = "deterministic_review"
AGENT = "agent"


# --- finding persistence ---------------------------------------------------


def _agent_finding_code(profile_id: str, finding) -> str:
    """Stable dedup key for an agent finding over its profile + target + normalized
    description (Milestone 9G, STEP 7)."""
    normalized = " ".join((finding.description or "").lower().split())
    parts = [
        profile_id, finding.field_id or "", finding.requirement_id or "",
        finding.evidence_anchor_id or "", finding.evidence_link_id or "", normalized,
    ]
    digest = hashlib.sha256(" ".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"a3:{digest}"


def apply_agent_findings(db: Session, run: AnalysisRun, findings, *, profile_id: str) -> None:
    """Idempotently upsert advisory agent findings (source=agent) and resolve agent
    findings of this profile not re-emitted. NEVER touches deterministic_review or
    human rows. Called ONLY after a successful, schema-valid A3 bundle (corr 2) — a
    failed/skipped run must not reach here, so prior findings are preserved.
    """
    existing = {
        f.finding_code: f
        for f in db.scalars(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.source == AGENT,
                ReviewFinding.profile_id == profile_id,
            )
        )
    }
    seen: set[str] = set()
    for finding in findings:
        code = _agent_finding_code(profile_id, finding)
        seen.add(code)
        advisory = finding.severity != "blocker"
        row = existing.get(code)
        if row is None:
            row = ReviewFinding(
                finding_id=str(uuid.uuid4()), run_id=run.run_id,
                workspace_id=run.workspace_id, profile_id=profile_id,
                field_id=finding.field_id, requirement_id=finding.requirement_id,
                severity=finding.severity, description=finding.description,
                suggested_improvement=finding.suggested_improvement,
                status="open", advisory=advisory, source=AGENT, finding_code=code,
                target_type="portal_field_draft" if finding.field_id else "requirement_assessment",
                target_id=finding.field_id or finding.requirement_id,
                recommended_next_action=finding.recommended_next_action,
            )
            db.add(row)
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="review.agent_finding_created", target_type="review_finding",
                target_id=row.finding_id,
                detail={"profile_id": profile_id, "severity": finding.severity},
            )
        else:
            row.severity = finding.severity
            row.description = finding.description
            row.suggested_improvement = finding.suggested_improvement
            row.field_id = finding.field_id
            row.requirement_id = finding.requirement_id
            row.recommended_next_action = finding.recommended_next_action
            row.advisory = advisory
            if row.status == "resolved":
                row.status = "open"

    # Resolve agent findings (same profile) the run no longer emits. Human/overridden/
    # dismissed states are preserved; only open agent findings auto-resolve.
    for code, row in existing.items():
        if code not in seen and row.status == "open":
            row.status = "resolved"
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="review.agent_finding_updated", target_type="review_finding",
                target_id=row.finding_id, detail={"status": "resolved"},
            )
    db.flush()


def apply_findings(db: Session, run: AnalysisRun) -> None:
    """Idempotently upsert deterministic findings and resolve fixed ones.

    Only ``source=deterministic_review`` rows are touched; human findings
    (section comments) are never overwritten here.
    """
    registry = get_registry()
    profile_id = registry.profile_id or REVIEW_PROFILE_VERSION
    specs = compute_finding_specs(db, run)

    existing = {
        f.finding_code: f
        for f in db.scalars(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.source == DETERMINISTIC,
            )
        )
    }
    now = datetime.now(timezone.utc)
    seen: set[str] = set()
    for spec in specs:
        seen.add(spec.finding_code)
        finding = existing.get(spec.finding_code)
        advisory = spec.severity != "blocker"
        # Issue-Modell v2 (R2.3, additiv): technische Identität + Klasse je
        # Emission. Kategorie der zugrunde liegenden Anforderung ordnet
        # Blocker-OpenIssues ein (budget → budget_blocker, sonst eligibility).
        requirement = (
            registry.requirements.get(spec.requirement_id)
            if spec.requirement_id
            else None
        )
        severity_class = classify_severity_class(
            spec.finding_code,
            requirement.category if requirement is not None else None,
        )
        fp = compute_finding_fingerprint(
            finding_code_family(spec.finding_code),
            spec.field_id or spec.requirement_id or spec.target_id,
        )
        if finding is None:
            finding = ReviewFinding(
                finding_id=str(uuid.uuid4()),
                run_id=run.run_id,
                workspace_id=run.workspace_id,
                profile_id=profile_id,
                field_id=spec.field_id,
                requirement_id=spec.requirement_id,
                severity=spec.severity,
                description=spec.description,
                suggested_improvement=spec.suggested_improvement,
                status="open",
                advisory=advisory,
                source=DETERMINISTIC,
                finding_code=spec.finding_code,
                target_type=spec.target_type,
                target_id=spec.target_id,
                recommended_next_action=spec.recommended_next_action,
                fingerprint=fp,
                severity_class=severity_class,
                last_seen_at=now,
            )
            db.add(finding)
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="review.finding_created", target_type="review_finding",
                target_id=finding.finding_id,
                detail={"code": spec.finding_code, "severity": spec.severity},
            )
        else:
            finding.severity = spec.severity
            finding.description = spec.description
            finding.suggested_improvement = spec.suggested_improvement
            finding.field_id = spec.field_id
            finding.requirement_id = spec.requirement_id
            finding.target_type = spec.target_type
            finding.target_id = spec.target_id
            finding.recommended_next_action = spec.recommended_next_action
            finding.advisory = advisory
            finding.fingerprint = fp
            finding.severity_class = severity_class
            finding.last_seen_at = now
            if finding.status == "resolved":
                finding.status = "open"
                audit.record(
                    db, workspace_id=run.workspace_id, actor_user_id=None,
                    action="review.finding_updated", target_type="review_finding",
                    target_id=finding.finding_id, detail={"status": "open"},
                )

    for code, finding in existing.items():
        if code not in seen and finding.status == "open":
            finding.status = "resolved"
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="review.finding_updated", target_type="review_finding",
                target_id=finding.finding_id, detail={"status": "resolved"},
            )
    db.flush()


# --- scope hash + version --------------------------------------------------


def compute_scope_hash(db: Session, run: AnalysisRun) -> str:
    """SHA-256 over the deterministically sorted review scope. Pure read."""
    registry = get_registry()
    parts: list[str] = [f"run:{run.run_id}"]

    drafts = db.scalars(
        select(PortalFieldDraft)
        .where(PortalFieldDraft.run_id == run.run_id)
        .order_by(PortalFieldDraft.field_id.asc())
    )
    for draft in drafts:
        parts.append(f"draft:{draft.field_id}:{draft.current_version_id}")

    links = db.scalars(
        select(EvidenceLink)
        .where(
            EvidenceLink.run_id == run.run_id,
            EvidenceLink.target_type == "draft_version",
        )
        .order_by(EvidenceLink.evidence_link_id.asc())
    )
    for link in links:
        parts.append(f"link:{link.evidence_link_id}:{link.status}")

    assessments = db.scalars(
        select(RequirementAssessment)
        .where(RequirementAssessment.run_id == run.run_id)
        .order_by(RequirementAssessment.assessment_id.asc())
    )
    for assessment in assessments:
        parts.append(f"assess:{assessment.assessment_id}:{assessment.status}")

    issues = db.scalars(
        select(OpenIssue)
        .where(OpenIssue.run_id == run.run_id)
        .order_by(OpenIssue.issue_id.asc())
    )
    for issue in issues:
        parts.append(f"issue:{issue.issue_id}:{issue.status}")

    findings = db.scalars(
        select(ReviewFinding)
        .where(ReviewFinding.run_id == run.run_id)
        .order_by(ReviewFinding.finding_id.asc())
    )
    for finding in findings:
        parts.append(f"finding:{finding.finding_id}:{finding.status}")

    parts.append(
        "reg:"
        f"{registry.requirement_registry_version}:"
        f"{registry.rule_registry_version}:"
        f"{registry.portal_field_profile_version}"
    )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def package_version(scope_hash: str) -> str:
    return "rpv-" + hashlib.sha256(scope_hash.encode("utf-8")).hexdigest()[:12]


# --- status + counts -------------------------------------------------------


def _open_findings(db: Session, run: AnalysisRun) -> list[ReviewFinding]:
    return list(
        db.scalars(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.status == "open",
            )
        )
    )


RELIABILITY = "M9K.reliability_assurance"


def _reliability_blocks(db: Session, run: AnalysisRun) -> bool:
    """Reliability blocker (Milestone 9K / M10.1). Lazy import avoids a cycle; counts M9K
    blockers whose claim belongs to the current non-stale RunQualitySummary, plus the
    run-level reliability_stale reason when a pass ran but the draft changed since (F3)."""
    from app.reliability import approval as reliability_approval

    return reliability_approval.has_reliability_blocker(db, run)


def has_open_blocker(db: Session, run: AnalysisRun) -> bool:
    if db.scalar(
        select(OpenIssue).where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.status == "open",
            OpenIssue.severity == "blocker",
        )
    ):
        return True
    # M9K reliability findings never block via the generic path — they are scope-bound.
    if any(
        f.severity == "blocker" and f.profile_id != RELIABILITY
        for f in _open_findings(db, run)
    ):
        return True
    return _reliability_blocks(db, run)


def has_open_change_request(db: Session, run: AnalysisRun) -> bool:
    return (
        db.scalar(
            select(ReviewFinding).where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.source == "human",
                ReviewFinding.status == "open",
            )
        )
        is not None
    )


def counts(db: Session, run: AnalysisRun) -> tuple[int, int, int]:
    """Returns (blocker_count, warning_count, stale_finding_count). M9K reliability blockers
    count only when scope-bound-current (not via the generic severity sum)."""
    open_findings = _open_findings(db, run)
    blocker = sum(
        1 for f in open_findings if f.severity == "blocker" and f.profile_id != RELIABILITY
    )
    if _reliability_blocks(db, run):
        from app.reliability import approval as reliability_approval

        blocker += len(reliability_approval.reliability_blocker_reasons(db, run))
    warning = sum(1 for f in open_findings if f.severity == "warning")
    stale = len(open_findings) if run.recheck_required else 0
    return blocker, warning, stale


def latest_run_approval(db: Session, run: AnalysisRun) -> ReviewApproval | None:
    return db.scalar(
        select(ReviewApproval)
        .where(ReviewApproval.run_id == run.run_id, ReviewApproval.scope == "run")
        .order_by(ReviewApproval.created_at.desc())
    )


def latest_approval(db: Session, run: AnalysisRun) -> ReviewApproval | None:
    return db.scalar(
        select(ReviewApproval)
        .where(ReviewApproval.run_id == run.run_id)
        .order_by(ReviewApproval.created_at.desc())
    )


def approval_status(db: Session, run: AnalysisRun, scope_hash: str) -> str:
    run_latest = latest_run_approval(db, run)
    if (
        run_latest is not None
        and run_latest.status == "approved"
        and run_latest.invalidated_at is None
        and run_latest.approval_scope_hash == scope_hash
    ):
        return "approved"
    # The most recent approval of any scope (run or field) that an edit
    # invalidated reads as stale — even when a recheck is also pending — so the
    # reviewer sees that their sign-off lapsed.
    latest = latest_approval(db, run)
    if latest is not None and (
        latest.invalidated_at is not None or latest.status == "stale"
    ):
        return "stale"
    if run.recheck_required or has_open_blocker(db, run):
        return "blocked"
    if has_open_change_request(db, run):
        return "changes_required"
    return "open"


# --- package refresh -------------------------------------------------------


def refresh_package(
    db: Session,
    run: AnalysisRun,
    *,
    clear_recheck: bool = False,
    recompute_findings: bool = True,
) -> ReviewPackage:
    """Recompute deterministic findings + the ReviewPackage snapshot. When
    ``clear_recheck`` is set (after a successful targeted recheck) the review
    state is current again, so ``recheck_required`` is cleared even if blocker
    findings remain."""
    if recompute_findings:
        apply_findings(db, run)
    if clear_recheck:
        run.recheck_required = False
    # M10.1 (F3): materialize/resolve the run-level reliability-stale blocker finding so a
    # changed draft is visible in the package and requires a fresh pass before approval.
    from app.reliability import approval as reliability_approval

    reliability_approval.sync_stale_finding(db, run)
    scope_hash = compute_scope_hash(db, run)
    version = package_version(scope_hash)
    blocker, warning, stale = counts(db, run)
    status = approval_status(db, run, scope_hash)

    run.approval_scope_hash = scope_hash
    run.review_package_version = version

    package = db.get(ReviewPackage, run.run_id)
    if package is None:
        package = ReviewPackage(
            run_id=run.run_id,
            workspace_id=run.workspace_id,
            review_package_version=version,
            approval_scope_hash=scope_hash,
            approval_status=status,
            blocker_count=blocker,
            warning_count=warning,
            stale_finding_count=stale,
            recheck_required=run.recheck_required,
        )
        db.add(package)
    else:
        package.review_package_version = version
        package.approval_scope_hash = scope_hash
        package.approval_status = status
        package.blocker_count = blocker
        package.warning_count = warning
        package.stale_finding_count = stale
        package.recheck_required = run.recheck_required
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="review.package_updated", target_type="run", target_id=run.run_id,
        detail={"version": version, "status": status, "blocker": blocker},
    )
    db.flush()
    return package
