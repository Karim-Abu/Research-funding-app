"""The single owner of run/operation status transitions.

Routers and graph nodes must mutate status only through these functions. Invalid
transitions raise a contract-compatible Problem (409).
"""
from __future__ import annotations

from app.api.errors import ProblemException
from app.db.models import AnalysisRun, AsyncOperation

# Allowed RunStatus transitions (M3 + recovery). Terminal states are sinks.
RUN_TRANSITIONS: dict[str, set[str]] = {
    "created": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "stopped", "cancelled", "paused_for_review"},
    "paused_for_review": {"running", "cancelled", "completed", "failed"},
    "completed": set(),
    "stopped": set(),
    "failed": set(),
    "cancelled": set(),
}

OPERATION_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def transition_run(run: AnalysisRun, to_status: str) -> None:
    if to_status not in RUN_TRANSITIONS.get(run.status, set()):
        raise ProblemException(
            status=409,
            code="invalid_run_transition",
            title="Conflict",
            detail=f"Run cannot transition from {run.status} to {to_status}.",
        )
    run.status = to_status


def transition_operation(operation: AsyncOperation, to_status: str) -> None:
    if to_status not in OPERATION_TRANSITIONS.get(operation.status, set()):
        raise ProblemException(
            status=409,
            code="invalid_operation_transition",
            title="Conflict",
            detail=(
                f"Operation cannot transition from {operation.status} to "
                f"{to_status}."
            ),
        )
    operation.status = to_status
