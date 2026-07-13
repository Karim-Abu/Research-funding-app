"""PortalFieldInfo — read-only registry catalog entry (Slice 4, E4-A).

Additive contract: exposes ALL registry portal fields (161) with a
deterministic display mode. The M6 draft contract (PortalFieldDraft)
is untouched.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DisplayMode = Literal["draft", "checklist", "upload", "external_only"]


class PortalFieldSubsection(BaseModel):
    """Registrierte Pflicht-Unterfrage eines Composite-Editors (additiv, R6).

    ``marker`` ist die sichtbare Portal-Gliederung ("3.1", "4.5.1"); ``label``
    die Registry-Frage. Reine Registry-Daten — kein Draft-Inhalt.
    """

    model_config = ConfigDict(extra="forbid")

    marker: str
    label: str


class PortalFieldInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    # Field-id prefix (INTRO | ORG | VC | SOL | PS | SUM).
    section: str
    label: str
    character_limit: int | None = None
    # Raw registry mandatory_status; `required` is only set where the registry
    # is unambiguous (required/optional/not_applicable), else None (H32: never
    # guess needs_verification/conditional statuses).
    mandatory_status: str
    required: bool | None = None
    # Raw registry values for debugging/audit/UI badges.
    support_mode: str
    field_kind: str
    display_mode: DisplayMode
    # True only for the supported M6 deterministic-draft fields.
    draft_available: bool
    # Sichtbare Unterabschnitte eines Composite-Editors (leer für einfache
    # Felder). Additiv — bestehende Clients ignorieren das Feld.
    subsections: list[PortalFieldSubsection] = []
