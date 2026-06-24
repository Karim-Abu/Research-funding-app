"""Deterministic template catalogue (Milestone 6) — version ``template-drafts-1``.

Internal implementation configuration, NOT an official Innosuisse rule. Each
template is pure scaffolding built only from the registry's exact
``label_or_question`` text plus visible, machine-detectable placeholders. It
never produces prose, never translates, and invents no project facts, market
claims or technical novelty.
"""
from __future__ import annotations

import re

from app.registry.loader import PortalFieldDef, Registry

TEMPLATE_CATALOG_VERSION = "template-drafts-1"
PLACEHOLDER_VERSION = "placeholder-1"

# Visible, versioned, machine-detectable placeholder syntax: [[Angabe ergänzen: …]]
PLACEHOLDER_RE = re.compile(r"\[\[Angabe ergänzen:[^\]]*\]\]")


def placeholder(hint: str) -> str:
    return f"[[Angabe ergänzen: {hint}]]"


def has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text))


def is_empty(text: str) -> bool:
    return not text.strip()


def build_template(field: PortalFieldDef, registry: Registry) -> str:
    """Deterministic scaffolding for one supported field.

    - composite_editor: the registered Mandatory-Content main questions in
      registry order, each kept verbatim as a heading with a placeholder beneath.
    - narrative_text: a single placeholder hinted by the field's exact label.
    The project title is not available in the immutable run snapshot, so short
    fields stay placeholders (no invented or auto-translated content).
    """
    if field.field_kind == "composite_editor":
        questions = registry.mandatory_questions(field.field_id)
        if questions:
            blocks: list[str] = []
            for question in questions:
                blocks.append(question.label_or_question)
                blocks.append(placeholder("Antwort fachlich ergänzen"))
                blocks.append("")
            return "\n".join(blocks).strip()
    # Narrative single field (incl. the English application name — placeholder
    # only, never auto-translated).
    return placeholder(field.label_or_question)
