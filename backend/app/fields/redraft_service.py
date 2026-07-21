"""createRedraft service + async executor (Milestone 9D; generalized in 9E).

Generates an advisory A2 suggestion for an A2-enabled field (SOL.INNOVATION_SOLUTION.
EDITOR / VC.BUSINESS_TARGETS_MODEL.EDITOR). Mirrors the M3 run-executor async pattern:
a queued AsyncOperation runs the A2 orchestrator in the background and stores the
suggestion in ``operation.result``. The endpoint pre-checks base-version currency (409)
and per-run availability (503) — it NEVER upgrades the run's processing mode.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.agents import field_drafting
from app.api.errors import ProblemException
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun, AsyncOperation, PortalFieldDraft
from app.db.session import SessionLocal
from app.fields import reason_codes
from app.repositories import audit
from app.runs.constants import TERMINAL_OPERATION_STATUSES
from app.runs.transitions import transition_operation

logger = logging.getLogger("app.fields.redraft")

# Sichere Detailgründe, die einen transienten Providerfehler anzeigen — nur
# dann darf die UI «Mit alternativem Modell versuchen» anbieten. Policy-Blocks,
# Budget-, Schema- und Refusal-Fehler bleiben ausgeschlossen.
_TRANSIENT_PROVIDER_REASONS = {
    "timeout",
    "provider_unavailable",
    "model_unavailable",
    "provider_outage",
    "provider_error",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def prepare_redraft(
    db,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    *,
    base_version_id: str,
    guidance: str | None,
    target_section: str | None,
    actor_user_id: str,
    idempotency_key: str | None,
    correlation_id: str | None,
) -> tuple[AsyncOperation, AsyncAccepted, str | None]:
    """Validate + queue. Returns (operation, accepted, guidance). Raises 409/503."""
    # Optimistic concurrency: the suggestion is for the *current* version.
    if draft.current_version_id != base_version_id:
        raise ProblemException(
            status=409, code="stale_base_version", title="Conflict",
            detail="Dieser Abschnitt wurde zwischenzeitlich geändert.",
        )
    available, reason = field_drafting.availability(run, draft.field_id)
    if not available:
        # R4.2: konkreter Grund statt Generiktext — code bleibt ai_unavailable,
        # reason_code + freigegebener deutscher Text kommen zusätzlich mit.
        reason_code, reason_text = reason_codes.to_reason(reason)
        raise ProblemException(
            status=503, code="ai_unavailable", title="Service Unavailable",
            detail=reason_text, reason_code=reason_code,
        )
    operation_id = str(uuid.uuid4())
    operation = AsyncOperation(
        operation_id=operation_id, workspace_id=run.workspace_id,
        project_id=run.project_id, resource_type="redraft", resource_id=draft.draft_id,
        status="queued", idempotency_key=idempotency_key, correlation_id=correlation_id,
    )
    db.add(operation)
    db.flush()
    accepted = AsyncAccepted(
        operation_id=operation_id, resource_type="redraft", resource_id=draft.draft_id,
        status="queued", poll_url=f"/api/v1/operations/{operation_id}",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="redraft.requested", target_type="portal_field_draft",
        target_id=draft.draft_id,
        detail={"field_id": draft.field_id, "target_section": target_section},
    )
    return operation, accepted, guidance


def execute_a2_operation(
    db,
    *,
    operation: AsyncOperation,
    run: AnalysisRun,
    draft_id: str,
    base_version_id: str,
    field_id: str,
    guidance: str | None = None,
    target_section: str | None = None,
    model_preference: str = "primary",
    improvement_mode: str = "clearer",
    selected_anchor_ids: list[str] | None = None,
    language: str | None = None,
    manifest_mode: bool = False,
):
    """Gemeinsamer A2-Kern für Redraft-Executor UND Run-Graph: Operation
    running → A2 → succeeded/failed inkl. result/error-Bookkeeping. Jede
    Suggestion hängt so an einer echten, erfolgreichen AsyncOperation — der
    bestehende Annahme-Pfad (updateField mit source_operation_id) greift
    unverändert. Committet selbst; gibt das A2Outcome zurück."""
    operation_id = operation.operation_id
    transition_operation(operation, "running")
    operation.started_at = _now()
    db.commit()

    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft_id, base_version_id=base_version_id,
        operation_id=operation_id, guidance=guidance,
        target_section=target_section, model_preference=model_preference,
        improvement_mode=improvement_mode,
        selected_anchor_ids=selected_anchor_ids or [], language=language,
        manifest_mode=manifest_mode,
    )

    op = db.get(AsyncOperation, operation_id)
    if op is None:
        return outcome
    if outcome.status in ("succeeded", "reused") and outcome.view is not None:
        transition_operation(op, "succeeded")
        op.result = outcome.view
        op.progress_percent = 100
    else:
        op.status = "failed"
        op.last_error_code = outcome.reason or "ai_unavailable"
        # R4.2: Verfügbarkeits-Skips (z. B. mode_deterministic_only) tragen
        # den Katalog-Reason; reine Generierungsfehler bleiben generisch.
        mapped = reason_codes.maybe_reason(outcome.reason or "")
        # Nur transiente Providerfehler auf der Primärroute dürfen den
        # expliziten Alternativ-Versuch anbieten — nie Policy/Budget/Schema/
        # Refusal, und nie nachdem die Alternative selbst versucht wurde.
        retry_alternative = (
            outcome.status in ("failed", "timed_out")
            and outcome.safe_detail in _TRANSIENT_PROVIDER_REASONS
            and model_preference == "primary"
        )
        # Volles Problem-Shape — der Operations-Lesecontract verlangt es
        # (die reduzierte Form machte fehlgeschlagene Redraft-Operationen
        # unlesbar).
        op.error = {
            "type": "/problems/redraft_failed",
            "title": "Redraft Error",
            "status": 503 if mapped else 500,
            "code": outcome.reason or "ai_unavailable",
            "detail": mapped[1] if mapped else "Es konnte kein Vorschlag erstellt werden.",
            "correlation_id": op.correlation_id or str(uuid.uuid4()),
            **({"reason_code": mapped[0]} if mapped else {}),
            **({"retry_with_alternative_model": True} if retry_alternative else {}),
        }
    op.finished_at = _now()
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action=f"operation.{op.status}", target_type="operation",
        target_id=operation_id,
    )
    db.commit()
    return outcome


def redraft_executor(
    operation_id: str, run_id: str, draft_id: str, base_version_id: str,
    guidance: str | None, field_id: str, target_section: str | None = None,
    model_preference: str = "primary",
    improvement_mode: str = "clearer",
    selected_anchor_ids: list[str] | None = None,
    language: str | None = None,
    manifest_mode: bool = False,
) -> None:
    """Background task: run A2 and store the suggestion in operation.result."""
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        run = db.get(AnalysisRun, run_id)
        if op is None or run is None or op.status in TERMINAL_OPERATION_STATUSES:
            return
        execute_a2_operation(
            db, operation=op, run=run, draft_id=draft_id,
            base_version_id=base_version_id, field_id=field_id, guidance=guidance,
            target_section=target_section, model_preference=model_preference,
            improvement_mode=improvement_mode,
            selected_anchor_ids=selected_anchor_ids or [], language=language,
            manifest_mode=manifest_mode,
        )
    except Exception:  # noqa: BLE001
        logger.exception("redraft execution failed")
        db.rollback()
        _mark_failed(operation_id)
    finally:
        db.close()


def _mark_failed(operation_id: str) -> None:
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = "REDRAFT_EXECUTION_FAILED"
            op.error = {
                "type": "/problems/redraft_failed",
                "title": "Redraft Error",
                "status": 500,
                "code": "REDRAFT_EXECUTION_FAILED",
                "detail": "Es konnte kein Vorschlag erstellt werden.",
                "correlation_id": op.correlation_id or str(uuid.uuid4()),
            }
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
