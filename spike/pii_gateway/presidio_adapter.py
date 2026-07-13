"""Tier B — optionaler ML-Detektor über Microsoft Presidio + deutsches spaCy.

Lazy Import: Sind ``presidio_analyzer``/``spacy``/das deutsche Modell nicht
installiert, meldet ``availability()`` ``(False, grund)`` und der Harness
überspringt diesen Tier EHRLICH (kein Fehler, kein Abbruch). So bleibt der
deterministische Tier auch ohne Installation vollständig lauffähig.

Presidio (presidio-analyzer/-anonymizer) und spaCy stehen unter MIT-Lizenz; das
Modell ``de_core_news_md`` (~44 MB) bzw. ``de_core_news_sm`` (~15 MB) ebenfalls
MIT. Inferenz läuft vollständig lokal, ohne Netzzugriff.

Spike-Regel: kein Import aus backend/app oder lib/. Keine Firecrawl-/Open-WebUI-
Verbindung.
"""
from __future__ import annotations

from detectors import (
    ADDRESS,
    DOB,
    EMAIL,
    IBAN,
    PERSON,
    PHONE,
    USERNAME,
    Span,
)

# Bevorzugte Modellreihenfolge (grösser = i. d. R. genauer).
_MODEL_CANDIDATES = ("de_core_news_md", "de_core_news_sm", "de_core_news_lg")

# Presidio-Entitätstyp -> Spike-Typ.
_PRESIDIO_TO_TYPE = {
    "PERSON": PERSON,
    "EMAIL_ADDRESS": EMAIL,
    "PHONE_NUMBER": PHONE,
    "IBAN_CODE": IBAN,
    "DATE_TIME": DOB,
    "LOCATION": ADDRESS,
    "USERNAME": USERNAME,
}

_analyzer = None
_model_used: str | None = None


def _pick_model() -> str | None:
    import importlib.util

    for name in _MODEL_CANDIDATES:
        if importlib.util.find_spec(name) is not None:
            return name
    return None


def availability() -> tuple[bool, str]:
    """(verfügbar, Grund). Prüft Libs + deutsches Modell, ohne zu crashen."""
    try:
        import importlib.util

        if importlib.util.find_spec("presidio_analyzer") is None:
            return False, "presidio-analyzer nicht installiert"
        if importlib.util.find_spec("spacy") is None:
            return False, "spacy nicht installiert"
    except Exception as exc:  # noqa: BLE001 — Spike: Grund festhalten, nicht crashen
        return False, f"Import-Prüfung fehlgeschlagen: {exc}"
    model = _pick_model()
    if model is None:
        return False, "kein deutsches spaCy-Modell (de_core_news_*) installiert"
    return True, f"verfügbar (Modell {model})"


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    global _model_used
    _model_used = _pick_model()
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": _model_used}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de"])

    # Benutzername ist kein Presidio-Standard — @handle als Pattern ergänzen,
    # damit der ML-Tier auf diesem Format nicht unfair schlechter dasteht.
    username = PatternRecognizer(
        supported_entity="USERNAME",
        supported_language="de",
        patterns=[Pattern("at_handle", r"@[A-Za-z0-9_]+", 0.6)],
        context=["benutzer", "benutzername", "user", "username", "portal"],
    )
    analyzer.registry.add_recognizer(username)
    return analyzer


def detect(text: str) -> list[Span]:
    """Presidio-Analyse (deutsch) -> Spike-Spans. Nur aufrufen, wenn availability()."""
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    entities = list(_PRESIDIO_TO_TYPE.keys())
    results = _analyzer.analyze(text=text, language="de", entities=entities)
    spans: list[Span] = []
    for r in results:
        etype = _PRESIDIO_TO_TYPE.get(r.entity_type)
        if etype is None:
            continue
        spans.append(Span(etype, r.start, r.end, text[r.start : r.end]))
    return spans


def model_used() -> str | None:
    return _model_used
