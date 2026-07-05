"""Erzeugt ein synthetisches Innolink-artiges Test-PDF (spike/fixtures/innolink_sample.pdf).

SPIKE-Werkzeug — ausschliesslich synthetische Daten (fiktives Projekt
"SmartGrid Optimizer"). Kein reportlab o. ä.: bewusst ein minimaler,
handgeschriebener PDF-Writer (Helvetica, WinAnsi/cp1252), damit keine neue
Dependency nötig ist. Ein eigenes/echtes Test-PDF kann die Datei einfach
ersetzen; ground_truth.json muss dann angepasst werden.

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


if __name__ == "__main__":
    main()
