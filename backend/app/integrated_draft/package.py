"""DraftPackage view for the integrated draft run (R5.9).

Pure in-memory dataclasses (no new DB model — DraftSuggestions persist via the existing A2
path). ``_classify_status`` maps an A2Outcome onto the ticket's FieldDraftItem status
vocabulary, reusing ``fields.reason_codes.maybe_reason`` exactly like the redraft executor
(availability blocks → "unavailable"; generation failures → "failed").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.fields.reason_codes import maybe_reason

FieldStatus = Literal[
    "generated", "deterministic", "missing_inputs", "skipped", "unavailable", "failed",
]


@dataclass
class FieldDraftItem:
    field_id: str
    field_label: str
    status: FieldStatus
    suggestion_text: str | None = None
    ai_proposal: dict | None = None
    missing_inputs: list[dict] = field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    usage_record_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    cost_status: str | None = None
    human_review_required: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass
class DraftPackage:
    package_id: str
    project_id: str
    case_id: str
    run_id: str
    created_at: str
    provider_mode: str
    data_mode: str
    fields: list[FieldDraftItem] = field(default_factory=list)
    usage_summary: dict = field(default_factory=dict)
    research_summary: dict = field(default_factory=dict)
    human_review_required: bool = True


def classify_status(a2_status: str, reason: str, *, has_missing_inputs: bool) -> tuple[FieldStatus, str | None]:
    """Map an A2Outcome (status, reason) onto a FieldDraftItem status.

    Returns ``(status, note)`` — ``note`` carries the availability reason text when the
    field is "unavailable", else None.
    """
    if a2_status in ("succeeded", "reused"):
        return ("missing_inputs" if has_missing_inputs else "generated"), None
    if a2_status == "skipped":
        return "skipped", None
    # blocked / failed / timed_out — split availability from generation failure.
    resolved = maybe_reason(reason)
    if resolved is not None:
        return "unavailable", resolved[1]
    return "failed", None
