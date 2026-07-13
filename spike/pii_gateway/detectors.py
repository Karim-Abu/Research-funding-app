"""Tier A — deterministischer, lokaler PII-Detektor (keine neuen Abhängigkeiten).

Reines Python-Stdlib + ``re``. Erkennt 7 Entitätstypen in deutsch-/schweiz-
bezogenem Text und liefert typisierte Spans. Die Regex-/Lexikon-Muster für
E-Mail, Telefon und die Firmensuffix-Ignoreliste sind bewusst aus
``backend/app/security/confidential_terms.py`` **dupliziert** (Spike-Regel: kein
Import aus backend/app). Zusätzlich: IBAN mit Mod-97-Prüfsumme, Geburtsdatum,
Benutzername sowie Name/Adresse über eine kleine Gazetteer-/Suffix-Heuristik.

Dies ist Pseudonymisierung/Tokenisierung, KEINE garantierte Anonymisierung: freie
Namen ausserhalb des Gazetteers und Fliesstext-Adressen ohne Strassensuffix
werden nicht zuverlässig erkannt — genau das misst der Spike.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Unterstützte Typen.
PERSON, EMAIL, PHONE, ADDRESS, DOB, IBAN, USERNAME = (
    "PERSON", "EMAIL", "PHONE", "ADDRESS", "DOB", "IBAN", "USERNAME"
)


@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int
    value: str


# --- Aus confidential_terms.py dupliziert (Muster, nicht importiert) ----------
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(
    r"(?:\+\d[\d\s().\-]{6,}\d)|(?:\b0\d{1,2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}\b)"
)
# Firmen-/Rechtsform-Suffixe, die nie als Namensteil zählen (Über-Redaktion vermeiden).
NAME_TOKEN_IGNORE = frozenset({
    "ag", "gmbh", "sa", "sarl", "ltd", "inc", "llc", "plc", "group", "gruppe",
    "holding", "co", "kg", "ohg", "se", "ev", "verein", "stiftung", "university",
    "universität", "hochschule", "institut", "institute", "fhnw",
})

# --- Neue Recognizer ----------------------------------------------------------
# IBAN-Region: Länderkürzel + 2 Prüfziffern + alphanumerischer Rumpf (Leerzeichen
# als Blocktrenner). Die Region kann ein Folgewort mitfangen; darum wird sie danach
# token-weise von rechts gekürzt, bis Mod-97 validiert (siehe _find_iban).
_IBAN_REGION_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}[A-Za-z0-9 ]{11,40}")

_MONTHS = (
    "januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|"
    "november|dezember"
)
_DOB_RES = (
    re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"),          # 14.03.1987
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                 # 1990-11-22
    re.compile(rf"\b\d{{1,2}}\.\s?(?:{_MONTHS})\s+\d{{4}}\b", re.IGNORECASE),  # 3. Februar 1975
)

# @handle bzw. Benutzername-Feld. Token erlaubt innere ._- zwischen alnum, aber
# kein abschliessendes Satzzeichen. Das @handle darf NICHT innerhalb einer
# E-Mail feuern → nur wenn '@' am Wortanfang steht (nicht nach Nicht-Leerzeichen).
_USERNAME_TOKEN = r"@?[A-Za-z0-9_]+(?:[._-][A-Za-z0-9_]+)*"
_USERNAME_HANDLE_RE = re.compile(r"(?<!\S)@[A-Za-z0-9_]+")
_USERNAME_FIELD_RE = re.compile(
    rf"(?i)\bbenutzer(?:name)?\s*[:\-]\s*({_USERNAME_TOKEN})"
)

# Adresse: Strassenname mit typischem Suffix + Hausnummer, optional PLZ + Ort.
_ADDRESS_RE = re.compile(
    r"[A-ZÄÖÜ][A-Za-zäöüß]*(?:strasse|straße|gasse|weg|platz|allee|ring|str\.)"
    r"\s+\d+[a-z]?(?:,\s*\d{4}\s+[A-ZÄÖÜ][A-Za-zäöüß]+)?"
)

# Kleiner Vorname-Gazetteer (häufige DE/CH-Vornamen inkl. der Fixture-Namen).
# Bewusst begrenzt: unbekannte Vornamen werden NICHT erkannt (ehrliche Schwäche).
FIRST_NAMES = frozenset({
    "anna", "tobias", "claude", "marco", "pascal", "sarah", "beat", "peter",
    "hans", "urs", "daniel", "michael", "thomas", "andreas", "martin", "stefan",
    "christian", "markus", "david", "simon", "lukas", "jonas", "nina", "laura",
    "julia", "sandra", "petra", "claudia", "barbara", "maria", "elena", "sophie",
    "lena", "eva", "monika", "regula", "franziska",
})
_CAP_WORD = re.compile(r"[A-ZÄÖÜ][A-Za-zäöüß'\-]+")
_WORD_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß'\-]+")


def iban_mod97_ok(candidate: str) -> bool:
    """IBAN-Prüfung: Länge 15–34, Mod-97 == 1 (ISO 13616)."""
    s = re.sub(r"\s", "", candidate).upper()
    if not (15 <= len(s) <= 34) or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    rearranged = s[4:] + s[:4]
    try:
        numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    except ValueError:
        return False
    return int(numeric) % 97 == 1


def _find_regex(text: str, pattern: re.Pattern[str], etype: str) -> list[Span]:
    return [Span(etype, m.start(), m.end(), m.group(0)) for m in pattern.finditer(text)]


def _find_iban(text: str) -> list[Span]:
    spans: list[Span] = []
    for m in _IBAN_REGION_RE.finditer(text):
        tokens = m.group(0).split(" ")
        # Von rechts kürzen, bis ein gültiger IBAN übrig bleibt (fängt ein
        # angehängtes Folgewort wie «beglichen» ab, das die Prüfsumme bricht).
        while tokens:
            candidate = " ".join(tokens)
            compact = candidate.replace(" ", "")
            if 15 <= len(compact) <= 34 and iban_mod97_ok(compact):
                spans.append(
                    Span(IBAN, m.start(), m.start() + len(candidate), candidate)
                )
                break
            tokens.pop()
    return spans


def _find_dob(text: str) -> list[Span]:
    spans: list[Span] = []
    for pattern in _DOB_RES:
        spans.extend(_find_regex(text, pattern, DOB))
    return spans


def _find_username(text: str) -> list[Span]:
    spans: list[Span] = [Span(USERNAME, m.start(), m.end(), m.group(0))
                         for m in _USERNAME_HANDLE_RE.finditer(text)]
    for m in _USERNAME_FIELD_RE.finditer(text):
        spans.append(Span(USERNAME, m.start(1), m.end(1), m.group(1)))
    return spans


def _find_person(text: str) -> list[Span]:
    """Vorname (Gazetteer) + folgender grossgeschriebener Nachname → PERSON.

    Token-basiert (kein bigram-Regex), damit ein vorangehendes grossgeschriebenes
    Wort (Anrede «Herr», «Frau») den Namen nicht «verschluckt».
    """
    tokens = list(_WORD_TOKEN.finditer(text))
    spans: list[Span] = []
    for i in range(len(tokens) - 1):
        first, second = tokens[i], tokens[i + 1]
        if (
            first.group(0).lower() in FIRST_NAMES
            and _CAP_WORD.fullmatch(second.group(0))
            and second.group(0).lower() not in NAME_TOKEN_IGNORE
        ):
            spans.append(Span(PERSON, first.start(), second.end(),
                              text[first.start():second.end()]))
    return spans


def _dedupe(spans: list[Span]) -> list[Span]:
    """Bei Überlappung gleichen Typs den längeren Span behalten."""
    by_type: dict[str, list[Span]] = {}
    for s in spans:
        by_type.setdefault(s.type, []).append(s)
    out: list[Span] = []
    for group in by_type.values():
        group.sort(key=lambda s: (s.start, -(s.end - s.start)))
        occupied: list[Span] = []
        for s in group:
            if any(s.start < o.end and o.start < s.end for o in occupied):
                continue
            occupied.append(s)
        out.extend(occupied)
    return sorted(out, key=lambda s: s.start)


def detect(text: str) -> list[Span]:
    """Alle Recognizer anwenden und überlappende Spans gleichen Typs entschärfen."""
    spans: list[Span] = []
    spans += _find_regex(text, EMAIL_RE, EMAIL)
    spans += _find_regex(text, PHONE_RE, PHONE)
    spans += _find_iban(text)
    spans += _find_dob(text)
    spans += _find_username(text)
    spans += _find_regex(text, _ADDRESS_RE, ADDRESS)
    spans += _find_person(text)
    return _dedupe(spans)
