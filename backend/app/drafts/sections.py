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


def extract_section(text: str, markers: tuple[str, ...], target: str) -> str:
    if target not in markers:
        raise SectionStructureError(f"section_target_unknown:{target}")
    span = next(s for s in section_spans(text, markers) if s.marker == target)
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
    span = next(s for s in section_spans(base_text, markers) if s.marker == target)
    replacement = candidate_text.rstrip()
    suffix = base_text[span.end:]
    if suffix and not replacement.endswith("\n"):
        replacement += "\n"
    return base_text[:span.start] + replacement + suffix.lstrip("\n")


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
