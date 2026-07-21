"""RUN 3C missing-input normalization and idempotent OpenIssue lifecycle."""
from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, DraftSuggestion, OpenIssue


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalized_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold().strip()
    return "-".join(re.findall(r"[\w]+", normalized, flags=re.UNICODE))[:160]


def fingerprint(run_id: str, field_id: str, requirement_id: str, key: str) -> str:
    body = "\n".join((run_id, field_id, requirement_id, normalized_key(key)))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def sync_issues(
    db: Session,
    run: AnalysisRun,
    suggestion: DraftSuggestion,
    items: list[dict],
) -> list[str]:
    """Upsert active missing inputs and resolve disappeared ones for the field."""
    now = _now()
    active_fingerprints: set[str] = set()
    issue_ids: list[str] = []
    issues_by_fingerprint = {
        issue.fingerprint: issue
        for issue in db.scalars(select(OpenIssue).where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.field_id == suggestion.field_id,
            OpenIssue.target_type == "missing_input",
        ))
        if issue.fingerprint
    }
    for item in items:
        key = normalized_key(str(item["key"]))
        for requirement_id in sorted(set(item["requirement_ids"])):
            fp = fingerprint(run.run_id, suggestion.field_id, requirement_id, key)
            active_fingerprints.add(fp)
            issue = issues_by_fingerprint.get(fp)
            if issue is None:
                issue = OpenIssue(
                    issue_id=str(uuid.uuid4()), run_id=run.run_id,
                    issue_type="missing_information", severity="warning",
                    description=str(item["label"]),
                    target_type="missing_input", target_id=fp,
                    recommended_next_action=str(item["reason"]), status="open",
                    fingerprint=fp, severity_class="content_gap",
                    fix_recommendation=str(item["reason"]), last_seen_at=now,
                    field_id=suggestion.field_id, requirement_id=requirement_id,
                    missing_input_key=key,
                    source_suggestion_id=suggestion.suggestion_id,
                )
                db.add(issue)
                issues_by_fingerprint[fp] = issue
            else:
                issue.description = str(item["label"])
                issue.recommended_next_action = str(item["reason"])
                issue.fix_recommendation = str(item["reason"])
                issue.last_seen_at = now
                issue.source_suggestion_id = suggestion.suggestion_id
                if issue.status in ("resolved", "stale"):
                    issue.status = "open"
                    issue.resolved_at = None
                    issue.stale_at = None
                    issue.status_reason = "missing_input_reappeared"
            issue_ids.append(issue.issue_id)

    for issue in issues_by_fingerprint.values():
        if issue.status != "open":
            continue
        if issue.fingerprint not in active_fingerprints:
            issue.status = "resolved"
            issue.resolved_at = now
            issue.status_reason = "missing_input_no_longer_reported"
    db.flush()
    return sorted(set(issue_ids))


def mark_suggestion_issues_stale(
    db: Session, suggestion_id: str, *, reason: str
) -> int:
    now = _now()
    count = 0
    for issue in db.scalars(select(OpenIssue).where(
        OpenIssue.source_suggestion_id == suggestion_id,
        OpenIssue.status == "open",
    )):
        issue.status = "stale"
        issue.stale_at = now
        issue.status_reason = reason
        count += 1
    db.flush()
    return count
