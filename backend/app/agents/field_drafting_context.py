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

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agents import allowed_facts
from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    HumanDecision,
    MarketComparison,
    MarketComparisonItem,
    OpenIssue,
    Partner,
    Project,
    ResearchResult,
    ResearchTask,
    RequirementAssessment,
    RunProjectSnapshot,
    SourceDocument,
    SourceVersion,
    SuggestionContextManifest,
    ToolInvocation,
)
from app.evidence.scope_policy import formal_application_scope, is_generated_or_review_source
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
    target_section_spans,
)
from app.drafts.templates import is_placeholder_only

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
    allowed_research_source_ids: set = field(default_factory=set)
    meta: dict = field(default_factory=dict)
    context_components: list[dict] = field(default_factory=list)
    # (kind, Text) genau so, wie er nach Budgetierung/Truncation im Prompt
    # landet. Basis der Erlaubt-Liste des Halluzinations-Gates: was hier fehlt,
    # hat das Modell nie gesehen und darf nicht als belegt gelten.
    visible_components: list[tuple[str, str]] = field(default_factory=list)
    manifest_mode: bool = False
    requirement_ids: set[str] = field(default_factory=set)
    rule_ids: set[str] = field(default_factory=set)
    source_version_ids: set[str] = field(default_factory=set)
    selected_anchor_ids: set[str] = field(default_factory=set)
    omitted_anchor_ids: set[str] = field(default_factory=set)
    market_comparison_id: str | None = None
    market_findings: list[dict] = field(default_factory=list)
    improvement_mode: str = "clearer"
    manifest_context_hash: str = ""
    # Erst-Entwurf: Zieltext ist leer oder besteht nur aus Vorlagen-Platzhaltern.
    is_initial_draft: bool = False


class ContextBudgetError(ValueError):
    pass


