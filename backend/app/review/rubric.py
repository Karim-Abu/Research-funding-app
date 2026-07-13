"""Rubric v0 (R6) — sieben deterministische Reviewer-Heuristiken.

Rein regelbasierte Textprüfungen über den aktuellen Feld-Drafts (kein LLM,
kein Netzwerk). Jede Heuristik emittiert höchstens EIN Finding pro Feld mit
``severity="warning"`` — die Klasse ``reviewer_risk`` (fingerprint.py) stellt
sicher, dass Rubric-Hinweise NIE blockieren und NIE wie ein Förderentscheid
wirken: sie markieren Stellen, die ein Gutachter erfahrungsgemäss hinterfragt.

Heuristiken (Demo-Scope):
    kpi_chain               Zielwert ohne Baseline/Messmethode/Validierung
    sota_differentiation    "innovativ" ohne Vergleichs-/Abgrenzungsbezug
    methodology_how         Lösungstext beschreibt WHAT, nicht HOW
    market_claim_unsourced  Marktzahl ohne verknüpften Beleg
    partner_fit             Partnernennung ohne Kompetenz-/Rollenbegründung
    risk_scope              Risikoabschnitt nur mit technischen Risiken
    cross_section_numbers   abweichende Kennzahlen zwischen Kapiteln
                            (gröbste Heuristik — dokumentierte False-Positive-
                            Erwartung, deshalb ausdrücklich nur reviewer_risk)

Meldungstexte: inline wie in checks.py; Owner-Freigabe der Formulierungen
ist Teil des Slice-Reviews (R2.6-Prinzip).
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceLink,
    PortalFieldDraft,
    RunProjectSnapshot,
)
from app.review.checks import FindingSpec

RUBRIC_CODES = (
    "kpi_chain",
    "sota_differentiation",
    "methodology_how",
    "market_claim_unsourced",
    "partner_fit",
    "risk_scope",
    "cross_section_numbers",
)

# Feld-Scope je Heuristik (nur wo die Frage fachlich hingehört).
_EXEC_FIELDS = ("INTRO.APP.ABSTRACT", "INTRO.APP.EXECUTIVE_SUMMARY")
_VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
_SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"

_NUMBER = re.compile(r"\d+(?:[.,'’]\d+)*\s*(?:%|prozent|chf|mio|mrd|mia)?", re.I)
_TARGET_WORDS = re.compile(
    r"\b(zielwert|reduzier\w*|steiger\w*|senk\w*|erhöh\w*|verbesser\w*)\b.{0,40}?\d|"
    r"\d\s*(?:%|prozent).{0,40}?"
    r"\b(reduzier|reduktion|steiger|senk|erhöh|verbesser|ziel)\w*",
    re.I | re.S,
)
_BASELINE_WORDS = re.compile(r"\b(baseline|ausgangswert|ausgangslage|ist-wert|heute bei|derzeit)\b", re.I)
_MEASURE_WORDS = re.compile(
    r"\b(messmethode|gemessen|messung|datenquelle|kpi-definition|validier\w*|evaluier\w*|erhebung)\b",
    re.I,
)
_INNOVATIV_WORDS = re.compile(r"\b(innovativ\w*|neuartig\w*|einzigartig\w*|erstmals|weltweit erstmal\w*)\b", re.I)
_COMPARISON_WORDS = re.compile(
    r"\b(stand der technik|state of the art|sota|bestehende\w*|herkömmlich\w*|bisherige\w*|"
    r"im vergleich|gegenüber|konkurrenz\w*|wettbewerb\w*|alternative\w*|abgrenzung)\b",
    re.I,
)
_HOW_WORDS = re.compile(
    r"\b(vorgehen|methode\w*|verfahren|schritt\w*|arbeitspaket\w*|prototyp\w*|test\w*|"
    r"validier\w*|iteration\w*|experiment\w*|messung\w*|implementier\w*|entwickel\w* wir)\b",
    re.I,
)
_MARKET_WORDS = re.compile(r"\b(markt\w*|umsatz\w*|marktanteil\w*|absatz\w*|kundenpotenzial|wachstum\w*)\b", re.I)
_SOURCE_HINT_WORDS = re.compile(r"\b(quelle|gemäss|laut|studie|report|bfs|statistik)\b", re.I)
_RISK_SECTION = re.compile(r"\brisik\w*", re.I)
_NON_TECH_RISK_WORDS = re.compile(
    r"\b(marktrisik\w*|finanzrisik\w*|finanzierungsrisik\w*|regulator\w*|rechtlich\w*|"
    r"akzeptanz\w*|personal\w*|lieferkett\w*|kommerzialisier\w*|nachfrage\w*)\b",
    re.I,
)
_ROLE_WORDS = re.compile(
    r"\b(kompetenz\w*|rolle\w*|erfahrung\w*|expertise|zuständig\w*|verantwort\w*|"
    r"beitrag\w*|infrastruktur|know-how|forschungspartner übernimmt|umsetzungspartner übernimmt)\b",
    re.I,
)
# Kennzahl-Themen für den Kapitelvergleich (cross_section_numbers).
_CROSS_TOPICS = ("umsatz", "marktanteil", "budget", "kosten")

_MIN_TEXT_LEN = 200  # Heuristiken erst ab substanziellem Text (weniger Rauschen)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _spec(
    code: str,
    draft: PortalFieldDraft,
    description: str,
    next_action: str,
    suggested: str | None = None,
) -> FindingSpec:
    return FindingSpec(
        finding_code=f"rubric:{code}:{draft.field_id}",
        severity="warning",
        description=description,
        target_type="portal_field_draft",
        target_id=draft.draft_id,
        field_id=draft.field_id,
        suggested_improvement=suggested,
        recommended_next_action=next_action,
    )


# --- Einzel-Heuristiken (pure Textfunktionen) --------------------------------


def check_kpi_chain(text: str) -> str | None:
    """Zielwert-Formulierung ohne Baseline ODER Messmethode → fehlende Glieder."""
    if not _TARGET_WORDS.search(text):
        return None
    missing: list[str] = []
    if not _BASELINE_WORDS.search(text):
        missing.append("Baseline/Ausgangswert")
    if not _MEASURE_WORDS.search(text):
        missing.append("Messmethode/Datenquelle inkl. Validierungszeitpunkt")
    return ", ".join(missing) if missing else None


def check_sota(text: str) -> bool:
    return bool(_INNOVATIV_WORDS.search(text)) and not _COMPARISON_WORDS.search(text)


def check_methodology_how(text: str) -> bool:
    return len(text) >= _MIN_TEXT_LEN and not _HOW_WORDS.search(text)


def find_unsourced_market_claim(text: str, has_evidence_link: bool) -> str | None:
    """Erster Satz mit Marktbegriff + Zahl, ohne Quellensignal im Satz und ohne
    verknüpften Beleg am Feld. Liefert einen kurzen Ausschnitt (≤ 80 Zeichen)."""
    if has_evidence_link:
        return None
    for sentence in _sentences(text):
        if (
            _MARKET_WORDS.search(sentence)
            and _NUMBER.search(sentence)
            and not _SOURCE_HINT_WORDS.search(sentence)
        ):
            return sentence[:80] + ("…" if len(sentence) > 80 else "")
    return None


def find_partner_without_role(text: str, partner_names: list[str]) -> str | None:
    """Erster Partnername, der im Text vorkommt, ohne dass der umgebende Satz
    eine Kompetenz-/Rollenbegründung enthält."""
    for name in partner_names:
        if len(name) < 3:
            continue
        for sentence in _sentences(text):
            if name.lower() in sentence.lower() and not _ROLE_WORDS.search(sentence):
                return name
    return None


def check_risk_scope(text: str) -> bool:
    """Risiken werden erwähnt, aber ausschliesslich technisch gerahmt."""
    return bool(_RISK_SECTION.search(text)) and not _NON_TECH_RISK_WORDS.search(text)


def find_cross_section_conflicts(
    texts_by_field: dict[str, str]
) -> list[tuple[str, str, str]]:
    """Gleiches Kennzahl-Thema mit disjunkten Zahlen in zwei Kapiteln.
    Grob und bewusst nur reviewer_risk. Liefert (thema, feld_a, feld_b)."""
    conflicts: list[tuple[str, str, str]] = []
    for topic in _CROSS_TOPICS:
        numbers_by_field: dict[str, set[str]] = {}
        for field_id, text in texts_by_field.items():
            numbers: set[str] = set()
            for sentence in _sentences(text):
                if topic in sentence.lower():
                    numbers.update(
                        m.group(0).strip() for m in _NUMBER.finditer(sentence)
                    )
            if numbers:
                numbers_by_field[field_id] = numbers
        fields = sorted(numbers_by_field)
        for i, field_a in enumerate(fields):
            for field_b in fields[i + 1 :]:
                if numbers_by_field[field_a].isdisjoint(numbers_by_field[field_b]):
                    conflicts.append((topic, field_a, field_b))
    return conflicts


# --- Aufbau der FindingSpecs --------------------------------------------------


def _enabled_codes() -> set[str]:
    settings = get_settings()
    if not settings.rubric_v0_enabled:
        return set()
    disabled = {
        code.strip()
        for code in settings.rubric_v0_disabled_codes.split(",")
        if code.strip()
    }
    return {code for code in RUBRIC_CODES if code not in disabled}


def compute_rubric_specs(db: Session, run: AnalysisRun) -> list[FindingSpec]:
    """Rubric-v0-Findings für einen Lauf (deterministisch, idempotent)."""
    enabled = _enabled_codes()
    if not enabled:
        return []

    drafts = {
        d.field_id: d
        for d in db.scalars(
            select(PortalFieldDraft)
            .where(PortalFieldDraft.run_id == run.run_id)
            .order_by(PortalFieldDraft.field_id.asc())
        )
    }
    # Nur inhaltliche Texte prüfen: unveränderte Strukturvorlagen und leere
    # Felder erzeugen keine Gutachter-Hinweise (reines Rauschen).
    texts: dict[str, str] = {}
    for field_id, draft in drafts.items():
        version = (
            db.get(DraftVersion, draft.current_version_id)
            if draft.current_version_id
            else None
        )
        if version is None or version.created_by == "template":
            texts[field_id] = ""
        else:
            texts[field_id] = version.text or ""

    linked_version_ids = {
        link.target_id
        for link in db.scalars(
            select(EvidenceLink).where(
                EvidenceLink.run_id == run.run_id,
                EvidenceLink.target_type == "draft_version",
                EvidenceLink.status == "active",
            )
        )
    }
    fields_with_links = {
        field_id
        for field_id, draft in drafts.items()
        if draft.current_version_id in linked_version_ids
    }

    snapshot = db.scalar(
        select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run.run_id)
    )
    partner_names = [
        str(p.get("name", "")).strip()
        for p in (snapshot.partners_json if snapshot else []) or []
        if str(p.get("name", "")).strip()
    ]

    specs: list[FindingSpec] = []

    if "kpi_chain" in enabled:
        for field_id in (_VC_FIELD, _SOL_FIELD, *_EXEC_FIELDS):
            draft = drafts.get(field_id)
            if draft is None:
                continue
            missing = check_kpi_chain(texts[field_id])
            if missing:
                specs.append(
                    _spec(
                        "kpi_chain",
                        draft,
                        "Der Abschnitt nennt Zielwerte, aber die KPI-Kette ist "
                        f"unvollständig: {missing} fehlt.",
                        "KPI vervollständigen: Baseline → Zielwert → Messmethode/"
                        "Datenquelle → Validierungszeitpunkt.",
                    )
                )
                break  # ein Hinweis genügt für die Demo (Fix Queue gruppiert)

    if "sota_differentiation" in enabled:
        draft = drafts.get(_SOL_FIELD)
        if draft is not None and check_sota(texts[_SOL_FIELD]):
            specs.append(
                _spec(
                    "sota_differentiation",
                    draft,
                    "Der Lösungstext bezeichnet das Vorhaben als innovativ, ohne "
                    "einen Vergleichsbezug zum Stand der Technik herzustellen.",
                    "Abgrenzung ergänzen: Was existiert heute, und was macht "
                    "dieses Vorhaben konkret anders?",
                )
            )

    if "methodology_how" in enabled:
        draft = drafts.get(_SOL_FIELD)
        if draft is not None and check_methodology_how(texts[_SOL_FIELD]):
            specs.append(
                _spec(
                    "methodology_how",
                    draft,
                    "Der Lösungstext beschreibt, WAS erreicht werden soll, aber "
                    "nicht, WIE (Vorgehen, Methoden, Arbeitsschritte).",
                    "Methodik ergänzen: Vorgehen, Arbeitsschritte und geplante "
                    "Validierung beschreiben.",
                )
            )

    if "market_claim_unsourced" in enabled:
        for field_id in (_VC_FIELD, *_EXEC_FIELDS):
            draft = drafts.get(field_id)
            if draft is None:
                continue
            snippet = find_unsourced_market_claim(
                texts[field_id], field_id in fields_with_links
            )
            if snippet:
                specs.append(
                    _spec(
                        "market_claim_unsourced",
                        draft,
                        "Der Abschnitt enthält eine Marktzahl ohne verknüpften "
                        f"Beleg: «{snippet}»",
                        "Quelle verknüpfen oder die Zahl als offene Angabe "
                        "markieren.",
                    )
                )
                break

    if "partner_fit" in enabled and partner_names:
        for field_id in (_SOL_FIELD, _VC_FIELD):
            draft = drafts.get(field_id)
            if draft is None:
                continue
            name = find_partner_without_role(texts[field_id], partner_names)
            if name:
                specs.append(
                    _spec(
                        "partner_fit",
                        draft,
                        f"Der Partner «{name}» wird genannt, ohne dass Kompetenz "
                        "oder Rolle im Projekt begründet wird.",
                        "Partner-Fit begründen: Welche Kompetenz bringt der "
                        "Partner ein, und welche Rolle übernimmt er?",
                    )
                )
                break

    if "risk_scope" in enabled:
        for field_id in (_SOL_FIELD, _VC_FIELD):
            draft = drafts.get(field_id)
            if draft is None:
                continue
            if check_risk_scope(texts[field_id]):
                specs.append(
                    _spec(
                        "risk_scope",
                        draft,
                        "Der Risikoabschnitt behandelt nur technische Risiken — "
                        "Markt-, Finanz- oder Umsetzungsrisiken fehlen.",
                        "Risikobild erweitern: auch Markt-, Finanzierungs- und "
                        "Umsetzungsrisiken benennen.",
                    )
                )
                break

    if "cross_section_numbers" in enabled:
        relevant = {
            field_id: texts[field_id]
            for field_id in (*_EXEC_FIELDS, _VC_FIELD, _SOL_FIELD)
            if field_id in drafts and texts.get(field_id)
        }
        for topic, field_a, field_b in find_cross_section_conflicts(relevant):
            draft = drafts[field_a]
            specs.append(
                FindingSpec(
                    finding_code=f"rubric:cross_section_numbers:{topic}:{field_a}:{field_b}",
                    severity="warning",
                    description=(
                        f"Die Kennzahl zum Thema «{topic}» unterscheidet sich "
                        "zwischen zwei Kapiteln. Bitte auf Konsistenz prüfen — "
                        "diese Heuristik kann auch legitime Unterschiede melden."
                    ),
                    target_type="portal_field_draft",
                    target_id=draft.draft_id,
                    field_id=field_a,
                    recommended_next_action=(
                        "Zahlen in Executive Summary, Wertschöpfung, Lösung und "
                        "Budget abgleichen."
                    ),
                )
            )
            break  # höchstens ein Konsistenz-Hinweis pro Lauf

    return specs
