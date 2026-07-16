"""A2 field → profile activation map (Milestone 9E).

The single, explicit source of truth for which portal fields may request an A2
draft suggestion, and which agent profile serves each. There is **no** generic
"all A2 enabled" mechanism — every pair is listed here, backed by the registries,
and validated fail-closed at import:

- SOL.INNOVATION_SOLUTION.EDITOR              → A2.solution_innovation         (M9D)
- VC.BUSINESS_TARGETS_MODEL.EDITOR            → A2.value_creation_market_logic (M9E)
- INTRO.APP.ABSTRACT                          → A2.introduction_public_summary (R5.5)
- INTRO.APP.EXECUTIVE_SUMMARY                 → A2.introduction_public_summary (R5.5)
- ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS → A2.organisations_governance (R5.6)
- PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION     → A2.project_setup_workplan      (R5.6)

Character limit and the mandatory question structure are resolved from the portal
field registry (never hardcoded). Composite editor fields (``*.EDITOR``) carry
mandatory sub-questions; singleton narrative fields (Abstract, Executive Summary,
Financial-Independence comment, Management-hours explanation) legitimately have
none, so ``mandatory_markers`` may be empty for them.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.agents.registry import get_agent_registry
from app.agents.role_skills import RoleSkillRegistryError, get_role_skill_registry
from app.registry import get_registry

# Explicit allow-list (STEP 3). Adding a pair here is the only way to enable A2.
A2_FIELD_PROFILES: dict[str, str] = {
    "SOL.INNOVATION_SOLUTION.EDITOR": "A2.solution_innovation",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": "A2.value_creation_market_logic",
    "INTRO.APP.ABSTRACT": "A2.introduction_public_summary",
    "INTRO.APP.EXECUTIVE_SUMMARY": "A2.introduction_public_summary",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS": "A2.organisations_governance",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION": "A2.project_setup_workplan",
}

# Per-field deterministic fake output (dev/test only — settings.agent_fake_provider).
# Composite editor texts MUST contain the field's registry mandatory markers so the
# structural validation passes; singleton narrative fields (Abstract, Executive
# Summary) have none. All use explicit placeholders, never invented facts. The
# Abstract text must stay within its 300-char registry limit.
_FAKE_TEXTS: dict[str, str] = {
    "SOL.INNOVATION_SOLUTION.EDITOR": (
        "4.1 Stand der Technik: bestehende Verfahren und deren Grenzen.\n"
        "4.2 Neuheit: klare Abgrenzung gegenüber dem Stand der Technik.\n"
        "4.3 Ziele: messbare Ziele mit Baseline und Zielwert, wo belegbar.\n"
        "4.4 Vorarbeiten: abgeschlossene Vorstudien getrennt von geplanter Arbeit.\n"
        "4.5.1 Patentrecherche: Ergebnisse als [Platzhalter], keine erfundenen Treffer.\n"
        "4.5.2 Freedom-to-Operate: Analysestand als [Platzhalter] ohne Rechtsaussage.\n"
        "4.5.3 IP-Schutzstrategie: geplanter Schutzweg als [Platzhalter].\n"
        "4.5.4 Rechts- und Vertragslage: bestehende Vereinbarungen als [Platzhalter].\n"
        "4.6 Partner: geeignete Kompetenzen und Infrastruktur der Partner."
    ),
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": (
        "3.1 Wertschöpfung: erwartete wirtschaftliche und gesellschaftliche Wirkung, "
        "mit Belegen oder – wo Marktdaten fehlen – als Platzhalter markiert.\n"
        "3.2 Geschäftsmodell und Markt: Zielkunden, Markteintritt und Differenzierung; "
        "fehlende Markt-, Wettbewerbs- oder Umsatzzahlen bleiben explizite Platzhalter.\n"
        "3.3 Energie-/Umwelt-/Sozialwirkung: relevante Wirkungen als [Platzhalter], "
        "ohne erfundene Wirkungszahlen."
    ),
    "INTRO.APP.ABSTRACT": (
        "Öffentliche Kurzfassung des Vorhabens und seines Innovationsziels, allgemein "
        "und ohne vertrauliche Details oder Partnernamen. Wo belastbare Angaben fehlen, "
        "bleibt eine [Platzhalter]-Markierung statt erfundener Zahlen."
    ),
    "INTRO.APP.EXECUTIVE_SUMMARY": (
        "Ausführlichere Zusammenfassung des Projekts: Ausgangslage, Innovationsziel, "
        "geplanter Nutzen und Umsetzung, in allgemein verständlicher Sprache. Fehlende "
        "Baselines, Markt- oder Wirkungszahlen bleiben als [Platzhalter] markiert statt "
        "erfunden; konkrete KPIs werden nur mit Beleg genannt."
    ),
    # Vorsichtig, HITL-pflichtig: keine Bestätigung der Unabhängigkeit ohne Nachweis,
    # keine erfundenen Anteils-/Beteiligungswerte, fehlende Daten als [Platzhalter].
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS": (
        "Erläuterung zur finanziellen Unabhängigkeit der Partner gemäss den vorliegenden "
        "Angaben. Eigentums- und Beteiligungsverhältnisse sind noch zu belegen "
        "[Platzhalter]; ohne Nachweis wird die Unabhängigkeit nicht bestätigt. Eine "
        "abschliessende Prüfung ist vor der Einreichung erforderlich."
    ),
    # Keine erfundenen Stunden-/Prozentwerte; allgemeine Management-Tätigkeiten,
    # fehlende Verteilung als [Platzhalter].
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION": (
        "Die Management-Stunden umfassen allgemein Projektkoordination, Reporting, "
        "Review-Meetings, Projektsteuerung und Partnerabstimmung. Die konkrete Verteilung "
        "der Stunden auf diese Aufgaben ist noch zu ergänzen [Platzhalter]; ohne belegte "
        "Grundlage werden keine Stunden- oder Prozentwerte genannt."
    ),
}


@dataclass(frozen=True)
class A2FieldConfig:
    field_id: str
    profile_id: str
    char_limit: int
    mandatory_markers: tuple[str, ...]
    fake_text: str


def skill_id_for(field_id: str, target_section: str | None) -> str | None:
    """Resolve the sole versioned skill that may draft a field subsection."""
    try:
        return get_role_skill_registry().skill_for_a2(field_id, target_section).skill_id
    except RoleSkillRegistryError:
        return None


def _registry_markers(field_id: str) -> tuple[str, ...]:
    """Registry mandatory markers for a composite editor field, e.g.
    VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1 → "3.1" (SOL → 4.1–4.5)."""
    registry = get_registry()
    markers: list[str] = []
    for question in registry.mandatory_questions(field_id):
        suffix = question.field_id.rsplit("MANDATORY_", 1)[-1]
        markers.append(suffix.replace("_", "."))
    return tuple(markers)


@lru_cache(maxsize=None)
def resolve_field_config(field_id: str) -> A2FieldConfig | None:
    """Resolve the A2 config for an enabled field, or None if not A2-enabled."""
    profile_id = A2_FIELD_PROFILES.get(field_id)
    if profile_id is None:
        return None
    fdef = get_registry().portal_fields.get(field_id)
    if fdef is None or fdef.character_limit is None:
        return None
    markers = _registry_markers(field_id)
    # Composite editor fields (SOL/VC) must expose their mandatory sub-questions;
    # singleton narrative fields (Abstract/Exec Summary) legitimately have none.
    if field_id.endswith(".EDITOR") and not markers:
        return None
    return A2FieldConfig(
        field_id=field_id,
        profile_id=profile_id,
        char_limit=fdef.character_limit,
        mandatory_markers=markers,
        fake_text=_FAKE_TEXTS[field_id],
    )


def validate_a2_field_registry() -> None:
    """Fail-closed: every enabled pair must resolve against both registries."""
    agents = get_agent_registry()
    for field_id, profile_id in A2_FIELD_PROFILES.items():
        agents.profile(profile_id)  # raises AgentRegistryError if unknown
        config = resolve_field_config(field_id)
        if config is None:
            raise RuntimeError(
                f"A2 field/profile pair unresolved in registry: {field_id} → {profile_id}"
            )
        if field_id not in _FAKE_TEXTS:
            raise RuntimeError(f"A2 enabled field missing fake text: {field_id}")
        for target_section in config.mandatory_markers or (None,):
            if skill_id_for(field_id, target_section) is None:
                raise RuntimeError(
                    f"A2 field/section has no versioned skill: {field_id}/{target_section}"
                )


# Validate at import — fail-closed, like the registry loaders themselves.
validate_a2_field_registry()
