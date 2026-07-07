"""Fix Queue — Gruppierungs-Read-View über offenen Findings (R2.4).

Gruppiert die offenen ``ReviewFinding``-Rows eines Runs nach dem
``display_group_key`` (severity_class + Meldungsfamilie — NIE der Claim-Text,
R2.1) und priorisiert die Gruppen deterministisch:

1 export_blocker · 2 eligibility_blocker · 3 budget_blocker ·
4 reviewer_risk · 5 evidence_risk · 6 style_risk.

Read-only: verändert keine Findings, keine Zähllogik des ReviewPackage.
Rows ohne persistierte ``severity_class`` (Altbestand, Human-Kommentare)
werden zur Lesezeit über dieselbe Klassifizierung eingeordnet.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.review import (
    FixQueueView,
    GroupedFinding,
    GroupedFindingExample,
)
from app.db.models import AnalysisRun, ReviewFinding
from app.registry import get_registry
from app.review.fingerprint import (
    classify_severity_class,
    compute_display_group_key,
    finding_code_family,
)

_MAX_EXAMPLES = 5

_CLASS_PRIORITY = {
    "export_blocker": 1,
    "eligibility_blocker": 2,
    "budget_blocker": 3,
    "reviewer_risk": 4,
    "evidence_risk": 5,
    "style_risk": 6,
}

# UI-Labels je Meldungsfamilie (Anzeige-Label, keine Regelaussage — Regel-/
# Meldungstexte selbst kommen unverändert aus den Findings/dem Katalog).
# Fallback: gemeinsamer description-Text der Gruppe bzw. die Familie.
_FAMILY_TITLES: dict[str, str] = {
    "draft_placeholder": "Sichtbare Platzhalter im Feldtext",
    "draft_over_limit": "Zeichenlimit überschritten",
    "draft_empty": "Pflichtfeld ist leer",
    "open_issue_blocker": "Blockierende Anforderung",
    "requirement_needs_input": "Anforderung benötigt zusätzliche Angaben",
    "stale_assessment": "Beurteilung beruht auf veraltetem Stand",
    "stale_evidence_link": "Veralteter Evidenz-Verweis",
    "unverified_linked_evidence": "Nicht exakt verifizierte Fundstelle verknüpft",
    "missing_evidence_link": "Kein aktiver Evidenz-Verweis hinterlegt",
    "reliability:unsupported": "Nicht belegte Aussage",
    "reliability:weak": "Schwach belegte Aussage",
    "reliability:conflict": "Konfliktende Belege",
    "reliability:quantified": "Quantifizierte Aussage ohne passenden Zahlenbeleg",
    "reliability:market": "Marktaussage ohne quellenbelegte Angabe",
    "reliability:proposed_fact": "Unbestätigte A1-Angabe als sicher formuliert",
    "reliability:false_consensus": "Mehrfachnennung ersetzt keinen Beleg",
    "reliability:drift": "Feldtext weicht vom geprüften Stand ab",
    "a3": "Evidenz-Konsistenz-Hinweis",
    "comment": "Kommentar aus der menschlichen Prüfung",
}

_SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}


def _row_severity_class(row: ReviewFinding, registry) -> str:
    if row.severity_class:
        return row.severity_class
    requirement = (
        registry.requirements.get(row.requirement_id) if row.requirement_id else None
    )
    return classify_severity_class(
        row.finding_code, requirement.category if requirement is not None else None
    )


def _group_title(family: str, rows: list[ReviewFinding]) -> str:
    if family in _FAMILY_TITLES:
        return _FAMILY_TITLES[family]
    descriptions = {r.description for r in rows}
    if len(descriptions) == 1:
        return next(iter(descriptions))
    return family


def build_fix_queue(db: Session, run: AnalysisRun) -> FixQueueView:
    """Deterministische Gruppierung der offenen Findings eines Runs."""
    registry = get_registry()
    rows = list(
        db.scalars(
            select(ReviewFinding)
            .where(
                ReviewFinding.run_id == run.run_id,
                ReviewFinding.status == "open",
            )
            .order_by(ReviewFinding.created_at.asc(), ReviewFinding.finding_id.asc())
        )
    )

    grouped: dict[str, list[ReviewFinding]] = {}
    keys: dict[str, tuple[str, str]] = {}  # group_key -> (severity_class, family)
    for row in rows:
        family = finding_code_family(row.finding_code)
        severity_class = _row_severity_class(row, registry)
        key = compute_display_group_key(severity_class, family)
        grouped.setdefault(key, []).append(row)
        keys[key] = (severity_class, family)

    groups: list[GroupedFinding] = []
    for key, members in grouped.items():
        severity_class, family = keys[key]
        fields = sorted({m.field_id for m in members if m.field_id})
        actions = Counter(
            m.recommended_next_action
            for m in members
            if m.recommended_next_action
        )
        severity = min(
            (m.severity for m in members),
            key=lambda s: _SEVERITY_RANK.get(s, 9),
        )
        groups.append(
            GroupedFinding(
                group_key=key,
                title=_group_title(family, members),
                count=len(members),
                severity_class=severity_class,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                affected_fields=fields,
                examples=[
                    GroupedFindingExample(
                        finding_id=m.finding_id,
                        field_id=m.field_id,
                        description=m.description,
                        target_type=m.target_type,
                        target_id=m.target_id,
                    )
                    for m in members[:_MAX_EXAMPLES]
                ],
                recommended_next_action=(
                    actions.most_common(1)[0][0] if actions else None
                ),
                target_field_id=fields[0] if len(fields) == 1 else None,
            )
        )

    groups.sort(
        key=lambda g: (
            _CLASS_PRIORITY.get(g.severity_class, 9),
            -g.count,
            g.group_key,
        )
    )
    return FixQueueView(
        run_id=run.run_id,
        grouped_findings=groups,
        next_actions=groups,
        total_open_findings=len(rows),
    )