class ContextSelectionError(ValueError):
    """A caller-selected context object is not usable for this frozen run."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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


def _linked_rule_ids(requirement_ids: set[str]) -> set[str]:
    registry = get_registry()
    return {
        rule_id
        for requirement_id in requirement_ids
        for rule_id in registry.requirements[requirement_id].linked_rule_ids
        if requirement_id in registry.requirements
    }


def _anchor_requirement_map(db: Session, run: AnalysisRun) -> dict[str, str]:
    assessment_requirement = {
        a.assessment_id: a.requirement_id
        for a in db.scalars(
            select(RequirementAssessment).where(RequirementAssessment.run_id == run.run_id)
        )
    }
    result: dict[str, str] = {}
    for link in db.scalars(
        select(EvidenceLink).where(
            EvidenceLink.run_id == run.run_id,
            EvidenceLink.target_type == "requirement_assessment",
            EvidenceLink.status == "active",
        )
    ):
        requirement_id = assessment_requirement.get(link.target_id)
        if requirement_id:
            result.setdefault(link.anchor_id, requirement_id)
    return result


def _manifest_evidence(
    db: Session,
    run: AnalysisRun,
    *,
    requirement_ids: set[str],
    selected_anchor_ids: set[str],
) -> tuple[list[dict], list[str]]:
    """Resolve exactly the application + explicitly selected drafting anchors.

    Application anchors must belong to the frozen primary application and the
    field's registry requirements.  External/supporting anchors additionally
    need a current, reviewed and safe source version.  Search snippets are not
    EvidenceAnchors and therefore cannot enter this path.
    """
    formal = formal_application_scope(db, run)
    requirement_by_anchor = _anchor_requirement_map(db, run)
    anchors = list(db.scalars(select(EvidenceAnchor).where(
        EvidenceAnchor.workspace_id == run.workspace_id,
        or_(
            EvidenceAnchor.project_id == run.project_id,
            EvidenceAnchor.project_id.is_(None),
        ),
    )))
    by_id = {row.anchor_id: row for row in anchors}
    unknown = sorted(selected_anchor_ids - set(by_id))
    if unknown:
        raise ContextSelectionError("unknown_selected_anchor")

    selected: list[dict] = []
    source_versions: set[str] = set()
    for anchor in anchors:
        requirement_id = requirement_by_anchor.get(anchor.anchor_id)
        is_application = (
            anchor.scope == "application"
            and formal.status == "configured"
            and anchor.source_id == formal.source_id
            and anchor.source_version_id == formal.source_version_id
            and requirement_id in requirement_ids
        )
        explicitly_selected = anchor.anchor_id in selected_anchor_ids
        if not is_application and not explicitly_selected:
            continue
        if anchor.verification_status not in ("exact_verified", "human_verified"):
            # Nur eine EXPLIZITE Nutzer-Auswahl ist ein behebbarer Fehler.
            # Automatisch einbezogene Application-Anker in nicht-verifiziertem
            # Zustand (z. B. rejected) sind schlicht kein Beleg — auslassen,
            # nie den ganzen Redraft dafür scheitern lassen.
            if explicitly_selected:
                raise ContextSelectionError("selected_anchor_not_verified")
            continue
        document = db.get(SourceDocument, anchor.source_id)
        version = db.get(SourceVersion, anchor.source_version_id)
        if (
            document is None
            or version is None
            or document.workspace_id != run.workspace_id
            or document.project_id != run.project_id
            or version.source_document_id != document.source_id
        ):
            raise ContextSelectionError("selected_anchor_scope_mismatch")
        if is_generated_or_review_source(document):
            raise ContextSelectionError("selected_anchor_generated_content")
        if explicitly_selected:
            if anchor.scope not in ("external", "drafting_context"):
                # Application evidence is selected by frozen scope, never by a
                # client-provided override.
                if not is_application:
                    raise ContextSelectionError("selected_anchor_scope_invalid")
            if document.current_source_version_id != anchor.source_version_id:
                raise ContextSelectionError("selected_anchor_source_version_stale")
            if version.content_review_status != "reviewed":
                raise ContextSelectionError("selected_anchor_review_required")
            if version.content_safety_status not in ("passed", "human_released"):
                raise ContextSelectionError("selected_anchor_quarantined")
        source_versions.add(anchor.source_version_id)
        selected.append({
            "anchor_id": anchor.anchor_id,
            "quote": anchor.quote,
            "source_name": anchor.source_name,
            "verification_status": anchor.verification_status,
            "page": anchor.page,
            "section": anchor.section,
            "requirement_id": requirement_id,
            "support_status": "supports_strongly" if is_application else "human_review_required",
            "context_kind": "application_evidence" if is_application else anchor.scope,
            "source_version_id": anchor.source_version_id,
        })
    selected.sort(key=lambda item: (item["context_kind"], item["anchor_id"]))
    return selected, sorted(source_versions)


def _field_relevance_tokens(field_id: str, requirement_ids: set[str]) -> set[str]:
    registry = get_registry()
    field_def = registry.portal_fields.get(field_id)
    text = " ".join([
        field_def.label_or_question if field_def else field_id,
        *(registry.requirements[item].title for item in sorted(requirement_ids)),
        *(registry.requirements[item].description for item in sorted(requirement_ids)),
    ])
    return {
        token.casefold()
        for token in re.findall(r"[\wÄÖÜäöüß-]{4,}", text, flags=re.UNICODE)
    }


def _market_findings(
    db: Session,
    run: AnalysisRun,
    *,
    field_id: str,
    requirement_ids: set[str],
    allowed_anchor_ids: set[str],
) -> tuple[str | None, list[dict]]:
    comparison = db.scalar(
        select(MarketComparison)
        .where(
            MarketComparison.project_id == run.project_id,
            MarketComparison.workspace_id == run.workspace_id,
            MarketComparison.status.in_(("ready_for_review", "limited")),
            MarketComparison.stale_reason.is_(None),
        )
        .order_by(MarketComparison.updated_at.desc())
    )
    if comparison is None:
        return None, []
    tokens = _field_relevance_tokens(field_id, requirement_ids)
    ranked: list[tuple[int, str, dict]] = []
    for item in db.scalars(
        select(MarketComparisonItem).where(
            MarketComparisonItem.comparison_id == comparison.comparison_id,
            MarketComparisonItem.status.in_(("accepted", "proposed")),
            MarketComparisonItem.confidence_label == "source_backed",
        )
    ):
        anchor_ids = sorted(set(item.evidence_anchor_ids or []) & allowed_anchor_ids)
        if not anchor_ids:
            continue
        text = " ".join(filter(None, (
            item.name, item.category, item.description,
            item.offering_summary, item.differentiation_relevance,
        )))
        score = len(tokens & {t.casefold() for t in re.findall(r"[\wÄÖÜäöüß-]{4,}", text)})
        ranked.append((score, item.item_id, {
            "finding_id": item.item_id,
            "category": item.category,
            "finding": text,
            "anchor_ids": anchor_ids,
        }))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return comparison.comparison_id, [row[2] for row in ranked[:5]]


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


def _target_question_label(field_id: str, target_section: str) -> str | None:
    for question in get_registry().mandatory_questions(field_id):
        marker = question.field_id.rsplit("MANDATORY_", 1)[-1].replace("_", ".")
        if marker == target_section:
            return question.label_or_question.strip()
    return None


def _section_is_initial_draft(
    section_text: str, field_id: str, target_section: str
) -> bool:
    """Erst-Entwurf eines Zielabschnitts: ohne Markerzeile bzw. Marker-Token
    bleibt nichts Substanzielles ausser Vorlagen-Platzhaltern. Die Registry-
    Frage als Überschrift ist Vorlagenzustand — Anwendertext auf der
    Markerzeile zählt dagegen als Inhalt."""
    lines = section_text.splitlines()
    if not lines:
        return True
    label = _target_question_label(field_id, target_section)
    if label is not None and lines[0].strip() == label:
        rest = lines[1:]
    else:
        rest = [
            re.sub(
                rf"^[ \t]*(?:#{{1,6}}[ \t]+)?{re.escape(target_section)}[.:)\s-]*",
                "", lines[0],
            ),
            *lines[1:],
        ]
    return is_placeholder_only("\n".join(rest))


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


def _requirement_definitions(requirement_ids: set[str]) -> list[dict]:
    """Titel + Beschreibung der verlinkten Anforderungen aus der Registry
    (statische D0-Contract-Daten, deterministische Reihenfolge)."""
    registry = get_registry()
    return [
        {
            "requirement_id": requirement_id,
            "title": registry.requirements[requirement_id].title,
            "description": registry.requirements[requirement_id].description,
        }
        for requirement_id in sorted(requirement_ids)
        if requirement_id in registry.requirements
    ]


def _trim(text: str | None, limit: int) -> str:
    one_line = " ".join((text or "").split())
    return one_line[:limit] + "…" if len(one_line) > limit else one_line


_SECTION_RESEARCH_MODULES: dict[str, set[str]] = {
    "3.1": {"market_growth", "customer_problem"},
    "3.2": {"competition_alternatives", "market_growth"},
    "3.3": {"customer_problem", "market_growth"},
    "4.1": {"state_of_the_art"},
    "4.2": {"state_of_the_art"},
    "4.6": {"swiss_research_partners"},
}


def retrieve_advisory_research_context(
    db: Session, run: AnalysisRun, profile_id: str, target_section: str | None = None,
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

    allowed_modules = _SECTION_RESEARCH_MODULES.get(target_section or "")
    rows = list(db.execute(
        select(SourceDocument, ResearchResult, ResearchTask)
        .join(ResearchResult, ResearchResult.source_document_id == SourceDocument.source_id)
        .join(ResearchTask, ResearchTask.research_task_id == ResearchResult.research_task_id)
        .join(
            SourceVersion,
            SourceVersion.source_version_id == SourceDocument.current_source_version_id,
        )
        .where(
            SourceDocument.project_id == run.project_id,
            SourceDocument.workspace_id == run.workspace_id,
            SourceDocument.status == "processed",
            SourceVersion.processing_status == "processed",
            ResearchResult.status == "imported",
            ResearchResult.content_review_status == "reviewed",
            ResearchResult.support_status.in_(("supports", "partially_supports")),
            ResearchTask.execution_mode == "live",
        )
    ))
    if allowed_modules is not None:
        rows = [row for row in rows if row[2].research_module in allowed_modules]
    sources = [row[0] for row in rows]
    provenance = {row[0].source_id: row for row in rows}
    fragments = source_scope.prefilter_fragments(
        db, sources, max_fragments=_RESEARCH_SOURCE_MAX_FRAGMENTS,
        char_budget=_RESEARCH_SOURCE_CHAR_BUDGET,
        require_market_signal=profile_id == "A2.value_creation_market_logic",
    )
    imported = [
        {
            "source_id": f.source_document_id,
            "source_name": provenance[f.source_document_id][1].title,
            "title": provenance[f.source_document_id][1].title,
            "source_url": (
                provenance[f.source_document_id][1].final_url
                or provenance[f.source_document_id][1].source_url
            ),
            "research_module": provenance[f.source_document_id][2].research_module,
            "content_review_status": provenance[f.source_document_id][1].content_review_status,
            "support_status": provenance[f.source_document_id][1].support_status,
            "snippet": _trim(f.text, _RESEARCH_SNIPPET_MAX),
        }
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
        lines.append(
            f"- [research_source_id={s['source_id']} | module={s['research_module']} | "
            f"user-reviewed public source | support={s['support_status']} | "
            f"{s['source_name']}] {s['snippet']}"
        )
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


def _selected_portal_language(structured: dict) -> str | None:
    """Read the explicit portal choice from the frozen structured input.

    Older snapshots may not carry this value.  In that case callers retain the
    established draft-language heuristic but mark it for human confirmation.
    """
    project = structured.get("project") or {}
    values = project.get("portal_field_values") or (
        (project.get("application_structure") or {}).get("portal_field_values")
    ) or {}
    value = values.get("INTRO.APP.COMMUNICATION_LANGUAGE") if isinstance(values, dict) else None
    if isinstance(value, dict):
        value = value.get("value") or value.get("selected")
    normalized = str(value or "").strip().casefold()
    if normalized in {"de", "deutsch", "german", "deutsch (de)"}:
        return "de"
    if normalized in {"en", "englisch", "english", "english (en)"}:
        return "en"
    return None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _budgeted_context(
    target_text: str,
    components: list[tuple[str, str, int, int]],
    budget: int,
    *,
    sentence_boundaries: bool = False,
) -> tuple[str, list[dict], list[tuple[str, str]]]:
    """Keep the applicant target in full and allocate the remaining budget.

    Component tuple = (kind, text, weight, item_count). Unused shares are
    redistributed in declared priority order. Only safe counts are returned as
    metadata. Der dritte Rückgabewert sind die (kind, Text)-Paare exakt in der
    Form, in der sie im Prompt stehen — abgeschnittene Anteile fehlen dort, wie
    sie auch dem Modell fehlen.
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
    visible = [("current_field_text", target_body)]
    for (kind, content, _, item_count), header, length in zip(active, headers, used):
        visible_content = content[:length]
        if sentence_boundaries and length < len(content):
            boundaries = [
                match.end()
                for match in re.finditer(r"(?:[.!?](?=\s|$)|\n)", visible_content)
            ]
            visible_content = visible_content[:boundaries[-1]] if boundaries else ""
        blocks.append(header + visible_content)
        meta.append({
            "kind": kind, "item_count": item_count,
            "character_count": len(visible_content),
            "truncated": len(visible_content) < len(content),
        })
        visible.append((kind, visible_content))
    rendered = "\n\n".join(blocks)
    if len(rendered) > budget:  # defensive accounting invariant
        raise ContextBudgetError("context_budget_accounting_error")
    return rendered, meta, visible


