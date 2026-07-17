"""Erlaubt-Basis für das Halluzinations-Gate (AllowedFactsManifest).

Das Gate fragt: Steht eine Zahl / ein Patent / eine Organisation im Text, die im
**tatsächlich sichtbaren Request** nicht vorkommt? Die Erlaubt-Basis darf darum
weder der gekürzte Kontextstring allein sein (dann gelten sichtbare
Strukturangaben als erfunden) noch ein beliebiger vollständiger Fallkorpus
(dann gelten unsichtbare Angaben als belegt). Sie wird deshalb aus genau den
Komponenten gebaut, die nach Budgetierung/Truncation im finalen Request stehen —
Feldtext, tatsächlich verwendete Fragmente, strukturierte Projektfakten,
Partner, Budgetwerte, akzeptierte Research-Fakten, Antragstellerangaben und
offene Angaben.

Normalisierung (deterministisch, dokumentiert):

* Tausendertrenner ``10'000 / 10’000 / 10 000 / 10000`` ⇒ identischer Schlüssel.
* Dezimalpunkt und Dezimalkomma ⇒ identischer Schlüssel (``45.5`` == ``45,5``).
* Echt mehrdeutige Schreibweisen (``1.234`` = 1234 oder 1.234) liefern BEIDE
  Lesarten als Kandidaten; ein Treffer genügt.
* Der Schlüssel ist der **Zahlenwert**, nicht die Einheit: ``45.5 %``,
  ``45,5 %``, ``45.5%`` und ``45,5 Prozent`` teilen ihn, und ``40–60 %`` sind
  schlicht die zwei bekannten Werte 40 und 60. Einheiten- und Kontexttreue sind
  Sache der inhaltlichen Gates und des menschlichen Reviews — nicht dieses
  Erfindungs-Checks.
* Organisationen: Gross-/Kleinschreibung, Interpunktion, Mehrfach-Leerzeichen
  und Umlautvarianten (``Zürich``/``Zurich``/``Zuerich``) sind dieselbe
  Organisation.

Was NICHT abgeschwächt wird: eine wirklich neue Zahl, ein wirklich neuer
Partner oder ein neues Patent bleiben eine Disqualifikation. Eine aus bekannten
Werten rein deterministisch berechenbare Zahl ist kein Beleg, aber auch keine
Erfindung — sie wird separat als ``derived_numeric_claim`` markiert und geht in
das menschliche Review.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Zifferngruppen mit Tausendertrennern; Alternation von spezifisch zu allgemein.
_GROUPED_SPACE = r"\d{1,3}(?:[   '’‘]\d{3})+"
_GROUPED_DOT = r"\d{1,3}(?:[.,]\d{3})+"
_NUMBER_RE = re.compile(
    rf"(?<![\w.,'’])(?:{_GROUPED_SPACE}|{_GROUPED_DOT}|\d+)(?:[.,]\d+)?"
)
_SEP_SPLIT_RE = re.compile(r"([   '’‘.,])")
_PATENT_RE = re.compile(r"\b(?:EP|WO|US|CH)\s?\d{4,}(?:[/.-]\d+)*\b", re.I)
_ORG_RE = re.compile(
    r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß&-]+\s+){0,5}"
    r"(?:AG|GmbH|Ltd\.?|Inc\.?|University|Universität|Hochschule|Institute|Institut)\b"
)
_TRL_RE = re.compile(r"\bTRL\s*\d\b", re.I)
_PATENT_WORD_RE = re.compile(r"\bpatent\w*", re.I)
_PUNCT_RE = re.compile(r"[.,;:!?()\[\]{}\"'’`´&/\\-]+")
_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss",
})
# Obergrenze für den Ableitungs-Check (Paarbildung ist quadratisch). Darüber
# wird nicht abgeleitet — eine unbekannte Zahl bleibt dann eine Erfindung.
_DERIVED_MAX_VALUES = 300


def _decimal_key(value: Decimal) -> str:
    """Kanonischer Schlüssel eines Zahlenwerts (45.50 == 45.5 == 4.55E+1)."""
    return format(value.normalize(), "f")


def _interpretations(body: str) -> set[Decimal]:
    """Alle deterministisch zulässigen Lesarten einer Zahlenschreibweise.

    Ein Trennzeichen ist Dezimaltrenner nur, wenn es genau einmal und zuletzt
    vorkommt; alle übrigen Trenner müssen dann exakt dreistellige Gruppen
    einleiten, und die führende Gruppe hat höchstens drei Ziffern.
    """
    parts = _SEP_SPLIT_RE.split(body.strip())
    groups, seps = parts[0::2], parts[1::2]
    if not groups or any(not group.isdigit() for group in groups):
        return set()
    if not seps:
        return {Decimal(groups[0])}
    results: set[Decimal] = set()
    for decimal_sep in (None, ".", ","):
        if decimal_sep is None:
            int_groups, frac, thousands_seps = groups, "", seps
        else:
            if seps.count(decimal_sep) != 1 or seps[-1] != decimal_sep:
                continue
            int_groups, frac, thousands_seps = groups[:-1], groups[-1], seps[:-1]
        if any(len(group) != 3 for group in int_groups[1:]):
            continue
        if thousands_seps and len(int_groups[0]) > 3:
            continue
        digits = "".join(int_groups)
        try:
            results.add(Decimal(f"{digits}.{frac}" if frac else digits))
        except InvalidOperation:  # pragma: no cover - defensiv
            continue
    return results


def _number_values(text: str) -> list[tuple[str, set[Decimal]]]:
    return [
        (token, _interpretations(token))
        for token in _NUMBER_RE.findall(text or "")
    ]


def _number_keys(text: str) -> set[str]:
    return {
        _decimal_key(value)
        for _token, values in _number_values(text)
        for value in values
    }


def _patent_key(token: str) -> str:
    return re.sub(r"\s+", "", token).casefold()


def _trl_key(token: str) -> str:
    return re.sub(r"\s+", "", token).upper()


def _org_known(candidate_keys: set[str], allowed: frozenset[str]) -> bool:
    """Bezeichnet der gefundene Name eine bekannte Organisation?

    Der Namensdetektor fasst die vorangehenden grossgeschriebenen Wörter mit
    («Der Partner Muster Technologies AG») und strukturierte Partnerangaben
    tragen die Rechtsform oft nicht («Fraunhofer» ⊂ «Fraunhofer Institut»).
    Bekannt ist deshalb, wessen Wortfolge in der jeweils anderen als
    zusammenhängende Wortfolge vorkommt — Wortgrenzen inklusive, damit
    «Neuerfundene Systeme GmbH» nie zufällig trifft.
    """
    for candidate in candidate_keys:
        padded_candidate = f" {candidate} "
        for known in allowed:
            padded_known = f" {known} "
            if padded_known in padded_candidate or padded_candidate in padded_known:
                return True
    return False


def _org_keys(name: str) -> set[str]:
    """Schlüsselvarianten einer Organisation (Umlaut-Transliteration UND
    Diakritika-Faltung — «Zürich» trifft «Zuerich» wie «Zurich»)."""
    collapsed = " ".join((name or "").split())
    if not collapsed:
        return set()
    transliterated = collapsed.translate(_UMLAUT_MAP)
    decomposed = "".join(
        char for char in unicodedata.normalize("NFKD", collapsed)
        if not unicodedata.combining(char)
    )
    keys = set()
    for variant in (transliterated, decomposed):
        cleaned = _PUNCT_RE.sub(" ", variant).casefold()
        keys.add(" ".join(cleaned.split()))
    return {key for key in keys if key}


@dataclass(frozen=True)
class AllowedFactsManifest:
    """Erlaubt-Basis aus den im finalen Request sichtbaren Komponenten."""

    numbers: frozenset[str] = frozenset()
    values: tuple[Decimal, ...] = ()
    patents: frozenset[str] = frozenset()
    organisations: frozenset[str] = frozenset()
    trl_levels: frozenset[str] = frozenset()
    # Kommen Schutzrechte im sichtbaren Request überhaupt vor? Eine
    # Patentbehauptung ohne jede Grundlage ist auch ohne konkrete ID erfunden.
    mentions_patent: bool = False
    components: tuple[dict, ...] = ()

    @property
    def sha256(self) -> str:
        payload = "|".join((
            ",".join(sorted(self.numbers)),
            ",".join(sorted(self.patents)),
            ",".join(sorted(self.organisations)),
            ",".join(sorted(self.trl_levels)),
            "patent" if self.mentions_patent else "",
        ))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def meta(self) -> dict:
        """Sichere Metadaten (nur Kinds/Zählwerte/Hash — nie Inhalte)."""
        return {
            "components": list(self.components),
            "number_count": len(self.numbers),
            "patent_count": len(self.patents),
            "organisation_count": len(self.organisations),
            "trl_level_count": len(self.trl_levels),
            "manifest_sha256": self.sha256,
        }


def build_manifest(components: list[tuple[str, str]]) -> AllowedFactsManifest:
    """Manifest aus typisierten, TATSÄCHLICH sichtbaren Textkomponenten.

    ``components`` = [(kind, sichtbarer Text), …] — der Aufrufer übergibt exakt
    die Auswahl, die nach Budgetierung/Truncation in den Request geht.
    """
    numbers: set[str] = set()
    values: set[Decimal] = set()
    patents: set[str] = set()
    organisations: set[str] = set()
    trl_levels: set[str] = set()
    mentions_patent = False
    meta: list[dict] = []
    for kind, text in components:
        text = text or ""
        mentions_patent = mentions_patent or bool(_PATENT_WORD_RE.search(text))
        component_numbers = _number_values(text)
        for _token, interpretations in component_numbers:
            for value in interpretations:
                numbers.add(_decimal_key(value))
                values.add(value)
        for token in _PATENT_RE.findall(text):
            patents.add(_patent_key(token))
        for token in _ORG_RE.findall(text):
            organisations |= _org_keys(token)
        for match in _TRL_RE.finditer(text):
            trl_levels.add(_trl_key(match.group(0)))
        meta.append({
            "kind": kind,
            "character_count": len(text),
            "number_count": len(component_numbers),
        })
    return AllowedFactsManifest(
        numbers=frozenset(numbers),
        values=tuple(sorted(values)[:_DERIVED_MAX_VALUES]),
        patents=frozenset(patents),
        organisations=frozenset(organisations),
        trl_levels=frozenset(trl_levels),
        mentions_patent=mentions_patent,
        components=tuple(meta),
    )


def add_known_organisations(
    manifest: AllowedFactsManifest, names: list[str]
) -> AllowedFactsManifest:
    """Bekannte Partner-/Organisationsnamen ergänzen (strukturierte Angaben
    tragen den Namen ohne Rechtsform-Suffix — die Regex allein fände sie nicht)."""
    extra: set[str] = set()
    for name in names:
        extra |= _org_keys(str(name or ""))
    if not extra:
        return manifest
    return dataclasses.replace(
        manifest,
        organisations=manifest.organisations | frozenset(extra),
        components=manifest.components + (
            {"kind": "known_partners", "character_count": 0,
             "number_count": 0, "organisation_count": len(extra)},
        ),
    )


def _is_derivable(value: Decimal, known: tuple[Decimal, ...]) -> bool:
    """Rein deterministisch aus zwei bekannten Werten berechenbar?

    Bewusst eng: Summe, Differenz, Produkt und prozentualer Anteil (auf eine
    Dezimale gerundet). Keine Heuristik, keine Näherung.
    """
    if len(known) > _DERIVED_MAX_VALUES:
        return False
    for i, a in enumerate(known):
        for b in known[i:]:
            if value in (a + b, a - b, b - a, a * b):
                return True
            if b and (100 * a / b).quantize(Decimal("0.1")) == value.quantize(
                Decimal("0.1")
            ):
                return True
            if a and (100 * b / a).quantize(Decimal("0.1")) == value.quantize(
                Decimal("0.1")
            ):
                return True
    return False


@dataclass(frozen=True)
class ClaimReport:
    """Kategorienweiser Befund der Erfindungsprüfung — die EINE kanonische
    Analyse für den Produktivpfad (erster harter Grund) und die Evaluation
    (Detailzeilen je Detektor). Keine parallele Zweitimplementierung."""

    invented_patents: tuple[str, ...] = ()
    invented_numbers: tuple[str, ...] = ()
    invented_organisations: tuple[str, ...] = ()
    invented_trl: tuple[str, ...] = ()
    derived_numbers: tuple[str, ...] = ()
    # Schutzrechts-Behauptung, obwohl der sichtbare Request Schutzrechte
    # nirgends erwähnt (auch ohne konkrete Patent-ID eine Erfindung).
    unsupported_patent_claim: bool = False

    @property
    def reason(self) -> str | None:
        """Erster harter Verstoss in der etablierten Prüfreihenfolge."""
        if self.invented_patents or self.unsupported_patent_claim:
            return "invented_patent_identifier"
        if self.invented_numbers:
            return "invented_numeric_token"
        if self.invented_organisations:
            return "invented_partner_name"
        return None


def analyze_claims(text: str, manifest: AllowedFactsManifest) -> ClaimReport:
    """Alle Erfindungs-Befunde eines generierten Textes gegen die Erlaubt-Basis."""
    patents = tuple(sorted({
        token for token in _PATENT_RE.findall(text or "")
        if _patent_key(token) not in manifest.patents
    }))
    invented_numbers: list[str] = []
    derived: list[str] = []
    for token, interpretations in _number_values(text or ""):
        keys = {_decimal_key(value) for value in interpretations}
        if keys & manifest.numbers:
            continue
        if any(_is_derivable(value, manifest.values) for value in interpretations):
            derived.append(token)
            continue
        invented_numbers.append(token)
    organisations = tuple(sorted({
        " ".join(token.split()) for token in _ORG_RE.findall(text or "")
        if not _org_known(_org_keys(token), manifest.organisations)
    }))
    trl = tuple(sorted({
        _trl_key(match.group(0)) for match in _TRL_RE.finditer(text or "")
        if _trl_key(match.group(0)) not in manifest.trl_levels
    }))
    return ClaimReport(
        invented_patents=patents,
        invented_numbers=tuple(invented_numbers),
        invented_organisations=organisations,
        invented_trl=trl,
        derived_numbers=tuple(derived),
        unsupported_patent_claim=bool(
            _PATENT_WORD_RE.search(text or "") and not manifest.mentions_patent
        ),
    )


@dataclass(frozen=True)
class ClaimCheck:
    """Ergebnis der Erfindungsprüfung eines generierten Textes (Produktivpfad)."""

    reason: str | None = None
    derived_numbers: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.reason is None


def check_claims(text: str, manifest: AllowedFactsManifest) -> ClaimCheck:
    """Erfindungsprüfung für den Produktivpfad: erster harter Verstoss.

    Dünne Sicht auf ``analyze_claims``; deterministisch ableitbare Zahlen
    blockieren nicht, sondern gehen als ``derived_numbers`` ins Review.
    """
    report = analyze_claims(text, manifest)
    return ClaimCheck(
        reason=report.reason, derived_numbers=report.derived_numbers
    )
