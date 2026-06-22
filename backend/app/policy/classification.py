"""DataClassification resolution per Data_Policy_v1_1.yaml.

Effective classification:
  - sensitivity   = most restrictive of project + source (public<internal<confidential)
  - nda_applies   = project OR source (logical OR)
  - origin        = the source's *declared* origin (origins are NOT a security ladder)
  - processing/web_research_mode = the source's *requested* modes (evaluated by
    Data Policy at run time; no merge ranking)
Missing fields fall back to conservative defaults.
"""
from __future__ import annotations

_SENSITIVITY_ORDER = {"public": 0, "internal": 1, "confidential": 2}

_DEFAULTS = {
    "sensitivity": "confidential",
    "origin": "real_project",
    "processing_mode": "deterministic_only",
    "web_research_mode": "off",
    "nda_applies": True,
}


def _sensitivity_rank(value: str) -> int:
    return _SENSITIVITY_ORDER.get(value, _SENSITIVITY_ORDER["confidential"])


def resolve_effective_classification(
    project_dc: dict, source_dc: dict | None
) -> tuple[dict, bool]:
    """Return (effective_classification, downgrade_attempted)."""
    source = source_dc or {}
    project_sens = project_dc.get("sensitivity", _DEFAULTS["sensitivity"])
    source_sens = source.get("sensitivity", _DEFAULTS["sensitivity"])

    downgrade = _sensitivity_rank(source_sens) < _sensitivity_rank(project_sens)
    effective_sens = (
        source_sens
        if _sensitivity_rank(source_sens) >= _sensitivity_rank(project_sens)
        else project_sens
    )

    project_nda = bool(project_dc.get("nda_applies", False))
    source_nda = bool(source.get("nda_applies", False))
    if project_nda and not source_nda:
        downgrade = True
    effective_nda = project_nda or source_nda

    effective = {
        "sensitivity": effective_sens,
        "origin": source.get("origin", _DEFAULTS["origin"]),
        "processing_mode": source.get(
            "processing_mode", _DEFAULTS["processing_mode"]
        ),
        "web_research_mode": source.get(
            "web_research_mode", _DEFAULTS["web_research_mode"]
        ),
        "nda_applies": effective_nda,
    }
    return effective, downgrade
