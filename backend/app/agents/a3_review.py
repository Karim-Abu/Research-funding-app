"""A3 review scope (Milestone 9G).

The single source of truth for which profile and which fields the A3 evidence
consistency review covers. Fail-closed validated at import. A3 reviews — it never
drafts; the scoped fields are exactly the A2-enabled fields (highest evidence risk).
"""
from __future__ import annotations

from app.agents import a2_fields
from app.agents.registry import get_agent_registry
from app.registry import get_registry

A3_PROFILE_ID = "A3.evidence_consistency"
A3_SCOPE_FIELDS: tuple[str, ...] = (
    "SOL.INNOVATION_SOLUTION.EDITOR",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR",
)


def validate_a3_scope() -> None:
    """Fail-closed: the profile exists and every scoped field is a known,
    A2-enabled portal field."""
    get_agent_registry().profile(A3_PROFILE_ID)  # raises if unknown
    registry = get_registry()
    for field_id in A3_SCOPE_FIELDS:
        if field_id not in registry.portal_fields:
            raise RuntimeError(f"A3 scope field unknown in registry: {field_id}")
        if a2_fields.resolve_field_config(field_id) is None:
            raise RuntimeError(f"A3 scope field is not A2-enabled: {field_id}")


validate_a3_scope()
