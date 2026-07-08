"""EvaluationRunSummary builder (Milestone 10, STEP 9).

Deterministic per-run evaluation metrics for M10/thesis reporting: aggregates dataset,
evidence, review and reliability counts for one completed run. Costs are never invented —
`estimated_cost` is an explicit placeholder. Reproducible for a fixed run + `generated_at`.

EVAL.1 (additiv, Schema unverändert `evaluation-run-summary-1`): neue Keys
``data_mode`` (abgeleitetes Label, kein Enforcement) und ``usage``
(Token-/Kostenstatus-Aggregat aus UsageRecords; ``cost_chf_priced`` summiert
nur ``cost_status='priced'``). ``estimated_cost`` bleibt bewusst der alte
Platzhalter — es existieren weiterhin keine Realpreise.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    EvidenceAnchor,
    ExportArtifact,
    MarketComparison,
    PortalFieldDraft,
    RequirementAssessment,
    ResearchTask,
    ReviewFinding,
    RunQualitySummary,
    SourceDocument,
)
from app.evaluation import SUMMARY_SCHEMA
from app.evaluation.data_mode import derive_data_mode
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.usage import run_usage_totals


def _count(db: Session, model_col, *where) -> int:
    return int(db.scalar(select(func.count()).select_from(model_col).where(*where)) or 0)


def build_evaluation_summary(
    db: Session, run: AnalysisRun, *, dataset_id: str | None = None,
    generated_at: str | None = None,
) -> dict:
    settings = get_settings()
    quality = db.scalar(
        select(RunQualitySummary)
        .where(RunQualitySummary.run_id == run.run_id)
        .order_by(RunQualitySummary.generated_at.desc())
    )
    anchors = _count(db, EvidenceAnchor, EvidenceAnchor.run_id == run.run_id)
    exact = _count(
        db, EvidenceAnchor, EvidenceAnchor.run_id == run.run_id,
        EvidenceAnchor.verification_status == "exact_verified",
    )
    web_used = _count(db, ResearchTask, ResearchTask.project_id == run.project_id) > 0
    market_used = _count(db, MarketComparison, MarketComparison.project_id == run.project_id) > 0

    return {
        "schema": SUMMARY_SCHEMA,
        "run_id": run.run_id,
        "dataset_id": dataset_id or run.project_id,
        "timestamp": generated_at or datetime.now(timezone.utc).isoformat(),
        "provider_mode": run.processing_mode,
        "data_mode": derive_data_mode(
            ai_eval_mode=settings.ai_eval_mode,
            origin=(run.effective_data_classification or {}).get("origin"),
        ),
        "fake_provider_used": bool(
            settings.agent_fake_provider or settings.web_research_fake_provider
        ),
        "web_research_used": web_used,
        "market_comparison_used": market_used,
        "source_count": _count(
            db, SourceDocument, SourceDocument.project_id == run.project_id
        ),
        "requirement_count": _count(
            db, RequirementAssessment, RequirementAssessment.run_id == run.run_id
        ),
        "draft_field_count": _count(
            db, PortalFieldDraft, PortalFieldDraft.run_id == run.run_id
        ),
        "evidence_anchor_count": anchors,
        "exact_verified_anchor_count": exact,
        "review_finding_count": _count(
            db, ReviewFinding, ReviewFinding.run_id == run.run_id,
            ReviewFinding.status == "open",
        ),
        "export_artifacts_created": _count(
            db, ExportArtifact, ExportArtifact.run_id == run.run_id
        ),
        "reliability_claim_count": quality.claim_count if quality else 0,
        "supported_claims": quality.supported_claims if quality else 0,
        "weakly_supported_claims": quality.weakly_supported_claims if quality else 0,
        "unsupported_claims": quality.unsupported_claims if quality else 0,
        "conflicting_claims": quality.conflicting_claims if quality else 0,
        "evidence_coverage": quality.evidence_coverage if quality else 0.0,
        "evidence_sufficiency_pass_rate": (
            quality.evidence_correctness_sample_pass_rate if quality else 0.0
        ),
        "blocker_count": quality.blocker_count if quality else 0,
        "warning_count": quality.warning_count if quality else 0,
        "reliability_quality_flag": quality.quality_flag if quality else None,
        "total_runtime_seconds": quality.latency_seconds if quality else None,
        "usage": {
            **run_usage_totals(db, run.run_id),
            "price_table_version": PRICE_TABLE_VERSION,
        },
        "estimated_cost": {
            "value_chf": None,
            "placeholder": True,
            "note": "Cost is not measured deterministically in the beta; no CHF invented.",
        },
    }


def render_markdown(summary: dict) -> str:
    lines = [
        "# EvaluationRunSummary",
        "",
        f"*Schema:* `{summary['schema']}` · *Generated:* {summary['timestamp']}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    order = [
        "run_id", "dataset_id", "provider_mode", "data_mode",
        "fake_provider_used",
        "web_research_used", "market_comparison_used", "source_count",
        "requirement_count", "draft_field_count", "evidence_anchor_count",
        "exact_verified_anchor_count", "review_finding_count",
        "export_artifacts_created", "reliability_claim_count", "supported_claims",
        "weakly_supported_claims", "unsupported_claims", "conflicting_claims",
        "evidence_coverage", "evidence_sufficiency_pass_rate", "blocker_count",
        "warning_count", "reliability_quality_flag", "total_runtime_seconds",
    ]
    for key in order:
        lines.append(f"| {key} | {summary.get(key)} |")
    usage = summary.get("usage") or {}
    for key in (
        "usage_record_count", "input_tokens", "output_tokens",
        "cost_status_counts", "cost_chf_priced", "price_table_version",
    ):
        lines.append(f"| usage.{key} | {usage.get(key)} |")
    cost = summary["estimated_cost"]
    lines.append(f"| estimated_cost | placeholder ({cost['note']}) |")
    lines.append("")
    lines.append(
        "> Coverage (any linked evidence) is kept separate from sufficiency "
        "(does the evidence support the claim under defined criteria). High coverage "
        "with low sufficiency is **risky**, not success."
    )
    return "\n".join(lines) + "\n"


def to_json(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
