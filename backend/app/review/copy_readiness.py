"""Copy-Readiness (R6) — kanonische, deterministische Ableitung je Portalfeld.

Beantwortet für die Kopieransicht: "Wie kopierfähig ist dieses Feld?" Die
Ableitung lebt im Backend (eine Quelle); das Frontend rendert nur. Kopieren
wird dadurch NIE blockiert — der Status führt, er sperrt nicht (Override mit
Begründung bleibt möglich). ``copy_ready`` heisst "bereit zum Kopieren",
niemals "einreichbereit" — die Einreichung bleibt vollständig beim Menschen.

Content-Zustände (leer/Platzhalter/Limit) werden LIVE aus dem aktuellen Text
berechnet — wie die Server-Warnungen des Copy-Event-Endpoints — damit ein
seit der letzten Prüfung bereinigter Text nicht fälschlich als Blocker
erscheint. Findings zählen nur für nicht live prüfbare Familien (z. B.
Evidenz-Blocker); die Review-Aktualität deckt ``recheck_required`` ab.

Präzedenz (erste zutreffende Stufe gewinnt):
    blocker             Limit überschritten, Pflichtfeld leer oder offenes
                        nicht-inhaltliches Blocker-Finding am Feld
    placeholders_open   sichtbare Platzhalter im Text
    not_reviewed        Prüfung nicht aktuell (Änderungen seit letzter Prüfung)
    draft               Arbeitskopie: geprüft aktuell, aber ohne menschliche
                        Freigabe für Feld oder Lauf
    copy_ready          menschlich freigegeben und aktuell
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    DraftVersion,
    PortalFieldDraft,
    ReviewApproval,
    ReviewFinding,
    ReviewPackage,
)
from app.drafts import has_placeholder, is_empty
from app.drafts.charcount import within_limit

COPY_READINESS_VALUES = (
    "blocker",
    "placeholders_open",
    "not_reviewed",
    "draft",
    "copy_ready",
)

# Finding-Familien, deren Zustand live aus dem Text berechnet wird — sie
# zählen hier nicht als Blocker-Finding (sonst bliebe ein bereits bereinigter
# Text bis zur erneuten Prüfung fälschlich "blocker").
_LIVE_CHECKED_FAMILIES = ("draft_empty:", "draft_placeholder:", "draft_over_limit:")


def derive_copy_readiness(
    *,
    text_is_empty: bool,
    text_has_placeholder: bool,
    text_over_limit: bool,
    has_blocker_finding: bool,
    recheck_required: bool,
    approved_current: bool,
) -> str:
    """Pure Präzedenzregel — Eingaben sind bereits berechnete Fakten.

    ``text_is_empty`` ist blocker (nicht draft): alle Draft-API-Felder sind
    unterstützte Pflichtfelder (deckungsgleich mit dem draft_empty-Finding).
    """
    if text_over_limit or text_is_empty or has_blocker_finding:
        return "blocker"
    if text_has_placeholder:
        return "placeholders_open"
    if recheck_required:
        return "not_reviewed"
    if not approved_current:
        return "draft"
    return "copy_ready"


# --- DB-Helfer (read-only) ---------------------------------------------------


def _fields_with_open_blockers(db: Session, run_id: str) -> set[str]:
    rows = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run_id,
            ReviewFinding.status == "open",
            ReviewFinding.severity == "blocker",
            ReviewFinding.field_id.is_not(None),
        )
    )
    return {
        finding.field_id
        for finding in rows
        if not (finding.finding_code or "").startswith(_LIVE_CHECKED_FAMILIES)
    }


def _fields_with_valid_approval(db: Session, run_id: str) -> set[str]:
    rows = db.scalars(
        select(ReviewApproval.scope_id).where(
            ReviewApproval.run_id == run_id,
            ReviewApproval.scope == "field",
            ReviewApproval.status == "approved",
            ReviewApproval.invalidated_at.is_(None),
        )
    )
    return set(rows)


def _run_approved_current(db: Session, run: AnalysisRun) -> bool:
    package = db.get(ReviewPackage, run.run_id)
    return package is not None and package.approval_status == "approved"


def copy_readiness_for_run(db: Session, run: AnalysisRun) -> dict[str, str]:
    """Copy-Readiness aller Feld-Drafts eines Laufs (Schlüssel: field_id)."""
    blocked_fields = _fields_with_open_blockers(db, run.run_id)
    approved_fields = _fields_with_valid_approval(db, run.run_id)
    run_approved = _run_approved_current(db, run)

    result: dict[str, str] = {}
    drafts = db.scalars(
        select(PortalFieldDraft).where(PortalFieldDraft.run_id == run.run_id)
    )
    for draft in drafts:
        version = db.get(DraftVersion, draft.current_version_id)
        text = version.text if version else ""
        over_limit = draft.character_limit is not None and not within_limit(
            text, draft.character_limit
        )
        result[draft.field_id] = derive_copy_readiness(
            text_is_empty=is_empty(text),
            text_has_placeholder=has_placeholder(text),
            text_over_limit=over_limit,
            has_blocker_finding=draft.field_id in blocked_fields,
            recheck_required=bool(run.recheck_required),
            approved_current=run_approved or draft.field_id in approved_fields,
        )
    return result
