"""Deterministic Registry-marker handling for composite portal drafts."""
from __future__ import annotations

import re
from dataclasses import dataclass


class SectionStructureError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SectionSpan:
    marker: str
    start: int
    end: int


def _pattern(marker: str) -> re.Pattern[str]:
    return re.compile(
        rf"^[ \t]*(?:#{{1,6}}[ \t]+)?{re.escape(marker)}(?![.\d])",
        re.MULTILINE,
    )


def section_spans(text: str, markers: tuple[str, ...]) -> list[SectionSpan]:
    """Return exactly one, registry-ordered span per marker or fail closed."""
    starts: list[tuple[str, int]] = []
    for marker in markers:
        matches = list(_pattern(marker).finditer(text or ""))
        if not matches:
            raise SectionStructureError(f"section_marker_missing:{marker}")
        if len(matches) != 1:
            raise SectionStructureError(f"section_marker_ambiguous:{marker}")
        starts.append((marker, matches[0].start()))
    if [start for _, start in starts] != sorted(start for _, start in starts):
        raise SectionStructureError("section_markers_out_of_order")
    return [
        SectionSpan(
            marker=marker,
            start=start,
            end=starts[index + 1][1] if index + 1 < len(starts) else len(text),
        )
        for index, (marker, start) in enumerate(starts)
    ]


def target_section_spans(
    text: str, markers: tuple[str, ...], target: str
) -> list[SectionSpan]:
    """Ziel-tolerante Variante von ``section_spans`` (Owner-Freigabe 2026-07-24).

    Nur der ZIELmarker ist Pflicht (genau einmal) — fehlende Nicht-Ziel-Marker
    gelten ehrlich als abwesend: ihr Abschnitt existiert im Text nicht, es
    werden keine Grenzen erfunden (jeder Span endet am nächsten VORHANDENEN
    Marker). Fail-closed bleiben: unbekanntes Ziel, fehlender/mehrdeutiger
    Zielmarker, mehrdeutige übrige Marker, Reihenfolge-Verletzung der
    vorhandenen Marker. Der Export-Pfad nutzt weiterhin das strikte
    ``section_spans`` (vollständige Struktur bleibt dort Pflicht).
    """
    if target not in markers:
        raise SectionStructureError(f"section_target_unknown:{target}")
    starts: list[tuple[str, int]] = []
    for marker in markers:
        matches = list(_pattern(marker).finditer(text or ""))
        if not matches:
            if marker == target:
                raise SectionStructureError(f"section_marker_missing:{marker}")
            continue
        if len(matches) != 1:
            raise SectionStructureError(f"section_marker_ambiguous:{marker}")
        starts.append((marker, matches[0].start()))
    if [start for _, start in starts] != sorted(start for _, start in starts):
        raise SectionStructureError("section_markers_out_of_order")
    return [
        SectionSpan(
            marker=marker,
            start=start,
            end=starts[index + 1][1] if index + 1 < len(starts) else len(text),
        )
        for index, (marker, start) in enumerate(starts)
    ]


def extract_section(text: str, markers: tuple[str, ...], target: str) -> str:
    span = next(
        s for s in target_section_spans(text, markers, target) if s.marker == target
    )
    return text[span.start:span.end].rstrip()


def validate_section_candidate(
    candidate_text: str, markers: tuple[str, ...], target: str
) -> None:
    """The model may return only the requested section, including its heading."""
    if target not in markers:
        raise SectionStructureError(f"section_target_unknown:{target}")
    target_matches = list(_pattern(target).finditer(candidate_text or ""))
    if len(target_matches) != 1 or target_matches[0].start() != 0:
        raise SectionStructureError("section_candidate_heading_invalid")
    for marker in markers:
        if marker != target and _pattern(marker).search(candidate_text or ""):
            raise SectionStructureError("section_candidate_contains_other_section")


def merge_section(
    base_text: str,
    markers: tuple[str, ...],
    target: str,
    candidate_text: str,
) -> str:
    validate_section_candidate(candidate_text, markers, target)
    span = next(
        s
        for s in target_section_spans(base_text, markers, target)
        if s.marker == target
    )
    replacement = candidate_text.rstrip()
    suffix = base_text[span.end:]
    if suffix and not replacement.endswith("\n"):
        replacement += "\n"
    return base_text[:span.start] + replacement + suffix.lstrip("\n")


def section_error_detail(reason: str) -> str | None:
    """Deutscher Klartext für deterministische Abschnittsstruktur-Fehler.

    Texte gemäss Katalog-Addendum 2026-07-24 (docs/repair/message-catalog.md).
    Rückgabe None für alle Nicht-Abschnitts-Codes.
    """
    code, _, marker = reason.partition(":")
    if code == "section_marker_missing":
        return (
            f"Die Markerzeile «{marker}» fehlt im Text. Stellen Sie die Zeile "
            f"«{marker}» wieder her oder wählen Sie einen vorhandenen "
            "Zielabschnitt."
        )
    if code == "section_marker_ambiguous":
        return (
            f"Die Markerzeile «{marker}» kommt mehrfach vor. Entfernen Sie die "
            "doppelte Zeile, damit der Abschnitt eindeutig bleibt."
        )
    if code == "section_markers_out_of_order":
        return (
            "Die Abschnittsmarker stehen nicht in der Reihenfolge der Vorlage. "
            "Ordnen Sie die Abschnitte wieder aufsteigend."
        )
    if code in ("section_target_unknown", "section_markers_missing"):
        return (
            "Der gewählte Abschnitt ist für dieses Feld nicht verfügbar. "
            "Bitte wählen Sie einen gültigen Zielabschnitt."
        )
    return None


def compact_adjacent_section(text: str, limit: int) -> str:
    """Deterministic synopsis: heading + first two and last sentence."""
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    selected = sentences[:2]
    if len(sentences) > 2:
        selected.append(sentences[-1])
    synopsis = " ".join(selected)
    return synopsis[: max(0, limit - 1)].rstrip() + "…"
