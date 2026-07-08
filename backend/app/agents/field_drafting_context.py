"""A2 field-drafting context assembly (Milestone 9D; generalized in 9E).

Field-specific, minimal, evidence-aware context for an A2 drafting profile, keyed by
``field_id`` + ``profile_id`` (SOL.INNOVATION_SOLUTION.EDITOR / A2.solution_innovation;
VC.BUSINESS_TARGETS_MODEL.EDITOR / A2.value_creation_market_logic). Six read-only
tool-services (recorded as ToolInvocations) gather: the current draft text + the field
profile (label, registry character limit, registry mandatory questions), requirement
assessments and open issues for the field, exact-verified evidence quotes, structured
project data, and advisory A1 facts. No full documents, secrets or unrelated fields.
Source text is untrusted data. The pinned ``FieldDraftingInput@v1`` carries the
structured fields; the current draft text + requirement assessments are rendered into
``context_text``.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceLink,
    OpenIssue,
    Partner,
    Project,
    RequirementAssessment,
    ToolInvocation,
)
from app.registry.loader import get_registry
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import extracted_facts as facts_repo


@dataclass
class A2Context:
    field_id: str = ""
    profile_id: str = ""
    field_profile: dict = field(default_factory=dict)
    # R5.1: advisory/proposed A1-Fakten — nie als bestätigte Wahrheit behandeln.
    advisory_facts: list[dict] = field(default_factory=list)
    verified_evidence: list[dict] = field(default_factory=list)
    structured_project_data: dict = field(default_factory=dict)
    open_issues: list[dict] = field(default_factory=list)
    language: str = "de"
    current_draft_text: str = ""
    requirement_assessments: list[dict] = field(default_factory=list)
    context_text: str = ""
    context_hash: str = ""
    allowed_anchor_ids: set = field(default_factory=set)
    allowed_issue_ids: set = field(default_factory=set)
    meta: dict = field(default_factory=dict)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_tool(
    db: Session, run: AnalysisRun, tool_id: str, output_hash: str, *, caller: str
) -> None:
    db.add(
        ToolInvocation(
            invocation_id=str(uuid.uuid4()), workspace_id=run.workspace_id,
            run_id=run.run_id, tool_id=tool_id, caller=caller,
            input_hash=_hash_text(run.run_id), output_hash=output_hash,
            status="succeeded",
        )
    )


def _linked_requirement_ids(field_id: str) -> set[str]:
    registry = get_registry()
    return {
        r.requirement_id for r in registry.requirements.values()
        if field_id in (r.affected_field_ids or [])
    }


def _field_profile_view(field_id: str) -> dict:
    registry = get_registry()
    fdef = registry.portal_fields.get(field_id)
    mandatory = [q.field_id for q in registry.mandatory_questions(field_id)]
    return {
        "field_id": field_id,
        "label": fdef.label_or_question if fdef else field_id,
        "character_limit": fdef.character_limit if fdef else None,
        "mandatory_questions": mandatory,
        "guidance": None,
    }


def _current_draft_text(db: Session, run: AnalysisRun, field_id: str) -> str:
    draft = drafts_repo.get_draft(db, run.run_id, field_id)
    if draft is None or draft.current_version_id is None:
        return ""
    version = db.get(DraftVersion, draft.current_version_id)
    return version.text if version is not None else ""


def retrieve_advisory_project_facts(db: Session, run: AnalysisRun) -> list[dict]:
    """A1 ExtractedFacts — advisory/proposed (not confirmed truth). R5.1: vormals
    ``retrieve_confirmed_project_facts`` (contract-pinned tool_id, tools_v1_1.yaml);
    der Wire-String bleibt bei der ToolInvocation-Aufzeichnung unverändert."""
    facts = []
    for f in facts_repo.list_for_run(db, run.run_id):
        # Advisory facts that carry provenance (so they satisfy ExtractedFactRecord).
        if f.status not in ("proposed", "conflicted") or not (f.source_fragment_ids or []):
            continue
        facts.append({
            "fact_id": f.fact_id, "statement": f.original_statement,
            "fact_type": f.fact_type, "normalized_value": f.normalized_value,
            "source_fragment_ids": list(f.source_fragment_ids or []),
        })
    return facts


def retrieve_verified_evidence(db: Session, run: AnalysisRun) -> list[dict]:
    """exact_verified EvidenceAnchors + the requirement they support via active links."""
    anchor_to_requirement: dict[str, str] = {}
    assessment_requirement = {
        a.assessment_id: a.requirement_id
        for a in db.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.run_id == run.run_id
            )
        )
    }
    for link in db.scalars(
        select(EvidenceLink).where(
            EvidenceLink.run_id == run.run_id,
            EvidenceLink.target_type == "requirement_assessment",
            EvidenceLink.status == "active",
        )
    ):
        req = assessment_requirement.get(link.target_id)
        if req is not None:
            anchor_to_requirement.setdefault(link.anchor_id, req)

    evidence = []
    for anchor in evidence_repo.list_anchors_for_run(db, run.run_id):
        if anchor.verification_status != "exact_verified":
            continue
        evidence.append({
            "anchor_id": anchor.anchor_id, "quote": anchor.quote,
            "source_name": anchor.source_name,
            "verification_status": anchor.verification_status,
            "page": anchor.page, "section": anchor.section,
            "requirement_id": anchor_to_requirement.get(anchor.anchor_id),
        })
    return evidence


def retrieve_structured_project_data(db: Session, run: AnalysisRun) -> dict:
    project = db.get(Project, run.project_id) if run.project_id else None
    partner_count = 0
    if run.project_id:
        partner_count = db.scalar(
            select(func.count(Partner.partner_id)).where(
                Partner.project_id == run.project_id
            )
        ) or 0
    return {
        "project_title": project.title if project else None,
        "funding_instrument_profile_id": (
            project.funding_instrument_profile_id if project else None
        ),
        "partner_count": int(partner_count),
    }


def retrieve_open_issues(
    db: Session, run: AnalysisRun, requirement_ids: set[str], field_id: str
) -> list[dict]:
    issues = []
    for issue in db.scalars(
        select(OpenIssue).where(OpenIssue.run_id == run.run_id, OpenIssue.status == "open")
    ):
        relevant = (
            (issue.target_type == "field" and issue.target_id == field_id)
            or (issue.target_type == "requirement_assessment")
            or (issue.target_id in requirement_ids)
        )
        if not relevant:
            continue
        issues.append({
            "issue_id": issue.issue_id, "issue_type": issue.issue_type,
            "severity": issue.severity, "description": issue.description,
            "target_type": issue.target_type, "target_id": issue.target_id,
        })
    return issues


def _requirement_assessments(db: Session, run: AnalysisRun, requirement_ids: set[str]) -> list[dict]:
    return [
        {"requirement_id": a.requirement_id, "status": a.status, "basis": a.basis}
        for a in db.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.run_id == run.run_id
            )
        )
        if a.requirement_id in requirement_ids
    ]


def _render_context_text(ctx: A2Context) -> str:
    parts = [
        "CURRENT DRAFT (the text to improve):\n" + (ctx.current_draft_text or "(empty)"),
        "FIELD PROFILE: " + str(ctx.field_profile),
        "MANDATORY QUESTIONS (preserve all): "
        + ", ".join(ctx.field_profile.get("mandatory_questions", [])),
        "REQUIREMENT ASSESSMENTS (advisory, do not change status): "
        + str(ctx.requirement_assessments),
        "VERIFIED EVIDENCE (exact_verified = quote exists in source, NOT approved):\n"
        + "\n".join(
            f"[{e['anchor_id']} | {e['source_name']} | {e['verification_status']}] "
            f"{e['quote']}" for e in ctx.verified_evidence
        ),
        "OPEN ISSUES: " + str(ctx.open_issues),
        "PROPOSED A1 FACTS (advisory, NOT confirmed): " + str(ctx.advisory_facts),
    ]
    return "\n\n".join(parts)


def assemble_a2_context(
    db: Session, run: AnalysisRun, *, field_id: str, profile_id: str, language: str = "de"
) -> A2Context:
    requirement_ids = _linked_requirement_ids(field_id)
    ctx = A2Context(field_id=field_id, profile_id=profile_id, language=language)
    ctx.field_profile = _field_profile_view(field_id)
    ctx.current_draft_text = _current_draft_text(db, run, field_id)
    ctx.advisory_facts = retrieve_advisory_project_facts(db, run)
    ctx.verified_evidence = retrieve_verified_evidence(db, run)
    ctx.structured_project_data = retrieve_structured_project_data(db, run)
    ctx.open_issues = retrieve_open_issues(db, run, requirement_ids, field_id)
    ctx.requirement_assessments = _requirement_assessments(db, run, requirement_ids)
    ctx.allowed_anchor_ids = {e["anchor_id"] for e in ctx.verified_evidence}
    ctx.allowed_issue_ids = {i["issue_id"] for i in ctx.open_issues}

    # Record the tool invocations (authorization checked against the registry).
    _record_tool(db, run, "lookup_portal_field_profile",
                 _hash_text(str(ctx.field_profile)), caller=profile_id)
    # Code liefert advisory Facts; der Wire-Name bleibt bis Contract v1.2.
    _record_tool(db, run, "retrieve_confirmed_project_facts",  # contract-pinned: tools_v1_1.yaml tool_id
                 _hash_text(",".join(f["fact_id"] for f in ctx.advisory_facts)), caller=profile_id)
    _record_tool(db, run, "retrieve_verified_evidence",
                 _hash_text(",".join(sorted(ctx.allowed_anchor_ids))), caller=profile_id)
    _record_tool(db, run, "retrieve_structured_project_data",
                 _hash_text(str(ctx.structured_project_data)), caller=profile_id)
    _record_tool(db, run, "retrieve_open_issues",
                 _hash_text(",".join(sorted(ctx.allowed_issue_ids))), caller=profile_id)
    _record_tool(db, run, "lookup_requirement_definition",
                 _hash_text(",".join(sorted(requirement_ids))), caller=profile_id)

    ctx.context_text = _render_context_text(ctx)
    settings = get_settings()
    budget = settings.a1_context_char_budget
    truncated = ctx.context_text[:budget]
    ctx.context_hash = _hash_text(truncated)
    ctx.context_text = truncated
    ctx.meta = {
        "context_hash": ctx.context_hash,
        "evidence_count": len(ctx.verified_evidence),
        "open_issue_count": len(ctx.open_issues),
        "fact_count": len(ctx.advisory_facts),
        "char_budget": budget,
        "total_chars": len(ctx.context_text),
    }
    return ctx


def build_input_payload(ctx: A2Context, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "profile_id": ctx.profile_id,
        "field_profiles": [ctx.field_profile],
        # Inhalt sind advisory Facts (R5.1); Wire-Key bleibt Contract v1.1.
        "confirmed_facts": [  # contract-pinned: schema_catalog.yaml FieldDraftingInput@v1
            {"fact_id": f["fact_id"], "statement": f["statement"],
             "fact_type": f.get("fact_type"), "normalized_value": f.get("normalized_value"),
             "source_fragment_ids": f.get("source_fragment_ids", []),
             "versioned_user_input_ids": []}
            for f in ctx.advisory_facts
        ],
        "verified_evidence": ctx.verified_evidence,
        "structured_project_data": ctx.structured_project_data,
        "open_issues": ctx.open_issues,
        "language": ctx.language,
    }
