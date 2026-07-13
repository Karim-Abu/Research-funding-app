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
import json
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceLink,
    HumanDecision,
    OpenIssue,
    Partner,
    Project,
    RequirementAssessment,
    RunProjectSnapshot,
    SourceDocument,
    ToolInvocation,
)
from app.market import source_scope
from app.registry.loader import get_registry
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import extracted_facts as facts_repo
from app.review.evidence_status import lineage_by_anchor, support_status_for_anchor
from app.drafts.sections import (
    SectionStructureError,
    compact_adjacent_section,
    extract_section,
    section_spans,
)

# R5.7/R8: only these two "big" A2 fields consume advisory research context. R8
# (Anforderung 10): NUR vom Menschen akzeptierte (importierte) D0/public-Quellen werden
# Kontext — nicht importierte ResearchResult-Kandidaten nie. All other A2 profiles get
# no research context (context_text/hash unchanged).
_MARKET_PURPOSE = "market_comparison"          # RESEARCH.1
_PARTNER_PURPOSE = "partner_research_org_topic"  # RESEARCH.2
_RESEARCH_CONTEXT_PURPOSES: dict[str, tuple[str, ...]] = {
    "A2.value_creation_market_logic": (_MARKET_PURPOSE,),
    "A2.solution_innovation": (_PARTNER_PURPOSE,),
}
# Bounded so advisory research context never dominates the A2 context budget.
_RESEARCH_SOURCE_CHAR_BUDGET = 4000
_RESEARCH_SOURCE_MAX_FRAGMENTS = 8
_RESEARCH_SNIPPET_MAX = 300


@dataclass
class A2Context:
    field_id: str = ""
    profile_id: str = ""
    target_section: str | None = None
    field_profile: dict = field(default_factory=dict)
    # R5.1: advisory/proposed A1-Fakten — nie als bestätigte Wahrheit behandeln.
    advisory_facts: list[dict] = field(default_factory=list)
    verified_evidence: list[dict] = field(default_factory=list)
    research_candidates: list[dict] = field(default_factory=list)
    structured_project_data: dict = field(default_factory=dict)
    open_issues: list[dict] = field(default_factory=list)
    language: str = "de"
    current_draft_text: str = ""
    requirement_assessments: list[dict] = field(default_factory=list)
    # R5.7: advisory research context (imported D0/public sources + non-imported research
    # candidates) — NEVER evidence, NEVER an anchor. Empty for non-VC/SOL profiles.
    research_context: dict = field(default_factory=dict)
    context_text: str = ""
    context_hash: str = ""
    allowed_anchor_ids: set = field(default_factory=set)
    allowed_issue_ids: set = field(default_factory=set)
    meta: dict = field(default_factory=dict)
    context_components: list[dict] = field(default_factory=list)


class ContextBudgetError(ValueError):
    pass


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
    """Evidence views with coverage and correctness kept separate.

    Only a public anchor with a latest human ``confirm`` decision and a
    Reliability support result may become ``external_evidence``. Merely finding
    the exact quote remains a ``research_candidate``.
    """
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

    latest_decision: dict[str, str] = {}
    for decision in db.scalars(
        select(HumanDecision)
        .where(
            HumanDecision.run_id == run.run_id,
            HumanDecision.target_type == "evidence_anchor",
        )
        .order_by(HumanDecision.created_at.desc())
    ):
        latest_decision.setdefault(decision.target_id, decision.action)
    sources = {
        source.source_id: source
        for source in db.scalars(
            select(SourceDocument).where(SourceDocument.project_id == run.project_id)
        )
    } if run.project_id else {}
    lineage = lineage_by_anchor(db, run.run_id)
    evidence = []
    for anchor in evidence_repo.list_anchors_for_run(db, run.run_id):
        if anchor.verification_status not in ("exact_verified", "human_verified"):
            continue
        support_status = support_status_for_anchor(
            anchor.verification_status, lineage.get(anchor.anchor_id)
        )
        source = sources.get(anchor.source_id)
        public_source = bool(
            source
            and (source.data_classification or {}).get("sensitivity") == "public"
            and not (source.data_classification or {}).get("nda_applies")
        )
        external = (
            public_source
            and latest_decision.get(anchor.anchor_id) == "confirm"
            and support_status in ("supports_partially", "supports_strongly")
        )
        evidence.append({
            "anchor_id": anchor.anchor_id, "quote": anchor.quote,
            "source_name": anchor.source_name,
            "verification_status": anchor.verification_status,
            "page": anchor.page, "section": anchor.section,
            "requirement_id": anchor_to_requirement.get(anchor.anchor_id),
            "support_status": support_status,
            "context_kind": (
                "external_evidence" if external else "research_candidate"
            ),
        })
    return evidence


