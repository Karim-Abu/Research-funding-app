"""Deterministic exact-quote verification (position-anchored, version-locked)."""
from __future__ import annotations

import uuid

from app.db.models import (
    AnalysisRun,
    EvidenceCandidate,
    RunProjectSnapshot,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.db.session import SessionLocal
from app.evidence.discovery import quote_hash
from app.evidence.verification import verify_candidate
from tests.conftest import DEMO_WS, VALID_CLASSIFICATION

PROFILE = "innosuisse_innovation_project_with_implementation_partner"


def _build(db, *, version_text, frag_text, frag_start=0, normalizer="normalizer-1",
           run_norm="normalizer-1", in_snapshot=True):
    project_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    sv_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=DEMO_WS,
        name="Quelle.txt", type="txt", status="processed",
        data_classification=VALID_CLASSIFICATION, created_by="user-anna",
    ))
    db.add(SourceVersion(
        source_version_id=sv_id, source_document_id=doc_id, version_number=1,
        original_content_hash="h", normalized_content_hash="h2",
        normalized_text=version_text, parser_version="parser-1",
        normalizer_version=normalizer, chunker_version="chunker-1",
        processing_status="processed", data_classification=VALID_CLASSIFICATION,
        storage_ref="a" * 32, original_filename="q.txt", byte_size=10,
        mime_type="text/plain",
    ))
    frag_id = str(uuid.uuid4())
    db.add(SourceFragment(
        fragment_id=frag_id, source_version_id=sv_id, ordinal=0,
        original_text=frag_text, normalized_text=frag_text,
        start_offset=frag_start, end_offset=frag_start + len(frag_text),
        content_hash="fh",
    ))
    db.add(AnalysisRun(
        run_id=run_id, project_id=project_id, workspace_id=DEMO_WS,
        created_by="user-anna", status="running", current_stage="verify_evidence",
        progress_percent=66, processing_mode="deterministic_only",
        effective_data_classification=VALID_CLASSIFICATION,
        snapshot_versions={"normalizer_version": run_norm},
        recheck_required=False, semantic_findings_stale=False,
    ))
    db.add(RunProjectSnapshot(
        run_id=run_id,
        project_id=project_id,
        project_json={
            "snapshot_schema_version": "run-project-v3",
            "primary_application_source_id": doc_id,
            "primary_application_source_version_id": sv_id,
            "primary_application_status": "configured",
        },
        partners_json=[],
        content_hash="scope-fixture",
        requirement_registry_version="1.0.0",
        rule_registry_version="1.1.0",
    ))
    if in_snapshot:
        db.add(RunSourceSnapshot(
            id=str(uuid.uuid4()), run_id=run_id, source_version_id=sv_id,
            source_id=doc_id,
        ))
    db.flush()
    run = db.get(AnalysisRun, run_id)
    frag = db.get(SourceFragment, frag_id)
    return run, sv_id, frag, doc_id


def _candidate(run, sv_id, frag, doc_id, *, quote, span_start, span_end,
               match_type="exact_normalized"):
    return EvidenceCandidate(
        candidate_id=str(uuid.uuid4()), run_id=run.run_id, workspace_id=DEMO_WS,
        target_type="requirement", target_requirement_id="REQ.X",
        fragment_id=frag.fragment_id, source_version_id=sv_id, source_id=doc_id,
        proposed_quote=quote, quote_hash=quote_hash(quote),
        span_start_in_fragment=span_start, span_end_in_fragment=span_end,
        match_type=match_type, retrieval_score=1.0, status="proposed",
        retrieval_algorithm_version="evidence-lexical-1",
    )


def test_exact_quote_becomes_exact_verified_with_offsets():
    db = SessionLocal()
    try:
        text = "Hallo Welt. Dies ist ein Test über Förderfähigkeit."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text)
        quote = "Dies ist ein Test über Förderfähigkeit."
        start = text.index(quote)
        cand = _candidate(run, sv_id, frag, doc_id, quote=quote,
                          span_start=start, span_end=start + len(quote))
        out = verify_candidate(db, run, cand)
        assert out.verification_status == "exact_verified"
        assert out.match_type == "exact_normalized"
        assert out.start_offset == start
        assert out.end_offset == start + len(quote)
    finally:
        db.rollback(); db.close()


def test_position_anchored_disambiguates_duplicate_quotes():
    db = SessionLocal()
    try:
        text = "Test. xyz. Test."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text)
        # "Test" occurs at 0 and 11. A candidate pointing at the SECOND occurrence
        # must verify at 11, not be globally matched to 0.
        cand = _candidate(run, sv_id, frag, doc_id, quote="Test",
                          span_start=11, span_end=15)
        out = verify_candidate(db, run, cand)
        assert out.verification_status == "exact_verified"
        assert (out.start_offset, out.end_offset) == (11, 15)
        # A candidate claiming "Test" at a position where the text is NOT "Test"
        # is unverified even though "Test" exists elsewhere (no global first-match).
        bad = _candidate(run, sv_id, frag, doc_id, quote="Test",
                         span_start=6, span_end=10)
        assert verify_candidate(db, run, bad).verification_status == "unverified"
    finally:
        db.rollback(); db.close()


def test_altered_quote_is_unverified():
    db = SessionLocal()
    try:
        text = "Die Förderfähigkeit ist gegeben."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text)
        cand = _candidate(run, sv_id, frag, doc_id, quote="Die Foerderfaehigkeit",
                          span_start=0, span_end=len("Die Foerderfaehigkeit"))
        assert verify_candidate(db, run, cand).verification_status == "unverified"
    finally:
        db.rollback(); db.close()


def test_foreign_source_version_rejected():
    db = SessionLocal()
    try:
        text = "Ein Satz."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text,
                                          in_snapshot=False)
        cand = _candidate(run, sv_id, frag, doc_id, quote="Ein Satz.",
                          span_start=0, span_end=len(text))
        assert verify_candidate(db, run, cand).verification_status == "rejected"
    finally:
        db.rollback(); db.close()


def test_normalizer_version_mismatch_rejected():
    db = SessionLocal()
    try:
        text = "Ein Satz."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text,
                                          normalizer="normalizer-1", run_norm="normalizer-2")
        cand = _candidate(run, sv_id, frag, doc_id, quote="Ein Satz.",
                          span_start=0, span_end=len(text))
        assert verify_candidate(db, run, cand).verification_status == "rejected"
    finally:
        db.rollback(); db.close()


def test_fuzzy_and_semantic_never_exact_verified():
    db = SessionLocal()
    try:
        text = "Exakter Treffer im Text."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text)
        for mt in ("fuzzy", "semantic", "manual"):
            cand = _candidate(run, sv_id, frag, doc_id, quote="Exakter Treffer",
                              span_start=0, span_end=len("Exakter Treffer"), match_type=mt)
            out = verify_candidate(db, run, cand)
            assert out.verification_status != "exact_verified"
    finally:
        db.rollback(); db.close()


def test_verification_never_produces_human_verified():
    db = SessionLocal()
    try:
        text = "Beliebiger Inhalt zur Prüfung."
        run, sv_id, frag, doc_id = _build(db, version_text=text, frag_text=text)
        for mt in ("exact_normalized", "fuzzy", "semantic", "manual"):
            cand = _candidate(run, sv_id, frag, doc_id, quote="Beliebiger",
                              span_start=0, span_end=10, match_type=mt)
            assert verify_candidate(db, run, cand).verification_status != "human_verified"
    finally:
        db.rollback(); db.close()
