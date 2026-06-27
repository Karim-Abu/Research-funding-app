"""Shared setup for Milestone 9C A1 evidence-mapping tests (fake provider only).

Builds runs whose fragment offsets are exact substrings of the version text, so the
deterministic verifier (`verify_evidence_quote`) can confirm agent quotes.
"""
from __future__ import annotations

import json
import uuid

from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.db.models import (
    AnalysisRun,
    ExtractedFact,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)

DEMO_WS = "ws-demo"
NORMALIZER = "normalizer-1"
# A real evaluable requirement id and an A1 portal field id (from the registry).
REQ_ID = "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"
FIELD_ID = "INTRO.APP.NAME"


def _classification(sensitivity: str, origin: str, mode: str, nda: bool) -> dict:
    return {
        "sensitivity": sensitivity, "origin": origin, "processing_mode": mode,
        "web_research_mode": "off", "nda_applies": nda,
    }


def build_run(
    db,
    *,
    fragments: list[str] | None = None,
    processing_mode: str = "cloud_assisted",
    sensitivity: str = "public",
    origin: str = "synthetic",
    nda: bool = False,
    workspace_id: str = DEMO_WS,
    in_snapshot: bool = True,
) -> tuple[AnalysisRun, list[str], str]:
    """Run with a frozen snapshot; fragments are contiguous spans of the version text
    (start_offset exact) so quote verification works. Returns (run, fragment_ids, sv_id)."""
    fragments = fragments or ["The Swiss implementation partner is based in Zurich."]
    cls = _classification(sensitivity, origin, processing_mode, nda)
    project_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    sv_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    version_text = "".join(fragments)  # contiguous: frag offset == position in version
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=workspace_id,
        name="Projektbeschreibung.txt", type="txt", status="processed",
        data_classification=cls, created_by="user-anna",
    ))
    db.add(SourceVersion(
        source_version_id=sv_id, source_document_id=doc_id, version_number=1,
        original_content_hash="h", normalized_content_hash="h2",
        normalized_text=version_text, parser_version="parser-1",
        normalizer_version=NORMALIZER, chunker_version="chunker-1",
        processing_status="processed", data_classification=cls,
        storage_ref="a" * 32, original_filename="p.txt", byte_size=10,
        mime_type="text/plain",
    ))
    fragment_ids: list[str] = []
    offset = 0
    for ordinal, text in enumerate(fragments):
        fid = str(uuid.uuid4())
        fragment_ids.append(fid)
        db.add(SourceFragment(
            fragment_id=fid, source_version_id=sv_id, ordinal=ordinal,
            original_text=text, normalized_text=text,
            start_offset=offset, end_offset=offset + len(text), content_hash="fh",
        ))
        offset += len(text)
    db.add(AnalysisRun(
        run_id=run_id, project_id=project_id, workspace_id=workspace_id,
        created_by="user-anna", status="running",
        current_stage="extract_facts_and_map_evidence", progress_percent=27,
        processing_mode=processing_mode, effective_data_classification=cls,
        snapshot_versions={"normalizer_version": NORMALIZER},
        recheck_required=False, semantic_findings_stale=False,
    ))
    if in_snapshot:
        db.add(RunSourceSnapshot(
            id=str(uuid.uuid4()), run_id=run_id, source_version_id=sv_id, source_id=doc_id,
        ))
    db.flush()
    return db.get(AnalysisRun, run_id), fragment_ids, sv_id


def add_fact(db, run, *, statement="A proposed fact.", status="proposed") -> str:
    fact_id = str(uuid.uuid4())
    db.add(ExtractedFact(
        fact_id=fact_id, run_id=run.run_id, workspace_id=run.workspace_id,
        fact_type="project_fact", normalized_value=None, original_statement=statement,
        status=status, source_fragment_ids=[], source_version_ids=[],
        profile_id="A1.project_fact_extraction", fact_fingerprint=fact_id,
    ))
    db.flush()
    return fact_id


def fake_resolver(provider: FakeProvider):
    return lambda _route: provider


def mapping_result(*, candidates=None, unmapped=None, conflicts=None) -> dict:
    return {
        "candidates": candidates or [],
        "unmapped_targets": unmapped or [],
        "conflicts": conflicts or [],
    }


def candidate(
    fragment_id: str, quote: str, *, target_id: str = REQ_ID,
    target_type: str = "requirement", match_type: str = "exact_normalized",
    extracted_fact_id: str | None = None,
) -> dict:
    return {
        "fragment_id": fragment_id, "quote": quote, "target_type": target_type,
        "target_id": target_id, "match_rationale": "supports target",
        "extracted_fact_id": extracted_fact_id, "match_type": match_type,
    }


def success_fake(payload: dict, *, input_tokens=12, output_tokens=20) -> FakeProvider:
    return FakeProvider(
        raw_output=json.dumps(payload),
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