def retrieve_structured_project_data(db: Session, run: AnalysisRun) -> dict:
    snapshot = db.get(RunProjectSnapshot, run.run_id)
    if snapshot is not None:
        project_data = dict(snapshot.project_json or {})
        partners = list(snapshot.partners_json or [])
        return {
            "project_title": project_data.get("title"),
            "funding_instrument_profile_id": project_data.get(
                "funding_instrument_profile_id"
            ),
            "partner_count": len(partners),
            "project": project_data,
            "partners": partners,
            "snapshot_schema_version": project_data.get(
                "snapshot_schema_version", "run-project-v1"
            ),
        }
    # Defensive compatibility for isolated unit tests without a persisted run
    # snapshot. Production run creation always freezes one.
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
        "project": {}, "partners": [], "snapshot_schema_version": "test-fallback",
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


def _trim(text: str | None, limit: int) -> str:
    one_line = " ".join((text or "").split())
    return one_line[:limit] + "…" if len(one_line) > limit else one_line


def retrieve_advisory_research_context(
    db: Session, run: AnalysisRun, profile_id: str
) -> dict:
    """R5.7/R8 — advisory research context for the two big fields only.

    Returns ``{}`` for any other profile (so their context is unchanged). For VC/SOL it
    gathers, bounded and deterministically, ONLY fragments of imported D0/public
    SourceDocuments (market-signal fragments). R8 (Anforderung 10): nicht importierte
    ResearchResult-Kandidaten fliessen NICHT mehr in den A2-Kontext — erst die vom
    Menschen akzeptierte («Als Quelle speichern») Quelle wird Kontext; verworfene nie.
    Everything here is UNTRUSTED, ADVISORY context — never evidence, never an anchor id.
    """
    purposes = _RESEARCH_CONTEXT_PURPOSES.get(profile_id)
    if not purposes or not run.project_id:
        return {}

    sources = source_scope.imported_public_sources(db, run.project_id, run.workspace_id)
    fragments = source_scope.prefilter_fragments(
        db, sources, max_fragments=_RESEARCH_SOURCE_MAX_FRAGMENTS,
        char_budget=_RESEARCH_SOURCE_CHAR_BUDGET,
    )
    imported = [
        {"source_name": f.source_name, "snippet": _trim(f.text, _RESEARCH_SNIPPET_MAX)}
        for f in fragments
    ]
    if not imported:
        return {}
    return {"imported_sources": imported}


def _render_research_context(rc: dict) -> str:
    lines = [
        "RESEARCH CONTEXT (advisory, human-accepted public sources — NOT evidence, NOT "
        "validated facts; any market number or partner name here is an UNVALIDATED "
        "CANDIDATE. Cite nothing from here as evidence_anchor_ids; if a claim would rely "
        "on it, keep a placeholder / missing_input instead):"
    ]
    for s in rc.get("imported_sources", []):
        lines.append(f"- [imported public source | {s['source_name']}] {s['snippet']}")
    return "\n".join(lines)


_DE_WORDS = frozenset({
    "der", "die", "das", "und", "ist", "mit", "fuer", "für", "werden",
    "projekt", "durch", "eine", "einen", "nicht", "ziel",
})
_EN_WORDS = frozenset({
    "the", "and", "is", "with", "for", "will", "project", "through",
    "a", "an", "not", "target", "this", "are",
})

