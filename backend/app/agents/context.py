"""A1 context assembly from the immutable RunSourceSnapshot (Milestone 9B).

Read-only, snapshot-scoped tool-services — model code never touches the DB and
gets no file/network/arbitrary-DB access. Fragments are selected deterministically,
capped by the profile fragment limit AND an explicit character budget, truncated
at fragment boundaries, hashed (context_hash) and accompanied by non-sensitive
metadata (selected/skipped counts). Source text is labelled untrusted data.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
    ToolInvocation,
)
from app.registry.loader import PortalFieldDef, get_registry

A1_FIELD_PREFIXES = ("INTRO.", "ORG.", "VC.", "SOL.", "PS.")


@dataclass(frozen=True)
class FragmentBlock:
    fragment_id: str
    source_version_id: str
    source_title: str
    ordinal: int
    page: int | None
    section: str | None
    text: str


@dataclass
class A1Context:
    fragment_blocks: list[FragmentBlock] = field(default_factory=list)
    requirement_defs: list[dict] = field(default_factory=list)
    field_defs: list[dict] = field(default_factory=list)
    extracted_facts: list[dict] = field(default_factory=list)
    context_text: str = ""
    context_hash: str = ""
    selected_fragment_ids: list[str] = field(default_factory=list)
    source_version_ids: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ordered_snapshot_versions(
    db: Session, run: AnalysisRun
) -> list[tuple[SourceVersion, SourceDocument | None]]:
    """Frozen run-snapshot sources in canonical order (created_at, document_id)."""
    rows = db.scalars(
        select(RunSourceSnapshot).where(RunSourceSnapshot.run_id == run.run_id)
    ).all()
    pairs: list[tuple[SourceVersion, SourceDocument | None]] = []
    seen: set[str] = set()
    for row in rows:
        if row.source_version_id in seen:
            continue
        seen.add(row.source_version_id)
        version = db.get(SourceVersion, row.source_version_id)
        if version is None or version.normalized_text is None:
            continue
        document = db.get(SourceDocument, version.source_document_id)
        pairs.append((version, document))
    pairs.sort(key=lambda pair: (pair[0].created_at, pair[0].source_document_id))
    return pairs


def retrieve_source_fragments(
    db: Session, run: AnalysisRun, *, max_fragments: int, char_budget: int
) -> tuple[list[FragmentBlock], dict]:
    """Deterministic, de-duplicated, budget-limited snapshot fragments.

    Selection order: snapshot source canonical order, then fragment ``ordinal``.
    Truncation is at fragment boundaries (trailing fragments dropped) — never mid
    fragment. Returns (selected blocks, metadata with selected/skipped counts).
    """
    ordered: list[FragmentBlock] = []
    seen_fragments: set[str] = set()
    for version, document in _ordered_snapshot_versions(db, run):
        fragments = list(
            db.scalars(
                select(SourceFragment).where(
                    SourceFragment.source_version_id == version.source_version_id
                )
            )
        )
        fragments.sort(key=lambda f: f.ordinal)
        title = document.name if document is not None else version.source_version_id
        for frag in fragments:
            if frag.fragment_id in seen_fragments:
                continue
            seen_fragments.add(frag.fragment_id)
            ordered.append(
                FragmentBlock(
                    fragment_id=frag.fragment_id,
                    source_version_id=version.source_version_id,
                    source_title=title,
                    ordinal=frag.ordinal,
                    page=frag.page,
                    section=frag.section,
                    text=frag.normalized_text,
                )
            )

    total_available = len(ordered)
    selected: list[FragmentBlock] = []
    used_chars = 0
    for block in ordered:
        if len(selected) >= max_fragments:
            break
        if used_chars + len(block.text) > char_budget and selected:
            break  # boundary truncation: stop before exceeding the budget
        selected.append(block)
        used_chars += len(block.text)

    meta = {
        "total_available_fragments": total_available,
        "selected_fragment_count": len(selected),
        "skipped_fragment_count": total_available - len(selected),
        "char_budget": char_budget,
        "total_chars": used_chars,
        "max_fragments": max_fragments,
    }
    return selected, meta


def lookup_requirement_definition(run: AnalysisRun) -> list[dict]:
    """Active evaluable requirement ids/titles (ids only, as needed)."""
    registry = get_registry()
    return [
        {"requirement_id": r.requirement_id, "title": r.title}
        for r in registry.evaluable_requirements()
    ]


def _is_a1_field(field_def: PortalFieldDef) -> bool:
    return any(field_def.field_id.startswith(p) for p in A1_FIELD_PREFIXES)


def lookup_portal_field_profile(run: AnalysisRun) -> list[dict]:
    """Active portal fields under the A1 allowed selectors (ids/labels only)."""
    registry = get_registry()
    fields = [f for f in registry.portal_fields.values() if _is_a1_field(f)]
    fields.sort(key=lambda f: f.registry_index)
    return [{"field_id": f.field_id, "label": f.label_or_question} for f in fields]


def _record_tool_invocation(
    db: Session, run: AnalysisRun, tool_id: str, input_hash: str, output_hash: str,
    *, caller: str = "A1.project_fact_extraction",
) -> None:
    db.add(
        ToolInvocation(
            invocation_id=str(uuid.uuid4()),
            workspace_id=run.workspace_id,
            run_id=run.run_id,
            tool_id=tool_id,
            caller=caller,
            input_hash=input_hash,
            output_hash=output_hash,
            status="succeeded",
        )
    )


def _render_context_text(blocks: list[FragmentBlock]) -> str:
    lines: list[str] = []
    for block in blocks:
        loc = f"ordinal={block.ordinal}"
        if block.page is not None:
            loc += f" page={block.page}"
        if block.section:
            loc += f" section={block.section}"
        lines.append(
            f"[fragment_id={block.fragment_id} source_version_id="
            f"{block.source_version_id} title={block.source_title!r} {loc}]\n{block.text}"
        )
    return "\n\n".join(lines)


def assemble_a1_context(
    db: Session, run: AnalysisRun, *, max_fragments: int
) -> A1Context:
    """Build the full controlled A1 context and record the three tool invocations.
    No secrets/keys/system state; source text is untrusted data."""
    settings = get_settings()
    blocks, meta = retrieve_source_fragments(
        db, run, max_fragments=max_fragments,
        char_budget=settings.a1_context_char_budget,
    )
    requirement_defs = lookup_requirement_definition(run)
    field_defs = lookup_portal_field_profile(run)

    context_text = _render_context_text(blocks)
    context_hash = _hash_text(context_text)
    selected_ids = [b.fragment_id for b in blocks]
    version_ids = sorted({b.source_version_id for b in blocks})

    _record_tool_invocation(
        db, run, "retrieve_source_fragments",
        input_hash=_hash_text(run.run_id), output_hash=context_hash,
    )
    _record_tool_invocation(
        db, run, "lookup_requirement_definition",
        input_hash=_hash_text(run.run_id),
        output_hash=_hash_text(",".join(d["requirement_id"] for d in requirement_defs)),
    )
    _record_tool_invocation(
        db, run, "lookup_portal_field_profile",
        input_hash=_hash_text(run.run_id),
        output_hash=_hash_text(",".join(d["field_id"] for d in field_defs)),
    )

    meta["context_hash"] = context_hash
    return A1Context(
        fragment_blocks=blocks,
        requirement_defs=requirement_defs,
        field_defs=field_defs,
        context_text=context_text,
        context_hash=context_hash,
        selected_fragment_ids=selected_ids,
        source_version_ids=version_ids,
        meta=meta,
    )


def assemble_evidence_mapping_context(
    db: Session, run: AnalysisRun, *, max_fragments: int
) -> A1Context:
    """Controlled context for A1.evidence_candidate_mapping: the run's ExtractedFacts
    (ids/statements/status only) + active requirements/fields + frozen fragments. Same
    payload minimization as fact extraction; source text is untrusted data."""
    from app.repositories import extracted_facts as facts_repo

    settings = get_settings()
    caller = "A1.evidence_candidate_mapping"
    blocks, meta = retrieve_source_fragments(
        db, run, max_fragments=max_fragments,
        char_budget=settings.a1_context_char_budget,
    )
    requirement_defs = lookup_requirement_definition(run)
    field_defs = lookup_portal_field_profile(run)
    facts = [
        {"fact_id": f.fact_id, "statement": f.original_statement, "status": f.status}
        for f in facts_repo.list_for_run(db, run.run_id)
    ]

    context_text = _render_context_text(blocks)
    context_hash = _hash_text(context_text)
    selected_ids = [b.fragment_id for b in blocks]
    version_ids = sorted({b.source_version_id for b in blocks})

    _record_tool_invocation(
        db, run, "retrieve_source_fragments", input_hash=_hash_text(run.run_id),
        output_hash=context_hash, caller=caller,
    )
    _record_tool_invocation(
        db, run, "lookup_requirement_definition", input_hash=_hash_text(run.run_id),
        output_hash=_hash_text(",".join(d["requirement_id"] for d in requirement_defs)),
        caller=caller,
    )
    _record_tool_invocation(
        db, run, "lookup_portal_field_profile", input_hash=_hash_text(run.run_id),
        output_hash=_hash_text(",".join(d["field_id"] for d in field_defs)),
        caller=caller,
    )

    meta["context_hash"] = context_hash
    meta["extracted_fact_count"] = len(facts)
    return A1Context(
        fragment_blocks=blocks,
        requirement_defs=requirement_defs,
        field_defs=field_defs,
        extracted_facts=facts,
        context_text=context_text,
        context_hash=context_hash,
        selected_fragment_ids=selected_ids,
        source_version_ids=version_ids,
        meta=meta,
    )
