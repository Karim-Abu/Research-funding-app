"""Output-schema validation boundary (Milestone 9A)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.schemas import (
    SchemaNotImplementedError,
    fact_reference_violations,
    validate_payload,
)

_OK = {"facts": [], "conflicts": [], "missing_information": []}


def test_valid_empty_result():
    result = validate_payload("ProjectFactExtractionResult@v1", _OK)
    assert result.facts == []


def test_missing_required_field():
    with pytest.raises(ValidationError):
        validate_payload("ProjectFactExtractionResult@v1", {"facts": []})


def test_forbidden_extra_field():
    with pytest.raises(ValidationError):
        validate_payload("ProjectFactExtractionResult@v1", {**_OK, "extra": 1})


def test_fact_without_provenance_is_invalid():
    bad = {**_OK, "facts": [{"fact_id": "f", "statement": "x"}]}
    with pytest.raises(ValidationError):
        validate_payload("ProjectFactExtractionResult@v1", bad)


def test_invalid_enum_in_classification():
    bad = {
        "run_id": "r", "fragment_ids": [], "active_requirement_ids": [], "active_field_ids": [],
        "data_classification": {
            "sensitivity": "top-secret",  # not a valid enum value
            "origin": "synthetic", "processing_mode": "cloud_assisted",
        },
    }
    with pytest.raises(ValidationError):
        validate_payload("ProjectFactExtractionInput@v1", bad)


def test_unimplemented_schema_fails_safely():
    with pytest.raises(SchemaNotImplementedError):
        validate_payload("ReviewFindingBundle@v1", {})  # A3 model not implemented yet


def test_hallucinated_fragment_reference():
    result = validate_payload(
        "ProjectFactExtractionResult@v1",
        {**_OK, "facts": [{"fact_id": "f", "statement": "x", "source_fragment_ids": ["GHOST"]}]},
    )
    assert fact_reference_violations(result, {"frag-1"}) == ["GHOST"]
    assert fact_reference_violations(result, {"GHOST"}) == []
