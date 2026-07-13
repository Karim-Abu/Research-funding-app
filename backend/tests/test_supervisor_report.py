"""EVAL.4 — hermetische Tests für den Supervisor Evaluation Report.

Kein Netz, keine DB, kein Provider-Call: ``render_supervisor_report`` ist eine reine
Funktion über fabrizierte Results-Dicts (dieselbe Envelope-Form wie R5.9-REAL). Prüft
OpenAI-only/Anthropic-only-Rendering, ein fehlgeschlagenes Feld, die unknown_price-Erklärung
und den No-Raw-/No-Secret-Canary.
"""
from __future__ import annotations

from app.agents import a2_fields
from app.evaluation.supervisor_report import render_supervisor_report
from app.registry.loader import get_registry

CANARY_TEXT = "EVAL4_CANARY_ROHTEXT_3K"
SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"


def _field_row(field_id: str, status: str, *, provider: str | None = None) -> dict:
    return {
        "field_id": field_id, "field_label": field_id, "status": status,
        "provider": provider, "model": "model-x" if provider else None,
        "input_tokens": 10 if provider else None,
        "output_tokens": 20 if provider else None,
        "total_tokens": 30 if provider else None,
        "latency_ms": 100 if provider else None,
        "cost_status": "unknown_price" if provider else None,
        "usage_record_id": "usg-1" if provider else None,
        "missing_inputs_count": 1 if status == "missing_inputs" else 0,
        "human_review_required": True,
        "suggestion_preview": "Öffentliche Kurzfassung (Vorschau, kein Rohtext).",
    }


def _full_envelope(provider: str, *, sol_status: str = "generated") -> dict:
    fields = []
    for field in get_registry().m6_draft_fields():
        config = a2_fields.resolve_field_config(field.field_id)
        if config is None:
            fields.append(_field_row(field.field_id, "deterministic"))
        elif field.field_id == SOL_FIELD:
            fields.append(_field_row(field.field_id, sol_status, provider=provider))
        else:
            fields.append(_field_row(field.field_id, "missing_inputs", provider=provider))
    return {
        "report": {
            "provider": provider, "case_id": "F1", "project_id": "p1", "run_id": "r1",
            "created_at": "2026-07-10T00:00:00+00:00", "data_mode": "synthetic_eval",
            "price_table_version": "x", "fields": fields,
            "usage_summary": {
                "input_tokens": 60, "output_tokens": 120, "total_tokens": 180,
                "usage_record_count": 6, "cost_status_counts": {"unknown_price": 6},
            },
            "research_summary": {
                "market": {"used": True, "candidates": 1, "imported_sources": 0},
                "partner": {"used": True, "candidates": 1, "imported_sources": 0},
            },
            "human_review_required": True,
        },
        "artifact": {"fields": [{
            "field_id": SOL_FIELD, "suggestion_text": CANARY_TEXT,
            "ai_proposal": {"raw": CANARY_TEXT}, "raw_outputs": [CANARY_TEXT],
        }]},
    }


def test_openai_only_renders_all_sections():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai")}, generated_at="2026-07-10"
    )
    for heading in (
        "1. Executive Summary", "2. Agent/Task Routing", "3. Integrated Draft Result",
        "4. Token & Cost Summary", "5. Research Summary", "6. Quality Assessment Table",
        "7. Safety/Governance", "8. Limitations",
    ):
        assert heading in report
    assert "openai" in report
    assert "anthropic" not in report.split("## 3. Integrated Draft Result")[1].split(
        "## 4."
    )[0]
    assert SOL_FIELD in report


def test_anthropic_only_renders_all_sections():
    report = render_supervisor_report(
        {"anthropic": _full_envelope("anthropic")}, generated_at="2026-07-10"
    )
    assert "### Provider: anthropic" in report
    assert "### Provider: openai" not in report


def test_report_handles_a_failed_field():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai", sol_status="failed")}, generated_at="2026-07-10"
    )
    section = report.split("## 3. Integrated Draft Result")[1].split("## 4.")[0]
    assert f"| {SOL_FIELD} | failed |" in section


def test_unknown_price_explained_never_priced_or_free():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai")}, generated_at="2026-07-10"
    )
    section = report.split("## 4. Token & Cost Summary")[1].split("## 5.")[0]
    assert "unknown_price" in section
    assert "niemals" in section.lower() or "nie" in section.lower()
    assert "0 CHF/gratis" in section or "gratis" in section.lower()
    # Never claims a priced amount when only unknown_price occurred.
    assert "cost_status counts: unknown_price=6" in section


def test_no_canary_in_report():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai")}, generated_at="2026-07-10"
    )
    assert CANARY_TEXT not in report


def test_quality_table_is_placeholder_only_never_scored():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai")}, generated_at="2026-07-10"
    )
    section = report.split("## 6. Quality Assessment Table")[1].split("## 7.")[0]
    assert f"| {SOL_FIELD} | TODO | TODO | TODO | TODO | TODO | TODO |" in section


def test_no_prompt_or_key_leakage():
    report = render_supervisor_report(
        {"openai": _full_envelope("openai"), "anthropic": _full_envelope("anthropic")},
        generated_at="2026-07-10",
    )
    assert "api_key" not in report.lower()
    assert "system prompt" not in report.lower()
    assert "BEGIN UNTRUSTED" not in report
