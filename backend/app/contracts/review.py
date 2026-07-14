"""Review-layer schemas — exact openapi-v1_1.yaml shapes (Milestone 7)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.draft import PortalFieldDraft
from app.contracts.requirement import OpenIssue, RequirementAssessment

FindingSeverity = Literal["blocker", "warning", "info"]
FindingStatus = Literal["open", "resolved", "overridden", "dismissed"]
ApprovalStatus = Literal[
    "open", "blocked", "approved", "changes_required", "stale"
]
ApprovalScope = Literal["run", "field"]


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    profile_id: str
    field_id: str | None = None
    target_section: str | None = None
    requirement_id: str | None = None
    severity: FindingSeverity
    description: str
    suggested_improvement: str | None = None
    recommended_next_action: str | None = None
    status: FindingStatus
    advisory: bool


class ReviewPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    requirements: list[RequirementAssessment]
    fields: list[PortalFieldDraft]
    findings: list[ReviewFinding]
    approval_status: ApprovalStatus
    blocker_count: int
    warning_count: int
    open_issues: list[OpenIssue]
    review_package_version: str
    current_approval_scope_hash: str
    recheck_required: bool
    stale_finding_count: int


class ReviewStatusView(BaseModel):
    """R1.2 — kanonischer, schlanker Status-Read-View für alle Screens.

    Additiv und read-only; Zahlen kommen aus denselben Zählfunktionen wie das
    ReviewPackage (``review.package.counts`` / ``approval_status``) — keine
    parallele Zähllogik. ``human_review_count`` zählt Requirement-Assessments
    mit Status ``needs_input`` (menschliche Angabe/Prüfung nötig).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    blocker_count: int
    warning_count: int
    human_review_count: int
    stale: bool
    approval_status: ApprovalStatus
    review_package_version: str
    per_area_counts: dict[str, int]
    last_reviewed_at: datetime | None = None
    # Additiv (B7): «Blockierende Aufgaben» = gruppierte Fix-Queue-Aufgaben mit
    # Severity blocker; «Unterliegende Evidenzhinweise» = offene claimgebundene
    # Findings. Beide aus build_fix_queue — keine parallele Zähllogik.
    blocking_task_count: int = 0
    evidence_note_count: int = 0


SeverityClass = Literal[
    "export_blocker", "eligibility_blocker", "budget_blocker",
    "reviewer_risk", "evidence_risk", "style_risk",
]

# Teil A — die neun Prüfbereiche + Status je Bereich.
CheckArea = Literal[
    "pflichtfelder", "zeichenlimits", "platzhalter", "voraussetzungen",
    "budget", "evidenz_coverage", "evidenz_suffizienz", "konsistenz", "export",
]
CheckAreaState = Literal["not_run", "passed", "warning", "failed"]


class GroupedFindingExample(BaseModel):
    """Ein Einzel-Finding als Beispiel innerhalb einer Gruppe — die
    individuellen Claims/Felder bleiben hier sichtbar."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    field_id: str | None = None
    description: str
    target_type: str | None = None
    target_id: str | None = None


class GroupedFinding(BaseModel):
    """R2.4 — UI-Gruppierung gleichartiger Meldungen. ``group_key`` ist der
    display_group_key (severity_class|Meldungsfamilie) und enthält NIE
    Roh-Claim-Text."""

    model_config = ConfigDict(extra="forbid")

    group_key: str
    title: str
    count: int
    severity_class: SeverityClass
    severity: FindingSeverity
    affected_fields: list[str]
    examples: list[GroupedFindingExample]
    recommended_next_action: str | None = None
    target_field_id: str | None = None
    # Additiv (Teil A) — Prüfbereich der Gruppe; None wenn keiner zuordenbar
    # ist (z. B. menschliche Kommentare).
    area: CheckArea | None = None


class FixQueueView(BaseModel):
    """R2.4 — Gruppierungs-/Fix-Queue-Read-View über den offenen Findings
    eines Runs. Read-only, additiv; ändert keine Findings."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    grouped_findings: list[GroupedFinding]
    next_actions: list[GroupedFinding]
    total_open_findings: int
    # Additiv (B7) — siehe ReviewStatusView.
    blocking_task_count: int = 0
    evidence_note_count: int = 0


# --- Teil A — autoritative Check-Status je Prüfbereich ----------------------


class CheckAreaStatus(BaseModel):
    """Status EINES Prüfbereichs. ``passed`` nur, wenn der Check nachweislich
    lief und erfolgreich war — Abwesenheit von Findings ohne gelaufenen Check
    ist ``not_run``, nie bestanden."""

    model_config = ConfigDict(extra="forbid")

    area: CheckArea
    status: CheckAreaState
    open_blockers: int
    open_warnings: int
    # Maschinen-Schlüssel für die UI-Übersetzung (z. B. "stale",
    # "not_executed") — nie roh im Standard-UI anzeigen.
    reason: str | None = None


class ReviewCheckStatusView(BaseModel):
    """Teil A — additiver, read-only Status-View über die neun Prüfbereiche.
    Einzige autoritative Statusquelle des Frontends für die Qualitätsprüfung;
    ersetzt die frühere automatische Pass-Logik im Frontend."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    areas: list[CheckAreaStatus]
    stale: bool
    blocking_task_count: int
    evidence_note_count: int
    review_package_version: str


# --- human decisions (discriminated by target_type) ------------------------


class RequirementDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["requirement_assessment"]
    target_id: str
    action: Literal["confirm", "override", "request_changes"]
    comment: str | None = None


class EvidenceDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["evidence_anchor"]
    target_id: str
    action: Literal["confirm", "reject"]
    comment: str | None = None


class FindingDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["review_finding"]
    target_id: str
    action: Literal["confirm", "override", "dismiss", "request_changes"]
    comment: str | None = None


class DraftDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["portal_field_draft"]
    target_id: str
    action: Literal["confirm", "request_changes"]
    comment: str | None = None


HumanDecisionCreate = Annotated[
    Union[
        RequirementDecisionCreate,
        EvidenceDecisionCreate,
        FindingDecisionCreate,
        DraftDecisionCreate,
    ],
    Field(discriminator="target_type"),
]


class HumanDecision(BaseModel):
    """Flattened openapi HumanDecision (HumanDecisionCreate + identity fields)."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal[
        "requirement_assessment",
        "evidence_anchor",
        "review_finding",
        "portal_field_draft",
    ]
    target_id: str
    action: str
    comment: str | None = None
    decision_id: str
    user_id: str
    run_id: str
    created_at: datetime


# --- approvals -------------------------------------------------------------


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: ApprovalScope
    scope_id: str
    expected_approval_scope_hash: str
    comment: str | None = None
    expected_review_package_version: str
    confirm_not_submission_approval: Literal[True]


class ReviewApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    run_id: str
    scope: ApprovalScope
    status: ApprovalStatus
    approval_scope_hash: str
    approved_by: str | None = None
    created_at: datetime


# --- targeted recheck ------------------------------------------------------


class TargetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: str
    target_id: str


class RecheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_review_package_version: str
    changed_target_refs: list[TargetRef]
    include_semantic_recheck: bool = True