def assemble_a2_context(
    db: Session,
    run: AnalysisRun,
    *,
    field_id: str,
    profile_id: str,
    target_section: str | None = None,
    section_markers: tuple[str, ...] = (),
    language: str | None = None,
    base_version_id: str | None = None,
    improvement_mode: str = "clearer",
    selected_anchor_ids: list[str] | None = None,
    manifest_mode: bool = False,
) -> A2Context:
    requirement_ids = _linked_requirement_ids(field_id)
    ctx = A2Context(
        field_id=field_id, profile_id=profile_id,
        target_section=target_section, language=language or "de",
        manifest_mode=manifest_mode,
        requirement_ids=set(requirement_ids),
        rule_ids=_linked_rule_ids(requirement_ids),
        selected_anchor_ids=set(selected_anchor_ids or []),
        improvement_mode=improvement_mode,
    )
    ctx.field_profile = _field_profile_view(field_id)
    full_draft_text = _current_draft_text(db, run, field_id)
    adjacent: list[dict] = []
    if target_section is not None:
        if not section_markers:
            raise SectionStructureError("section_markers_missing")
        # Ziel-tolerant (2026-07-24): fehlende Nicht-Ziel-Marker sind kein
        # Blocker mehr — nur der Zielabschnitt muss im Text existieren.
        spans = target_section_spans(
            full_draft_text, section_markers, target_section
        )
        ctx.current_draft_text = extract_section(
            full_draft_text, section_markers, target_section
        )
        ctx.is_initial_draft = _section_is_initial_draft(
            ctx.current_draft_text, field_id, target_section
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
        ctx.is_initial_draft = is_placeholder_only(full_draft_text)
    ctx.language = language or detect_application_language(ctx.current_draft_text)
    ctx.advisory_facts = [] if manifest_mode else retrieve_advisory_project_facts(db, run)
    if manifest_mode:
        ctx.verified_evidence, source_version_ids = _manifest_evidence(
            db, run, requirement_ids=requirement_ids,
            selected_anchor_ids=ctx.selected_anchor_ids,
        )
        ctx.source_version_ids = set(source_version_ids)
        ctx.research_candidates = []
    else:
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
    portal_language = _selected_portal_language(ctx.structured_project_data)
    if language is None and portal_language is not None:
        ctx.language = portal_language
    ctx.open_issues = retrieve_open_issues(db, run, requirement_ids, field_id)
    ctx.requirement_assessments = _requirement_assessments(db, run, requirement_ids)
    # R5.7: advisory research context (VC/SOL only) — never added to allowed_anchor_ids.
    ctx.research_context = (
        {}
        if manifest_mode
        else retrieve_advisory_research_context(db, run, profile_id, target_section)
    )
    ctx.allowed_anchor_ids = {e["anchor_id"] for e in ctx.verified_evidence}
    ctx.allowed_issue_ids = {i["issue_id"] for i in ctx.open_issues}
    ctx.allowed_research_source_ids = {
        item["source_id"] for item in ctx.research_context.get("imported_sources", [])
    }
    if manifest_mode:
        ctx.market_comparison_id, ctx.market_findings = _market_findings(
            db, run, field_id=field_id, requirement_ids=requirement_ids,
            allowed_anchor_ids=ctx.allowed_anchor_ids,
        )

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
        "requirement_ids": sorted(ctx.requirement_ids),
        # Titel + Beschreibung aus der Registry (statische D0-Daten) — ohne sie
        # sind die Anforderungs-IDs für das Modell inhaltsleer.
        "requirement_definitions": _requirement_definitions(ctx.requirement_ids),
        "rule_ids": sorted(ctx.rule_ids),
        "improvement_mode": improvement_mode,
        "allowed_evidence_types": [
            "application_evidence",
            "external_evidence",
            "drafting_context",
            "applicant_claim_with_provenance",
        ],
        # Konditional, damit der Kontext für Bestandsentwürfe unverändert
        # bleibt — Schlüssel nie unkonditional aufnehmen. Die zugehörige
        # Anweisung steht als Aufgaben-Direktive im Instruction-Teil.
        **({"draft_state": "initial"} if ctx.is_initial_draft else {}),
    })
    research_candidates = {
        "location_only_or_unconfirmed_anchors": ctx.research_candidates,
        "public_source_candidates": ctx.research_context.get("imported_sources", []),
        "advisory_a1_facts": ctx.advisory_facts,
    }
    def context_components() -> list[tuple[str, str, int, int]]:
        return [
            ("accepted_project_input", _json(ctx.structured_project_data), 25, 1),
            ("external_evidence", _json(ctx.verified_evidence), 35,
             len(ctx.verified_evidence)),
            ("open_issue", _json(ctx.open_issues), 15, len(ctx.open_issues)),
            ("imported_applicant_text", _json(adjacent), 15, len(adjacent)),
            # Gewicht 10 (vorher 5): schützt die Anforderungsdefinitionen vor
            # Budget-Truncation in evidenzlastigen Runs; ohne Budget-Druck
            # bleibt der Output byte-identisch.
            ("portal_requirement", portal_requirement, 10,
             len(ctx.requirement_assessments)),
            ("market_finding", _json(ctx.market_findings), 5,
             len(ctx.market_findings)),
            ("research_candidate", _json(research_candidates), 5,
             len(ctx.research_candidates)
             + len(ctx.research_context.get("imported_sources", []))
             + len(ctx.advisory_facts)),
        ]

    ctx.context_text, ctx.context_components, ctx.visible_components = _budgeted_context(
        ctx.current_draft_text,
        context_components(),
        budget,
        sentence_boundaries=manifest_mode,
    )
    # Manifest contexts never pass a partial evidence object through the separate
    # structured INPUT payload. If the evidence component does not fit as a whole,
    # remove the lowest-priority anchor and rebuild until every retained anchor is
    # fully visible. The removed IDs remain auditable in the metadata-only manifest.
    while manifest_mode and ctx.verified_evidence and any(
        component["kind"] == "external_evidence" and component["truncated"]
        for component in ctx.context_components
    ):
        omitted = ctx.verified_evidence.pop()
        ctx.omitted_anchor_ids.add(omitted["anchor_id"])
        ctx.allowed_anchor_ids = {
            item["anchor_id"] for item in ctx.verified_evidence
        }
        ctx.source_version_ids = {
            item["source_version_id"]
            for item in ctx.verified_evidence
            if item.get("source_version_id")
        }
        ctx.market_findings = [
            item for item in ctx.market_findings
            if set(item.get("anchor_ids") or []) & ctx.allowed_anchor_ids
        ]
        ctx.context_text, ctx.context_components, ctx.visible_components = _budgeted_context(
            ctx.current_draft_text,
            context_components(),
            budget,
            sentence_boundaries=True,
        )
    adjacent_was_compacted = any(item["truncated"] for item in adjacent)
    if adjacent_was_compacted:
        for component in ctx.context_components[1:]:
            if component["kind"] == "imported_applicant_text":
                component["truncated"] = True
    ctx.context_hash = _hash_text(ctx.context_text)
    manifest_components = {
        kind: _hash_text(text)
        for kind, text in ctx.visible_components
    }
    manifest_payload = {
        "run_id": run.run_id,
        "field_id": field_id,
        "base_version_id": base_version_id,
        "target_section": target_section,
        "improvement_mode": improvement_mode,
        "language": ctx.language,
        "selected_anchor_ids": sorted(ctx.selected_anchor_ids),
        "anchor_ids": sorted(ctx.allowed_anchor_ids),
        "omitted_anchor_ids": sorted(ctx.omitted_anchor_ids),
        "source_version_ids": sorted(ctx.source_version_ids),
        "market_comparison_id": ctx.market_comparison_id,
        "requirement_ids": sorted(ctx.requirement_ids),
        "rule_ids": sorted(ctx.rule_ids),
        "component_hashes": manifest_components,
    }
    ctx.manifest_context_hash = _hash_text(_json(manifest_payload))
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
        "language_source": (
            "explicit_argument" if language is not None
            else "portal_communication_language" if portal_language is not None
            else "draft_language_detection_requires_human_review"
        ),
        "language_needs_review": language is None and portal_language is None,
        "components": ctx.context_components,
        "manifest_mode": manifest_mode,
        "manifest_context_hash": ctx.manifest_context_hash,
        "selected_anchor_count": len(ctx.selected_anchor_ids),
        "source_version_count": len(ctx.source_version_ids),
        "market_finding_count": len(ctx.market_findings),
        "context_truncated": any(
            component["truncated"] for component in ctx.context_components
        ) or bool(ctx.omitted_anchor_ids),
        "omitted_anchor_ids": sorted(ctx.omitted_anchor_ids),
    }
    return ctx


