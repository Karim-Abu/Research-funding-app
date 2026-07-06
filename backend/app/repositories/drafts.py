"""PortalFieldDraft + DraftVersion persistence (Milestone 6).

Deterministic template drafts, immutable versions, optimistic-concurrency edits
(base_version_id), char-limit enforcement and field-level OpenIssues. All
persistence is upsert/immutable: terminal-run artifacts are never rewritten.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.draft import DraftVersion as DraftVersionSchema
from app.contracts.draft import PortalFieldDraft as DraftSchema
from app.db.models import (
    AnalysisRun,
    AsyncOperation,
    DraftVersion,
    OpenIssue,
    PortalFieldDraft,
)
from app.drafts import (
    TEMPLATE_CATALOG_VERSION,
    build_template,
    char_count,
    has_placeholder,
    is_empty,
)
from app.drafts.charcount import within_limit
from app.registry import PortalFieldDef, get_registry
from app.repositories import audit
from app.repositories import evidence as evidence_repo
from app.repositories.requirements import _issue_to_contract

FIELD_ISSUE_TEXT = (
    "Diese Strukturvorlage enthält noch offene Angaben und muss fachlich "
    "bearbeitet werden."
)

# Versions worth carrying into a new run (Slice 2, E1-A). Template versions are
# never a carry source: a fresh template is identical or — after a catalog
# update — the correct newer scaffold.
CARRY_OVER_CREATED_BY = ("user", "agent", "carried_over")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_version(
    db: Session,
    draft_id: str,
    text: str,
    created_by: str,
    *,
    base_version_id: str | None = None,
    source_operation_id: str | None = None,
) -> DraftVersion:
    version = DraftVersion(
        draft_version_id=str(uuid.uuid4()),
        draft_id=draft_id,
        text=text,
        character_count=char_count(text),
        created_by=created_by,
        content_hash=_content_hash(text),
        base_version_id=base_version_id,
        source_operation_id=source_operation_id,
    )
    db.add(version)
    db.flush()
    return version


def _sync_field_issue(
    db: Session, run: AnalysisRun, field_id: str, needed: bool
) -> int:
    """Maintain at most one deterministic field-level OpenIssue. Returns the
    open count (0 or 1)."""
    existing = db.scalar(
        select(OpenIssue).where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.target_type == "portal_field",
            OpenIssue.target_id == field_id,
        )
    )
    if needed:
        if existing is None:
            db.add(
                OpenIssue(
                    issue_id=str(uuid.uuid4()),
                    run_id=run.run_id,
                    issue_type="draft_incomplete",
                    severity="warning",
                    description=FIELD_ISSUE_TEXT,
                    target_type="portal_field",
                    target_id=field_id,
                    recommended_next_action=(
                        "Ergänzen Sie die offenen Angaben in dieser Strukturvorlage."
                    ),
                    status="open",
                )
            )
            db.flush()
        elif existing.status != "open":
            existing.status = "open"
            db.flush()
        return 1
    if existing is not None and existing.status == "open":
        existing.status = "resolved"
        db.flush()
    return 0


def _carry_over_source(
    db: Session, run: AnalysisRun, field_id: str
) -> tuple[DraftVersion, str] | None:
    """Latest meaningful current_version of the same project's prior runs for
    this field, newest run first. Run status is deliberately ignored: a newer
    cancelled/failed run's user edit must win over an older completed run's
    text. Returns (version, source_run_id) or None (→ template as today)."""
    row = db.execute(
        select(DraftVersion, PortalFieldDraft.run_id)
        .join(
            PortalFieldDraft,
            PortalFieldDraft.current_version_id == DraftVersion.draft_version_id,
        )
        .join(AnalysisRun, AnalysisRun.run_id == PortalFieldDraft.run_id)
        .where(
            AnalysisRun.project_id == run.project_id,
            AnalysisRun.workspace_id == run.workspace_id,
            AnalysisRun.run_id != run.run_id,
            PortalFieldDraft.field_id == field_id,
            DraftVersion.created_by.in_(CARRY_OVER_CREATED_BY),
        )
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def get_draft(db: Session, run_id: str, field_id: str) -> PortalFieldDraft | None:
    return db.scalar(
        select(PortalFieldDraft).where(
            PortalFieldDraft.run_id == run_id,
            PortalFieldDraft.field_id == field_id,
        )
    )


def create_initial_draft(
    db: Session, run: AnalysisRun, field: PortalFieldDef
) -> PortalFieldDraft:
    """Idempotent: one PortalFieldDraft per run+field. Initial version carries
    the newest meaningful prior version of the project (Slice 2, E1-A) or the
    deterministic template (first run / flag off / no meaningful predecessor)."""
    existing = get_draft(db, run.run_id, field.field_id)
    if existing is not None:
        return existing

    from app.config.settings import get_settings

    carried = (
        _carry_over_source(db, run, field.field_id)
        if get_settings().draft_carry_over_enabled
        else None
    )
    if carried is not None:
        # Carried text is never dropped, even over the current limit: the
        # existing draft_over_limit review blocker gates the run instead.
        text, created_by = carried[0].text, "carried_over"
        source_run_id = carried[1]
    else:
        text, created_by = build_template(field, get_registry()), "template"
        source_run_id = None
    draft_id = str(uuid.uuid4())
    draft = PortalFieldDraft(
        draft_id=draft_id,
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        field_id=field.field_id,
        field_name=field.label_or_question,
        status="needs_review",  # M6 never sets reviewed
        character_limit=field.character_limit,
        current_version_id=None,
        open_issue_count=0,
        template_catalog_version=TEMPLATE_CATALOG_VERSION,
    )
    db.add(draft)
    db.flush()
    version = _new_version(db, draft_id, text, created_by)
    draft.current_version_id = version.draft_version_id
    draft.open_issue_count = _sync_field_issue(
        db, run, field.field_id, is_empty(text) or has_placeholder(text)
    )
    created_detail: dict = {
        "field_id": field.field_id,
        "carried_over": carried is not None,
        "source_run_id": source_run_id,
    }
    if carried is not None and not within_limit(text, field.character_limit):
        created_detail["over_limit_at_initialization"] = True
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.template_created", target_type="portal_field_draft",
        target_id=draft_id, detail=created_detail,
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.version_created", target_type="draft_version",
        target_id=version.draft_version_id,
        detail={"created_by": created_by, "content_hash": version.content_hash},
    )
    db.flush()
    return draft


def _resolve_agent_acceptance(
    db: Session,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    *,
    base_version_id: str,
    text: str,
    source_operation_id: str | None,
):
    """Return the proposed DraftSuggestion iff `source_operation_id` legitimately
    identifies it (M9D corr #3): the operation succeeded; it belongs to the same
    run/workspace/draft/field and base_version_id; a still-proposed suggestion exists;
    and its content_hash equals the accepted text. Else None (→ normal user edit)."""
    if not source_operation_id:
        return None
    from app.repositories import draft_suggestions as suggestions_repo

    suggestion = suggestions_repo.get_by_operation(db, source_operation_id)
    if suggestion is None or suggestion.status != "proposed":
        return None
    if (
        suggestion.run_id != run.run_id
        or suggestion.workspace_id != run.workspace_id
        or suggestion.draft_id != draft.draft_id
        or suggestion.field_id != draft.field_id
        or suggestion.base_version_id != base_version_id
        or suggestion.content_hash != _content_hash(text)
    ):
        return None
    operation = db.get(AsyncOperation, source_operation_id)
    if operation is None or operation.status != "succeeded":
        return None
    return suggestion


def apply_update(
    db: Session,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    *,
    base_version_id: str,
    text: str,
    source_operation_id: str | None,
    actor_user_id: str,
) -> PortalFieldDraft:
    """Optimistic-concurrency edit. 409 on stale base, 422 over limit, no-op on
    identical text. On success: immutable user version + stale prior links +
    recheck flag."""
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="draft.update_attempted", target_type="portal_field_draft",
        target_id=draft.draft_id,
    )
    base = db.get(DraftVersion, base_version_id)
    if (
        base is None
        or base.draft_id != draft.draft_id
        or draft.current_version_id != base_version_id
    ):
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
            action="draft.version_conflict", target_type="portal_field_draft",
            target_id=draft.draft_id,
        )
        raise ProblemException(
            status=409, code="stale_base_version", title="Conflict",
            detail="Dieser Abschnitt wurde zwischenzeitlich geändert.",
        )
    if not within_limit(text, draft.character_limit):
        raise ProblemException(
            status=422, code="character_limit_exceeded",
            title="Unprocessable Entity",
            detail=(
                f"Der Text überschreitet das Limit von {draft.character_limit} "
                "Zeichen."
            ),
        )
    if base.text == text:
        return draft  # identical → no redundant version

    # M9D: accepting an A2 suggestion (source_operation_id resolves to a still-proposed
    # suggestion for this exact draft/base/text) creates an agent version; otherwise a
    # normal user edit. Never mark arbitrary text created_by=agent.
    accepted = _resolve_agent_acceptance(
        db, run, draft, base_version_id=base_version_id, text=text,
        source_operation_id=source_operation_id,
    )
    created_by = "agent" if accepted is not None else "user"
    version = _new_version(
        db, draft.draft_id, text, created_by,
        base_version_id=base_version_id, source_operation_id=source_operation_id,
    )
    # The superseded version's active evidence links become stale.
    stale = evidence_repo.mark_draft_version_links_stale(db, base_version_id)
    draft.current_version_id = version.draft_version_id
    if accepted is not None:
        from app.repositories import draft_suggestions as suggestions_repo

        suggestions_repo.mark_accepted(
            db, accepted, accepted_draft_version_id=version.draft_version_id,
            decided_by=actor_user_id,
        )
        suggestions_repo.expire_superseded(db, draft.draft_id, version.draft_version_id)
    draft.open_issue_count = _sync_field_issue(
        db, run, draft.field_id, is_empty(text) or has_placeholder(text)
    )
    run.recheck_required = True
    # An edit changes the review scope; any prior approval is now stale.
    from app.review.invalidation import invalidate_approvals

    invalidate_approvals(db, run, actor_user_id=actor_user_id)
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="draft.update_succeeded", target_type="draft_version",
        target_id=version.draft_version_id,
        detail={"content_hash": version.content_hash, "stale_links": stale},
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="run.recheck_required", target_type="run", target_id=run.run_id,
    )
    db.flush()
    return draft


# --- read model ------------------------------------------------------------


def _version_contract(version: DraftVersion) -> DraftVersionSchema:
    return DraftVersionSchema(
        draft_version_id=version.draft_version_id,
        text=version.text,
        character_count=version.character_count,
        created_by=version.created_by,
        created_at=version.created_at,
        content_hash=version.content_hash,
    )


def to_contract(db: Session, draft: PortalFieldDraft) -> DraftSchema:
    current = db.get(DraftVersion, draft.current_version_id)
    version_ids = list(
        db.scalars(
            select(DraftVersion.draft_version_id).where(
                DraftVersion.draft_id == draft.draft_id
            )
        )
    )
    links = evidence_repo.links_for_draft_versions(db, version_ids)
    issues = db.scalars(
        select(OpenIssue).where(
            OpenIssue.run_id == draft.run_id,
            OpenIssue.target_type == "portal_field",
            OpenIssue.target_id == draft.field_id,
        )
    )
    return DraftSchema(
        draft_id=draft.draft_id,
        field_id=draft.field_id,
        field_name=draft.field_name,
        status=draft.status,
        current_version=_version_contract(current),
        character_count=current.character_count,
        character_limit=draft.character_limit,
        open_issue_count=draft.open_issue_count,
        evidence_links=[evidence_repo.to_link_contract(link) for link in links],
        open_issues=[
            _issue_to_contract(issue) for issue in issues if issue.status == "open"
        ],
    )
