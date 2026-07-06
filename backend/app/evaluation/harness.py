"""Minimal R0 evaluation harness skeleton.

This module is intentionally detached from DB sessions, settings, provider clients and
network access. It only proves that the evaluation package has a deterministic smoke
entrypoint for the repair roadmap.
"""
from __future__ import annotations


def run_r0_harness_smoke() -> dict[str, object]:
    """Return a deterministic fake/local smoke result for R0.

    Placeholder metrics are allowed to be ``None`` until later repair tickets define
    real evaluation logic and reviewed gold fixtures.
    """
    return {
        "ok": True,
        "harness": "r0",
        "provider_mode": "fake/local",
        "external_provider_calls": 0,
        "metrics": {
            "finding_precision": None,
            "finding_recall": None,
            "evidence_sufficiency_agreement": None,
            "import_field_mapping_accuracy": None,
            "copy_paste_readiness_rate": None,
            "manual_effort_reduction": None,
            "latency_seconds": None,
            "cost": None,
        },
    }