def persist_suggestion_manifest(
    db: Session,
    run: AnalysisRun,
    ctx: A2Context,
    *,
    base_version_id: str,
    prompt_version: str,
    output_schema_version: str,
) -> SuggestionContextManifest:
    """Persist the metadata-only manifest for an already assembled context."""
    existing = db.scalar(
        select(SuggestionContextManifest).where(
            SuggestionContextManifest.run_id == run.run_id,
            SuggestionContextManifest.field_id == ctx.field_id,
            SuggestionContextManifest.base_draft_version_id == base_version_id,
            SuggestionContextManifest.context_hash == ctx.manifest_context_hash,
        )
    )
    if existing is not None:
        return existing
    registry = get_registry()
    formal = formal_application_scope(db, run)
    field_instruction_hash = _hash_text(_json(ctx.field_profile))
    manifest = SuggestionContextManifest(
        manifest_id=str(uuid.uuid4()),
        schema_version="SuggestionContextManifest@v1",
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        run_id=run.run_id,
        field_id=ctx.field_id,
        base_draft_version_id=base_version_id,
        primary_application_source_version_id=(
            formal.source_version_id if formal.status == "configured" else None
        ),
        requirement_registry_version=registry.requirement_registry_version,
        rule_registry_version=registry.rule_registry_version,
        field_instruction_hash=field_instruction_hash,
        improvement_mode=ctx.improvement_mode,
        language=ctx.language,
        selected_anchor_ids=sorted(ctx.selected_anchor_ids),
        source_version_ids=sorted(ctx.source_version_ids),
        market_comparison_id=ctx.market_comparison_id,
        requirement_ids=sorted(ctx.requirement_ids),
        rule_ids=sorted(ctx.rule_ids),
        prompt_version=prompt_version,
        output_schema_version=output_schema_version,
        omitted_anchor_ids=sorted(ctx.omitted_anchor_ids),
        component_hashes={kind: _hash_text(text) for kind, text in ctx.visible_components},
        context_hash=ctx.manifest_context_hash,
    )
    db.add(manifest)
    db.flush()
    return manifest


