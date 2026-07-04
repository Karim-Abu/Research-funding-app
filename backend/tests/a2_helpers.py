"""Shared setup for Milestone 9D A2 solution-innovation tests (fake provider only)."""
from __future__ import annotations

import hashlib
import json
import uuid

from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.db.models import (
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    PortalFieldDraft,
    RequirementAssessment,
)
from tests.a1_mapping_helpers import build_run

FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"
VC_FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
REQ_ID = "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"
# A suggestion body that preserves the mandatory 4.1-4.5 structure.
GOOD_TEXT = (
    "4.1 Stand der Technik: bestehende Verfahren.\n"
    "4.2 Neuheit: klare Abgrenzung.\n"
    "4.3 Ziele: messbar mit Baseline.\n"
    "4.4 Vorarbeiten: abgeschlossene Vorstudien.\n"
    "4.5 Partner: geeignete Infrastruktur."
)
# A VC suggestion body that preserves the registry mandatory 3.1/3.2 structure.
VC_GOOD_TEXT = (
    "3.1 Wertschöpfung: erwartete Wirkung, mit Belegen oder Platzhalter [Marktzahl fehlt].\n"
    "3.2 Geschäftsmodell und Markt: Zielkunden und Differenzierung; Wettbewerb [unklar]."
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_run_with_draft(
    db, *, draft_text: str = "4.1 ... 4.2 ... 4.3 ... 4.4 ... 4.5 ...",
    processing_mode: str = "cloud_assisted", sensitivity: str = "public",
    origin: str = "synthetic", nda: bool = False, workspace_id: str = "ws-demo",
    field_id: str = FIELD_ID, character_limit: int = 25000,
    field_name: str = "Innovation Solution",
):
    """Run + an A2-enabled draft (SOL by default, or VC) with a current version.
    Returns (run, draft, base_version_id)."""
    run, _frags, _sv = build_run(
        db, fragments=["Synthetic project context."], processing_mode=processing_mode,
        sensitivity=sensitivity, origin=origin, nda=nda, workspace_id=workspace_id,
    )
    draft_id = "draft-" + uuid.uuid4().hex[:8]
    version_id = "ver-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=version_id, draft_id=draft_id, text=draft_text,
        character_count=len(draft_text), created_by="template", content_hash=_hash(draft_text),
    ))
    db.add(PortalFieldDraft(
        draft_id=draft_id, run_id=run.run_id, workspace_id=run.workspace_id,
        field_id=field_id, field_name=field_name, status="draft",
        character_limit=character_limit, current_version_id=version_id, open_issue_count=0,
        template_catalog_version="tpl-1",
    ))
    db.flush()
    draft = db.get(PortalFieldDraft, draft_id)
    return run, draft, version_id


def add_verified_anchor(db, run, *, quote="Verified passage.") -> str:
    """Insert an exact_verified anchor + active link → a requirement assessment."""
    anchor_id = "anchor-" + uuid.uuid4().hex[:8]
    db.add(EvidenceAnchor(
        anchor_id=anchor_id, run_id=run.run_id, workspace_id=run.workspace_id,
        source_version_id="sv", source_id="src", source_name="Quelle.txt",
        source_type="txt", fragment_id="frag", quote=quote, quote_hash=_hash(quote),
        match_type="exact_normalized", normalizer_version="normalizer-1",
        verification_status="exact_verified",
    ))
    assessment_id = "assess-" + uuid.uuid4().hex[:8]
    db.add(RequirementAssessment(
        assessment_id=assessment_id, run_id=run.run_id, requirement_id=REQ_ID,
        requirement_version="1.0.0", status="met", basis="deterministic_rule",
        reasoning="test",
    ))
    db.add(EvidenceLink(
        evidence_link_id="link-" + uuid.uuid4().hex[:8], run_id=run.run_id,
        workspace_id=run.workspace_id, anchor_id=anchor_id,
        target_type="requirement_assessment", target_id=assessment_id, status="active",
    ))
    db.flush()
    return anchor_id


def fake_resolver(provider: FakeProvider):
    return lambda _route: provider


def bundle(*, suggested_text=GOOD_TEXT, evidence_anchor_ids=None, open_issue_ids=None,
           placeholders=None, rationale="Improved per evidence.", field_id=FIELD_ID) -> dict:
    return {
        "draft_candidates": [{
            "field_id": field_id, "suggested_text": suggested_text,
            "rationale": rationale, "evidence_anchor_ids": evidence_anchor_ids or [],
            "open_issue_ids": open_issue_ids or [],
        }],
        "placeholders": placeholders or [],
        "field_level_warnings": [],
    }


def success_fake(payload: dict, *, input_tokens=40, output_tokens=120) -> FakeProvider:
    return FakeProvider(
        raw_output=json.dumps(payload),
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
