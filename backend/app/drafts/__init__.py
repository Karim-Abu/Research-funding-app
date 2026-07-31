"""Deterministic template drafts (Milestone 6).

Scaffolding-only field templates (exact registry labels/questions + visible
placeholders), immutable versioned drafts, optimistic-concurrency edits and
draft-version evidence links. No LLM/agent/provider — purely deterministic.
"""
from app.drafts.charcount import char_count
from app.drafts.templates import (
    PLACEHOLDER_RE,
    PLACEHOLDER_VERSION,
    TEMPLATE_CATALOG_VERSION,
    build_template,
    has_placeholder,
    is_empty,
    is_placeholder_only,
)

__all__ = [
    "char_count",
    "PLACEHOLDER_RE",
    "PLACEHOLDER_VERSION",
    "TEMPLATE_CATALOG_VERSION",
    "build_template",
    "has_placeholder",
    "is_empty",
    "is_placeholder_only",
]