def suggestion_context_options(db: Session, run: AnalysisRun) -> dict:
    """Metadata-only projection of anchors a user may explicitly select."""
    anchors: list[dict] = []
    for anchor in db.scalars(
        select(EvidenceAnchor).where(
            EvidenceAnchor.workspace_id == run.workspace_id,
            EvidenceAnchor.project_id == run.project_id,
            EvidenceAnchor.scope.in_(("external", "drafting_context")),
            EvidenceAnchor.verification_status.in_(("exact_verified", "human_verified")),
        ).order_by(EvidenceAnchor.anchor_id)
    ):
        document = db.get(SourceDocument, anchor.source_id)
        version = db.get(SourceVersion, anchor.source_version_id)
        if (
            document is None or version is None
            or document.current_source_version_id != anchor.source_version_id
            or version.content_review_status != "reviewed"
            or version.content_safety_status not in ("passed", "human_released")
            or is_generated_or_review_source(document)
        ):
            continue
        anchors.append({
            "anchor_id": anchor.anchor_id,
            "source_id": anchor.source_id,
            "source_version_id": anchor.source_version_id,
            "source_name": anchor.source_name,
            "scope": anchor.scope,
            "verification_status": anchor.verification_status,
            "page": anchor.page,
            "section": anchor.section,
        })
    comparison = db.scalar(
        select(MarketComparison)
        .where(
            MarketComparison.project_id == run.project_id,
            MarketComparison.workspace_id == run.workspace_id,
            MarketComparison.status.in_(("ready_for_review", "limited")),
            MarketComparison.stale_reason.is_(None),
        )
        .order_by(MarketComparison.updated_at.desc())
    )
    return {
        "anchors": anchors,
        "market_comparison_id": comparison.comparison_id if comparison else None,
        "market_comparison_status": comparison.status if comparison else None,
    }


