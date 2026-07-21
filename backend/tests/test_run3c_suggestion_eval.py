from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.suggestion_grounding import validate_grounding


DATASET = (
    Path(__file__).resolve().parents[2]
    / "docs" / "evaluation" / "cases" / "run3c_suggestion_eval_v1.json"
)
CASES = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]


def test_eval_set_is_versioned_synthetic_and_has_minimum_case_count():
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "Run3CSuggestionEval@v1"
    assert payload["data_classification"] == "F1_synthetic"
    assert len(payload["cases"]) >= 14
    assert len({case["case_id"] for case in payload["cases"]}) == len(payload["cases"])


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_independent_claim_extraction_eval(case):
    result = validate_grounding(
        case["suggestion_text"],
        original_text=case["original_text"],
        structured_project_data=case["structured_project_data"],
        anchors=case["anchors"],
    )
    claim_types = {claim.claim_type for claim in result.claims}
    assert claim_types == set(case["expected_claim_types"])
    unsupported = {claim.value for claim in result.unsupported_critical}
    assert unsupported == set(case["expected_unsupported_values"])
