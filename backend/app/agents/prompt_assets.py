"""Prompt/profile asset versions (Milestone 9A).

Reads the versioned placeholder prompt files under ``prompts/`` to record a
``prompt_version`` on AgentInvocations. The prompts themselves are NOT used in
normal M9A runs.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent / "prompts"


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
