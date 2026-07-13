"""Versioned confidential-term dictionary + sensitive-pattern regexes (Milestone 9J).

Deterministic, local, no LLM. Generic detectors (NDA markers, e-mail, phone, currency
amounts, confidential keywords) apply to **all** data classes. The *project-specific*
lexicon (partner names, project title, representatives) is built per project in
``search_query_firewall`` and only applied to confidential classes (D1/D2), since for a
public (D0) project those names are public by definition.
"""
from __future__ import annotations

import re

CONFIDENTIAL_DICTIONARY_VERSION = "m9j-confidential-2"

# NDA / legal-restriction markers (normalized, casefolded substrings). High weight.
NDA_MARKERS: frozenset[str] = frozenset(
    {
        "nda", "non-disclosure", "non disclosure", "geheimhaltung",
        "geheimhaltungsvereinbarung", "vertraulichkeitsvereinbarung",
        "streng geheim", "streng vertraulich", "betriebsgeheimnis",
        "geschäftsgeheimnis", "trade secret",
    }
)

# Confidential business keywords (lower weight; one or two may be benign, several are not).
CONFIDENTIAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "vertraulich", "confidential", "geheim", "proprietär", "proprietary",
        "geschäftsmodell", "business model", "patent", "patentanmeldung",
        "intellectual property", "geistiges eigentum", "roadmap", "unveröffentlicht",
        "interne kalkulation", "kalkulation", "marge", "gewinnmarge", "cap table",
        "term sheet", "investorengespräch",
    }
)

# Company/legal-form suffixes that must NOT be treated as a removable name token on
# their own (too generic — would over-redact).
NAME_TOKEN_IGNORE: frozenset[str] = frozenset(
    {
        "ag", "gmbh", "sa", "sarl", "ltd", "inc", "llc", "plc", "group", "gruppe",
        "holding", "co", "kg", "ohg", "se", "ev", "verein", "stiftung", "university",
        "universität", "hochschule", "institut", "institute", "fhnw",
    }
)

# Currency amounts: a currency token adjacent to a number, in either order. Anchored on
# an explicit currency so plain years/counts in public queries are not flagged.
_CURRENCY = r"(?:chf|eur|usd|gbp|fr\.?|franken|€|\$|£|mio\.?|mrd\.?|million(?:en)?|milliarden)"
_AMOUNT = r"\d[\d'’.,\s]*"
BUDGET_RE = re.compile(
    rf"(?i)(?:{_CURRENCY}\s*{_AMOUNT}|{_AMOUNT}\s*{_CURRENCY})"
)

# Beträge in Zahlwörtern (R8-Leakage): «eine halbe Million Franken»,
# «fünfhunderttausend Franken», «half a million francs». Verlangt zwingend ein
# Währungswort am Ende, damit Mengenangaben («Millionen von Nutzern») nicht als
# Budget markiert werden. Erste Position muss ein Zahl-/Zahlkompositum sein, damit
# ein blosses «Millionen …» nicht anschlägt.
_NUM_WORD = (
    r"(?:ein(?:e[nmrs]?)?|zwei|drei|vier|f(?:ü|ue)nf|sechs|sieben|acht|neun|zehn|"
    r"elf|zw(?:ö|oe)lf|zwanzig|dreissig|dreißig|vierzig|f(?:ü|ue)nfzig|sechzig|"
    r"siebzig|achtzig|neunzig|halbe?[nmrs]?|anderthalb|"
    r"half|one|two|three|four|five|six|seven|eight|nine|ten|a|an)"
)
_NUM_COMPOUND = r"(?:[a-zäöüß]*(?:hundert|tausend)[a-zäöüß]*)"
_MAGNITUDE_WORD = r"(?:million(?:en)?|mio\.?|milliarden?|mrd\.?|thousand|billion)"
_CURRENCY_WORD = r"(?:chf|franken|francs?|euros?|eur|usd|dollars?|pfund|pounds?|€|\$|£)"
BUDGET_WORD_RE = re.compile(
    rf"(?i)\b(?:{_NUM_COMPOUND}|{_NUM_WORD})"
    rf"(?:\s+(?:{_NUM_COMPOUND}|{_NUM_WORD}|{_MAGNITUDE_WORD})){{0,3}}"
    rf"\s+{_CURRENCY_WORD}\b"
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Conservative phone match: an international (+..) number or a long grouped run of digits.
PHONE_RE = re.compile(r"(?:\+\d[\d\s().\-]{6,}\d)|(?:\b0\d{1,2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}\b)")


# Risk weights per *distinct* detected category (summed, capped at 10). Calibrated so a
# couple of removable identifiers (partner + budget + project name) stays sanitizable
# (risk ≤ 5 → require approval), while an NDA marker or a free-form idea blocks on its own
# (≥ 6), and combinations that leave little to search on also block.
CATEGORY_WEIGHTS: dict[str, int] = {
    "nda_marker": 6,
    "free_form_idea": 6,
    "email": 3,
    "phone": 3,
    "partner_name": 2,
    "budget_amount": 2,
    "person_name": 2,
    "project_name": 2,
    "project_alias": 2,
    "confidential_keyword": 2,
}

# Human-facing German labels (UI redaction summary). No raw values are ever included.
CATEGORY_LABELS: dict[str, str] = {
    "nda_marker": "NDA-/Vertraulichkeitsmarker",
    "partner_name": "Partnername",
    "budget_amount": "Budget-/Finanzangabe",
    "free_form_idea": "Ausführliche Projektbeschreibung",
    "email": "E-Mail-Adresse",
    "phone": "Telefonnummer",
    "person_name": "Personenname",
    "project_name": "Projektname",
    "project_alias": "Projektkürzel",
    "confidential_keyword": "Vertrauliches Schlüsselwort",
}
