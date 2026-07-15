"""Erzeugt synthetische Innolink-artige Test-PDFs (spike/fixtures/*.pdf).

SPIKE-Werkzeug — ausschliesslich synthetische Daten (fiktive Projekte
"SmartGrid Optimizer" und "TERRAFLUX"). Kein reportlab o. ä.: bewusst ein
minimaler, handgeschriebener PDF-Writer (Helvetica, WinAnsi/cp1252), damit
keine neue Dependency nötig ist. Ein eigenes/echtes Test-PDF kann die Datei
einfach ersetzen; ground_truth.json muss dann angepasst werden.

Fixtures:
- innolink_sample.pdf           — narrativer 8-Feld-Golden-Path (SmartGrid).
- innolink_sample_degraded.pdf  — schlechte Extraktion (Zeilen verschmolzen).
- innolink_structured.pdf       — funktionale Abnahme (TERRAFLUX): leere
  Executive Summary, strukturierte Partner/Budget/Antworten, Management 0,
  Alt-Schema (IPR unter Introduction, 4.5 Partner-Eignung → 4.6).

Aufruf:  python spike/make_fixture.py
"""
from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# (style, text) — style: h1 = Sektion, h2 = Subsektion, label = Feldlabel,
# body = Inhalt, noise = Portal-Rauschen (Zeichenzähler, Hinweise).
Line = tuple[str, str]

STYLES = {
    "h1": ("F2", 14.0),
    "h2": ("F2", 11.5),
    "label": ("F2", 10.0),
    "body": ("F1", 10.0),
    "noise": ("F1", 8.5),
}

LINES: list[Line] = [
    ("h1", "1 Introduction"),
    ("h2", "Application Name and Abstract"),
    ("label", "Application name"),
    ("body", "SmartGrid Optimizer - Adaptive Lastprognose für Verteilnetze"),
    ("label", "Application Name in English"),
    ("noise", "Characters: 0/200"),
    ("label", "Abstract (wird in Aramis publiziert)"),
    ("noise", "Characters: 254/300"),
    ("body", "Das Projekt entwickelt eine adaptive Lastprognose für städtische"),
    ("body", "Verteilnetze. Durch selbstkalibrierende Modelle sinken Prognosefehler"),
    ("body", "um bis zu 30 Prozent, was Netzausbaukosten reduziert und die"),
    ("body", "Integration erneuerbarer Energien beschleunigt."),
    ("label", "Executive summary (wird nicht in Aramis publiziert)"),
    ("noise", "Characters: 812/2000"),
    ("body", "Verteilnetzbetreiber stehen vor stark schwankenden Lastprofilen durch"),
    ("body", "Photovoltaik, Wärmepumpen und Elektromobilität. Bestehende Prognose-"),
    ("body", "werkzeuge benötigen manuelle Nachkalibrierung und liefern in Quartieren"),
    ("body", "mit hoher PV-Dichte unzuverlässige Werte."),
    ("body", "Der SmartGrid Optimizer kombiniert physikalische Netzmodelle mit einem"),
    ("body", "lernenden Korrekturverfahren. Der Umsetzungspartner Netzwerk Stadt AG"),
    ("body", "bringt Messdaten aus zwei Pilotquartieren ein; die Hochschule liefert"),
    ("body", "die Modellarchitektur und Validierungsmethodik."),
    ("h1", "2 Organisations & People"),
    ("h2", "Independence of Research and Implementation Partners"),
    ("noise", "Confirmation personal independence: Yes"),
    ("noise", "Confirmation financial independence: No"),
    ("label", "Explanations and Comments"),
    ("noise", "Characters: 231/300"),
    ("body", "Die Netzwerk Stadt AG hält eine Minderheitsbeteiligung von 8 Prozent an"),
    ("body", "der Spin-off-Gesellschaft der Forschungsgruppe. Die Beteiligung hat"),
    ("body", "keinen Einfluss auf Projektentscheide; Governance-Massnahmen sind im"),
    ("body", "Konsortialvertrag geregelt."),
    ("h1", "3 Value Creation"),
    ("h2", "Business Targets & Business Model"),
    ("noise", "Open Editor"),
    ("body", "3.1 Which business targets do you pursue with this project?"),
    ("body", "Innerhalb von drei Jahren nach Projektende sollen 12 Verteilnetz-"),
    ("body", "betreiber die Lösung lizenzieren. Zielumsatz im dritten Jahr:"),
    ("body", "CHF 1.8 Mio. wiederkehrend aus SaaS-Lizenzen."),
    ("body", "3.2 What is your business model?"),
    ("body", "SaaS-Abonnement pro Netzgebiet, gestaffelt nach Anzahl Messpunkten."),
    ("body", "Vertrieb über bestehende Leittechnik-Integratoren als Partnerkanal."),
    ("h1", "4 Solution"),
    ("h2", "Innovation Solution"),
    ("noise", "Open Editor"),
    ("body", "4.1 What is the innovation in your solution?"),
    ("body", "Neu ist die Kopplung eines physikalischen Netzmodells mit einem"),
    ("body", "online lernenden Fehlerkorrektur-Modul, das ohne manuelle"),
    ("body", "Rekalibrierung auskommt und Konzeptdrift automatisch erkennt."),
    ("body", "4.2 What is the current state of the art?"),
    ("body", "Kommerzielle Werkzeuge nutzen statische Regressionsmodelle, die bei"),
    ("body", "hoher PV-Dichte systematisch abweichen und quartalsweise manuell"),
    ("body", "nachgeführt werden müssen."),
    ("h1", "5 Project Setup"),
    ("h2", "Planned Hours"),
    ("noise", "Partner | Research | Implementation | Management"),
    ("noise", "Hochschule | 2400 | 0 | 180"),
    ("noise", "Netzwerk Stadt AG | 0 | 1600 | 120"),
    ("label", "Explanation"),
    ("noise", "Characters: 176/1000"),
    ("body", "Die Management-Stunden verteilen sich auf Projektleitung (60 Prozent"),
    ("body", "Hochschule) und Koordination der Pilotquartiere (40 Prozent"),
    ("body", "Umsetzungspartner), entsprechend der Arbeitspaketverantwortung."),
]