_PARTNER_NAME_KEYS = (
    "name", "organisation", "organization", "institution", "partner_name",
    "legal_name", "display_name",
)


def _partner_names(structured: dict) -> list[str]:
    names: list[str] = []
    for partner in structured.get("partners") or []:
        if isinstance(partner, str):
            names.append(partner)
            continue
        if not isinstance(partner, dict):
            continue
        names.extend(
            str(value) for key, value in partner.items()
            if key in _PARTNER_NAME_KEYS and isinstance(value, str) and value.strip()
        )
    return names


# --------------------------------------------------------------------------
# 2026-07-26 — Halluzinationsschutz: technische Kennungen dürfen keine Zahlen
# erlauben.
#
# ``allowed_facts._NUMBER_RE`` erkennt jede Ziffernfolge an einer
# Nicht-Wortgrenze. Im rohen INPUT-Payload stehen aber UUIDs (``run_id``,
# ``primary_application_source_id``, …) und reine Telemetrie
# (``character_count``, ``item_count``). Deren Ziffern landeten dadurch in der
# Erlaubt-Basis, und ``_is_derivable`` erzeugte daraus per Arithmetik weitere
# „erlaubte" Zahlen. Folge: eine erfundene Zahl konnte die Prüfung zufällig
# passieren (gemessen ~5 % pro Lauf; sichtbar als sporadisch rote
# ``invented_numeric_token``-Fälle).
#
# Diese Projektion gilt AUSSCHLIESSLICH für die Erlaubt-Basis. Das an den
# Provider gesendete Payload bleibt unverändert — nur die Frage „welche Zahl
# darf im Text vorkommen" wird auf inhaltstragende Felder eingeschränkt.
# --------------------------------------------------------------------------
_IDENTIFIER_KEY_RE = re.compile(r"(?:^|_)(?:id|ids|hash|hashes|uuid|version)$", re.IGNORECASE)
_TELEMETRY_KEYS = frozenset({
    "context_components", "character_count", "item_count", "character_limit",
    "research_candidate_count",
})
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _facts_only(value: object) -> object:
    """Entfernt Kennungen und Telemetrie — nur für die Erlaubt-Basis."""
    if isinstance(value, dict):
        return {
            key: _facts_only(item)
            for key, item in value.items()
            if key not in _TELEMETRY_KEYS and not _IDENTIFIER_KEY_RE.search(str(key))
        }
    if isinstance(value, list):
        return [_facts_only(item) for item in value]
    if isinstance(value, str):
        return _UUID_RE.sub("", value)
    return value


