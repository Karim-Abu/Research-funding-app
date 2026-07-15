"""Prompt/profile asset versions (Milestone 9A).

Reads the versioned placeholder prompt files under ``prompts/`` to record a
``prompt_version`` on AgentInvocations. The prompts themselves are NOT used in
normal M9A runs.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent / "prompts"
_AGENT_DIR = Path(__file__).parent


def _parse_prompt(path: Path) -> tuple[str | None, str | None, str]:
    """Return (profile_id, version, body-after-frontmatter) for a prompt file."""
    text = path.read_text(encoding="utf-8")
    pid = ver = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("profile_id:"):
            pid = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("version:"):
            ver = stripped.split(":", 1)[1].strip()
    # Body = everything after the closing '---' of the YAML frontmatter.
    parts = text.split("---", 2)
    body = parts[2].strip() if len(parts) == 3 else text.strip()
    return pid, ver, body


@lru_cache
def prompt_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for path in sorted(_PROMPT_DIR.glob("*.md")):
        pid, ver, _ = _parse_prompt(path)
        if pid and ver:
            versions[pid] = ver
    return versions


@lru_cache
def prompt_instructions() -> dict[str, str]:
    """Activated profiles only: the prompt body used to build the model prompt.
    Placeholder prompts (``status: placeholder_*``) are excluded."""
    bodies: dict[str, str] = {}
    for path in sorted(_PROMPT_DIR.glob("*.md")):
        pid, _, body = _parse_prompt(path)
        if pid and "placeholder" not in path.read_text(encoding="utf-8").split("---", 2)[1]:
            bodies[pid] = body
    return bodies


def prompt_version_for(profile_id: str) -> str | None:
    return prompt_versions().get(profile_id)


def prompt_instructions_for(profile_id: str) -> str | None:
    return prompt_instructions().get(profile_id)


@lru_cache
def _contract_asset_body(relative_path: str) -> str:
    """Read a role/skill asset without ever treating source data as prompt text."""
    path = _AGENT_DIR / relative_path
    _pid, _version, body = _parse_prompt(path)
    return body


def role_skill_instructions_for(profile_id: str, skill_id: str | None = None) -> str | None:
    """Compose the versioned base role and the selected versioned skill.

    The legacy profile prompt remains the compatibility fallback.  This keeps the
    current Gateway as the sole prompt boundary while making the professional
    contract explicit and independently versioned.
    """
    from app.agents.role_skills import RoleSkillRegistryError, get_role_skill_registry

    try:
        resolved = get_role_skill_registry().resolve(profile_id, skill_id)
    except RoleSkillRegistryError:
        return None
    return "\n\n".join(
        (
            _contract_asset_body(resolved.role.prompt_asset),
            _contract_asset_body(resolved.skill.prompt_asset),
        )
    )
