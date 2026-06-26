"""Prompt/profile asset versions (Milestone 9A).

Reads the versioned placeholder prompt files under ``prompts/`` to record a
``prompt_version`` on AgentInvocations. The prompts themselves are NOT used in
normal M9A runs.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent / "prompts"


@lru_cache
def prompt_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for path in sorted(_PROMPT_DIR.glob("*.md")):
        pid = ver = None
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("profile_id:"):
                pid = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("version:"):
                ver = stripped.split(":", 1)[1].strip()
        if pid and ver:
            versions[pid] = ver
    return versions


def prompt_version_for(profile_id: str) -> str | None:
    return prompt_versions().get(profile_id)