_PORTAL_HEADING_RE = re.compile(
    r"^\s*\d+(?:\.\d+)*\s+(?:Describe|Indicate|Please describe|Does the planned)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\[\[Angabe ergänzen:[^\]]*\]\]", re.IGNORECASE)


def _applicant_language_text(text: str) -> str:
    """Ignore registry questions and empty German scaffolding when no answer exists."""
    without_questions = _PORTAL_HEADING_RE.sub("", text or "")
    return _TEMPLATE_PLACEHOLDER_RE.sub("", without_questions)


def detect_application_language(text: str) -> str:
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", _applicant_language_text(text).lower())
    de = sum(word in _DE_WORDS for word in words)
    en = sum(word in _EN_WORDS for word in words)
    return "en" if en > de else "de"


def application_language_conflicts(text: str, expected: str) -> bool:
    """Reject a clear translation while tolerating short technical headings."""
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", (text or "").lower())
    de = sum(word in _DE_WORDS for word in words)
    en = sum(word in _EN_WORDS for word in words)
    if de + en < 2 or de == en:
        return False
    return ("en" if en > de else "de") != expected


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _budgeted_context(
    target_text: str,
    components: list[tuple[str, str, int, int]],
    budget: int,
) -> tuple[str, list[dict]]:
    """Keep the applicant target in full and allocate the remaining budget.

    Component tuple = (kind, text, weight, item_count). Unused shares are
    redistributed in declared priority order. Only safe counts are returned as
    metadata.
    """
    target_body = target_text or "(empty)"
    target_block = "[imported_applicant_text:target_full]\n" + target_body
    if len(target_block) > budget:
        raise ContextBudgetError("target_section_exceeds_context_budget")
    active = [(k, t, w, n) for k, t, w, n in components if t]
    headers = [f"[{kind}]\n" for kind, _, _, _ in active]
    separator_chars = 2 * len(active)
    content_budget = budget - len(target_block) - sum(map(len, headers)) - separator_chars
    if content_budget < 0:
        raise ContextBudgetError("context_component_headers_exceed_budget")
    total_weight = sum(weight for _, _, weight, _ in active) or 1
    caps = [int(content_budget * weight / total_weight) for _, _, weight, _ in active]
    used = [min(len(item[1]), cap) for item, cap in zip(active, caps)]
    remaining = content_budget - sum(used)
    # Redistribute unused shares to still-truncated components in priority order.
    for index, item in enumerate(active):
        if remaining <= 0:
            break
        room = len(item[1]) - used[index]
        add = min(room, remaining)
        used[index] += add
        remaining -= add
    blocks = [target_block]
    meta = [{
        "kind": "imported_applicant_text", "item_count": 1,
        "character_count": len(target_body), "truncated": False,
    }]
    for (kind, content, _, item_count), header, length in zip(active, headers, used):
        blocks.append(header + content[:length])
        meta.append({
            "kind": kind, "item_count": item_count,
            "character_count": length, "truncated": length < len(content),
        })
    rendered = "\n\n".join(blocks)
    if len(rendered) > budget:  # defensive accounting invariant
        raise ContextBudgetError("context_budget_accounting_error")
    return rendered, meta


