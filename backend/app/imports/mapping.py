"""Deterministisches Mapping «begonnener Innolink-Export → Portal-Felder».

Das Mapping ist absichtlich struktur- statt inhaltsbasiert: jedes Feld und
jeder Composite-Unterabschnitt besitzt explizite Start-/Stop-Headings. Dadurch
kann ein leeres Feld niemals den Text eines folgenden Portalbereichs erben.
Es gibt weder OCR noch LLM-Zuordnung.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from functools import lru_cache

from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.ingestion.parsers import ParseResult, parse
from app.registry.loader import get_registry


MAPPING_VERSION = "innolink-narrative-v2"
STRUCTURED_MAPPING_VERSION = "innolink-structured-v1"
LEGACY_SCHEMA_MIGRATION_VERSION = "innolink-intro-ip-to-solution-v1"

CONFIDENCE_FOUND = "found"
CONFIDENCE_UNCERTAIN = "uncertain"

STATUS_CONTENT_DETECTED = "content_detected"
STATUS_EMPTY = "empty"
STATUS_LEGACY_MIGRATED = "legacy_migrated"
STATUS_UNCERTAIN = "uncertain"


# Portalbereiche, die auch dann Grenzen sind, wenn das MVP sie nicht als
# Draft-Feld exportiert. Die Patterns matchen normalisierte vollständige Zeilen.
PORTAL_AREA_HEADINGS = (
    r"^(?:\d+\.?\s+)?introduction$",
    r"^application name and abstract$",
    r"^context$",
    r"^scientific integrity$",
    r"^intellectual property rights?$",
    r"^(?:\d+\.?\s+)?organisations?(?: and |\s*&\s*)people$",
    r"^main contacts$",
    r"^innovation mentor$",
    r"^(?:\d+\.?\s+)?value creation$",
    r"^business targets(?: and |\s*&\s*)business model$",
    r"^(?:\d+\.?\s+)?solution$",
    r"^innovation solution$",
    r"^(?:\d+\.?\s+)?project setup$",
    r"^risk management$",
    r"^planned hours$",
    r"^total planned hours\b",
    r"^salary costs$",
    r"^material costs$",
    r"^financial overview$",
    r"^project budget distribution\b",
    r"^project budget$",
)

INTRO_LABEL_HEADINGS = (
    r"^application name$",
    r"^application name \(",
    r"^projektname\b",
    r"^title\s*:$",
    r"^project title\b",
    r"^application name in english\b",
    r"^projektname englisch\b",
    r"^title in english\s*:?$",
    r"^abstract\b",
    r"^executive summary\b",
    r"^management summary$",
    r"^project duration\s*:$",
    r"^number\s*:$",
)

LEGACY_IP_QUESTION_HEADINGS = (
    r"^was a patent search performed\b",
    r"^does the project require \(patent-?\)licen[cs][a-z]*(?:\(s\))?",
    r"^have the project partners concluded a prior written agreement\b",
)

COMPOSITE_HEADINGS = tuple(
    rf"^{marker.replace('.', r'\.')}(?:\s|$)"
    for marker in (
        "3.1", "3.2", "3.3", "4.1", "4.2", "4.3", "4.4",
        "4.5", "4.5.1", "4.5.2", "4.5.3", "4.5.4", "4.6",
    )
)

ALL_STRUCTURAL_HEADINGS = (
    *PORTAL_AREA_HEADINGS,
    *INTRO_LABEL_HEADINGS,
    *LEGACY_IP_QUESTION_HEADINGS,
    *COMPOSITE_HEADINGS,
    r"^independence of research and implementation partners$",
    r"^explanations and comments\b",
    r"^erläuterungen und kommentare\b",
    r"^explanation(?:\s|$|\()",
    r"^erklärung\b",
)


NOISE_PATTERNS = (
    r"^characters:\s*\d+\s*/\s*\d+$",
    r"^open editor$",
    r"^review mandatory content$",
    r"^confirmation .+:\s*(yes|no)$",
    r"^innosuisse innolink\b",
    r"^seite \d+$",
    r"-\s+seite\s+\d+$",
    r"^\d+\s*$",
    r"^[a-zäöü ]+\|.*\|",
    r"^please note(?:,| that|\b)",
    r"^.{0,80}\s\d{1,3}/\d{1,3}$",
    r"^\d{1,3}/\d{1,3}$",
    r"^\d{3}\.\d{3}\b",
)


@dataclass(frozen=True)
class FieldPattern:
    field_id: str
    label_patterns: tuple[str, ...]
    stop_patterns: tuple[str, ...]
    question_field_id: str | None = None


@dataclass(frozen=True)
class SubsectionPattern:
    parent_field_id: str
    target_sections: tuple[str, ...]
    start_patterns: tuple[str, ...]
    stop_patterns: tuple[str, ...]
    question_field_id: str | None = None
    migration_version: str | None = None
    requires_manual_assignment: bool = False


@dataclass(frozen=True)
class MappedSection:
    target_sections: tuple[str, ...]
    source_location: str | None
    status: str
    candidate_text: str
    original_excerpt: str
    migration_version: str | None = None
    requires_manual_assignment: bool = False
    review_note: str | None = None


@dataclass(frozen=True)
class MappedField:
    """Ein erkanntes Feld — Basis für einen ImportCandidate."""

    field_id: str
    label: str
    extracted_text: str
    confidence: str
    source_location: str | None
    mapping_status: str
    sections: tuple[MappedSection, ...] = ()
    mapping_version: str = MAPPING_VERSION


@dataclass(frozen=True)
class MappedStructuredCandidate:
    candidate_kind: str
    target_key: str
    payload_json: dict[str, Any]
    confidence: str
    source_location: str | None
    mapping_version: str = STRUCTURED_MAPPING_VERSION


@dataclass
class MappingResult:
    fields: list[MappedField] = field(default_factory=list)
    structured_candidates: list[MappedStructuredCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_manual_input: bool = False


@dataclass(frozen=True)
class _Line:
    page: int | None
    raw: str
    norm: str


@dataclass(frozen=True)
class _Extracted:
    text: str
    original_excerpt: str
    source_location: str | None


def _normalize(line: str) -> str:
    text = unicodedata.normalize("NFKC", line).strip()
    return re.sub(r"\s+", " ", text).lower()


def _word_tokens(line: str) -> list[str]:
    return re.findall(r"[a-z0-9äöü]+", _normalize(line))


def _matches(norm: str, patterns: tuple[str, ...]) -> bool:
    return any(re.match(pattern, norm) for pattern in patterns)


def _is_noise(norm: str) -> bool:
    return any(re.search(pattern, norm) for pattern in NOISE_PATTERNS)


def _lines_with_pages(result: ParseResult) -> list[_Line]:
    lines: list[_Line] = []
    for block in result.blocks:
        for raw in block.text.splitlines():
            lines.append(_Line(block.page, raw, _normalize(raw)))
    return lines


def _layout_lines_with_pages(result: ParseResult) -> list[_Line]:
    """Layouttreue PDF-Zeilen; nur für strukturierte Tabellen verwendet."""
    lines: list[_Line] = []
    for block in result.blocks:
        source = block.layout_text or block.text
        for raw in source.splitlines():
            lines.append(_Line(block.page, raw, _normalize(raw)))
    return lines


@lru_cache(maxsize=1)
def _question_texts() -> dict[str, str]:
    registry = get_registry()
    ids = (
        "INTRO.IP.PATENT_SEARCH",
        "INTRO.IP.PATENT_LICENCES",
        "INTRO.IP.PRIOR_WRITTEN_AGREEMENT",
    )
    out = {
        field_id: registry.portal_fields[field_id].label_or_question
        for field_id in ids
    }
    # Wortlaut des belegten älteren Exports. Diese Texte sind Portalfragen,
    # keine Antragstellerinhalte; sie dienen nur dazu, umgebrochene Fragen
    # vollständig vom Antwortbereich zu trennen.
    out.update(
        {
            "INTRO.IP.PATENT_SEARCH": (
                "Was a patent search performed with or without IPI "
                "(Swiss Federal Institute for Intellectual Property)?"
            ),
            "INTRO.IP.PATENT_LICENCES": (
                "Does the project require (patent-)licencense(s)? If yes, "
                "please explain which background IP is needed for the project "
                "and the ownership of that background IP."
            ),
            "INTRO.IP.PRIOR_WRITTEN_AGREEMENT": (
                "Have the project partners concluded a prior written agreement "
                "regarding the assignement or exploitation of any research "
                "findings or patents?"
            ),
        }
    )
    for parent in (
        "VC.BUSINESS_TARGETS_MODEL.EDITOR",
        "SOL.INNOVATION_SOLUTION.EDITOR",
    ):
        for question in registry.mandatory_questions(parent):
            out[question.field_id] = question.label_or_question
    return out


def _heading_end(
    lines: list[_Line], start: int, question_field_id: str | None
) -> int:
    """Return first content line after a possibly wrapped portal question."""
    if question_field_id is None:
        return start + 1
    question = _question_texts().get(question_field_id)
    if not question:
        return start + 1
    expected = _word_tokens(question)
    consumed = _word_tokens(lines[start].raw)
    index = start + 1
    while len(consumed) < len(expected) and index < len(lines):
        if not lines[index].norm:
            break
        trial = consumed + _word_tokens(lines[index].raw)
        if trial != expected[: len(trial)]:
            break
        consumed = trial
        index += 1
    return index


def _question_match(norm: str) -> tuple[tuple[str, ...], str] | None:
    for spec in SUBSECTIONS:
        if _matches(norm, spec.start_patterns) and spec.question_field_id:
            return spec.start_patterns, spec.question_field_id
    return None


def _clean_content(lines: list[_Line], start: int, end: int) -> str:
    content: list[str] = []
    index = start
    while index < end:
        line = lines[index]
        if not line.norm or _is_noise(line.norm):
            index += 1
            continue
        repeated = _question_match(line.norm)
        if repeated is not None:
            index = min(_heading_end(lines, index, repeated[1]), end)
            continue
        content.append(line.raw.strip())
        index += 1
    return "\n".join(content).strip()


def _source_location(lines: list[_Line], start: int, end: int) -> str | None:
    pages = [line.page for line in lines[start:end] if line.page is not None]
    if not pages:
        return None
    first, last = min(pages), max(pages)
    return f"Seite {first}" if first == last else f"Seiten {first}–{last}"


def _extract(
    lines: list[_Line],
    start: int,
    stop_patterns: tuple[str, ...],
    question_field_id: str | None = None,
) -> _Extracted:
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].norm and _matches(lines[index].norm, stop_patterns):
            end = index
            break
    content_start = _heading_end(lines, start, question_field_id)
    text = _clean_content(lines, content_start, end)
    original = "\n".join(
        line.raw.strip() for line in lines[start:end] if line.raw.strip()
    ).strip()
    return _Extracted(text, original, _source_location(lines, start, end))


def _find_first(lines: list[_Line], patterns: tuple[str, ...]) -> int | None:
    return next(
        (index for index, line in enumerate(lines) if _matches(line.norm, patterns)),
        None,
    )


def _simple_section(field_id: str, extracted: _Extracted) -> MappedSection:
    status = STATUS_CONTENT_DETECTED if extracted.text else STATUS_EMPTY
    return MappedSection(
        target_sections=(EXPORT_FIELD_LABELS[field_id],),
        source_location=extracted.source_location,
        status=status,
        candidate_text=extracted.text,
        original_excerpt=extracted.original_excerpt,
    )


def _map_simple_field(lines: list[_Line], spec: FieldPattern) -> MappedField | None:
    start = _find_first(lines, spec.label_patterns)
    if start is None:
        return None
    extracted = _extract(lines, start, spec.stop_patterns, spec.question_field_id)
    section = _simple_section(spec.field_id, extracted)
    confidence = CONFIDENCE_FOUND if extracted.text else CONFIDENCE_UNCERTAIN
    return MappedField(
        field_id=spec.field_id,
        label=EXPORT_FIELD_LABELS[spec.field_id],
        extracted_text=extracted.text,
        confidence=confidence,
        source_location=extracted.source_location,
        mapping_status=section.status,
        sections=(section,),
    )


def _map_header_title(lines: list[_Line]) -> tuple[MappedField, str | None]:
    page_one = [
        (index, line) for index, line in enumerate(lines) if line.page in (None, 1)
    ]
    matches: list[tuple[int, str, str]] = []
    for position, (index, line) in enumerate(page_one):
        inline = re.match(r"^(.+?)\s*/\s*application$", line.raw.strip(), re.I)
        if inline and inline.group(1).strip():
            matches.append((index, inline.group(1).strip(), line.raw.strip()))
        if line.norm != "application":
            continue
        previous = position - 1
        while previous >= 0 and not page_one[previous][1].norm:
            previous -= 1
        if previous < 0:
            continue
        title_line = page_one[previous][1]
        if (
            title_line.norm
            and not _matches(title_line.norm, ALL_STRUCTURAL_HEADINGS)
            and 1 <= len(title_line.raw.strip()) <= 200
        ):
            matches.append(
                (
                    title_line.page or index,
                    title_line.raw.strip(),
                    f"{title_line.raw.strip()}\nApplication",
                )
            )
    unique = {(title, excerpt) for _, title, excerpt in matches}
    if len(unique) == 1:
        title, excerpt = next(iter(unique))
        section = MappedSection(
            target_sections=(EXPORT_FIELD_LABELS["INTRO.APP.NAME"],),
            source_location="Seite 1" if any(line.page == 1 for _, line in page_one) else None,
            status=STATUS_UNCERTAIN,
            candidate_text=title,
            original_excerpt=excerpt,
            review_note=(
                "Konservativ aus dem Dokumentkopf erkannt – bitte prüfen."
            ),
        )
        return (
            MappedField(
                field_id="INTRO.APP.NAME",
                label=EXPORT_FIELD_LABELS["INTRO.APP.NAME"],
                extracted_text=title,
                confidence=CONFIDENCE_UNCERTAIN,
                source_location=section.source_location,
                mapping_status=STATUS_UNCERTAIN,
                sections=(section,),
            ),
            "title_from_document_header",
        )
    section = MappedSection(
        target_sections=(EXPORT_FIELD_LABELS["INTRO.APP.NAME"],),
        source_location="Seite 1" if page_one else None,
        status=STATUS_UNCERTAIN,
        candidate_text="",
        original_excerpt="",
        review_note="Dokumentkopf nicht eindeutig – Titel bitte manuell prüfen.",
    )
    return (
        MappedField(
            field_id="INTRO.APP.NAME",
            label=EXPORT_FIELD_LABELS["INTRO.APP.NAME"],
            extracted_text="",
            confidence=CONFIDENCE_UNCERTAIN,
            source_location=section.source_location,
            mapping_status=STATUS_UNCERTAIN,
            sections=(section,),
        ),
        "title_header_ambiguous",
    )


def _mapped_subsection(lines: list[_Line], spec: SubsectionPattern) -> MappedSection | None:
    start = _find_first(lines, spec.start_patterns)
    if start is None:
        return None
    extracted = _extract(lines, start, spec.stop_patterns, spec.question_field_id)
    if spec.requires_manual_assignment:
        status = STATUS_UNCERTAIN
        note = (
            "Altangabe kann 4.5.2 oder 4.5.3 betreffen – fachlich zuordnen, "
            "keine FTO- oder IP-Schlussfolgerung."
        )
    elif spec.migration_version:
        status = STATUS_LEGACY_MIGRATED if extracted.text else STATUS_EMPTY
        note = "Aus älterer Innolink-Struktur migriert – fachlich prüfen."
    else:
        status = STATUS_CONTENT_DETECTED if extracted.text else STATUS_EMPTY
        note = None
    return MappedSection(
        target_sections=spec.target_sections,
        source_location=extracted.source_location,
        status=status,
        candidate_text=extracted.text,
        original_excerpt=extracted.original_excerpt,
        migration_version=spec.migration_version,
        requires_manual_assignment=spec.requires_manual_assignment,
        review_note=note,
    )


_TARGET_ORDER = {
    marker: index
    for index, marker in enumerate(
        (
            "3.1", "3.2", "3.3", "4.1", "4.2", "4.3", "4.4",
            "4.5.1", "4.5.2", "4.5.3", "4.5.4", "4.6",
        )
    )
}


def _map_composite(lines: list[_Line], field_id: str) -> MappedField | None:
    found: list[MappedSection] = []
    direct_targets: set[str] = set()
    for spec in (item for item in SUBSECTIONS if item.parent_field_id == field_id):
        section = _mapped_subsection(lines, spec)
        if section is None:
            continue
        if spec.migration_version and any(
            target in direct_targets for target in spec.target_sections
        ):
            continue
        found.append(section)
        if spec.migration_version is None:
            direct_targets.update(spec.target_sections)
    if not found:
        return None
    found.sort(key=lambda section: _TARGET_ORDER.get(section.target_sections[0], 999))
    blocks: list[str] = []
    for section in found:
        if (
            section.candidate_text
            and len(section.target_sections) == 1
            and not section.requires_manual_assignment
        ):
            blocks.extend((section.target_sections[0], section.candidate_text, ""))
    text = "\n".join(blocks).strip()
    migrated = any(section.migration_version for section in found)
    ambiguous = any(section.requires_manual_assignment for section in found)
    status = (
        STATUS_LEGACY_MIGRATED
        if migrated
        else STATUS_CONTENT_DETECTED if text else STATUS_EMPTY
    )
    confidence = (
        CONFIDENCE_UNCERTAIN
        if ambiguous or not text
        else CONFIDENCE_FOUND
    )
    pages = [section.source_location for section in found if section.source_location]
    return MappedField(
        field_id=field_id,
        label=EXPORT_FIELD_LABELS[field_id],
        extracted_text=text,
        confidence=confidence,
        source_location=pages[0] if len(set(pages)) == 1 else "Mehrere Seiten",
        mapping_status=status,
        sections=tuple(found),
    )


FIELDS: tuple[FieldPattern, ...] = (
    FieldPattern(
        "INTRO.APP.NAME",
        (r"^application name$", r"^application name \(", r"^projektname\b", r"^title\s*:$", r"^project title\b"),
        (*INTRO_LABEL_HEADINGS, *PORTAL_AREA_HEADINGS),
    ),
    FieldPattern(
        "INTRO.APP.NAME_EN",
        (r"^application name in english\b", r"^projektname englisch\b", r"^title in english\s*:?$"),
        (*INTRO_LABEL_HEADINGS, *PORTAL_AREA_HEADINGS),
    ),
    FieldPattern(
        "INTRO.APP.ABSTRACT",
        (r"^abstract\b",),
        (r"^management summary$", r"^executive summary\b", *PORTAL_AREA_HEADINGS),
    ),
    FieldPattern(
        "INTRO.APP.EXECUTIVE_SUMMARY",
        (r"^executive summary\b", r"^management summary$"),
        (
            r"^context$", r"^scientific integrity$",
            r"^intellectual property rights?$", *PORTAL_AREA_HEADINGS,
        ),
    ),
    FieldPattern(
        "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
        (r"^explanations and comments\b", r"^erläuterungen und kommentare\b"),
        (
            r"^main contacts$", r"^innovation mentor$",
            r"^(?:\d+\.?\s+)?value creation$", *PORTAL_AREA_HEADINGS,
        ),
    ),
    # Composite-Felder bleiben Teil von FIELDS, damit die bestehende 8-Feld-
    # Coverage-Invariante erhalten bleibt; ihre Details stehen in SUBSECTIONS.
    FieldPattern("VC.BUSINESS_TARGETS_MODEL.EDITOR", (r"^3\.1(?:\s|$)",), ()),
    FieldPattern("SOL.INNOVATION_SOLUTION.EDITOR", (r"^4\.1(?:\s|$)",), ()),
    FieldPattern(
        "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
        (r"^explanation$", r"^explanation \(", r"^erklärung\b"),
        (
            r"^risk management$", r"^salary costs$", r"^material costs$",
            r"^financial overview$", r"^project budget distribution\b",
            r"^project budget$", *PORTAL_AREA_HEADINGS,
        ),
    ),
)


def _numbered_stops(*markers: str, include_areas: bool = True) -> tuple[str, ...]:
    patterns = tuple(rf"^{marker.replace('.', r'\.')}(?:\s|$)" for marker in markers)
    return (*patterns, *PORTAL_AREA_HEADINGS) if include_areas else patterns


SUBSECTIONS: tuple[SubsectionPattern, ...] = (
    SubsectionPattern(
        "VC.BUSINESS_TARGETS_MODEL.EDITOR", ("3.1",), (r"^3\.1(?:\s|$)",),
        _numbered_stops("3.2", "3.3", "4.1"),
        "VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1",
    ),
    SubsectionPattern(
        "VC.BUSINESS_TARGETS_MODEL.EDITOR", ("3.2",), (r"^3\.2(?:\s|$)",),
        _numbered_stops("3.3", "4.1"),
        "VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_2",
    ),
    SubsectionPattern(
        "VC.BUSINESS_TARGETS_MODEL.EDITOR", ("3.3",), (r"^3\.3(?:\s|$)",),
        _numbered_stops("4.1"),
        "VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_3",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.1",), (r"^4\.1(?:\s|$)",),
        _numbered_stops("4.2", "4.3", "4.4", "4.5", "4.5.1", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_1",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.2",), (r"^4\.2(?:\s|$)",),
        _numbered_stops("4.3", "4.4", "4.5", "4.5.1", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_2",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.3",), (r"^4\.3(?:\s|$)",),
        _numbered_stops("4.4", "4.5", "4.5.1", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_3",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.4",), (r"^4\.4(?:\s|$)",),
        _numbered_stops("4.5", "4.5.1", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_4",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.1",), (r"^4\.5\.1(?:\s|$)",),
        _numbered_stops("4.5.2", "4.5.3", "4.5.4", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_5_1",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.2",), (r"^4\.5\.2(?:\s|$)",),
        _numbered_stops("4.5.3", "4.5.4", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_5_2",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.3",), (r"^4\.5\.3(?:\s|$)",),
        _numbered_stops("4.5.4", "4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_5_3",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.4",), (r"^4\.5\.4(?:\s|$)",),
        _numbered_stops("4.6"),
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_5_4",
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.6",), (r"^4\.6(?:\s|$)",),
        PORTAL_AREA_HEADINGS,
        "SOL.INNOVATION_SOLUTION.MANDATORY_4_6",
    ),
    # Älteres Innolink-Schema: IPR unter Introduction, Partner Suitability 4.5.
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.1",),
        (r"^was a patent search performed\b",),
        (*LEGACY_IP_QUESTION_HEADINGS, *PORTAL_AREA_HEADINGS),
        "INTRO.IP.PATENT_SEARCH", LEGACY_SCHEMA_MIGRATION_VERSION,
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.2", "4.5.3"),
        (r"^does the project require \(patent-?\)licen[cs][a-z]*(?:\(s\))?",),
        (*LEGACY_IP_QUESTION_HEADINGS, *PORTAL_AREA_HEADINGS),
        "INTRO.IP.PATENT_LICENCES", LEGACY_SCHEMA_MIGRATION_VERSION, True,
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.5.4",),
        (r"^have the project partners concluded a prior written agreement\b",),
        (*LEGACY_IP_QUESTION_HEADINGS, *PORTAL_AREA_HEADINGS),
        "INTRO.IP.PRIOR_WRITTEN_AGREEMENT", LEGACY_SCHEMA_MIGRATION_VERSION,
    ),
    SubsectionPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR", ("4.6",),
        (r"^4\.5\s+describe how the selected partners\b",),
        PORTAL_AREA_HEADINGS,
        None, LEGACY_SCHEMA_MIGRATION_VERSION,
    ),
)


# ---------------------------------------------------------------------------
# Strukturierte Kandidaten (separat von field_id-gebundenen Drafttexten)
# ---------------------------------------------------------------------------

_STRUCTURED_LABELS: dict[str, str] = {
    "project.title": "Projekttitel",
    "project.title_en": "Projekttitel (Englisch)",
    "project.start_date": "Projektstart",
    "project.end_date": "Projektende",
    "project.duration_months": "Projektdauer",
    "project.direct_total_project_costs_excluding_overhead": (
        "Direkte Projektkosten ohne Overhead"
    ),
    "project.implementation_own_contribution": "Eigenleistung Umsetzungspartner",
    "project.cash_contribution": "Barbeitrag",
    "project.total_requested_funding": "Beantragte Förderung ohne Overhead",
    "project.total_requested_funding_including_overhead": (
        "Beantragte Förderung inklusive Overhead"
    ),
    "answer.scientific_integrity": "Wissenschaftliche Integrität",
    "answer.management_hours": "Management-Stunden",
}

_PERSONNEL_QUESTION_IDS = (
    "ORG.INDEPENDENCE.PERSONNEL.EMPLOYEE_OVERLAP",
    "ORG.INDEPENDENCE.PERSONNEL.BOARD_ROLE",
    "ORG.INDEPENDENCE.PERSONNEL.OTHER_ROLE",
)
_FINANCIAL_QUESTION_IDS = (
    "ORG.INDEPENDENCE.FINANCIAL.EMPLOYEE_OWNERSHIP_CONFIRMATION",
    "ORG.INDEPENDENCE.FINANCIAL.LEGAL_ENTITY_OWNERSHIP_CONFIRMATION",
)
_SCIENTIFIC_QUESTION_ID = "SUM.SCIENTIFIC_INTEGRITY.SANCTION_QUESTION"

_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.I)
_PHONE_RE = re.compile(r"(?:\+|00)\d[\d\s()./-]{6,}")


def structured_label(target_key: str) -> str:
    if target_key.startswith("partner.research"):
        return "Forschungspartner"
    if target_key.startswith("partner.implementation"):
        return "Umsetzungspartner"
    return _STRUCTURED_LABELS.get(target_key, target_key)


def _location(line: _Line) -> str | None:
    return f"Seite {line.page}" if line.page is not None else None


def _strict_date(raw: str) -> str | None:
    cleaned = unicodedata.normalize("NFKC", raw).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _strict_number(raw: str, *, currency: bool = False) -> float | None:
    cleaned = unicodedata.normalize("NFKC", raw).strip()
    if currency:
        if re.search(r"[A-Za-z]", re.sub(r"(?i)chf", "", cleaned)):
            return None
        cleaned = re.sub(r"(?i)\bchf\b", "", cleaned).strip()
    elif re.search(r"[A-Za-z%]", cleaned):
        return None
    cleaned = cleaned.replace("’", "'").replace("`", "'")
    if not re.fullmatch(
        r"[+-]?(?:\d{1,3}(?:['\s]\d{3})+|\d+)(?:[.,]\d{1,2})?", cleaned
    ):
        return None
    compact = cleaned.replace("'", "").replace(" ", "")
    if "," in compact and "." not in compact:
        compact = compact.replace(",", ".")
    try:
        value = float(compact)
    except ValueError:
        return None
    return value if value >= 0 else None


def _display_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _scalar_value(
    lines: list[_Line], patterns: tuple[str, ...]
) -> tuple[str, _Line] | None:
    """Findet einen strikt gelabelten Einzelwert, inline oder in Folgezeile."""
    for index, line in enumerate(lines):
        raw = unicodedata.normalize("NFKC", line.raw).strip()
        for pattern in patterns:
            match = re.match(pattern, raw, re.I)
            if match is None:
                continue
            inline = (match.groupdict().get("value") or "").strip(" :-")
            if inline:
                return inline, line
            for following in lines[index + 1 : index + 7]:
                if not following.norm or following.norm in {"number:", "number"}:
                    continue
                if _matches(following.norm, PORTAL_AREA_HEADINGS):
                    break
                return following.raw.strip(), following
    return None


_QUESTION_ALIASES: dict[str, tuple[str, ...]] = {
    "ORG.INDEPENDENCE.FINANCIAL.EMPLOYEE_OWNERSHIP_CONFIRMATION": (
        "None of the employees involved in the project on the part of the research partners holds more than 20% shares in an involved implementation partner",
    ),
    "ORG.INDEPENDENCE.FINANCIAL.LEGAL_ENTITY_OWNERSHIP_CONFIRMATION": (
        "None of the research partners (legal person) holds more than 20% shares in an involved implementation partner",
    ),
}


def _question_tokens(line: str) -> list[str]:
    # Das ältere offizielle Schema schreibt «3 years», die Registry
    # «three years». Diese rein orthografische Variante bleibt exakt genug.
    return ["3" if token == "three" else token for token in _word_tokens(line)]


def _answer_marker(raw: str) -> bool | None:
    normalized = unicodedata.normalize("NFKC", raw).strip()
    if normalized.startswith(("☒", "☑", "✓")):
        return True
    if normalized.startswith("☐"):
        return False
    match = re.search(
        r"(?:^|[.?!)\]\s])(?P<answer>yes|no|checked|unchecked|true|false|x)\s*$",
        normalized,
        re.I,
    )
    if match is None:
        return None
    return match.group("answer").casefold() in {"yes", "checked", "true", "x"}


def _question_answer(lines: list[_Line], field_id: str) -> tuple[bool, _Line] | None:
    field_def = get_registry().portal_fields.get(field_id)
    if field_def is None:
        return None
    questions = (field_def.label_or_question, *_QUESTION_ALIASES.get(field_id, ()))
    for question in questions:
        expected = _question_tokens(question)
        if not expected:
            continue
        for start, line in enumerate(lines):
            consumed = _question_tokens(line.raw)
            if not consumed or consumed != expected[: len(consumed)]:
                continue
            index = start + 1
            while len(consumed) < len(expected) and index < len(lines):
                trial = consumed + _question_tokens(lines[index].raw)
                prefix_length = min(len(trial), len(expected))
                if trial[:prefix_length] != expected[:prefix_length]:
                    break
                consumed = trial
                index += 1
            if len(consumed) < len(expected) or consumed[: len(expected)] != expected:
                continue
            # Inline-Antworten («...? No») und Checkboxen sind in älteren
            # Exporten Teil derselben Textzeile.
            for answer_line in lines[start : index + 7]:
                answer = _answer_marker(answer_line.raw)
                if answer is not None:
                    return answer, answer_line
                if answer_line.norm and _matches(
                    answer_line.norm, ALL_STRUCTURAL_HEADINGS
                ):
                    break
    return None


def _safe_representative(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = _EMAIL_RE.sub("", raw)
    cleaned = _PHONE_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;-/")
    return cleaned or None


_PARTNER_FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "name": (
        r"^(?:name|selected organisation|organisation name)\s*:?\s*(?P<value>.*)$",
    ),
    "country": (r"^(?:country|country code)\s*:?\s*(?P<value>.*)$",),
    "department": (r"^department\s*:?\s*(?P<value>.*)$",),
    "industry": (r"^(?:industry|sector)\s*:?\s*(?P<value>.*)$",),
    "fte": (
        r"^(?:fte|total employees \(fte\) of the selected organisation)\s*:?\s*(?P<value>.*)$",
    ),
    "project_role": (r"^(?:project role|role in the project)\s*:?\s*(?P<value>.*)$",),
    "official_representative": (
        r"^official representative\s*:?\s*(?P<value>.*)$",
    ),
    "swiss_value_creation": (
        r"^(?:swiss value creation|value creation in switzerland)\s*:?\s*(?P<value>.*)$",
    ),
}


def _block_scalar(
    lines: list[_Line], start: int, end: int, patterns: tuple[str, ...]
) -> str | None:
    found = _scalar_value(lines[start:end], patterns)
    return found[0] if found else None


def _layout_cells(raw: str, starts: list[int]) -> list[str]:
    return [
        raw[start : starts[index + 1] if index + 1 < len(starts) else None].strip()
        for index, start in enumerate(starts)
    ]


def _join_layout_parts(parts: list[str]) -> str | None:
    value = re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()
    return value or None


def _independence_values(
    lines: list[_Line],
) -> tuple[list[tuple[bool, _Line] | None], list[tuple[bool, _Line] | None]]:
    return (
        [_question_answer(lines, item) for item in _PERSONNEL_QUESTION_IDS],
        [_question_answer(lines, item) for item in _FINANCIAL_QUESTION_IDS],
    )


def _layout_partner_candidates(
    layout_lines: list[_Line],
    answer_lines: list[_Line],
    financial_comment: str | None,
) -> list[MappedStructuredCandidate]:
    """Liest die spaltenbasierte Organisations-Tabelle älterer Digital-PDFs.

    Die Spaltengrenzen stammen ausschließlich aus den exportierten
    Tabellenüberschriften. Die Kontaktspalte wird bewusst nie in einen
    Kandidaten übernommen.
    """
    role_headings: list[tuple[int, str]] = []
    for index, line in enumerate(layout_lines):
        if re.fullmatch(r"research partners?", line.norm):
            role_headings.append((index, "research"))
        elif re.fullmatch(r"implementation partners?", line.norm):
            role_headings.append((index, "implementation"))
    if not role_headings:
        return []

    personnel_values, financial_values = _independence_values(answer_lines)
    personnel_confirmed = all(
        item is not None and item[0] is False for item in personnel_values
    )
    financial_confirmed = all(
        item is not None and item[0] is True for item in financial_values
    )
    personnel_status = "confirmed" if personnel_confirmed else "needs_input"
    financial_status = "confirmed" if financial_confirmed else "needs_input"

    candidates: list[MappedStructuredCandidate] = []
    ordinals = {"research": 0, "implementation": 0}
    for role_position, (heading_index, role) in enumerate(role_headings):
        end = (
            role_headings[role_position + 1][0]
            if role_position + 1 < len(role_headings)
            else len(layout_lines)
        )
        for index in range(heading_index + 1, end):
            if layout_lines[index].norm in {"main contacts", "innovation mentor"}:
                end = index
                break
        header_index = next(
            (
                index
                for index in range(heading_index + 1, end)
                if "contract party" in layout_lines[index].norm
                and (
                    (role == "research" and "research center" in layout_lines[index].norm)
                    or (role == "implementation" and "start-up" in layout_lines[index].norm)
                )
            ),
            None,
        )
        if header_index is None:
            continue
        header = layout_lines[header_index].raw
        if role == "research":
            starts = [
                header.casefold().find("contract party"),
                header.casefold().find("research center"),
                header.casefold().find("department"),
                header.casefold().find("organisation"),
                header.casefold().find("contact"),
            ]
        else:
            starts = [
                header.casefold().find("contract party"),
                header.casefold().find("start-up"),
                header.casefold().find("total"),
                header.casefold().find("industry"),
                header.casefold().find("organisation"),
                header.casefold().find("contact"),
            ]
        if any(start < 0 for start in starts) or starts != sorted(starts):
            continue

        rows: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line_index in range(header_index + 2, end):
            line = layout_lines[line_index]
            if re.match(r"^\d+[.]\d+.*\s+-\s+", line.norm):
                continue  # wiederholter Dokumentkopf nach Seitenumbruch
            cells = _layout_cells(line.raw, starts)
            if role == "research":
                # Fortsetzungszeilen enthalten ebenfalls Name und Typ. Der
                # Vertreter steht dagegen nur in der ersten Tabellenzeile
                # eines neuen Partners und bildet die konservative Zeilengrenze.
                is_start = bool(cells[0] and cells[1] and cells[3])
            else:
                # Folgeseiten können die Spalten um wenige Zeichen verschieben.
                # Start-up und FTE sind zwei explizite Spalten und grenzen eine
                # neue Zeile ohne fuzzy Namensabgleich eindeutig ab.
                implementation_start = re.match(
                    r"^(?P<name>.+?)\s{2,}(?P<startup>yes|no)\s{2,}"
                    r"(?P<fte>\d+(?:[.,]\d+)?)\s{2,}(?P<industry>.*?)"
                    r"(?:\s{2,}(?P<representative>\S.*))?$",
                    line.raw.strip(),
                    re.I,
                )
                is_start = implementation_start is not None
            if is_start:
                if current is not None:
                    rows.append(current)
                current = {
                    "start_line": line,
                    "name": [],
                    "department": [],
                    "industry": [],
                    "representative": [],
                    "fte": None,
                }
                if role == "implementation" and implementation_start is not None:
                    current["name"].append(implementation_start.group("name"))
                    current["fte"] = _strict_number(implementation_start.group("fte"))
                    if implementation_start.group("industry"):
                        current["industry"].append(
                            implementation_start.group("industry")
                        )
                    if implementation_start.group("representative"):
                        current["representative"].append(
                            implementation_start.group("representative")
                        )
                    continue
            if current is None:
                continue
            if cells[0]:
                current["name"].append(cells[0])
            if role == "research":
                if cells[2]:
                    current["department"].append(cells[2])
                if cells[3]:
                    current["representative"].append(cells[3])
            else:
                if cells[2] and current["fte"] is None:
                    current["fte"] = _strict_number(cells[2])
                if cells[3]:
                    current["industry"].append(cells[3])
                if cells[4]:
                    current["representative"].append(cells[4])
        if current is not None:
            rows.append(current)

        for row in rows:
            name = _join_layout_parts(row["name"])
            if not name:
                continue
            ordinals[role] += 1
            representative = _safe_representative(
                _join_layout_parts(row["representative"])
            )
            payload: dict[str, Any] = {
                "name": name,
                "partner_type": f"{role}_partner",
                "project_role": None,
                "country": None,
                "department": _join_layout_parts(row["department"]),
                "industry": _join_layout_parts(row["industry"]),
                "fte": (
                    _display_number(row["fte"])
                    if isinstance(row["fte"], float)
                    else None
                ),
                "swiss_value_creation": None,
                "official_representative": (
                    {"display_name": representative} if representative else None
                ),
                "personnel_independence_status": personnel_status,
                "financial_independence_status": financial_status,
                "review_comment": (
                    financial_comment
                    if not personnel_confirmed or not financial_confirmed
                    else None
                ),
                "personnel_answers": [
                    item[0] if item else None for item in personnel_values
                ],
                "financial_confirmations": [
                    item[0] if item else None for item in financial_values
                ],
            }
            # Das ältere Tabellenformat enthält kein explizites Land. Eine
            # Schweizer Eignung wird daraus nie gefolgert; der Kandidat bleibt
            # deshalb bearbeitungspflichtig.
            candidates.append(
                MappedStructuredCandidate(
                    candidate_kind="partner",
                    target_key=f"partner.{role}.{ordinals[role]:02d}",
                    payload_json=payload,
                    confidence=CONFIDENCE_UNCERTAIN,
                    source_location=_location(row["start_line"]),
                )
            )
    return candidates


def _partner_candidates(
    lines: list[_Line], financial_comment: str | None
) -> list[MappedStructuredCandidate]:
    region_start = _find_first(
        lines, (r"^(?:\d+\.?\s+)?organisations?(?: and |\s*&\s*)people$",)
    )
    if region_start is None:
        return []
    region_end = len(lines)
    for index in range(region_start + 1, len(lines)):
        if _matches(
            lines[index].norm,
            (
                r"^independence of research and implementation partners$",
                r"^personnel independence$",
                r"^main contacts$",
                r"^innovation mentor$",
                r"^(?:\d+\.?\s+)?value creation$",
            ),
        ):
            region_end = index
            break

    role_starts: list[tuple[int, str]] = []
    for index in range(region_start + 1, region_end):
        match = re.match(
            r"^(research|implementation) partner(?:\s+\d+)?\s*:?$",
            lines[index].norm,
        )
        if match:
            role_starts.append((index, match.group(1)))

    personnel_values, financial_values = _independence_values(lines)
    personnel_confirmed = all(item is not None and item[0] is False for item in personnel_values)
    financial_confirmed = all(item is not None and item[0] is True for item in financial_values)
    personnel_status = "confirmed" if personnel_confirmed else "needs_input"
    financial_status = "confirmed" if financial_confirmed else "needs_input"

    result: list[MappedStructuredCandidate] = []
    ordinals = {"research": 0, "implementation": 0}
    for role_index, (start, role) in enumerate(role_starts):
        end = role_starts[role_index + 1][0] if role_index + 1 < len(role_starts) else region_end
        name_positions = [
            index
            for index in range(start + 1, end)
            if any(re.match(pattern, lines[index].raw.strip(), re.I) for pattern in _PARTNER_FIELD_PATTERNS["name"])
        ]
        row_starts = name_positions or [start]
        for row_index, row_start in enumerate(row_starts):
            row_end = row_starts[row_index + 1] if row_index + 1 < len(row_starts) else end
            name = _block_scalar(lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["name"])
            if name is None and row_start == start:
                # Konservativer Fallback nur direkt nach einem eindeutigen Rollen-Heading.
                for candidate_line in lines[start + 1 : min(start + 4, row_end)]:
                    if candidate_line.norm and not _matches(candidate_line.norm, ALL_STRUCTURAL_HEADINGS):
                        name = candidate_line.raw.strip()
                        break
            if not name:
                continue
            ordinals[role] += 1
            country = _block_scalar(lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["country"])
            fte_raw = _block_scalar(lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["fte"])
            fte = _strict_number(fte_raw) if fte_raw else None
            swiss_raw = _block_scalar(
                lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["swiss_value_creation"]
            )
            swiss_value = None
            if swiss_raw and _normalize(swiss_raw) in {"yes", "true", "confirmed"}:
                swiss_value = True
            elif swiss_raw and _normalize(swiss_raw) in {"no", "false"}:
                swiss_value = False
            representative = _safe_representative(
                _block_scalar(
                    lines,
                    row_start,
                    row_end,
                    _PARTNER_FIELD_PATTERNS["official_representative"],
                )
            )
            payload: dict[str, Any] = {
                "name": name,
                "partner_type": f"{role}_partner",
                "project_role": _block_scalar(
                    lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["project_role"]
                ),
                "country": country,
                "department": _block_scalar(
                    lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["department"]
                ),
                "industry": _block_scalar(
                    lines, row_start, row_end, _PARTNER_FIELD_PATTERNS["industry"]
                ),
                "fte": _display_number(fte) if fte is not None else None,
                "swiss_value_creation": swiss_value,
                "official_representative": (
                    {"display_name": representative} if representative else None
                ),
                "personnel_independence_status": personnel_status,
                "financial_independence_status": financial_status,
                "review_comment": (
                    financial_comment
                    if not personnel_confirmed or not financial_confirmed
                    else None
                ),
                "personnel_answers": [item[0] if item else None for item in personnel_values],
                "financial_confirmations": [item[0] if item else None for item in financial_values],
            }
            complete_review = (
                personnel_confirmed
                and financial_confirmed
                or bool((financial_comment or "").strip())
            )
            confidence = (
                CONFIDENCE_FOUND
                if (
                    complete_review
                    and bool((country or "").strip())
                    and (fte_raw is None or fte is not None)
                )
                else CONFIDENCE_UNCERTAIN
            )
            result.append(
                MappedStructuredCandidate(
                    candidate_kind="partner",
                    target_key=f"partner.{role}.{ordinals[role]:02d}",
                    payload_json=payload,
                    confidence=confidence,
                    source_location=_source_location(lines, row_start, row_end),
                )
            )
    return result


def _project_duration_candidates(lines: list[_Line]) -> list[MappedStructuredCandidate]:
    heading = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"project duration\s*:? ?", line.norm)
        ),
        None,
    )
    if heading is None:
        return []
    region = lines[heading + 1 : heading + 10]
    specs = (
        ("project.start_date", r"^start\s*:\s*(?P<value>.+)$", "date"),
        ("project.end_date", r"^end\s*:\s*(?P<value>.+)$", "date"),
        (
            "project.duration_months",
            r"^duration\s*:\s*\(?(?P<value>\d+)\s*(?:m|months?|monate)?\)?$",
            "duration",
        ),
    )
    result: list[MappedStructuredCandidate] = []
    for target_key, pattern, kind in specs:
        for line in region:
            match = re.match(pattern, line.raw.strip(), re.I)
            if match is None:
                continue
            raw = match.group("value").strip()
            value: Any = _strict_date(raw) if kind == "date" else int(raw)
            result.append(
                MappedStructuredCandidate(
                    "project_metadata",
                    target_key,
                    {target_key.removeprefix("project."): value},
                    CONFIDENCE_FOUND,
                    _location(line),
                )
            )
            break
    return result


def _structured_scalar_candidates(
    lines: list[_Line], mapped: dict[str, MappedField]
) -> list[MappedStructuredCandidate]:
    result = _project_duration_candidates(lines)

    # Der unbeschriftete Haupttitel übernimmt bewusst die konservative
    # Dokumentkopf-Erkennung des narrativen Mappings. Der englische Titel hat
    # dagegen ein eigenes Portal-Label: als strukturierter Einzelwert darf er
    # nie bis zum nächsten narrativen Exportanker weiterlaufen.
    title = mapped.get("INTRO.APP.NAME")
    if title and title.extracted_text:
        result.append(
            MappedStructuredCandidate(
                "project_metadata",
                "project.title",
                {"title": title.extracted_text},
                title.confidence,
                title.source_location,
            )
        )
    title_en = _scalar_value(
        lines,
        (r"^(?:title in english|english title)\s*:?\s*(?P<value>.*)$",),
    )
    if title_en is not None:
        raw_title_en, title_en_line = title_en
        result.append(
            MappedStructuredCandidate(
                "project_metadata",
                "project.title_en",
                {"title_en": raw_title_en},
                CONFIDENCE_FOUND,
                _location(title_en_line),
            )
        )

    scalar_specs = (
        (
            "project.start_date",
            "project_metadata",
            (
                r"^(?:project start date|project start)\s*:?\s*(?P<value>.*)$",
            ),
            "date",
        ),
        (
            "project.end_date",
            "project_metadata",
            (r"^(?:project end date|project end)\s*:?\s*(?P<value>.*)$",),
            "date",
        ),
        (
            "project.duration_months",
            "project_metadata",
            (r"^project duration\s*:?\s*(?P<value>.*)$",),
            "duration",
        ),
        (
            "project.total_requested_funding_including_overhead",
            "budget",
            (
                r"^requested innosuisse funding\s+(?:incl\.?|including)\s+overhead\s*:?\s*(?P<value>.*)$",
                r"^total requested funding\s+(?:incl\.?|including)\s+overhead\s*:?\s*(?P<value>.*)$",
            ),
            "currency",
        ),
        (
            "project.direct_total_project_costs_excluding_overhead",
            "budget",
            (
                r"^(?:direct\s+)?total project costs\s+(?:excl\.?|excluding|without)\s+overhead\s*:?\s*(?P<value>.*)$",
                r"^direct project costs\s+(?:excl\.?|excluding|without)\s+overhead\s*:?\s*(?P<value>.*)$",
            ),
            "currency",
        ),
        (
            "project.implementation_own_contribution",
            "budget",
            (
                # \b: Spaltenüberschriften wie «… Contributions» sind KEIN
                # gelabelter Einzelwert (sie lieferten sonst «s» als Wert).
                r"^(?:implementation partner\s+)?own contribution\b\s*:?\s*(?P<value>.*)$",
            ),
            "currency",
        ),
        (
            "project.cash_contribution",
            "budget",
            (r"^cash contribution\b\s*:?\s*(?P<value>.*)$",),
            "currency",
        ),
        (
            "project.total_requested_funding",
            "budget",
            (
                r"^requested innosuisse funding(?!.*(?:incl|including).*overhead)\s*:?\s*(?P<value>.*)$",
                r"^total requested funding(?!.*(?:incl|including).*overhead)\s*:?\s*(?P<value>.*)$",
            ),
            "currency",
        ),
    )
    existing_targets = {item.target_key for item in result}
    for target_key, kind, patterns, value_type in scalar_specs:
        if target_key in existing_targets:
            continue
        found = _scalar_value(lines, patterns)
        if found is None:
            continue
        raw, source_line = found
        value: Any = None
        if value_type == "date":
            value = _strict_date(raw)
        elif value_type == "duration":
            duration_match = re.fullmatch(r"(\d+)\s*(?:months?|monate)?", raw.strip(), re.I)
            value = int(duration_match.group(1)) if duration_match and int(duration_match.group(1)) > 0 else None
        else:
            numeric = _strict_number(raw, currency=True)
            value = _display_number(numeric) if numeric is not None else None
        field_name = target_key.removeprefix("project.")
        result.append(
            MappedStructuredCandidate(
                candidate_kind=kind,
                target_key=target_key,
                payload_json={field_name: value, "raw_value": raw} if value is None else {field_name: value},
                confidence=CONFIDENCE_FOUND if value is not None else CONFIDENCE_UNCERTAIN,
                source_location=_location(source_line),
            )
        )
    return result


def _scientific_candidate(lines: list[_Line]) -> MappedStructuredCandidate | None:
    answer = _question_answer(lines, _SCIENTIFIC_QUESTION_ID)
    if answer is None:
        return None
    value, source_line = answer
    # Der Kommentar wird nur im Antwortbereich der Integritätsfrage gesucht
    # (bis zum nächsten Struktur-Heading). «Explanations and Comments» der
    # Unabhängigkeit und «Explanation» der Planned Hours sind andere
    # Portalfelder und dürfen nie als Integritätskommentar erscheinen.
    answer_index = next(
        (index for index, line in enumerate(lines) if line is source_line), None
    )
    region: list[_Line] = []
    if answer_index is not None:
        for line in lines[answer_index + 1 :]:
            if line.norm and _matches(line.norm, ALL_STRUCTURAL_HEADINGS):
                break
            region.append(line)
    comment_match = _scalar_value(
        region,
        (
            r"^(?:scientific integrity )?(?:comment|explanation)\b\s*:?\s*(?P<value>.*)$",
        ),
    )
    comment = comment_match[0] if comment_match else None
    return MappedStructuredCandidate(
        candidate_kind="answer",
        target_key="answer.scientific_integrity",
        payload_json={"sanction_answer": value, "comment": comment},
        confidence=(
            CONFIDENCE_FOUND if value is False or bool((comment or "").strip())
            else CONFIDENCE_UNCERTAIN
        ),
        source_location=_location(source_line),
    )


def _layout_numeric_tokens(line: _Line) -> list[float]:
    values: list[float] = []
    for token in re.findall(r"(?<![\w])\d[\d'’.,]*(?![\w%])", line.raw):
        value = _strict_number(token, currency=True)
        if value is not None:
            values.append(value)
    return values


def _layout_financial_candidates(
    lines: list[_Line],
) -> list[MappedStructuredCandidate]:
    start = next(
        (index for index, line in enumerate(lines) if line.norm == "financial overview"),
        None,
    )
    if start is None:
        return []
    page = lines[start].page
    region = [
        line
        for line in lines[start + 1 :]
        if line.page == page and not line.norm.startswith("explanations regarding")
    ]
    found: dict[str, tuple[float, _Line]] = {}
    for index, line in enumerate(region):
        numbers = _layout_numeric_tokens(line)
        if line.norm.startswith("total implementation partners") and len(numbers) >= 2:
            found["project.cash_contribution"] = (numbers[0], line)
            found["project.implementation_own_contribution"] = (numbers[1], line)
        elif line.norm.startswith("total project costs") and numbers:
            found["project.direct_total_project_costs_excluding_overhead"] = (
                numbers[-1],
                line,
            )
        elif line.norm.startswith("total innosuisse contributions") and numbers:
            next_norm = region[index + 1].norm if index + 1 < len(region) else ""
            target = (
                "project.total_requested_funding_including_overhead"
                if "including overhead" in line.norm or next_norm == "including overhead"
                else "project.total_requested_funding"
            )
            found[target] = (numbers[-1], line)
    return [
        MappedStructuredCandidate(
            "budget",
            target,
            {target.removeprefix("project."): _display_number(value)},
            CONFIDENCE_FOUND,
            _location(line),
        )
        for target, (value, line) in found.items()
    ]


def _layout_management_candidate(
    lines: list[_Line],
) -> MappedStructuredCandidate | None:
    question_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.norm.startswith(
                "how many of the total planned hours are dedicated to project management activities"
            )
        ),
        None,
    )
    if question_index is None:
        return None
    management: float | None = None
    source_line = lines[question_index]
    for line in lines[question_index : question_index + 7]:
        match = re.search(
            r"(?:(?P<hours>\d[\d'’.,]*)\s+)?hours\s*\((?P<percent>\d+(?:[.,]\d+)?)%\)",
            line.raw,
            re.I,
        )
        if match is None:
            continue
        if match.group("hours"):
            management = _strict_number(match.group("hours"))
        elif float(match.group("percent").replace(",", ".")) == 0:
            management = 0.0
        source_line = line
        break
    if management is None:
        return None
    total: float | None = None
    for line in lines:
        if line.norm.startswith("total planned hours"):
            numbers = _layout_numeric_tokens(line)
            if numbers:
                total = numbers[-1]
                break
    return MappedStructuredCandidate(
        "answer",
        "answer.management_hours",
        {
            "management_hours": _display_number(management),
            "total_project_hours": _display_number(total) if total is not None else None,
        },
        CONFIDENCE_FOUND,
        _location(source_line),
    )


def _management_candidate(lines: list[_Line]) -> MappedStructuredCandidate | None:
    direct = _scalar_value(
        lines,
        (r"^(?:total )?management hours\s*:?\s*(?P<value>.*)$",),
    )
    total = _scalar_value(
        lines,
        (r"^total project hours\s*:?\s*(?P<value>.*)$",),
    )
    management_value = _strict_number(direct[0]) if direct else None
    total_value = _strict_number(total[0]) if total else None
    source_line = direct[1] if direct else None

    if management_value is None:
        for header_index, line in enumerate(lines):
            if "|" not in line.raw or "management" not in line.norm:
                continue
            management_sum = 0.0
            project_sum = 0.0
            rows = 0
            for row in lines[header_index + 1 :]:
                if row.norm.startswith("explanation") or _matches(
                    row.norm, (r"^salary costs$", r"^material costs$", r"^financial overview$")
                ):
                    break
                if "|" not in row.raw:
                    continue
                cells = [cell.strip() for cell in row.raw.split("|")]
                numbers = [_strict_number(cell) for cell in cells[1:]]
                if not numbers or any(number is None for number in numbers):
                    management_sum = -1
                    break
                rows += 1
                management_sum += numbers[-1] or 0
                project_sum += sum(number or 0 for number in numbers)
                source_line = row
            if rows and management_sum >= 0:
                management_value = management_sum
                total_value = project_sum
                break
    if management_value is None or source_line is None:
        return None
    payload: dict[str, Any] = {
        "management_hours": _display_number(management_value),
        "total_project_hours": (
            _display_number(total_value) if total_value is not None else None
        ),
    }
    return MappedStructuredCandidate(
        candidate_kind="answer",
        target_key="answer.management_hours",
        payload_json=payload,
        confidence=CONFIDENCE_FOUND,
        source_location=_location(source_line),
    )


def _structured_candidates(
    lines: list[_Line], layout_lines: list[_Line], mapped: dict[str, MappedField]
) -> list[MappedStructuredCandidate]:
    result = _structured_scalar_candidates(lines, mapped)

    # Gelabelte Skalare haben Vorrang — AUSSER ihr Wert liess sich nicht
    # streng parsen (value None): dann ersetzt der geparste Wert aus der
    # Financial-Overview-Tabelle den unbrauchbaren Kandidaten (nie zwei
    # Kandidaten pro target_key; Belegter SEDATE-Fall: Spaltenüberschrift
    # neben echter Tabellenzeile).
    def _parsed(item: MappedStructuredCandidate) -> bool:
        field_name = item.target_key.removeprefix("project.")
        return item.payload_json.get(field_name) is not None

    layout_by_target = {
        item.target_key: item
        for item in _layout_financial_candidates(layout_lines)
    }
    result = [
        item
        for item in result
        if _parsed(item) or item.target_key not in layout_by_target
    ]
    existing_targets = {item.target_key for item in result}
    result.extend(
        item
        for item in layout_by_target.values()
        if item.target_key not in existing_targets
    )
    financial = mapped.get("ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS")
    financial_comment = financial.extracted_text if financial else None
    layout_partners = _layout_partner_candidates(
        layout_lines, lines, financial_comment
    )
    result.extend(layout_partners or _partner_candidates(lines, financial_comment))
    scientific = _scientific_candidate(lines)
    if scientific:
        result.append(scientific)
    management = _management_candidate(lines) or _layout_management_candidate(
        layout_lines
    )
    if management:
        result.append(management)
    return result


def _apply_zero_management_text(
    mapped: dict[str, MappedField], structured: list[MappedStructuredCandidate]
) -> None:
    management = next(
        (item for item in structured if item.target_key == "answer.management_hours"),
        None,
    )
    if management is None or management.payload_json.get("management_hours") != 0:
        return
    field_id = "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"
    existing = mapped.get(field_id)
    if existing is not None and existing.extracted_text.strip():
        return
    total = management.payload_json.get("total_project_hours")
    text = (
        f"No project-management hours are planned (0 of {total} hours)."
        if total is not None
        else "No project-management hours are planned (0 hours)."
    )
    section = MappedSection(
        target_sections=(EXPORT_FIELD_LABELS[field_id],),
        source_location=management.source_location,
        status=STATUS_UNCERTAIN,
        candidate_text=text,
        original_excerpt=(
            existing.sections[0].original_excerpt
            if existing is not None and existing.sections
            else ""
        ),
        review_note=(
            "Aus bestätigungsbedürftigen strukturierten 0 Management-Stunden "
            "abgeleitet; Sprache und Wortlaut prüfen."
        ),
    )
    mapped[field_id] = MappedField(
        field_id=field_id,
        label=EXPORT_FIELD_LABELS[field_id],
        extracted_text=text,
        confidence=CONFIDENCE_UNCERTAIN,
        source_location=management.source_location,
        mapping_status=STATUS_UNCERTAIN,
        sections=(section,),
    )


def map_parse_result(
    result: ParseResult, *, include_structured: bool = False
) -> MappingResult:
    """Mappt ein bereits geparstes Dokument auf unterstützte Draft-Felder."""
    if result.needs_manual_input:
        return MappingResult(warnings=list(result.warnings), needs_manual_input=True)

    lines = _lines_with_pages(result)
    layout_lines = _layout_lines_with_pages(result)
    mapped: dict[str, MappedField] = {}
    warnings = list(result.warnings)
    for spec in FIELDS:
        if spec.field_id.endswith(".EDITOR"):
            field_result = _map_composite(lines, spec.field_id)
        else:
            field_result = _map_simple_field(lines, spec)
        if field_result is not None:
            mapped[spec.field_id] = field_result

    # Ein gelabelter Titel hat Vorrang; nur sonst den Dokumentkopf prüfen.
    if "INTRO.APP.NAME" not in mapped:
        title, warning = _map_header_title(lines)
        mapped[title.field_id] = title
        if warning:
            warnings.append(warning)

    structured = (
        _structured_candidates(lines, layout_lines, mapped)
        if include_structured
        else []
    )
    if structured:
        _apply_zero_management_text(mapped, structured)
    ordered = [mapped[spec.field_id] for spec in FIELDS if spec.field_id in mapped]
    return MappingResult(
        fields=ordered, structured_candidates=structured, warnings=warnings
    )


def map_document(source_type: str, data: bytes) -> MappingResult:
    """Parst fail-closed wie jede andere Quelle und mappt das Dokument."""
    return map_parse_result(
        parse(source_type, data), include_structured=source_type == "pdf"
    )
