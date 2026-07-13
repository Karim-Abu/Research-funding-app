"""EVAL.1 — Read-only Usage-/Cost-/Latenz-Aggregation für Evaluation-Reports.

Nur Lesen, keine Persistenz. Invarianten:
- Run-Aggregation filtert strikt ``run_id == :r`` — ``run_id IS NULL`` wird
  NIE unter einem Run aggregiert (M9I-A); Research-Usage ist separat pro
  ``research_task_id``.
- ``cost_chf`` wird NUR über ``cost_status='priced'`` summiert;
  unknown_price/not_applicable tragen nie zu Summen bei.
- Latenz stammt aus ``AgentInvocation.latency_ms`` (LLM) bzw.
  ``ToolInvocation.duration_ms`` (Web) — nie aus UsageRecord.
- Keine Rohinhalte: alle Resultate sind Zahlen, Status- und Profilnamen.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AgentInvocation, ToolInvocation, UsageRecord
from app.evaluation.pricing import COST_STATUS_PRICED

# Identisch zu research/cost_guard._COUNTED_STATUSES: Credits = gezählte
# ToolInvocation-Zeilen (native Einheit, keine spekulative CHF-Umrechnung).
_TOOL_COUNTED_STATUSES = ("queued", "running", "succeeded", "failed")


def run_usage_totals(db: Session, run_id: str) -> dict:
    """Token-/Kosten-Totale eines Runs (inkl. technischem Seed-Row)."""
    totals = db.execute(
        select(
            func.count(UsageRecord.usage_record_id),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
        ).where(UsageRecord.run_id == run_id)
    ).one()
    status_rows = db.execute(
        select(UsageRecord.cost_status, func.count())
        .where(UsageRecord.run_id == run_id)
        .group_by(UsageRecord.cost_status)
        .order_by(UsageRecord.cost_status)
    ).all()
    priced_sum = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_chf), 0.0)).where(
            UsageRecord.run_id == run_id,
            UsageRecord.cost_status == COST_STATUS_PRICED,
        )
    )
    return {
        "usage_record_count": int(totals[0]),
        "input_tokens": int(totals[1]),
        "output_tokens": int(totals[2]),
        "cost_status_counts": {row[0]: int(row[1]) for row in status_rows},
        "cost_chf_priced": round(float(priced_sum or 0.0), 6),
    }


def usage_by_agent_task(db: Session, run_id: str) -> list[dict]:
    """Pro agent_task (= profile_id): Invocations, Tokens, Latenz, Kostenstatus.

    Join AgentInvocation → UsageRecord über usage_record_id; Invocations ohne
    UsageRecord (blocked/failed) zählen mit 0 Tokens. Deterministische
    Sortierung nach profile_id.
    """
    rows = db.execute(
        select(
            AgentInvocation.profile_id,
            func.count(AgentInvocation.invocation_id),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            func.avg(AgentInvocation.latency_ms),
            func.max(AgentInvocation.latency_ms),
            func.coalesce(
                func.sum(UsageRecord.cost_chf).filter(
                    UsageRecord.cost_status == COST_STATUS_PRICED
                ),
                0.0,
            ),
        )
        .select_from(AgentInvocation)
        .outerjoin(
            UsageRecord,
            AgentInvocation.usage_record_id == UsageRecord.usage_record_id,
        )
        .where(AgentInvocation.run_id == run_id)
        .group_by(AgentInvocation.profile_id)
        .order_by(AgentInvocation.profile_id)
    ).all()
    result = []
    for row in rows:
        statuses = db.scalars(
            select(UsageRecord.cost_status)
            .distinct()
            .join(
                AgentInvocation,
                AgentInvocation.usage_record_id == UsageRecord.usage_record_id,
            )
            .where(
                AgentInvocation.run_id == run_id,
                AgentInvocation.profile_id == row[0],
            )
            .order_by(UsageRecord.cost_status)
        ).all()
        result.append(
            {
                "agent_task": row[0],
                "invocation_count": int(row[1]),
                "input_tokens": int(row[2]),
                "output_tokens": int(row[3]),
                "avg_latency_ms": (
                    round(float(row[4]), 1) if row[4] is not None else None
                ),
                "max_latency_ms": int(row[5]) if row[5] is not None else None,
                "cost_statuses": list(statuses),
                "cost_chf_priced": round(float(row[6] or 0.0), 6),
            }
        )
    return result


def tool_usage_by_research_task(db: Session, research_task_id: str) -> dict:
    """Web-/Research-Tool-Calls pro Task: Zeilen nach Status + Credits nativ."""
    rows = db.execute(
        select(
            ToolInvocation.tool_id,
            ToolInvocation.status,
            func.count(),
            func.avg(ToolInvocation.duration_ms),
        )
        .where(ToolInvocation.research_task_id == research_task_id)
        .group_by(ToolInvocation.tool_id, ToolInvocation.status)
        .order_by(ToolInvocation.tool_id, ToolInvocation.status)
    ).all()
    by_tool: dict[str, dict] = {}
    for tool_id, status, count, avg_ms in rows:
        entry = by_tool.setdefault(
            tool_id, {"rows_by_status": {}, "credits_native": 0}
        )
        entry["rows_by_status"][status] = int(count)
        if status in _TOOL_COUNTED_STATUSES:
            entry["credits_native"] += int(count)
        if avg_ms is not None:
            entry.setdefault("avg_duration_ms", round(float(avg_ms), 1))
    return {"research_task_id": research_task_id, "by_tool": by_tool}
