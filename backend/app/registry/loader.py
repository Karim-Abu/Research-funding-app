"""Load + validate the requirement and rule registries (fail-closed).

Resolves ``requirements.yaml`` (RequirementDefinitions) and
``innosuisse_innovation_project_v1_1.yaml`` (the 12 official core RuleDefinitions)
from the frozen contract set. Validation is strict: any structural corruption,
version drift, or a requirement linking an unknown rule raises ``RegistryError``
so the application/run fails closed instead of evaluating against a broken
policy. The registry is immutable once loaded.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config.settings import get_settings

logger = logging.getLogger("app.registry")

REQUIREMENTS_FILE = "requirements.yaml"
RULES_FILE = "innosuisse_innovation_project_v1_1.yaml"

EXPECTED_REQUIREMENT_REGISTRY_ID = "requirements.innosuisse_innovation_project"
EXPECTED_RULE_REGISTRY_ID = (
    "innosuisse-innovation-project-with-implementation-partner"
)
EXPECTED_PROFILE_ID = "innosuisse_innovation_project_with_implementation_partner"

# RequirementAssessment.basis (openapi) — the registry assessment_basis must map
# into one of these. human_override is reserved for human decisions (not M4).
VALID_ASSESSMENT_BASIS = {"deterministic_rule", "semantic_assessment", "hybrid"}

# M6 deterministic-draft field scope: agent-writable narrative/composite editors
# that map to a singleton (non-repeated) structured path. Repeated work-package /
# milestone fields are excluded by the "[]" path marker; repeated budget-position
# families have no contract field_instance_id and are deferred explicitly.
M6_DRAFT_FIELD_KINDS = {"narrative_text", "composite_editor"}
M6_DEFERRED_FIELD_PREFIXES = ("PS.MATERIAL_POSITION.", "PS.CASH_CONTRIBUTION.")


class RegistryError(RuntimeError):
    """Raised when a registry file is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class RuleDef:
    rule_id: str
    requirement_id: str | None
    title: str
    category: str
    execution_mode: str
    severity: str
    applies_when: dict[str, Any] | None
    required_inputs: list[str]
    condition: dict[str, Any]
    result_mapping: dict[str, str]
    status: str
    test_cases: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RequirementDef:
    requirement_id: str
    profile_id: str
    title: str
    description: str
    category: str
    type: str
    applies_when: dict[str, Any] | None
    affected_field_ids: list[str]
    linked_rule_ids: list[str]
    evidence_requirement: str
    assessment_basis: str
    severity: str
    status: str
    user_facing: bool
    version: str


@dataclass(frozen=True)
class PortalFieldDef:
    field_id: str
    label_or_question: str
    portal_section: str
    subsection: str
    portal_area: str
    character_limit: int | None
    field_kind: str
    support_mode: str
    agent_writable: bool
    structured_data_path: str
    evidence_requirement: str
    # Raw registry mandatory_status (required | optional | not_applicable |
    # conditional | needs_verification). Exposed read-only; never interpreted
    # beyond the deterministic mapping in the portal-fields endpoint (H32).
    mandatory_status: str
    registry_index: int  # position in the registry → canonical stable order

    @property
    def is_m6_draft_field(self) -> bool:
        return (
            self.agent_writable
            and self.support_mode == "draft_text"
            and self.field_kind in M6_DRAFT_FIELD_KINDS
            and "[]" not in (self.structured_data_path or "")
            and not self.field_id.startswith(M6_DEFERRED_FIELD_PREFIXES)
        )


