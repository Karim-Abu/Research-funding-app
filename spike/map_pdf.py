"""SPIKE: Machbarkeit "begonnenes Innolink-PDF importieren" — deterministisch, kein LLM.

Extrahiert Text mit pypdf (gleiche Library wie backend/app/ingestion/parsers.py,
Logik hier bewusst dupliziert statt importiert — Spike-Regel: kein Import aus
backend/app) und mappt Textblöcke per Label-/Synonymliste auf die 8 vom MVP
unterstützten M6-Felder. Misst die Mapping-Quote gegen fixtures/ground_truth.json.

R3.GATE-Iteration (2026-07-07): Nachtest mit einem echten Portal-Export (lokal,
nicht versioniert) zeigte abweichendes Label-Vokabular gegenüber dem synthetischen
Fixture: `Title in English:`-Kurzlabels, `Management summary` statt `Executive
summary`, Kapitel im Format `N. Name`, nummerierte Hauptfragen (3.1/4.1) statt
Sektions-Headings, `Please note`-Hinweise und Seitenköpfe mit `n/m`-Paginierung.
Die Patterns unten decken beide Vokabulare ab; die synthetische Regression
(8/8 gegen ground_truth.json) bleibt Pflicht.

Aufruf:  python spike/map_pdf.py [pfad/zum.pdf]
         (Default: spike/fixtures/innolink_sample.pdf; bei fremden PDFs wird ohne
         Ground Truth nur die Anker-/Konfidenz-Tabelle gedruckt — die Bewertung
         correct/partial/… erfolgt manuell im Gate-Report.)
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

SPIKE_DIR = Path(__file__).parent
DEFAULT_PDF = SPIKE_DIR / "fixtures" / "innolink_sample.pdf"
GROUND_TRUTH = SPIKE_DIR / "fixtures" / "ground_truth.json"

# ---------------------------------------------------------------------------
# Die 8 M6-Felder mit Erkennungsmustern. Quelle der Labels:
# final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml
# (label_or_question + portal_section/subsection). Synonyme decken die im
# Portal sichtbaren Kurzformen ab. Reihenfolge = Registry-Reihenfolge.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldPattern:
    field_id: str
    # Regexes (case-insensitive, auf normalisierte Zeile) — Zeile gilt als
    # Label-Überschrift dieses Felds, wenn eines matcht.
    label_patterns: tuple[str, ...]
    # Editor-Felder: Inhalt beginnt bei nummerierten Hauptfragen (z. B. 3.1);
    # None = normales Textfeld, Inhalt = Folgezeilen bis zum nächsten Anker.
    section_hint: str | None = None


FIELDS: tuple[FieldPattern, ...] = (
    FieldPattern(
        "INTRO.APP.NAME",
        # Echte Portal-Exporte können den Haupttitel ganz ohne Label führen
        # (Nachtest R3.GATE) — dann bleibt das Feld ehrlich "nicht gefunden".
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
        # Portal-Export führt keinen Editor-Heading; Kapitel 3 (Value Creation)
        # beginnt inhaltlich mit der nummerierten Hauptfrage 3.1.
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
    r"^\d{1,3}/\d{1,3}$",  # nackte Paginierung (Seitenkopf ueber 2 Zeilen gebrochen)
    r"^\d{3}\.\d{3}\b",  # laufender Seitenkopf mit Antragsnummer (NNN.NNN …)
)

# Sektionen (h1/h2) als Content-Stopper.
SECTION_PATTERNS = (
    r"^\d+\s+(introduction|organisations?\s*&\s*people|value creation|solution|project setup)$",
    # Portal-Export: Kapitel im Format "N. Name" (Nachtest R3.GATE).
    r"^\d+\.\s+(introduction|organisations( and |\s*&\s*)people|value creation|solution|project setup)$",
    r"^application name and abstract$",
    r"^independence of research and implementation partners$",
    r"^business targets\s*&\s*business model$",
    r"^innovation solution$",
    r"^planned hours$",
    r"^total planned hours\b",
    r"^project budget distribution\b",
    r"^project budget$",  # dasselbe Heading, vom Export ueber 2 Zeilen gebrochen
    r"^explanations regarding\b",
)

# Kurzes Metadaten-Label mit Doppelpunkt ("project duration:") beendet den
# Inhalt eines KURZfelds (Titel u. ä.). In Editor-Blöcken sind Doppelpunkt-
# Zeilen normale Aufzählungen im Fliesstext — dort gilt dieser Stopper nicht.
SHORT_FIELD_STOP = r"^[a-z][a-z /()&-]{2,40}:$"


def normalize(line: str) -> str:
    text = unicodedata.normalize("NFKC", line).strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def is_noise(norm: str) -> bool:
    return any(re.search(p, norm) for p in NOISE_PATTERNS)


def is_section(norm: str) -> bool:
    return any(re.match(p, norm) for p in SECTION_PATTERNS)


def match_field(norm: str) -> FieldPattern | None:
    for fp in FIELDS:
        if any(re.match(p, norm) for p in fp.label_patterns):
            return fp
    return None


# ---------------------------------------------------------------------------
# Extraktion (pypdf, wie parse_pdf im Backend — dupliziert, nicht importiert)
# ---------------------------------------------------------------------------


def extract_lines(pdf_path: Path) -> tuple[list[str], list[str]]:
    from pypdf import PdfReader

    warnings: list[str] = []
    reader = PdfReader(io.BytesIO(pdf_path.read_bytes()))
    if reader.is_encrypted:
        return [], ["encrypted_pdf"]
    lines: list[str] = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — Spike: Befund festhalten, nicht crashen
            warnings.append(f"page_extract_failed:{index + 1}")
            continue
        lines.extend(text.splitlines())
    if not any(line.strip() for line in lines):
        warnings.append("no_extractable_text")
    return lines, warnings


# ---------------------------------------------------------------------------
# Mapping: Label-Anker finden, Folgezeilen bis zum nächsten Anker zuordnen.
# ---------------------------------------------------------------------------


@dataclass
class Mapped:
    field_id: str
    text: str
    label_line: int
    confidence: str  # "found" | "uncertain"


def map_fields(lines: list[str]) -> dict[str, Mapped]:
    anchors: list[tuple[int, FieldPattern]] = []
    for i, raw in enumerate(lines):
        norm = normalize(raw)
        if not norm:
            continue
        fp = match_field(norm)
        if fp and (fp.field_id not in {a[1].field_id for a in anchors}):
            anchors.append((i, fp))

    result: dict[str, Mapped] = {}
    for pos, (start, fp) in enumerate(anchors):
        end = anchors[pos + 1][0] if pos + 1 < len(anchors) else len(lines)
        content: list[str] = []
        for raw in lines[start + 1 : end]:
            norm = normalize(raw)
            if not norm or is_noise(norm):
                continue
            if is_section(norm):
                break
            if fp.section_hint != "editor" and re.match(SHORT_FIELD_STOP, norm):
                break
            content.append(raw.strip())
        text = "\n".join(content).strip()
        # Editor-Felder ohne nummerierte Hauptfrage → unsicher (Struktur fehlt).
        confidence = "found"
        if fp.section_hint == "editor" and not re.search(r"^\d\.\d\s", text, re.M):
            confidence = "uncertain"
        if not text:
            confidence = "uncertain"
        result[fp.field_id] = Mapped(fp.field_id, text, start, confidence)
    return result


# ---------------------------------------------------------------------------
# Messung gegen Ground Truth
# ---------------------------------------------------------------------------


def evaluate(mapped: dict[str, Mapped], truth: dict) -> dict:
    rows = []
    correct = 0
    present_total = 0
    for fp in FIELDS:
        gt = truth["fields"].get(fp.field_id, {})
        present = bool(gt.get("present"))
        expected = gt.get("expected_prefix")
        got = mapped.get(fp.field_id)
        if present:
            present_total += 1
        if got is None:
            status = "nicht gefunden" if present else "korrekt abwesend"
        elif expected is None:
            # Feld vorhanden, aber leer: korrekt, wenn kein (falscher) Text.
            status = "korrekt (leer erkannt)" if not got.text else "falsch zugeordnet"
        elif got.text.startswith(expected):
            status = "korrekt"
        elif expected.split()[0].lower() in got.text.lower():
            status = "teilweise (Inhalt verschoben)"
        else:
            status = "falsch zugeordnet"
        if status.startswith("korrekt"):
            correct += 1
        rows.append(
            {
                "field_id": fp.field_id,
                "status": status,
                "confidence": got.confidence if got else "-",
                "chars": len(got.text) if got else 0,
            }
        )
    quote = correct / present_total if present_total else 0.0
    return {"rows": rows, "correct": correct, "present": present_total, "quote": quote}


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.is_file():
        print(f"FEHLER: PDF nicht gefunden: {pdf_path}")
        sys.exit(2)
    lines, warnings = extract_lines(pdf_path)
    print(f"PDF: {pdf_path.name} — {len(lines)} extrahierte Zeilen")
    if warnings:
        print(f"Warnungen: {', '.join(warnings)}")
    if not lines:
        print("Befund: keine extrahierbare Struktur — Mapping nicht möglich.")
        sys.exit(1)

    mapped = map_fields(lines)

    # Ground Truth existiert nur für die synthetischen Fixtures. Fremde PDFs
    # (z. B. der lokale R3.GATE-Nachtest) bekommen nur die Anker-/Konfidenz-
    # Tabelle — ohne Inhalte, die Bewertung erfolgt manuell im Gate-Report.
    known_fixtures = {DEFAULT_PDF.resolve(), (SPIKE_DIR / "fixtures" / "innolink_sample_degraded.pdf").resolve()}
    if pdf_path.resolve() not in known_fixtures:
        print()
        print(f"{'Feld':55} {'Anker':10} {'Konfidenz':10} Zeichen")
        for fp in FIELDS:
            got = mapped.get(fp.field_id)
            anchor = f"Zeile {got.label_line}" if got else "—"
            print(
                f"{fp.field_id:55} {anchor:10} "
                f"{(got.confidence if got else '-'):10} {len(got.text) if got else 0}"
            )
        print()
        print(
            "Keine Ground Truth für dieses PDF — Bewertung "
            "correct/partial/uncertain/missed/false-positive manuell "
            "(docs/evaluation/pdf-import-gate-report.md)."
        )
        return

    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    report = evaluate(mapped, truth)

    print()
    print(f"{'Feld':55} {'Status':28} {'Konfidenz':10} Zeichen")
    for row in report["rows"]:
        print(
            f"{row['field_id']:55} {row['status']:28} "
            f"{row['confidence']:10} {row['chars']}"
        )
    print()
    print(
        f"Mapping-Quote: {report['correct']}/{report['present']} "
        f"= {report['quote']:.0%}  (Abbruchkriterium: < 60 %)"
    )


if __name__ == "__main__":
    main()
