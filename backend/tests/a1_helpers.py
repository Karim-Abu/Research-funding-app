"""Shared setup for Milestone 9B A1 fact-extraction tests (fake provider only)."""
from __future__ import annotations

import json
import uuid

from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.db.models import (
    AnalysisRun,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)

DEMO_WS = "ws-demo"

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
    """Build a run with a frozen snapshot of N fragments. Returns (run, fragment_ids,
    source_version_id)."""
    fragments = fragments or ["Synthetic project fragment about the consortium."]
    cls = _classification(sensitivity, origin, processing_mode, nda)
    project_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    sv_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=workspace_id,
        name="Projektbeschreibung.txt", type="txt", status="processed",
        data_classification=cls, created_by="user-anna",
    ))
    db.add(SourceVersion(
        source_version_id=sv_id, source_document_id=doc_id, version_number=1,
        original_content_hash="h", normalized_content_hash="h2",
        normalized_text="\n".join(fragments), parser_version="parser-1",
        normalizer_version="normalizer-1", chunker_version="chunker-1",
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
        snapshot_versions={"normalizer_version": "normalizer-1"},
        recheck_required=False, semantic_findings_stale=False,
    ))
    if in_snapshot:
        db.add(RunSourceSnapshot(
            id=str(uuid.uuid4()), run_id=run_id, source_version_id=sv_id,
            source_id=doc_id,
        ))
    db.flush()
    return db.get(AnalysisRun, run_id), fragment_ids, sv_id


def fake_resolver(provider: FakeProvider):
    return lambda _route: provider


def result_payload(*, facts=None, conflicts=None, missing=None) -> dict:
    return {
        "facts": facts or [],
        "conflicts": conflicts or [],
        "missing_information": missing or [],
    }


def fact(fact_id: str, fragment_ids: list[str], *, statement="A fact.",
         fact_type="project_fact", normalized_value=None, target_ref=None) -> dict:
    return {
        "fact_id": fact_id, "statement": statement, "fact_type": fact_type,
        "normalized_value": normalized_value, "target_ref": target_ref,
        "source_fragment_ids": fragment_ids,
    }


def success_fake(payload: dict, *, input_tokens=12, output_tokens=20) -> FakeProvider:
    return FakeProvider(
        raw_output=json.dumps(payload),
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
