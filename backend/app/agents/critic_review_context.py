"""A3 evidence-consistency context assembly (Milestone 9G).

Minimal, evidence-focused context for A3.evidence_consistency over the scoped
fields (SOL + VC) that have a current, non-empty DraftVersion. Reuses the A2
read-only tool-services. Builds the pinned ``CriticReviewInput@v1`` plus a rendered
``context_text`` (which carries PROPOSED A1 facts explicitly marked as *unconfirmed*,
A2 lineage and active blocker open issues). No full source documents, secrets,
unrelated fields or other projects. Source text is untrusted data.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import field_drafting_context as a2_context
from app.agents.a3_review import A3_PROFILE_ID, A3_SCOPE_FIELDS
from app.config.settings import get_settings
from app.db.models import AnalysisRun, DraftVersion, EvidenceLink, ToolInvocation
from app.registry import get_registry
from app.repositories import drafts as drafts_repo
from app.repositories import extracted_facts as facts_repo

import uuid


@dataclass
class CriticContext:
    payload: dict = field(default_factory=dict)
    context_text: str = ""
    context_hash: str = ""
    meta: dict = field(default_factory=dict)
    allowed_field_ids: set = field(default_factory=set)
    allowed_requirement_ids: set = field(default_factory=set)
    allowed_anchor_ids: set = field(default_factory=set)
    allowed_link_ids: set = field(default_factory=set)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_tool(db: Session, run: AnalysisRun, tool_id: str, output_hash: str) -> None:
    db.add(
        ToolInvocation(
            invocation_id=str(uuid.uuid4()), workspace_id=run.workspace_id,
            run_id=run.run_id, tool_id=tool_id, caller=A3_PROFILE_ID,
            input_hash=_hash_text(run.run_id), output_hash=output_hash,
            status="succeeded",
        )
    )


def _scoped_drafts(db: Session, run: AnalysisRun) -> list[dict]:
    """In-scope fields with a current, NON-EMPTY DraftVersion (corr 5)."""
    drafts: list[dict] = []
    for field_id in A3_SCOPE_FIELDS:
        draft = drafts_repo.get_draft(db, run.run_id, field_id)
        if draft is None or draft.current_version_id is None:
            continue
        version = db.get(DraftVersion, draft.current_version_id)
        if version is None or not (version.text or "").strip():
            continue
        drafts.append({
            "field_id": field_id,
            "draft_version_id": version.draft_version_id,
            "text": version.text,
            "created_by": version.created_by,
            "character_count": version.character_count,
        })
    return drafts


def _rule_results(db: Session, run: AnalysisRun, requirement_ids: set[str]) -> list[dict]:
    registry = get_registry()
    results: list[dict] = []
    for record in a2_context._requirement_assessments(db, run, requirement_ids):
        req = registry.requirements.get(record["requirement_id"])
        rule_id = req.linked_rule_ids[0] if req and req.linked_rule_ids else "unknown"
        results.append({
            "rule_id": rule_id, "status": record["status"],
            "requirement_id": record["requirement_id"],
        })
    return results


def _active_draft_links(db: Session, run: AnalysisRun) -> list[EvidenceLink]:
    return list(db.scalars(
        select(EvidenceLink).where(
            EvidenceLink.run_id == run.run_id,
            EvidenceLink.target_type == "draft_version",
            EvidenceLink.status == "active",
        )
    ))


def _confirmed_facts(db: Session, run: AnalysisRun) -> list[dict]:
    """Genuinely confirmed facts ONLY (corr 1) — proposed A1 facts are never here."""
    facts: list[dict] = []
    for f in facts_repo.list_for_run(db, run.run_id):
        if f.status != "confirmed" or not (f.source_fragment_ids or []):
            continue
        facts.append({
            "fact_id": f.fact_id, "statement": f.original_statement,
            "fact_type": f.fact_type, "normalized_value": f.normalized_value,
            "source_fragment_ids": list(f.source_fragment_ids or []),
        })
    return facts


def _render(drafts, evidence, requirements, rule_results, proposed_facts,
            blocker_issues, existing_findings) -> str:
    lines: list[str] = ["# A3 Evidence Consistency Context"]
    for d in drafts:
        lines.append(
            f"\n## Field {d['field_id']} (version {d['draft_version_id']}, "
            f"created_by={d['created_by']})"
        )
        if d["created_by"] == "agent":
            lines.append("[A2-Vorschlag übernommen — prüfe Belege besonders sorgfältig]")
        lines.append(d["text"])
    lines.append("\n## Verifizierte Belege")
    for e in evidence:
        lines.append(
            f"- {e['anchor_id']} [{e['verification_status']}] {e['source_name']}: "
            f"\"{e['quote'][:200]}\" (req {e.get('requirement_id')})"
        )
    lines.append("\n## Anforderungsstatus (deterministisch)")
    for r in rule_results:
        lines.append(f"- {r['requirement_id']} → {r['status']} (rule {r['rule_id']})")
    lines.append(
        "\n## Vorgeschlagene A1-Fakten — UNBESTÄTIGT (keine bestätigten Fakten; "
        "nicht als gesichert behandeln)"
    )
    for f in proposed_facts:
        lines.append(f"- [unbestätigt] {f['statement']}")
    if blocker_issues:
        lines.append("\n## Offene blockierende Hinweise")
        for i in blocker_issues:
            lines.append(f"- {i['issue_id']} [{i['severity']}] {i['description']}")
    if existing_findings:
        lines.append("\n## Bereits offene KI-Hinweise (nicht duplizieren)")
        for f in existing_findings:
            lines.append(f"- {f}")
    return "\n".join(lines)


def assemble_critic_context(db: Session, run: AnalysisRun) -> CriticContext | None:
    """Returns the assembled context, or None when no scoped field has draft content
    (corr 5 — the caller then skips A3 with a ControlResult/AuditEvent)."""
    drafts = _scoped_drafts(db, run)
    if not drafts:
        return None

    field_ids = {d["field_id"] for d in drafts}
    requirement_ids: set[str] = set()
    for field_id in field_ids:
        requirement_ids |= a2_context._linked_requirement_ids(field_id)

    evidence = a2_context.retrieve_verified_evidence(db, run)
    requirements = a2_context._requirement_assessments(db, run, requirement_ids)
    rule_results = _rule_results(db, run, requirement_ids)
    structured = a2_context.retrieve_structured_project_data(db, run)
    confirmed_facts = _confirmed_facts(db, run)
    proposed_facts = a2_context.retrieve_confirmed_project_facts(db, run)  # proposed/unconfirmed
    draft_links = _active_draft_links(db, run)

    blocker_issues = [
        i for fid in field_ids
        for i in a2_context.retrieve_open_issues(db, run, requirement_ids, fid)
        if i["severity"] == "blocker"
    ]

    evidence_links = [
        {"anchor_id": e["anchor_id"], "quote": e["quote"], "source_name": e["source_name"],
         "verification_status": e["verification_status"], "page": e.get("page"),
         "section": e.get("section"), "requirement_id": e.get("requirement_id")}
        for e in evidence
    ]

    payload = {
        "run_id": run.run_id,
        "profile_ids": [A3_PROFILE_ID],
        "current_drafts": drafts,
        "requirements": requirements,
        "rule_results": rule_results,
        "evidence_links": evidence_links,
        "confirmed_facts": confirmed_facts,
        "structured_project_data": structured,
    }

    for tool_id, payload_hash in (
        ("retrieve_current_drafts", _hash_text(",".join(sorted(field_ids)))),
        ("retrieve_verified_evidence", _hash_text(",".join(sorted(e["anchor_id"] for e in evidence)))),
        ("retrieve_rule_results", _hash_text(",".join(sorted(requirement_ids)))),
        ("retrieve_structured_project_data", _hash_text(str(structured))),
    ):
        _record_tool(db, run, tool_id, payload_hash)

    context_text = _render(
        drafts, evidence, requirements, rule_results, proposed_facts, blocker_issues, [],
    )
    budget = get_settings().a1_context_char_budget
    context_text = context_text[:budget]
    context_hash = _hash_text(context_text)

    return CriticContext(
        payload=payload,
        context_text=context_text,
        context_hash=context_hash,
        meta={
            "context_hash": context_hash,
            "draft_count": len(drafts),
            "evidence_count": len(evidence),
            "requirement_count": len(requirements),
            "proposed_fact_count": len(proposed_facts),
            "confirmed_fact_count": len(confirmed_facts),
            "char_budget": budget,
            "total_chars": len(context_text),
        },
        allowed_field_ids=field_ids,
        allowed_requirement_ids=requirement_ids,
        allowed_anchor_ids={e["anchor_id"] for e in evidence},
        allowed_link_ids={link.evidence_link_id for link in draft_links},
    )
