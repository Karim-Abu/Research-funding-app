"""Shared, user-visible generation provenance.

The distinction is deliberately based on the adapter that actually served a
request, never on a configured route.  A configured route without a call is
not model-generated output.
"""
from __future__ import annotations

from typing import Literal

GenerationKind = Literal["rule_template", "fake_demo", "model_generated"]

RULE_TEMPLATE: GenerationKind = "rule_template"
FAKE_DEMO: GenerationKind = "fake_demo"
MODEL_GENERATED: GenerationKind = "model_generated"


def for_adapter_name(adapter_name: str | None) -> GenerationKind | None:
    if adapter_name == "fake":
        return FAKE_DEMO
    if adapter_name in ("openai_direct", "anthropic_direct"):
        return MODEL_GENERATED
    return None


def is_real_model_call(adapter_name: str | None) -> bool:
    return for_adapter_name(adapter_name) == MODEL_GENERATED

