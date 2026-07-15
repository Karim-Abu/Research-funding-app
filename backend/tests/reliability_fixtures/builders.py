"""Row builders for the reliability regression fixtures (Milestone 9K)."""
from __future__ import annotations

import hashlib
import uuid

from app.db.models import (
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    MarketComparison,
    MarketComparisonItem,
    ReviewFinding,
)
from tests.a1_mapping_helpers import add_fact  # noqa: F401 (re-exported for tests)
from tests.a2_helpers import FIELD_ID, build_run_with_draft


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def completed_run_with_draft(db, *, draft_text: str, created_by: str = "user",
                             field_id: str = FIELD_ID, workspace_id: str = "ws-demo"):
    """A completed run + a draft (current version) carrying ``draft_text``."""
    run, draft, version_id = build_run_with_draft(
        db, draft_text=draft_text, field_id=field_id, workspace_id=workspace_id,
    )
    run.status = "completed"
    version = db.get(DraftVersion, version_id)
    version.created_by = created_by
    db.flush()
    return run, draft, version_id


def link_anchor_to_draft(db, run, version_id: str, *, quote: str,
                         verification_status: str = "exact_verified") -> str:
    """An EvidenceAnchor + an active EvidenceLink to the draft version (field-level evidence)."""
    anchor_id = "anchor-" + uuid.uuid4().hex[:10]
    db.add(EvidenceAnchor(
        anchor_id=anchor_id, run_id=run.run_id, workspace_id=run.workspace_id,
        source_version_id="sv", source_id="src", source_name="Quelle.txt",
        source_type="txt", fragment_id="frag-" + uuid.uuid4().hex[:6], quote=quote,
        quote_hash=_hash(quote), match_type="exact_normalized",
        normalizer_version="normalizer-1", verification_status=verification_status,
    ))
    db.add(EvidenceLink(
        evidence_link_id="link-" + uuid.uuid4().hex[:10], run_id=run.run_id,
        workspace_id=run.workspace_id, anchor_id=anchor_id,
        target_type="draft_version", target_id=version_id, status="active",
    ))
    db.flush()
    return anchor_id


def add_source_backed_market_item(db, run, *, name: str, quote: str) -> str:
    """A source-backed MarketComparisonItem with a verified quote for the run's project."""
    comparison_id = "cmp-" + uuid.uuid4().hex[:10]
    db.add(MarketComparison(
        comparison_id=comparison_id, project_id=run.project_id,
        workspace_id=run.workspace_id, status="ready_for_review", research_gaps=[],
        warnings=[], comparison_version=1, created_by="user-anna",
        generation_kind="model_generated",
    ))
    item_id = "item-" + uuid.uuid4().hex[:10]
    db.add(MarketComparisonItem(
        item_id=item_id, comparison_id=comparison_id, workspace_id=run.workspace_id,
        name=name, name_normalized=name.lower(), category="competitor",
        confidence_label="source_backed", status="accepted", source_document_ids=[],
        verified_quote_refs=[{"quote": quote, "source_document_id": "d",
                              "source_version_id": "v", "verification_method": "x"}],
    ))
    db.flush()
    return item_id


def add_a3_finding(db, run, *, field_id: str, description: str = "A3 note") -> str:
    """An open advisory A3 finding on a field (so it is NOT a silent consensus)."""
    finding_id = "a3-" + uuid.uuid4().hex[:10]
    db.add(ReviewFinding(
        finding_id=finding_id, run_id=run.run_id, workspace_id=run.workspace_id,
        profile_id="A3.evidence_consistency", field_id=field_id, requirement_id=None,
        severity="warning", description=description, status="open", advisory=True,
        source="agent", finding_code="a3:" + finding_id,
        target_type="portal_field_draft", target_id=field_id,
    ))
    db.flush()
    return finding_id
