"""Versioned role and skill contracts for the existing agent runtime.

This is deliberately a registry extension, not a second agent framework.  The
ModelGateway remains the only model boundary; this module only resolves the
professional role and the field-specific skill that have to be recorded with
an invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.registry.loader import RegistryError, _contracts_dir, _read_yaml


ROLE_SKILLS_FILE = "role_skills_v2.yaml"


class RoleSkillRegistryError(RegistryError):
    """Raised for an incomplete or internally inconsistent role/skill contract."""


@dataclass(frozen=True)
class RoleDef:
    role_id: str
    version: str
    prompt_asset: str
    execution_kind: str


@dataclass(frozen=True)
class SkillDef:
    skill_id: str
    role_id: str
    version: str
    prompt_asset: str
    bindings: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class ResolvedRoleSkill:
    role: RoleDef
    skill: SkillDef


@dataclass(frozen=True)
class RoleSkillRegistry:
    roles: dict[str, RoleDef]
    skills: dict[str, SkillDef]
    profile_defaults: dict[str, str]

    def resolve(self, profile_id: str, skill_id: str | None = None) -> ResolvedRoleSkill:
        default_skill_id = self.profile_defaults.get(profile_id)
        selected = skill_id or default_skill_id
        if selected is None or default_skill_id is None:
            raise RoleSkillRegistryError(f"missing role/skill binding for profile {profile_id}")
        try:
            skill = self.skills[selected]
            role = self.roles[skill.role_id]
            default_skill = self.skills[default_skill_id]
        except KeyError as exc:
            raise RoleSkillRegistryError(
                f"unknown role/skill binding for profile {profile_id}: {selected}"
            ) from exc
        # A caller may only specialize a profile within its professional role.
        # This permits A2's field-specific skills, but prevents an accidental or
        # injected request from relabelling an A1/A3 call as another role.
        if skill.role_id != default_skill.role_id:
            raise RoleSkillRegistryError(
                f"skill {selected} is not compatible with profile {profile_id}"
            )
        return ResolvedRoleSkill(role=role, skill=skill)

    def skill_for_a2(self, field_id: str, target_section: str | None) -> SkillDef:
        for skill in self.skills.values():
            if skill.role_id != "A2_INNOSUISSE_PROPOSAL_WRITER":
                continue
            if (field_id, target_section) in skill.bindings:
                return skill
        raise RoleSkillRegistryError(
            f"no A2 skill binding for field={field_id} section={target_section}"
        )


def _asset_exists(relative_path: str) -> bool:
    return (Path(__file__).parent / relative_path).is_file()


def _build(raw: dict[str, Any]) -> RoleSkillRegistry:
    roles: dict[str, RoleDef] = {}
    for entry in raw.get("roles", []) or []:
        role_id = str(entry.get("role_id") or "")
        if not role_id or role_id in roles:
            raise RoleSkillRegistryError(f"duplicate or missing role_id: {role_id!r}")
        asset = str(entry.get("prompt_asset") or "")
        if not asset or not _asset_exists(asset):
            raise RoleSkillRegistryError(f"{role_id}: missing role prompt asset {asset!r}")
        roles[role_id] = RoleDef(
            role_id=role_id,
            version=str(entry.get("version") or ""),
            prompt_asset=asset,
            execution_kind=str(entry.get("execution_kind") or "model_gateway"),
        )
        if not roles[role_id].version:
            raise RoleSkillRegistryError(f"{role_id}: missing version")

    skills: dict[str, SkillDef] = {}
    seen_bindings: set[tuple[str, str | None]] = set()
    for entry in raw.get("skills", []) or []:
        skill_id = str(entry.get("skill_id") or "")
        role_id = str(entry.get("role_id") or "")
        if not skill_id or skill_id in skills:
            raise RoleSkillRegistryError(f"duplicate or missing skill_id: {skill_id!r}")
        if role_id not in roles:
            raise RoleSkillRegistryError(f"{skill_id}: unknown role_id {role_id}")
        asset = str(entry.get("prompt_asset") or "")
        if not asset or not _asset_exists(asset):
            raise RoleSkillRegistryError(f"{skill_id}: missing skill prompt asset {asset!r}")
        bindings = tuple(
            (str(binding["field_id"]), binding.get("section_id"))
            for binding in entry.get("bindings", []) or []
        )
        for binding in bindings:
            if role_id == "A2_INNOSUISSE_PROPOSAL_WRITER" and binding in seen_bindings:
                raise RoleSkillRegistryError(f"duplicate A2 field/section binding: {binding}")
            seen_bindings.add(binding)
        version = str(entry.get("version") or "")
        if not version:
            raise RoleSkillRegistryError(f"{skill_id}: missing version")
        skills[skill_id] = SkillDef(skill_id, role_id, version, asset, bindings)

    profile_defaults = {
        str(profile_id): str(skill_id)
        for profile_id, skill_id in (raw.get("profile_defaults") or {}).items()
    }
    for profile_id, skill_id in profile_defaults.items():
        if skill_id not in skills:
            raise RoleSkillRegistryError(
                f"{profile_id}: references unknown default skill {skill_id}"
            )
    if not roles or not skills:
        raise RoleSkillRegistryError("role/skill registry must declare roles and skills")
    return RoleSkillRegistry(roles=roles, skills=skills, profile_defaults=profile_defaults)


def load_role_skill_registry() -> RoleSkillRegistry:
    return _build(_read_yaml(_contracts_dir() / ROLE_SKILLS_FILE))


@lru_cache
def get_role_skill_registry() -> RoleSkillRegistry:
    return load_role_skill_registry()
