"""Milestone 10 — deterministic evaluation enrichment for the demo dataset.

Applied ONLY when seeding with ``--evaluation`` (a superset of the plain demo seed). It
enriches the main demo project so an evaluator can see the full reliability surface end to
end, deterministically and with synthetic/public data only:

* a Value Creation draft (VC field),
* a **strong unsupported** claim (→ M9K reliability blocker) + a weak/warning claim (VC),
* a **supported** technical claim backed by an existing verified anchor (SOL),
* a **source-backed** MarketComparison item whose verified quote exactly matches an
  imported synthetic public source (via ``app/market/verify.py``),
* a RunQualitySummary + reliability findings from a real reliability pass.

Plain ``--reset`` never runs this, so the demo dataset (and demo-dataset.spec) is unchanged.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    EvidenceAnchor,
    MarketComparison,
    MarketComparisonItem,
    Project,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.demo.dataset import DEMO_PROJECTS, stable_id
from app.evidence.tokenize import content_terms
from app.fields import service as fields_service
from app.market import verify as market_verify
from app.reliability.executor import run_reliability_pass
from app.repositories import drafts as drafts_repo

logger = logging.getLogger("app.demo.evaluation")

SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

# A synthetic PUBLIC market source (no network). The verified quote is an exact substring.
_MARKET_SOURCE_TEXT = (
    "Die Referenzloesung Alpha bietet etablierte Zustandsueberwachung fuer "
    "industrielle Anlagen und wird von mehreren Anbietern am Markt eingesetzt."
)
_MARKET_QUOTE = (
    "Die Referenzloesung Alpha bietet etablierte Zustandsueberwachung fuer "
    "industrielle Anlagen"
)
_MARKET_CLASSIFICATION = {
    "sensitivity": "public", "origin": "public_source",
    "processing_mode": "deterministic_only", "web_research_mode": "validated_public",
    "nda_applies": False,
}

# VC draft: a strong UNSUPPORTED market claim (blocker) + a weak/hedged market claim.
_VC_TEXT = (
    "3.1 Wertschoepfung: Wir sind der weltweit erste und unangefochten fuehrende "
    "Anbieter mit dem groessten Marktanteil weltweit.\n"
    "3.2 Markt: Der adressierbare Markt fuer diese Loesung duerfte kuenftig "
    "voraussichtlich moderat wachsen."
)


def _main_run(db: Session) -> tuple[Project, AnalysisRun]:
    demo = DEMO_PROJECTS[0]
    project = db.get(Project, demo.project_id)
    run = db.get(AnalysisRun, demo.run_id)
    if project is None or run is None or run.status != "completed":
        raise RuntimeError("Evaluation enrichment requires the completed main demo run.")
    return project, run


def _first_anchor(db: Session, run: AnalysisRun) -> EvidenceAnchor:
    anchor = db.scalar(
        select(EvidenceAnchor)
        .where(
            EvidenceAnchor.run_id == run.run_id,
            EvidenceAnchor.verification_status == "exact_verified",
        )
        .order_by(EvidenceAnchor.created_at.asc(), EvidenceAnchor.anchor_id.asc())
    )
    if anchor is None:
        raise RuntimeError("Evaluation enrichment requires a verified evidence anchor.")
    return anchor


def _supported_sol_text(quote: str) -> str:
    """A single clean supported claim built from the anchor's CONTENT TERMS (no punctuation,
    no numbers) so it shares ≥2 key terms with the anchor quote and is not quantified —
    deterministically → supports_claim."""
    terms = sorted(t for t in content_terms(quote) if not t.isdigit() and len(t) >= 4)
    key = " ".join(terms[:6]) if len(terms) >= 2 else (quote or "Grundlage").strip()[:40]
    return (
        f"Das Verfahren nutzt nachweislich {key} und erreicht damit die belegte "
        "technische Leistung dieser Lösung."
    )


def _apply_edit(db: Session, run: AnalysisRun, field_id: str, text: str) -> str:
    draft = drafts_repo.get_draft(db, run.run_id, field_id)
    if draft is None:
        raise RuntimeError(f"Evaluation enrichment: missing draft field {field_id}.")
    drafts_repo.apply_update(
        db, run, draft, base_version_id=draft.current_version_id, text=text,
        source_operation_id=None, actor_user_id="user-anna",
    )
    db.flush()
    fresh = drafts_repo.get_draft(db, run.run_id, field_id)
    return fresh.current_version_id


def _link_anchor(db: Session, run: AnalysisRun, field_id: str, version_id: str,
                 anchor_id: str) -> None:
    draft = drafts_repo.get_draft(db, run.run_id, field_id)
    fields_service.create_draft_evidence_link(
        db, run=run, draft=draft, anchor_id=anchor_id,
        base_version_id=version_id, actor_user_id="user-anna",
    )
    db.flush()


def _ensure_market_source(db: Session, project: Project) -> tuple[str, SourceFragment]:
    doc_id = stable_id("eval-source", f"market:{project.project_id}")
    sv_id = stable_id("eval-source-version", f"market:{project.project_id}")
    frag_id = stable_id("eval-source-fragment", f"market:{project.project_id}")
    existing = db.get(SourceDocument, doc_id)
    if existing is None:
        db.add(SourceDocument(
            source_id=doc_id, project_id=project.project_id,
            workspace_id=project.workspace_id, name="Öffentliche Marktquelle (Demo)",
            type="url", status="processed", data_classification=_MARKET_CLASSIFICATION,
            created_by="user-anna", current_source_version_id=sv_id,
        ))
        db.add(SourceVersion(
            source_version_id=sv_id, source_document_id=doc_id, version_number=1,
            original_content_hash="eval-mkt", normalized_content_hash="eval-mkt-n",
            normalized_text=_MARKET_SOURCE_TEXT, parser_version="parser-1",
            normalizer_version="normalizer-1", chunker_version="chunker-1",
            processing_status="processed", data_classification=_MARKET_CLASSIFICATION,
            storage_ref="eval-market-source", original_filename="markt.txt",
            byte_size=len(_MARKET_SOURCE_TEXT), mime_type="text/plain",
        ))
        db.add(SourceFragment(
            fragment_id=frag_id, source_version_id=sv_id, ordinal=0,
            original_text=_MARKET_SOURCE_TEXT, normalized_text=_MARKET_SOURCE_TEXT,
            start_offset=0, end_offset=len(_MARKET_SOURCE_TEXT), content_hash="eval-mkt-f",
        ))
        db.flush()
    return doc_id, db.get(SourceFragment, frag_id)


def _ensure_market_comparison(db: Session, project: Project) -> None:
    doc_id, fragment = _ensure_market_source(db, project)
    # corr 4: source_backed ONLY when the verified quote exactly matches the source text.
    ref = market_verify.verify_quote(
        db, fragment=fragment, source_document_id=doc_id, quote=_MARKET_QUOTE
    )
    if ref is None:
        raise RuntimeError("Evaluation market fixture: quote did not verify against source.")
    comparison_id = stable_id("market-comparison", project.project_id)
    if db.get(MarketComparison, comparison_id) is None:
        db.add(MarketComparison(
            comparison_id=comparison_id, project_id=project.project_id,
            workspace_id=project.workspace_id, status="ready_for_review",
            research_gaps=[], warnings=[], comparison_version=1, created_by="user-anna",
            generation_status="succeeded",
        ))
    item_id = stable_id("market-item", project.project_id)
    if db.get(MarketComparisonItem, item_id) is None:
        db.add(MarketComparisonItem(
            item_id=item_id, comparison_id=comparison_id,
            workspace_id=project.workspace_id, name="Referenzlösung Alpha (Demo)",
            name_normalized="referenzloesung alpha (demo)", category="reference_solution",
            description="Öffentlich erwähnte Referenzlösung.", relation_to_project="reference",
            confidence_label="source_backed", status="proposed",
            source_document_ids=[doc_id], verified_quote_refs=[ref],
        ))
    db.flush()


def apply_evaluation(db: Session) -> None:
    """Idempotently apply the M10 evaluation enrichment to the main demo project."""
    project, run = _main_run(db)
    anchor = _first_anchor(db, run)

    # SOL: a single supported technical claim backed by the existing verified anchor.
    sol_version = _apply_edit(db, run, SOL_FIELD, _supported_sol_text(anchor.quote))
    _link_anchor(db, run, SOL_FIELD, sol_version, anchor.anchor_id)

    # VC: a strong unsupported claim (blocker) + a weak claim (warning). No evidence link.
    _apply_edit(db, run, VC_FIELD, _VC_TEXT)

    # Source-backed market comparison (deterministic, no network).
    _ensure_market_comparison(db, project)
    db.commit()
    db.expire_all()

    # Deterministic reliability pass → RunQualitySummary + reliability findings.
    run = db.get(AnalysisRun, run.run_id)
    run_reliability_pass(db, run)
    db.commit()
    logger.info("evaluation enrichment complete for run=%s", run.run_id)