@dataclass(frozen=True)
class Registry:
    requirement_registry_version: str
    rule_registry_version: str
    portal_field_profile_version: str
    profile_id: str
    requirements: dict[str, RequirementDef]
    rules: dict[str, RuleDef]
    portal_fields: dict[str, PortalFieldDef]
    # The M4-evaluable subset: active, user-facing requirements whose linked
    # rules are all known official core rules (the 12 REQ.INNO.* requirements).
    evaluable_requirement_ids: tuple[str, ...]

    def evaluable_requirements(self) -> list[RequirementDef]:
        return [self.requirements[r] for r in self.evaluable_requirement_ids]

    def rule_for(self, requirement: RequirementDef) -> RuleDef:
        # M4 requirements link exactly one core rule.
        return self.rules[requirement.linked_rule_ids[0]]

    def m6_draft_fields(self) -> list[PortalFieldDef]:
        """The supported deterministic-draft fields, in canonical registry order."""
        return [f for f in self.portal_fields.values() if f.is_m6_draft_field]

    def mandatory_questions(self, editor_field_id: str) -> list[PortalFieldDef]:
        """Registered Mandatory-Content main questions of a composite editor,
        in registry order (e.g. VC 3.1/3.2, SOL 4.1–4.5)."""
        family = editor_field_id.removesuffix(".EDITOR")
        prefix = f"{family}.MANDATORY_"
        return [
            f for f in self.portal_fields.values() if f.field_id.startswith(prefix)
        ]


