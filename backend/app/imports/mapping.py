"""Deterministisches Mapping «begonnener Innolink-Export → Portal-Felder» (R3.1).

Saubere Portierung von ``spike/map_pdf.py`` (Gate bestanden, siehe
``docs/evaluation/pdf-import-gate-report.md``): Label-/Synonym-Anker je Feld,
Noise-Filter für Portal-Rauschen, Sektions-Stopper für Blockgrenzen. Extraktion
läuft über ``app.ingestion.parsers.parse`` (gleiches fail-closed-Verhalten wie
jede andere Quelle — verschlüsselte/gescannte PDFs liefern nie Kandidaten).

Nur die 8 vom MVP unterstützten Felder (Deckung mit ``EXPORT_FIELD_LABELS``
wird testseitig erzwungen). Kein LLM, kein OCR. Ein leeres oder strukturell
unsicheres Feld wird als ``uncertain`` markiert — nie mit Fremdinhalt gefüllt
und nie automatisch übernehmbar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.ingestion.parsers import ParseResult, parse


@dataclass(frozen=True)
class FieldPattern:
    field_id: str
    # Regexes (case-insensitive, auf normalisierte Zeile) — Zeile gilt als
    # Label-Überschrift dieses Felds, wenn eines matcht.
    label_patterns: tuple[str, ...]
    # Editor-Felder: Inhalt beginnt bei nummerierten Hauptfragen (z. B. 3.1);
    # None = normales Textfeld, Inhalt = Folgezeilen bis zum nächsten Anker.
    section_hint: str | None = None


# Erkennungsmuster je Feld. Quelle der Labels: Registry (label_or_question)
# plus die im R3.GATE-Nachtest belegten Portal-Export-Varianten (Title-
# Kurzlabels, "Management summary", Hauptfragen 3.1/4.1 als Editor-Anker).
FIELDS: tuple[FieldPattern, ...] = (
    FieldPattern(
        "INTRO.APP.NAME",
        # Echte Portal-Exporte können den Haupttitel ganz ohne Label führen
        # (Gate-Report) — dann bleibt das Feld ehrlich ohne Kandidat.
        (
            r"^application name$", r"^application name \(", r"^projektname\b",
            r"^title\s*:$", r"^project title\b",
        ),
    ),
    FieldPattern(
        "INTRO.APP.NAME_EN",
        (
            r"^application name in english\b", r"^projektname englisch\b",
            r"^title in english\s*:?$",
        ),
    ),
    FieldPattern(
        "INTRO.APP.ABSTRACT",
        (r"^abstract\b",),
    ),
    FieldPattern(
        "INTRO.APP.EXECUTIVE_SUMMARY",
        (r"^executive summary\b", r"^management summary$"),
    ),
    FieldPattern(
        "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
        (r"^explanations and comments\b", r"^erläuterungen und kommentare\b"),
        section_hint="independence",
    ),
    FieldPattern(
        "VC.BUSINESS_TARGETS_MODEL.EDITOR",
        (
            r"^business targets\s*&\s*business model$",
            r"^business targets and business model$",
            r"^3\.1\s",
        ),
        section_hint="editor",
    ),
    FieldPattern(
        "SOL.INNOVATION_SOLUTION.EDITOR",
        (r"^innovation solution$", r"^4\.1\s"),
        section_hint="editor",
    ),
    FieldPattern(
        "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
        (r"^explanation$", r"^explanation \(", r"^erklärung\b"),
        section_hint="planned hours",
    ),
)

# Zeilen, die nie Feldinhalt sind (Portal-Rauschen).
NOISE_PATTERNS = (
    r"^characters:\s*\d+\s*/\s*\d+$",
    r"^open editor$",
    r"^confirmation .+:\s*(yes|no)$",
    r"^innosuisse innolink\b",
    r"^seite \d+$",
    r"-\s+seite\s+\d+$",
    r"^\d+\s*$",
    r"^[a-zäöü ]+\|.*\|",  # einfache Tabellenzeilen "a | b | c"
    r"^please note\b",  # Portal-Hinweistexte (kein Antragsinhalt)
    r"^.{0,80}\s\d{1,3}/\d{1,3}$",  # Seitenkopf/-fuss mit n/m-Paginierung
    r"^\d{1,3}/\d{1,3}$",  # nackte Paginierung (Seitenkopf über 2 Zeilen)
    r"^\d{3}\.\d{3}\b",  # laufender Seitenkopf mit Antragsnummer (NNN.NNN …)
)

# Sektionen (h1/h2) als Content-Stopper.
SECTION_PATTERNS = (
    r"^\d+\s+(introduction|organisations?\s*&\s*people|value creation|solution|project setup)$",
    # Portal-Export: Kapitel im Format "N. Name" (Gate-Nachtest).
    r"^\d+\.\s+(introduction|organisations( and |\s*&\s*)people|value creation|solution|project setup)$",
    r"^application name and abstract$",
    r"^independence of research and implementation partners$",
    r"^business targets\s*&\s*business model$",
    r"^innovation solution$",
    r"^planned hours$",
    r"^total planned hours\b",
    r"^project budget distribution\b",
    r"^project budget$",  # dasselbe Heading, vom Export über 2 Zeilen gebrochen
    r"^explanations regarding\b",
)

# Kurzes Metadaten-Label mit Doppelpunkt ("project duration:") beendet den
# Inhalt eines KURZfelds (Titel u. ä.). In Editor-Blöcken sind Doppelpunkt-
# Zeilen normale Aufzählungen im Fliesstext — dort gilt dieser Stopper nicht.
SHORT_FIELD_STOP = r"^[a-z][a-z /()&-]{2,40}:$"

CONFIDENCE_FOUND = "found"
CONFIDENCE_UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class MappedField:
    """Ein erkanntes Feld — Basis für einen ImportCandidate (decision=pending)."""

    field_id: str
    label: str
    extracted_text: str
    confidence: str  # CONFIDENCE_FOUND | CONFIDENCE_UNCERTAIN
    source_location: str | None  # z. B. "Seite 3"; None bei Textquellen


@dataclass
class MappingResult:
    fields: list[MappedField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # True = Dokument ohne extrahierbare Struktur (verschlüsselt/gescannt) —
    # fail-closed, keine Kandidaten, manuelle Eingabe nötig.
    needs_manual_input: bool = False


def _normalize(line: str) -> str:
    text = unicodedata.normalize("NFKC", line).strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _is_noise(norm: str) -> bool:
    return any(re.search(p, norm) for p in NOISE_PATTERNS)


def _is_section(norm: str) -> bool:
    return any(re.match(p, norm) for p in SECTION_PATTERNS)


def _match_field(norm: str) -> FieldPattern | None:
    for fp in FIELDS:
        if any(re.match(p, norm) for p in fp.label_patterns):
            return fp
    return None


def _lines_with_pages(result: ParseResult) -> list[tuple[int | None, str]]:
    lines: list[tuple[int | None, str]] = []
    for block in result.blocks:
        for raw in block.text.splitlines():
            lines.append((block.page, raw))
    return lines


def map_parse_result(result: ParseResult) -> MappingResult:
    """Mappt ein bereits geparstes Dokument auf die unterstützten Felder."""
    if result.needs_manual_input:
        return MappingResult(warnings=list(result.warnings), needs_manual_input=True)

    lines = _lines_with_pages(result)
    anchors: list[tuple[int, FieldPattern]] = []
    for i, (_, raw) in enumerate(lines):
        norm = _normalize(raw)
        if not norm:
            continue
        fp = _match_field(norm)
        if fp and (fp.field_id not in {a[1].field_id for a in anchors}):
            anchors.append((i, fp))

    mapped: list[MappedField] = []
    for pos, (start, fp) in enumerate(anchors):
        end = anchors[pos + 1][0] if pos + 1 < len(anchors) else len(lines)
        content: list[str] = []
        for _, raw in lines[start + 1 : end]:
            norm = _normalize(raw)
            if not norm or _is_noise(norm):
                continue
            if _is_section(norm):
                break
            if fp.section_hint != "editor" and re.match(SHORT_FIELD_STOP, norm):
                break
            content.append(raw.strip())
        text = "\n".join(content).strip()
        # Editor-Felder ohne nummerierte Hauptfrage → unsicher (Struktur fehlt).
        confidence = CONFIDENCE_FOUND
        if fp.section_hint == "editor" and not re.search(r"^\d\.\d\s", text, re.M):
            confidence = CONFIDENCE_UNCERTAIN
        if not text:
            confidence = CONFIDENCE_UNCERTAIN
        page = lines[start][0]
        mapped.append(
            MappedField(
                field_id=fp.field_id,
                label=EXPORT_FIELD_LABELS[fp.field_id],
                extracted_text=text,
                confidence=confidence,
                source_location=f"Seite {page}" if page is not None else None,
            )
        )
    return MappingResult(fields=mapped, warnings=list(result.warnings))


def map_document(source_type: str, data: bytes) -> MappingResult:
    """Parst (fail-closed wie jede Quelle) und mappt ein Dokument.

    ``ParserError`` (korrupte Datei) propagiert an den Aufrufer — eine kaputte
    Datei wird nie stillschweigend als «keine Felder» interpretiert.
    """
    return map_parse_result(parse(source_type, data))
