"""evaluate_requirements_and_rules — deterministic precheck for one run.

Loads the versioned registry, builds engine inputs from the *frozen* project +
partner snapshot, runs every official core rule, persists one RuleResult per
rule, aggregates a RequirementAssessment per evaluable requirement, and creates
deduplicated OpenIssues for unmet/unresolved requirements. No LLM, no network,
no source text. Non-applicable rules are persisted as not_applicable RuleResults
and omitted from the user-facing assessments.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    OpenIssue,
    RequirementAssessment,
    RuleResult,
    RunProjectSnapshot,
)
from app.registry.loader import Registry, get_registry
from app.rules.aggregation import aggregate
from app.rules.engine import evaluate_rule
from app.rules.inputs import inputs_from_snapshot


def _clear_previous(db: Session, run_id: str) -> None:
    """Idempotent re-evaluation: drop any prior artifacts for this run."""
    for model in (OpenIssue, RequirementAssessment, RuleResult):
        for row in db.scalars(select(model).where(model.run_id == run_id)):
            db.delete(row)
    db.flush()


def evaluate_run(
    db: Session, run_id: str, *, registry: Registry | None = None
) -> dict[str, int]:
    """Run the deterministic prechecks for ``run_id``. Returns issue counts by
    severity. Caller owns the transaction (commit)."""
    registry = registry or get_registry()
    snapshot = db.get(RunProjectSnapshot, run_id)
    if snapshot is None:
        raise ValueError(f"No project snapshot for run {run_id}.")

    inputs = inputs_from_snapshot(
        profile_id=snapshot.project_json.get("funding_instrument_profile_id"),
        partner_dicts=list(snapshot.partners_json or []),
    )

    _clear_previous(db, run_id)

    counts = {"blocker": 0, "warning": 0, "info": 0}

    for requirement in registry.evaluable_requirements():
        rule = registry.rule_for(requirement)
        outcome = evaluate_rule(
            rule, inputs, rule_version=registry.rule_registry_version
        )

        # Persist the RuleResult (including not_applicable, for traceability).
        db.add(
            RuleResult(
                rule_result_id=str(uuid.uuid4()),
                run_id=run_id,
                requirement_id=requirement.requirement_id,
                rule_id=rule.rule_id,
                rule_version=registry.rule_registry_version,
                status=outcome.status,
                outcome_label=outcome.outcome_label,
                mapping_key=outcome.mapping_key,
                severity=outcome.severity,
                execution_mode=outcome.execution_mode,
                observed=outcome.observed,
                reason=outcome.reason,
            )
        )

        result = aggregate(requirement, outcome)
        if result is None:
            # Rule not applicable → no user-facing assessment, no issue.
            continue

        db.add(
            RequirementAssessment(
                assessment_id=str(uuid.uuid4()),
                run_id=run_id,
                requirement_id=requirement.requirement_id,
                requirement_version=requirement.version,
                title=requirement.title,
                status=result.status,
                basis=result.basis,
                reasoning=result.reasoning,
                stale=False,
            )
        )

        if result.issue is not None:
            counts[result.issue.severity] = counts.get(result.issue.severity, 0) + 1
            db.add(
                OpenIssue(
                    issue_id=str(uuid.uuid4()),
                    run_id=run_id,
                    issue_type=result.issue.issue_type,
                    severity=result.issue.severity,
                    description=result.issue.description,
                    target_type="requirement",
                    target_id=requirement.requirement_id,
                    recommended_next_action=result.issue.recommended_next_action,
                    status="open",
                )
            )

    db.flush()
    return counts