def _contracts_dir() -> Path:
    configured = get_settings().contracts_dir
    if configured:
        return Path(configured).resolve()
    # app/registry/loader.py -> app -> backend -> repo root.
    return (Path(__file__).resolve().parents[3] / "final_backend_contracts_v1_1")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RegistryError(f"Registry file not found: {path.name}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # malformed YAML
        raise RegistryError(f"Registry file {path.name} is not valid YAML.") from exc
    if not isinstance(data, dict):
        raise RegistryError(f"Registry file {path.name} has no top-level mapping.")
    return data


def _parse_rules(raw: dict[str, Any]) -> dict[str, RuleDef]:
    if raw.get("registry_id") != EXPECTED_RULE_REGISTRY_ID:
        raise RegistryError("Rule registry_id mismatch.")
    core = raw.get("official_core_rules")
    if not isinstance(core, list) or not core:
        raise RegistryError("Rule registry has no official_core_rules.")
    rules: dict[str, RuleDef] = {}
    for entry in core:
        if not isinstance(entry, dict):
            raise RegistryError("A rule entry is not a mapping.")
        rule_id = entry.get("rule_id")
        condition = entry.get("condition")
        mapping = entry.get("result_mapping")
        if not rule_id or not isinstance(condition, dict) or not isinstance(mapping, dict):
            raise RegistryError(f"Rule {rule_id!r} is missing condition/result_mapping.")
        if "type" not in condition:
            raise RegistryError(f"Rule {rule_id!r} condition has no type.")
        if rule_id in rules:
            raise RegistryError(f"Duplicate rule_id {rule_id!r}.")
        rules[rule_id] = RuleDef(
            rule_id=rule_id,
            requirement_id=entry.get("requirement_id"),
            title=entry.get("title", rule_id),
            category=entry.get("category", ""),
            execution_mode=entry.get("execution_mode", ""),
            severity=entry.get("severity", "info"),
            applies_when=entry.get("applies_when"),
            required_inputs=list(entry.get("required_inputs", []) or []),
            condition=condition,
            result_mapping={str(k): str(v) for k, v in mapping.items()},
            status=entry.get("status", "active"),
            test_cases=list(entry.get("test_cases", []) or []),
        )
    return rules


def _parse_requirements(raw: dict[str, Any]) -> dict[str, RequirementDef]:
    if raw.get("registry_id") != EXPECTED_REQUIREMENT_REGISTRY_ID:
        raise RegistryError("Requirement registry_id mismatch.")
    entries = raw.get("requirements")
    if not isinstance(entries, list) or not entries:
        raise RegistryError("Requirement registry has no requirements.")
    requirements: dict[str, RequirementDef] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RegistryError("A requirement entry is not a mapping.")
        req_id = entry.get("requirement_id")
        if not req_id:
            raise RegistryError("A requirement is missing requirement_id.")
        if req_id in requirements:
            raise RegistryError(f"Duplicate requirement_id {req_id!r}.")
        basis = entry.get("assessment_basis", "")
        requirements[req_id] = RequirementDef(
            requirement_id=req_id,
            profile_id=entry.get("profile_id", ""),
            title=entry.get("title", req_id),
            description=entry.get("description", ""),
            category=entry.get("category", ""),
            type=entry.get("type", ""),
            applies_when=entry.get("applies_when"),
            affected_field_ids=list(entry.get("affected_field_ids", []) or []),
            linked_rule_ids=list(entry.get("linked_rule_ids", []) or []),
            evidence_requirement=entry.get("evidence_requirement", ""),
            assessment_basis=basis,
            severity=entry.get("severity", "info"),
            status=entry.get("status", "active"),
            user_facing=bool(entry.get("user_facing", False)),
            version=str(entry.get("version", "")),
        )
    return requirements


def _parse_portal_fields(raw: dict[str, Any]) -> dict[str, PortalFieldDef]:
    entries = raw.get("portal_fields")
    if not isinstance(entries, list) or not entries:
        raise RegistryError("Rule registry has no portal_fields.")
    fields: dict[str, PortalFieldDef] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RegistryError("A portal field entry is not a mapping.")
        field_id = entry.get("field_id")
        if not field_id:
            raise RegistryError("A portal field is missing field_id.")
        if field_id in fields:
            raise RegistryError(f"Duplicate portal field_id {field_id!r}.")
        limit = entry.get("character_limit")
        fields[field_id] = PortalFieldDef(
            field_id=field_id,
            label_or_question=str(entry.get("label_or_question", "")),
            portal_section=str(entry.get("portal_section", "")),
            subsection=str(entry.get("subsection", "")),
            portal_area=str(entry.get("portal_area", "")),
            character_limit=int(limit) if isinstance(limit, int) else None,
            field_kind=str(entry.get("field_kind", "")),
            support_mode=str(entry.get("support_mode", "")),
            agent_writable=bool(entry.get("agent_writable", False)),
            structured_data_path=str(entry.get("structured_data_path", "")),
            evidence_requirement=str(entry.get("evidence_requirement", "")),
            mandatory_status=str(entry.get("mandatory_status", "")),
            registry_index=index,
        )
    return fields


def load_registry() -> Registry:
    """Read + validate both registries. Raises RegistryError (fail-closed)."""
    base = _contracts_dir()
    rules_raw = _read_yaml(base / RULES_FILE)
    reqs_raw = _read_yaml(base / REQUIREMENTS_FILE)

    rule_version = str(rules_raw.get("schema_version", ""))
    req_version = str(reqs_raw.get("schema_version", ""))
    if not rule_version or not req_version:
        raise RegistryError("A registry file is missing schema_version.")

    rules = _parse_rules(rules_raw)
    requirements = _parse_requirements(reqs_raw)
    portal_fields = _parse_portal_fields(rules_raw)

    # Referential integrity + build the evaluable subset deterministically.
    evaluable: list[str] = []
    for req in requirements.values():
        for linked in req.linked_rule_ids:
            if linked not in rules:
                raise RegistryError(
                    f"Requirement {req.requirement_id} links unknown rule {linked}."
                )
        if not (req.status == "active" and req.user_facing and req.linked_rule_ids):
            continue
        if not all(rid in rules for rid in req.linked_rule_ids):
            continue
        if req.assessment_basis not in VALID_ASSESSMENT_BASIS:
            raise RegistryError(
                f"Requirement {req.requirement_id} has invalid "
                f"assessment_basis {req.assessment_basis!r}."
            )
        evaluable.append(req.requirement_id)

    if not evaluable:
        raise RegistryError("No evaluable requirements resolved from the registry.")

    return Registry(
        requirement_registry_version=req_version,
        rule_registry_version=rule_version,
        portal_field_profile_version=rule_version,
        profile_id=EXPECTED_PROFILE_ID,
        requirements=requirements,
        rules=rules,
        portal_fields=portal_fields,
        evaluable_requirement_ids=tuple(evaluable),
    )


_registry: Registry | None = None


def get_registry() -> Registry:
    """Return the cached registry, loading + validating it on first use."""
    global _registry
    if _registry is None:
        _registry = load_registry()
        logger.info(
            "registry loaded requirement_registry_version=%s rule_registry_version=%s "
            "evaluable_requirements=%d core_rules=%d",
            _registry.requirement_registry_version,
            _registry.rule_registry_version,
            len(_registry.evaluable_requirement_ids),
            len(_registry.rules),
        )
    return _registry
