"""R4.3 — ProviderPolicy: maschinell durchgesetzte Provider×Datenklassen-Matrix.

Owner-Entscheide (E-02 bestätigt 2026-07-08; Opt-in-Entscheid 2026-07-08,
docs/repair/decision-log-needed.md, docs/repair/data-class-mapping.md §3/§3.1):

- fake/local bleibt Default für Tests und Demo.
- D1/D2-KI läuft nur über den LOKALEN Pfad (heute Fake-Provider, Ziel Azure
  Enterprise Boundary) und nur nach manuellem Opt-in + Warnung — die
  Bestätigung erzwingt ``data_policy`` über ``run_confirmation``.
- Direkte Consumer-APIs (OpenAI/Anthropic) sind für echte D1/D2-Daten
  (origin ``real_project``) blockiert — unabhängig von gesetzten API-Keys
  (Contract DP-04). Synthetische/anonymisierte Evaluationsfälle (F1 synthetic)
  nur mit ``AI_EVAL_MODE=real``.
- Azure ist dokumentierter Zielpfad, nicht aktiv (Contract: azure_foundry
  ``allowed_sensitivity: []``) — jeder Azure-Eintrag bleibt blockiert, bis ein
  separater Slice den Adapter + institutionelle Freigabe bringt.
- D3/UNKNOWN sind für JEDEN Provider blockiert — auch für den Fake.

Fail-closed: unbekannte Adapter, Klassen oder fehlende Tabelleneinträge ⇒
blocked. Diese Schicht wirkt zusätzlich (UND) zu ``data_policy`` und
``policy_matrix`` — sie kann bestehende Gates nie lockern.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.config.settings import Settings
from app.security.data_class import DataClass, derive_data_class


class ProviderKind(StrEnum):
    FAKE_LOCAL = "fake_local"
    AZURE = "azure"
    DIRECT_OPENAI = "direct_openai"
    DIRECT_ANTHROPIC = "direct_anthropic"


# Adapter-Selbstauskunft (``adapter.name``) → Policy-Kind. Unbekannt ⇒ blocked.
_ADAPTER_NAME_TO_KIND: dict[str, ProviderKind] = {
    "fake": ProviderKind.FAKE_LOCAL,
    "openai_direct": ProviderKind.DIRECT_OPENAI,
    "anthropic_direct": ProviderKind.DIRECT_ANTHROPIC,
    "azure_foundry": ProviderKind.AZURE,
}

_DIRECT = (ProviderKind.DIRECT_OPENAI, ProviderKind.DIRECT_ANTHROPIC)
_EVAL_ORIGINS = ("synthetic", "anonymized")

BLOCKED_REASON = "provider_blocked_for_data_class"


@dataclass(frozen=True)
class ProviderDecision:
    allowed: bool
    reason: str
    # Vertrags-/Betriebsbasis als Textreferenz (Doku/Audit, nie Nutzertext).
    required_basis: str


# Statische Erlaubnis-Einträge (kind × class) → Basis. Alles Fehlende ist
# blocked; direkte APIs für D1/D2 werden origin-/eval-abhängig unten behandelt.
_ALLOWED: dict[tuple[ProviderKind, DataClass], str] = {
    (ProviderKind.FAKE_LOCAL, DataClass.D0_PUBLIC):
        "lokal-deterministischer Fake-Provider, keine externen Calls (Tests/Demo)",
    (ProviderKind.FAKE_LOCAL, DataClass.D1_INTERNAL):
        "lokaler Pfad; manuelles Opt-in + Warnung (Owner-Entscheid 2026-07-08)",
    (ProviderKind.FAKE_LOCAL, DataClass.D2_CONFIDENTIAL_IDEA):
        "lokaler Pfad; manuelles Opt-in + Warnung (Owner-Entscheid 2026-07-08)",
    (ProviderKind.DIRECT_OPENAI, DataClass.D0_PUBLIC):
        "nur öffentliche/synthetische Beta-Daten (E-02) + M9D.2-Bestätigung",
    (ProviderKind.DIRECT_ANTHROPIC, DataClass.D0_PUBLIC):
        "nur öffentliche/synthetische Beta-Daten (E-02) + M9D.2-Bestätigung",
}


def kind_of_adapter(adapter: object) -> ProviderKind | None:
    """Policy-Kind eines Provider-Adapters (``adapter.name``); None = unbekannt."""
    return _ADAPTER_NAME_TO_KIND.get(getattr(adapter, "name", ""))


def decide(
    kind: ProviderKind | None,
    classification: dict | None,
    settings: Settings,
) -> ProviderDecision:
    """Policy-Entscheid provider × data_class (× origin/eval-Modus). Fail-closed."""
    if kind is None:
        return ProviderDecision(False, "provider_unknown_adapter",
                                "kein Tabelleneintrag — fail-closed")
    data_class = derive_data_class(classification)
    if data_class in (DataClass.D3_NDA_BLOCKED, DataClass.UNKNOWN):
        return ProviderDecision(False, BLOCKED_REASON,
                                "D3/Unknown: immer blockiert, auch Fake (GO-Auflage 2)")
    basis = _ALLOWED.get((kind, data_class))
    if basis is not None:
        return ProviderDecision(True, "provider_allowed", basis)
    if kind in _DIRECT and data_class in (
        DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA
    ):
        origin = (classification or {}).get("origin")
        if origin in _EVAL_ORIGINS and settings.ai_eval_mode == "real":
            return ProviderDecision(
                True, "provider_allowed_eval",
                "synthetische/anonymisierte Evaluation (F1 synthetic); "
                "AI_EVAL_MODE=real = dokumentierte Owner-Freigabe (§3.1)",
            )
        return ProviderDecision(
            False, BLOCKED_REASON,
            "direkte Consumer-API für echte D1/D2-Daten blockiert (E-02, DP-04) "
            "— unabhängig von gesetzten API-Keys",
        )
    return ProviderDecision(False, BLOCKED_REASON,
                            "kein Tabelleneintrag — fail-closed")


def decide_for_adapter(
    adapter: object, classification: dict | None, settings: Settings
) -> ProviderDecision:
    return decide(kind_of_adapter(adapter), classification, settings)
