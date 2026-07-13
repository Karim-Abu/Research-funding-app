"""Read-only Budget-Vorprüfung (run-unabhängig).

Reine Ableitung aus dem bestehenden Rule-Kern über die Live-Projekt- und
Partnerdaten: dieselben Handler, dieselben Schwellen aus der Registry-YAML
(``rule.condition``) — nichts wird persistiert, nichts doppelt hardcodiert.
Der Status ist bewusst ein EIGENES Vokabular (kein Requirement-Status):
``fulfilled`` (formal erfüllt) | ``review`` (Ausnahme geltend gemacht —
menschliche Prüfung) | ``blocker`` (formal verletzt, keine Ausnahme) |
``missing`` (Angabe fehlt / 0-Nenner — nie ein erfundenes Urteil).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

BudgetPrecheckStatus = Literal["fulfilled", "review", "blocker", "missing"]


class BudgetPrecheckFigures(BaseModel):
    """Abgeleitete Eckwerte; None = Angabe fehlt (kein 0-Ersatz)."""

    direct_costs_chf: float | None = None
    own_contribution_chf: float | None = None
    cash_contribution_chf: float | None = None
    requested_funding_chf: float | None = None
    # Umsetzungspartnerbeitrag = Eigenleistung + Barbeitrag (nur wenn beide
    # erfasst sind — Identität «Own + Cash = Beitrag»).
    implementation_contribution_chf: float | None = None
    implementation_share_percent: float | None = None
    cash_share_percent: float | None = None
    funding_share_percent: float | None = None
    exception_claimed: bool = False


class BudgetPrecheckCheck(BaseModel):
    rule_id: str
    requirement_id: str | None = None
    # Deutscher Anzeigetitel (Registry-Requirement) — UI zeigt nie rohe IDs.
    title: str
    status: BudgetPrecheckStatus
    reason: str
    observed: dict[str, Any]
    # Schwellen 1:1 aus der Registry (z. B. {"type": "range_percent",
    # "min": 40, "max": 60}) — die einzige Quelle der Wahrheit.
    condition: dict[str, Any]
    severity: str
    source_ref: str | None = None
    source_version: str | None = None
    last_checked: str | None = None
    rule_version: str


class BudgetPrecheck(BaseModel):
    figures: BudgetPrecheckFigures
    checks: list[BudgetPrecheckCheck]