# Funktionale Abnahme (Prompt B): unfertiger Antrag im ÄLTEREN Innolink-Schema
# mit strukturierten Angaben. Rein fiktives Projekt "TERRAFLUX" (Testdaten-
# Policy R0.4). Frage-Wortlaute entsprechen dem belegten älteren Export bzw.
# der Registry (siehe backend/app/imports/mapping.py und
# backend/tests/structured_import_fixture.py).
STRUCTURED_LINES: list[Line] = [
    ("noise", "Project Start Date: 01.03.2026"),
    ("noise", "Project End Date: 31.08.2027"),
    ("noise", "Project Duration: 18 months"),
    ("h1", "1 Introduction"),
    ("h2", "Application Name and Abstract"),
    ("label", "Application name"),
    ("body", "TERRAFLUX - Adaptive Bewässerungssteuerung für Stadtgrün"),
    ("label", "Title in English:"),
    ("body", "TERRAFLUX - Adaptive Irrigation Control for Urban Green"),
    ("label", "Abstract (wird in Aramis publiziert)"),
    ("noise", "Characters: 228/300"),
    ("body", "Das Projekt entwickelt eine adaptive Bewässerungssteuerung für"),
    ("body", "städtisches Grün. Sensorbasierte Bodenmodelle senken den"),
    ("body", "Wasserverbrauch um bis zu 25 Prozent und entlasten die"),
    ("body", "Betriebsteams der Stadtgärtnereien."),
    ("label", "Executive summary (wird nicht in Aramis publiziert)"),
    ("noise", "Characters: 0/2000"),
    ("h2", "Scientific Integrity"),
    (
        "body",
        "Has any staff member who will be collaborating on the application "
        "been severely sanctioned for violation of scientific integrity in "
        "the last three years?",
    ),
    ("body", "No"),
    ("h2", "Intellectual Property Rights"),
    (
        "body",
        "Was a patent search performed with or without IPI (Swiss Federal "
        "Institute for Intellectual Property)?",
    ),
    ("body", "Yes"),
    ("body", "Eine synthetische Recherche ergab zwei thematisch verwandte Dokumente."),
    (
        "body",
        "Does the project require (patent-)licencense(s)? If yes, please "
        "explain which background IP is needed for the project and the "
        "ownership of that background IP.",
    ),
    ("body", "No"),
    (
        "body",
        "Have the project partners concluded a prior written agreement "
        "regarding the assignement or exploitation of any research findings "
        "or patents?",
    ),
    ("body", "Yes"),
    ("body", "Ein Konsortialvertrag regelt die Verwertung der Ergebnisse."),
    ("h1", "2 Organisations & People"),
    ("h2", "Research Partner"),
    ("body", "Name: Nordlicht Institut für Angewandte Forschung"),
    ("body", "Country: CH"),
    ("body", "Department: Umweltsysteme"),
    ("body", "Industry: Research"),
    ("body", "FTE: 38"),
    ("body", "Official Representative: Robin Muster"),
    ("body", "Project Role: Modellentwicklung und Validierung"),
    ("h2", "Implementation Partner 1"),
    ("body", "Name: Voltaris AG"),
    ("body", "Country: CH"),
    ("body", "Department: Produktentwicklung"),
    ("body", "Industry: Sensorik"),
    ("body", "FTE: 74"),
    ("body", "Official Representative: Alex Beispiel"),
    ("body", "Project Role: Systemintegration und Pilotierung"),
    ("h2", "Implementation Partner 2"),
    ("body", "Name: Brimatec GmbH"),
    ("body", "Country: CH"),
    ("body", "Department: Betrieb"),
    ("body", "Industry: Gartenbau"),
    ("body", "FTE: 26"),
    ("body", "Official Representative: Kim Probe"),
    ("body", "Project Role: Pilotbetrieb in zwei Städten"),
    ("h2", "Independence of Research and Implementation Partners"),
    ("body", "Personnel Independence"),
    (
        "body",
        "Are any of the employees involved in the project on the part of a "
        "research partner also an employee of an implementation partner?",
    ),
    ("body", "No"),
    (
        "body",
        "Are any of the employees involved in the project on the part of the "
        "research partners a member of an involved implementation partner's "
        "executive board, supervisory board or scientific committee?",
    ),
    ("body", "No"),
    (
        "body",
        "Have any of the employees involved in the project on the part of "
        "the research partners been commissioned by an involved "
        "implementation partner to perform another role?",
    ),
    ("body", "No"),
    ("body", "Financial Independence"),
    (
        "body",
        "I confirm that none of the employees involved in the project on "
        "behalf of the research partners holds 20% or more of the ownership "
        "interest (e.g., shares) in any implementation partner",
    ),
    ("body", "Checked"),
    (
        "body",
        "I confirm that the research partner, as a legal entity, does not "
        "hold 20% or more of the ownership interest (e.g., shares) in any "
        "implementation partner",
    ),
    ("body", "Checked"),
    ("label", "Explanations and Comments"),
    ("noise", "Characters: 0/300"),
    ("h1", "3 Value Creation"),
    ("body", "3.1 Describe the business targets and the business model."),
    ("body", "Zielmodell ist ein Abo pro Grünfläche; nach drei Jahren sollen"),
    ("body", "zwölf Städte die Lösung im Regelbetrieb nutzen."),
    ("body", "3.2 Describe potential customers and how they are to be reached"),
    ("body", "Stadtgärtnereien und Facility-Betreiber werden über bestehende"),
    ("body", "Fachverbände und Pilotreferenzen erreicht."),
    (
        "body",
        "3.3 Does the planned project have a particular relevance to energy "
        "or ecological or social topics?",
    ),
    ("body", "Der reduzierte Wasserverbrauch entlastet städtische Ökosysteme."),
    ("h1", "4 Solution"),
    ("body", "4.1 Describe the state of the art that you intend to advance."),
    ("body", "Bestehende Steuerungen bewässern nach festen Zeitplänen ohne"),
    ("body", "Bodenfeuchtemodell."),
    (
        "body",
        "4.2 Describe the novelty of your solution (technology, product, "
        "business model or process, service)",
    ),
    ("body", "Neu ist die Kopplung eines Bodenfeuchtemodells mit selbstlernender"),
    ("body", "Ventilsteuerung je Grünfläche."),
    ("body", "4.3 Describe the quantifiable goals to reach."),
    ("body", "Wasserverbrauch minus 25 Prozent in zwei Pilotstädten."),
    ("body", "4.4 Describe the preliminary work already performed."),
    ("body", "Ein Laborprüfstand mit zwölf Ventilen wurde aufgebaut und vermessen."),
    (
        "body",
        "4.5 Describe how the selected partners are suited for the planned "
        "project.",
    ),
    ("body", "Forschung, Sensorik und Betrieb ergänzen sich ohne Überschneidung."),
    ("h1", "5 Project Setup"),
    ("h2", "Planned Hours"),
    ("noise", "Partner | Research | Implementation | Management"),
    ("noise", "Nordlicht Institut | 2400 | 0 | 0"),
    ("noise", "Voltaris AG | 0 | 1100 | 0"),
    ("noise", "Brimatec GmbH | 0 | 500 | 0"),
    ("label", "Explanation"),
    ("h2", "Financial Overview"),
    ("body", "Direct total project costs excluding overhead: CHF 200'000"),
    ("body", "Implementation Partner Own Contribution: CHF 105'000"),
    ("body", "Cash Contribution: CHF 13'000"),
    ("body", "Requested Innosuisse Funding: CHF 82'000"),
    ("body", "Requested Innosuisse Funding incl. Overhead: CHF 94'300"),
]