def assemble_a2_context(
    db: Session,
    run: AnalysisRun,
    *,
    field_id: str,
    profile_id: str,
    target_section: str | None = None,
    section_markers: tuple[str, ...] = (),
    language: str | None = None,
) -> A2Context:
    requirement_ids = _linked_requirement_ids(field_id)
    ctx = A2Context(
        field_id=field_id, profile_id=profile_id,
        target_section=target_section, language=language or "de",
    )
    ctx.field_profile = _field_profile_view(field_id)
    full_draft_text = _current_draft_text(db, run, field_id)
    adjacent: list[dict] = []
    if target_section is not None:
        if not section_markers:
            raise SectionStructureError("section_markers_missing")
        spans = section_spans(full_draft_text, section_markers)
        ctx.current_draft_text = extract_section(
            full_draft_text, section_markers, target_section
        )
        for span in spans:
            if span.marker == target_section:
                continue
            original_section = full_draft_text[span.start:span.end]
            synopsis = compact_adjacent_section(original_section, 900)
            adjacent.append({
                "section": span.marker,
                "synopsis": synopsis,
                "original_character_count": len(original_section),
                "truncated": len(synopsis) < len(" ".join(original_section.split())),
            })
    else:
        ctx.current_draft_text = full_draft_text
    ctx.language = language or detect_application_language(ctx.current_draft_text)
    ctx.advisory_facts = retrieve_advisory_project_facts(db, run)
    typed_evidence = retrieve_verified_evidence(db, run)
    ctx.verified_evidence = [
        item for item in typed_evidence
        if item.get("context_kind") == "external_evidence"
    ]
    ctx.research_candidates = [
        item for item in typed_evidence
        if item.get("context_kind") == "research_candidate"
    ]
    ctx.structured_project_data = retrieve_structured_project_data(db, run)
    ctx.open_issues = retrieve_open_issues(db, run, requirement_ids, field_id)
    ctx.requirement_assessments = _requirement_assessments(db, run, requirement_ids)
    # R5.7: advisory research context (VC/SOL only) — never added to allowed_anchor_ids.
    ctx.research_context = retrieve_advisory_research_context(db, run, profile_id)
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

    settings = get_settings()
    budget = settings.a1_context_char_budget
    portal_requirement = _json({
        "field_profile": ctx.field_profile,
        "requirement_assessments": ctx.requirement_assessments,
    })
    research_candidates = {
        "location_only_or_unconfirmed_anchors": ctx.research_candidates,
        "public_source_candidates": ctx.research_context.get("imported_sources", []),
        "advisory_a1_facts": ctx.advisory_facts,
    }
    ctx.context_text, ctx.context_components = _budgeted_context(
        ctx.current_draft_text,
        [
            ("accepted_project_input", _json(ctx.structured_project_data), 25, 1),
            ("external_evidence", _json(ctx.verified_evidence), 35,
             len(ctx.verified_evidence)),
            ("open_issue", _json(ctx.open_issues), 15, len(ctx.open_issues)),
            ("imported_applicant_text", _json(adjacent), 15, len(adjacent)),
            ("portal_requirement", portal_requirement, 5,
             len(ctx.requirement_assessments)),
            ("research_candidate", _json(research_candidates), 5,
             len(ctx.research_candidates)
             + len(ctx.research_context.get("imported_sources", []))
             + len(ctx.advisory_facts)),
        ],
        budget,
    )
    adjacent_was_compacted = any(item["truncated"] for item in adjacent)
    if adjacent_was_compacted:
        for component in ctx.context_components[1:]:
            if component["kind"] == "imported_applicant_text":
                component["truncated"] = True
    ctx.context_hash = _hash_text(ctx.context_text)
    ctx.meta = {
        "context_hash": ctx.context_hash,
        "evidence_count": len(ctx.verified_evidence),
        "open_issue_count": len(ctx.open_issues),
        "fact_count": len(ctx.advisory_facts),
        "research_context_count": len(ctx.research_context.get("imported_sources", [])),
        "research_candidate_count": len(ctx.research_candidates),
        "char_budget": budget,
        "total_chars": len(ctx.context_text),
        "target_section": target_section,
        "language": ctx.language,
        "components": ctx.context_components,
    }
    return ctx


def build_input_payload(ctx: A2Context, run_id: str) -> dict:
    if ctx.target_section is not None:
        return {
            "run_id": run_id,
            "profile_id": ctx.profile_id,
            "field_profile": ctx.field_profile,
            "target_section": ctx.target_section,
            "accepted_project_input": ctx.structured_project_data,
            "external_evidence": ctx.verified_evidence,
            "research_candidate_count": (
                len(ctx.research_candidates)
                + len(ctx.research_context.get("imported_sources", []))
            ),
            "open_issues": ctx.open_issues,
            "context_components": ctx.context_components,
            "language": ctx.language,
        }
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
        "structured_project_data": {
            key: ctx.structured_project_data.get(key)
            for key in (
                "project_title", "funding_instrument_profile_id", "partner_count"
            )
        },
        "open_issues": ctx.open_issues,
        "language": ctx.language,
    }
