"""Privacy data classes D0–D3/UNKNOWN (Milestone 9J).

A **code-only, beta-internal** label derived from the finalized 5-field
``DataClassification`` — it does NOT change the contract schema. The labels give the
policy matrix and the Search Query Firewall a single, explicit axis to reason about.

Derivation (deny-by-default; reuses ``effective_sensitivity`` so a missing/garbage
sensitivity collapses to the most restrictive interpretation):

    nda_applies (or D3-equivalent)            -> D3_NDA_BLOCKED
    sensitivity == confidential               -> D2_CONFIDENTIAL_IDEA
    sensitivity == internal                   -> D1_INTERNAL
    sensitivity == public + public/synthetic  -> D0_PUBLIC
    anything ambiguous / unmappable           -> UNKNOWN  (blocked everywhere)

``UNKNOWN`` is deliberately distinct from ``D2``/``D3``: it marks *we cannot tell*, and
every tool decision for ``UNKNOWN`` is ``blocked``. ``D3`` marks *we can tell, and it is
NDA/legal-restricted*. Both are blocked from external tools, but the audit reason differs.
"""
from __future__ import annotations

from enum import StrEnum

# Origins that may use public web research directly when sensitivity is public.
_PUBLIC_ORIGINS = {"public_source", "synthetic"}
_KNOWN_SENSITIVITIES = {"public", "internal", "confidential"}


class DataClass(StrEnum):
    D0_PUBLIC = "D0_PUBLIC"
    D1_INTERNAL = "D1_INTERNAL"
    D2_CONFIDENTIAL_IDEA = "D2_CONFIDENTIAL_IDEA"
    D3_NDA_BLOCKED = "D3_NDA_BLOCKED"
    UNKNOWN = "UNKNOWN"


def derive_data_class(classification: dict | None) -> DataClass:
    """Map an *effective* DataClassification dict onto a privacy data class.

    Pure and deterministic. ``classification`` should already be the effective (merged,
    most-restrictive) classification; when callers only have raw project + source dicts
    they should resolve it first via ``resolve_effective_classification``.
    """
    cls = classification or {}
    raw_sensitivity = cls.get("sensitivity")

    # A present-but-unrecognized sensitivity value is UNKNOWN, not silently public.
    if raw_sensitivity is not None and raw_sensitivity not in _KNOWN_SENSITIVITIES:
        return DataClass.UNKNOWN

    # NDA wins over everything — legally restricted, never an external query.
    if bool(cls.get("nda_applies")):
        return DataClass.D3_NDA_BLOCKED

    # No sensitivity at all → we cannot tell (deny-by-default). Callers with a real
    # project pass a fully-populated classification; a resolved-effective classification
    # (resolve_effective_classification) always carries a concrete sensitivity, so a
    # genuinely-missing one only reaches here when nothing is known.
    if raw_sensitivity is None:
        return DataClass.UNKNOWN

    if raw_sensitivity == "confidential":
        return DataClass.D2_CONFIDENTIAL_IDEA
    if raw_sensitivity == "internal":
        return DataClass.D1_INTERNAL
    # raw_sensitivity == "public"
    if cls.get("origin") in _PUBLIC_ORIGINS:
        return DataClass.D0_PUBLIC
    # public sensitivity but a non-public origin (e.g. real_project/anonymized) is
    # ambiguous for external use — treat as UNKNOWN (blocked), not D0.
    return DataClass.UNKNOWN


def is_external_blocked(data_class: DataClass) -> bool:
    """D3/UNKNOWN never reach any external tool, regardless of the firewall."""
    return data_class in (DataClass.D3_NDA_BLOCKED, DataClass.UNKNOWN)