PAGE_HEADER = "Innosuisse Innolink - Innovationsprojekt (Entwurf)"
LINES_PER_PAGE = 34
PAGE_W, PAGE_H = 595, 842  # A4 in pt
MARGIN_X, TOP_Y, LEADING = 72, 780, 16


def _esc(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", rb"\\").replace(b"(", rb"\(").replace(b")", rb"\)")


def _content_stream(lines: list[Line], page_no: int) -> bytes:
    parts = [b"BT", f"{MARGIN_X} {TOP_Y} Td".encode(), f"{LEADING} TL".encode()]
    header = [("noise", f"{PAGE_HEADER}  -  Seite {page_no}"), ("noise", "")]
    for style, text in header + lines:
        font, size = STYLES.get(style, STYLES["body"])
        parts.append(f"/{font} {size} Tf".encode())
        parts.append(b"(" + _esc(text) + b") Tj T*")
    parts.append(b"ET")
    return b"\n".join(parts)


def build_pdf(all_lines: list[Line]) -> bytes:
    pages = [
        all_lines[i : i + LINES_PER_PAGE]
        for i in range(0, len(all_lines), LINES_PER_PAGE)
    ]
    # Objekte: 1 Catalog, 2 Pages, 3 F1, 4 F2, dann je Seite (Page, Content).
    objects: dict[int, bytes] = {
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>",
    }
    page_ids = []
    next_id = 5
    for page_no, page_lines in enumerate(pages, start=1):
        content = _content_stream(page_lines, page_no)
        content_id, page_id = next_id, next_id + 1
        next_id += 2
        objects[content_id] = (
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
            + content + b"\nendstream"
        )
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
            + f"{PAGE_W} {PAGE_H}".encode()
            + b"] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents "
            + f"{content_id} 0 R >>".encode()
        )
        page_ids.append(page_id)
    kids = b" ".join(f"{pid} 0 R".encode() for pid in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count "
        + str(len(page_ids)).encode() + b" >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for obj_id in sorted(objects):
        offsets[obj_id] = len(out)
        out += f"{obj_id} 0 obj\n".encode() + objects[obj_id] + b"\nendobj\n"
    xref_pos = len(out)
    max_id = max(objects)
    out += f"xref\n0 {max_id + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for obj_id in range(1, max_id + 1):
        out += f"{offsets[obj_id]:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(max_id + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


def degraded_lines(lines: list[Line]) -> list[Line]:
    """Simuliert schlechte Extraktion realer PDFs: Label + Inhalt fliessen in
    eine Zeile zusammen (kein Zeilenumbruch zwischen logischen Zeilen)."""
    out: list[Line] = []
    buffer: list[str] = []
    for style, text in lines:
        if style in ("h1", "h2"):
            if buffer:
                out.append(("body", " ".join(buffer)))
                buffer = []
            out.append((style, text))
        else:
            buffer.append(text)
    if buffer:
        out.append(("body", " ".join(buffer)))
    return out


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    target = FIXTURES / "innolink_sample.pdf"
    target.write_bytes(build_pdf(LINES))
    print(f"wrote {target} ({target.stat().st_size} bytes)")
    degraded = FIXTURES / "innolink_sample_degraded.pdf"
    degraded.write_bytes(build_pdf(degraded_lines(LINES)))
    print(f"wrote {degraded} ({degraded.stat().st_size} bytes)")
    structured = FIXTURES / "innolink_structured.pdf"
    structured.write_bytes(build_pdf(STRUCTURED_LINES))
    print(f"wrote {structured} ({structured.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
