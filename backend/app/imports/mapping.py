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
from functools import lru_cache

from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.ingestion.parsers import ParseResult, parse
from app.registry.loader import get_registry


MAPPING_VERSION = "innolink-narrative-v2"
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


@dataclass
class MappingResult:
    fields: list[MappedField] = field(default_factory=list)
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


def map_parse_result(result: ParseResult) -> MappingResult:
    """Mappt ein bereits geparstes Dokument auf unterstützte Draft-Felder."""
    if result.needs_manual_input:
        return MappingResult(warnings=list(result.warnings), needs_manual_input=True)

    lines = _lines_with_pages(result)
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

    ordered = [mapped[spec.field_id] for spec in FIELDS if spec.field_id in mapped]
    return MappingResult(fields=ordered, warnings=warnings)


def map_document(source_type: str, data: bytes) -> MappingResult:
    """Parst fail-closed wie jede andere Quelle und mappt das Dokument."""
    return map_parse_result(parse(source_type, data))
