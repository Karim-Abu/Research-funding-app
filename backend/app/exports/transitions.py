"""Export status transition authority (Milestone 8).

Only ``queued → generating → available`` and ``queued|generating → failed`` are
valid. Routers and generators never set status ad hoc — they call here. Invalid
transitions fail closed.
"""
from __future__ import annotations

from app.db.models import ExportArtifact

_ALLOWED: dict[str, set[str]] = {
    "queued": {"generating", "failed"},
    "generating": {"available", "failed"},
    "available": set(),
    "failed": set(),
}


class InvalidExportTransition(Exception):
    pass


def transition(artifact: ExportArtifact, target: str) -> None:
    if target not in _ALLOWED.get(artifact.status, set()):
        raise InvalidExportTransition(
            f"cannot move export from {artifact.status} to {target}"
        )
    artifact.status = target