def build_allowed_facts(
    ctx: A2Context, input_payload: dict
) -> allowed_facts.AllowedFactsManifest:
    """Erlaubt-Basis aus genau dem, was im finalen Request sichtbar ist.

    Sichtbar ist (siehe ``gateway._assemble_prompt``) das strukturierte
    ``INPUT``-Payload plus der budgetierte Kontexttext. Beides geht typisiert
    ein — nicht der volle Fallkorpus und nicht nur der gekürzte Kontextstring.
    Bekannte Partnernamen werden ergänzt, sofern sie tatsächlich im Request
    stehen (ein wegen Budget entfallener Partner gilt nie als bekannt).
    """
    payload_text = _json(input_payload)
    # Erlaubt-Basis ohne Kennungen/Telemetrie (siehe _facts_only) …
    components = [
        *ctx.visible_components,
        ("structured_input_payload", _json(_facts_only(input_payload))),
    ]
    # … der Sichtbarkeitstest für Partnernamen nutzt weiterhin das echte,
    # unveränderte Payload — sonst gälte ein tatsächlich gesendeter Name als
    # nicht gesendet.
    visible_text = "\n".join([payload_text, *(text for _kind, text in ctx.visible_components)])
    haystack = visible_text.casefold()
    names = [
        name for name in _partner_names(ctx.structured_project_data)
        if name.strip().casefold() in haystack
    ]
    return allowed_facts.add_known_organisations(
        allowed_facts.build_manifest(components), names
    )


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
