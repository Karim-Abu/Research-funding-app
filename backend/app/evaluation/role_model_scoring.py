"""Rollen-Modell-Evaluation — pure Scorer, Gates und Aggregation (kein DB-Zugriff).

Bewertet A1-/A2-/A3-Outputs gegen die maschinenlesbaren Fall-Goldstandards
(``docs/evaluation/cases/<case>_gold.json`` + ``<case>_fragments.json``).
Deterministische Metriken nur — die blinde Human-Rubrik bleibt ausdrücklich
menschlich (Ingest über ``role_model_eval``). Wiederverwendet die bestehenden
A2-Metriken aus ``model_quality`` (keine Duplikation).

Ehrliche Definitionen (siehe docs/evaluation/metrics.md):
- ``boundary_accuracy`` ist Fragment-Provenienz + exakte Wertgrenze — das
  A1-Schema (``ExtractedFactRecord``) kennt keine Zeichen-Offsets; eine
  Offset-Boundary wäre eine Contract-Änderung und ist bewusst NICHT Teil
  dieser Evaluation.
- Sprachkonsistenz ist eine Stopwort-Heuristik; Rechts-/Partner-Detektoren
  sind Regex-Flags. Ein Fatal-Ausschluss erfolgt erst nach menschlicher
  Adjudikation (``requires_human_adjudication``).
"""
from __future__ import annotations

import json
import random
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

from app.agents import allowed_facts
from app.evaluation.model_quality import (
    FAIL,
    NOT_RUN,
    PASS,
    MetricResult,
    char_limit_respected,
    extract_numbers,
    kpi_gaps_marked_open,
    mandatory_subsections_present,
    no_review_notes_as_prose,
    terms_preserved,
)

# Die Erfindungs-Detektoren dieser Evaluation stammen AUSSCHLIESSLICH aus
# ``app.agents.allowed_facts`` — derselben Implementierung, die das
# Produktionsgate benutzt (Owner 2026-07-17). Die frühere Zweitimplementierung
# (Exakt-Token-Vergleich gegen einen eigenen Fallkorpus) hat bekannte
# Fixture-Angaben als Erfindung markiert und ist ersatzlos entfallen.

# Severity-Gewichte für den A3-Recall (Safety-/Blocker-Findings zählen mehr).
SEVERITY_WEIGHTS = {
    "budget_blocker": 3,
    "export_blocker": 3,
    "evidence_risk": 2,
    "human_review_required": 2,
    "reviewer_risk": 1,
}

# A2-Gewichtung nach bestandenem Fatal-Gate (Auftrag; Summe = 1.0).
A2_WEIGHTS = {
    "factuality_evidence": 0.25,
    "coverage_fit": 0.20,
    "argumentation_usefulness": 0.20,
    "market_reviewer": 0.10,
    "structure_readability": 0.10,
    "consistency_charbudget": 0.10,
    "cost_latency": 0.05,
}

# Blinde Human-Rubrik A2 (8 Kriterien, 1–5) → Gewichtungs-Bucket.
A2_RUBRIC_BUCKETS = {
    "crit_1_feldrelevanz_vollstaendigkeit": "coverage_fit",
    "crit_2_logische_argumentation": "argumentation_usefulness",
    "crit_3_markt_nutzerorientierung": "market_reviewer",
    "crit_4_innosuisse_reviewer_passung": "coverage_fit",
    "crit_5_spezifitaet_statt_buzzwords": "argumentation_usefulness",
    "crit_6_struktur_lesbarkeit": "structure_readability",
    "crit_7_faktentreue_evidence_disziplin": "factuality_evidence",
    "crit_8_nuetzlichkeit_nachbearbeitung": "argumentation_usefulness",
}

# Blinde Human-Rubrik A3 (8 Kriterien, 1–5) — direkt gemittelt.
A3_RUBRIC_CRITERIA = (
    "crit_1_baseline_kpi_luecken",
    "crit_2_methodology_abstraction",
    "crit_3_schwache_sota_differenzierung",
    "crit_4_unbelegte_marktclaims",
    "crit_5_partner_rollenluecken",
    "crit_6_scope_wp_risk_probleme",
    "crit_7_gruppierung_statt_alertflut",
    "crit_8_konkrete_naechste_aktion",
)

_DEFAULT_CASES_DIR = (
    Path(__file__).resolve().parents[3] / "docs" / "evaluation" / "cases"
)


class GoldError(ValueError):
    """Gold-/Fragmentdatei fehlt oder verletzt das erwartete Schema."""


@dataclass(frozen=True)
class CaseGold:
    case_id: str
    holdout: bool
    title_de: str
    title_en: str
    required_terms: tuple[str, ...]
    entities: tuple[str, ...]
    portal_boilerplate: tuple[str, ...]
    gold_facts: tuple[dict, ...]
    gold_missing: tuple[dict, ...]
    gold_findings: tuple[dict, ...]
    # Kanonische Antragssprache des Falls (Priorität 1 der Sprachauflösung);
    # None ⇒ aus dem Draft/Portalfeld ableiten, nie still auf «de» fallen.
    case_language: str | None = None


def load_case_gold(case_id: str, cases_dir: Path | None = None) -> CaseGold:
    path = (cases_dir or _DEFAULT_CASES_DIR) / f"{case_id}_gold.json"
    if not path.exists():
        raise GoldError(f"Gold-Datei fehlt: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in ("case_id", "title_de", "title_en", "required_terms",
                "entities", "portal_boilerplate", "gold_facts", "gold_missing"):
        if key not in raw:
            raise GoldError(f"{path.name}: Pflichtschlüssel fehlt: {key}")
    if raw["case_id"] != case_id:
        raise GoldError(f"{path.name}: case_id {raw['case_id']!r} != {case_id!r}")
    for fact in raw["gold_facts"]:
        for key in ("gold_id", "fact_type", "keywords", "fragment_ids"):
            if key not in fact:
                raise GoldError(
                    f"{path.name}: gold_fact ohne Pflichtschlüssel {key!r}"
                )
    for finding in raw.get("gold_findings", []):
        for key in ("finding_id", "field_id", "target_section", "severity",
                    "a3_scope", "keywords"):
            if key not in finding:
                raise GoldError(
                    f"{path.name}: gold_finding ohne Pflichtschlüssel {key!r}"
                )
    return CaseGold(
        case_id=raw["case_id"],
        holdout=bool(raw.get("holdout", False)),
        title_de=raw["title_de"],
        title_en=raw["title_en"],
        required_terms=tuple(raw["required_terms"]),
        entities=tuple(raw["entities"]),
        portal_boilerplate=tuple(raw["portal_boilerplate"]),
        gold_facts=tuple(raw["gold_facts"]),
        gold_missing=tuple(raw["gold_missing"]),
        gold_findings=tuple(raw.get("gold_findings", [])),
        case_language=raw.get("case_language"),
    )


def resolve_expected_language(
    gold: CaseGold | None,
    *,
    draft_language: str | None = None,
    project_language: str | None = None,
    detected_language: str | None = None,
) -> tuple[str, str]:
    """Kanonische Antragssprache → (Sprache, Quelle). NIE ein stiller
    «de»-Default: die Reihenfolge ist explizite Fallkonfiguration → Draft-/
    Portalfeldsprache → Projektantragssprache → dokumentierte Erkennung.

    Die Draft-/Portalfeldsprache ist dieselbe Quelle, die das Produktionsgate
    verwendet (``A2Context.language``) — Evaluation und Produktion beurteilen
    damit dieselbe Erwartung.
    """
    for value, source in (
        (gold.case_language if gold else None, "case_language"),
        (draft_language, "draft_field_language"),
        (project_language, "project_application_language"),
        (detected_language, "language_detection_fallback"),
    ):
        normalized = str(value or "").strip().casefold()
        if normalized in ("de", "en"):
            return normalized, source
    raise GoldError(
        "Erwartete Sprache nicht auflösbar — kein stiller Default. Setze "
        "case_language im Gold oder übergib die Draft-/Projektsprache."
    )


def load_case_fragments(case_id: str, cases_dir: Path | None = None) -> list[dict]:
    path = (cases_dir or _DEFAULT_CASES_DIR) / f"{case_id}_fragments.json"
    if not path.exists():
        raise GoldError(f"Fragment-Datei fehlt: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    fragments = raw.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        raise GoldError(f"{path.name}: keine Fragmente")
    for frag in fragments:
        if not frag.get("fragment_id") or not (frag.get("text") or "").strip():
            raise GoldError(f"{path.name}: Fragment ohne id/text")
    return fragments


def fragments_corpus(fragments: list[dict]) -> str:
    return "\n\n".join(frag["text"] for frag in fragments)


# --- Textnormalisierung ------------------------------------------------------


def _fold(text: str | None) -> str:
    return (text or "").casefold()


def _norm_value(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"[\d.,'’ ]+", text):
        return text.replace("'", "").replace("’", "").replace(" ", "").replace(",", ".")
    return " ".join(text.casefold().split())


def keyword_ratio(text: str | None, keywords: list[str] | tuple[str, ...]) -> float:
    if not keywords:
        return 0.0
    folded = _fold(text)
    return sum(1 for kw in keywords if _fold(kw) in folded) / len(keywords)


def section_matches(pred_section: str | None, gold_section: str | None) -> bool:
    """Präfix-Match: Gold «4.5» trifft Vorhersagen «4.5», «4.5.1» …"""
    if not gold_section:
        return True
    if not pred_section:
        return False
    return pred_section == gold_section or pred_section.startswith(gold_section + ".")


# --- A1: Fact-Extraction-Scoring ---------------------------------------------


def _value_matches(pred: dict, gold: dict) -> bool:
    gold_value = _norm_value(gold.get("normalized_value"))
    if not gold_value:
        return False
    if _norm_value(pred.get("normalized_value")) == gold_value:
        return True
    statement = _norm_value(pred.get("statement"))
    return bool(gold_value) and gold_value in statement


def match_a1_fact(pred: dict, gold: dict) -> bool:
    """Wert-Match ODER ≥0.5 Keyword-Trefferquote auf dem Statement."""
    if _value_matches(pred, gold):
        return True
    return keyword_ratio(pred.get("statement"), gold.get("keywords", [])) >= 0.5


def _greedy_match(preds: list[dict], golds: tuple[dict, ...], matcher) -> dict[str, int]:
    """Greedy Gold→Prediction-Zuordnung; jede Prediction höchstens einmal."""
    used: set[int] = set()
    pairs: dict[str, int] = {}
    for gold in golds:
        for idx, pred in enumerate(preds):
            if idx in used:
                continue
            if matcher(pred, gold):
                pairs[gold["gold_id"]] = idx
                used.add(idx)
                break
    return pairs


def score_a1(result: dict, gold: CaseGold) -> dict:
    """Deterministische A1-Metriken gegen den Fall-Goldstandard.

    ``result`` ist das schema-validierte ``ProjectFactExtractionResult``-Payload
    (facts / conflicts / missing_information).
    """
    preds = list(result.get("facts") or [])
    missing_preds = list(result.get("missing_information") or [])
    pairs = _greedy_match(preds, gold.gold_facts, match_a1_fact)

    # Precision: Anteil Predictions, die IRGENDEIN Gold-Fakt treffen (auch ohne
    # Greedy-Slot — Doppel-Nennungen desselben Fakts sind kein False Positive).
    matched_pred = sum(
        1 for pred in preds
        if any(match_a1_fact(pred, g) for g in gold.gold_facts)
    )
    fact_precision = matched_pred / len(preds) if preds else 0.0
    fact_recall = len(pairs) / len(gold.gold_facts) if gold.gold_facts else 0.0

    # Field accuracy: Gold-Fakten mit target_ref — Match UND gleicher target_ref.
    targeted = [g for g in gold.gold_facts if g.get("target_ref")]
    field_hits = 0
    for g in targeted:
        idx = pairs.get(g["gold_id"])
        if idx is not None and preds[idx].get("target_ref") == g["target_ref"]:
            field_hits += 1
    field_accuracy = field_hits / len(targeted) if targeted else None

    # Boundary: Provenienz ⊆ Gold-Fragmente UND (falls Gold-Wert) exakter Wert.
    boundary_hits = 0
    for g in gold.gold_facts:
        idx = pairs.get(g["gold_id"])
        if idx is None:
            continue
        pred = preds[idx]
        allowed = set(g.get("fragment_ids") or [])
        provenance_ok = bool(pred.get("source_fragment_ids")) and set(
            pred.get("source_fragment_ids") or []
        ) <= allowed
        gold_value = _norm_value(g.get("normalized_value"))
        value_ok = (not gold_value) or (
            _norm_value(pred.get("normalized_value")) == gold_value
        )
        if provenance_ok and value_ok:
            boundary_hits += 1
    boundary_accuracy = boundary_hits / len(pairs) if pairs else None

    # Entity preservation: erwähnte Entities müssen wörtlich erhalten sein.
    mentioned = preserved = 0
    all_statements = [str(p.get("statement") or "") for p in preds]
    for entity in gold.entities:
        hits = [s for s in all_statements if _fold(entity) in _fold(s)]
        if not hits:
            continue
        mentioned += 1
        if any(entity in s for s in hits):
            preserved += 1
    entity_preservation = preserved / mentioned if mentioned else None

    # Falsche Portaltextübernahme: Statements, die Portal-Boilerplate enthalten.
    portal_hits = sum(
        1 for s in all_statements
        if any(_fold(marker) in _fold(s) for marker in gold.portal_boilerplate)
    )
    portal_adoption_rate = portal_hits / len(preds) if preds else 0.0

    # Missing-Information-Recall (target_ref-Gleichheit ODER Keyword-Match).
    def match_missing(pred: dict, g: dict) -> bool:
        if g.get("target_ref") and pred.get("target_ref") == g["target_ref"]:
            return True
        return keyword_ratio(pred.get("description"), g.get("keywords", [])) >= 0.34

    missing_pairs = _greedy_match(
        [dict(m, gold_id="") for m in missing_preds], gold.gold_missing, match_missing
    ) if gold.gold_missing else {}
    missing_recall = (
        len(missing_pairs) / len(gold.gold_missing) if gold.gold_missing else None
    )

    return {
        "fact_precision": round(fact_precision, 4),
        "fact_recall": round(fact_recall, 4),
        "field_accuracy": None if field_accuracy is None else round(field_accuracy, 4),
        "boundary_accuracy": (
            None if boundary_accuracy is None else round(boundary_accuracy, 4)
        ),
        "entity_preservation": (
            None if entity_preservation is None else round(entity_preservation, 4)
        ),
        "portal_text_adoption_rate": round(portal_adoption_rate, 4),
        "missing_recall": None if missing_recall is None else round(missing_recall, 4),
        "counts": {
            "predicted_facts": len(preds),
            "gold_facts": len(gold.gold_facts),
            "matched_gold": len(pairs),
            "predicted_missing": len(missing_preds),
            "gold_missing": len(gold.gold_missing),
            "portal_text_hits": portal_hits,
        },
        "matched_gold_ids": sorted(pairs),
    }


# --- A2: automatische Gates + Fatal-Detektoren -------------------------------

# Kleine Stopwort-Listen (Heuristik, dokumentiert in metrics.md).
_DE_STOPWORDS = frozenset(
    "der die das und oder nicht mit für von einen eine einem durch wird werden "
    "sind ist im am auf bei nach über unter zwischen sowie dass sich auch noch "
    "bereits sollen soll kann können müssen wurde wurden".split()
)
_EN_STOPWORDS = frozenset(
    "the and or not with for from through will are is in on at after about "
    "under between as that also already shall can must was were been this "
    "these those has have had which".split()
)

_ORG_SUFFIX_RE = re.compile(
    r"\b([A-ZÄÖÜ][\w&.-]*(?:\s+[A-ZÄÖÜ][\w&.-]*){0,4})\s+(AG|GmbH|SA|SARL|Sàrl|Ltd|Inc)\b"
)
_TRL_RE = re.compile(r"\bTRL\s*\d\b", re.I)
_LEGAL_CLAIM_PATTERNS = (
    re.compile(r"\bförderfähig\b", re.I),
    re.compile(r"\bförderberechtigt\b", re.I),
    re.compile(r"\brechtlich (?:zulässig|unbedenklich|geklärt)\b", re.I),
    re.compile(r"\beligib(?:le|ility) (?:is )?(?:confirmed|granted|approved)\b", re.I),
    re.compile(r"\berfüllt alle (?:rechtlichen|gesetzlichen) (?:Anforderungen|Vorgaben)\b", re.I),
    re.compile(r"\bZusage der Förderung\b", re.I),
)
_URL_RE = re.compile(r"https?://[^\s)\]>»]+", re.I)


def language_consistent(text: str, expected: str) -> MetricResult:
    """Stopwort-Heuristik: dominante Sprache muss ``expected`` sein (Anteil ≥ 0.6).

    ``expected`` ist PFLICHT — ein Default («de») hat englische Fälle
    reihenweise falsch disqualifiziert. Die Erwartung kommt aus der kanonischen
    Fallkonfiguration (``resolve_expected_language``), nie aus dieser Funktion.

    Kurztexte (< 30 Wörter) sind nicht bewertbar → not_run. Heuristik — das
    Human-Bestätigungsfeld im Blindbogen bleibt massgeblich.
    """
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", _fold(text))
    if len(words) < 30:
        return MetricResult(
            "language_consistent", NOT_RUN, "Text zu kurz für die Sprachheuristik."
        )
    de_hits = sum(1 for w in words if w in _DE_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    total = de_hits + en_hits
    if total < 8:
        return MetricResult(
            "language_consistent", NOT_RUN, "Zu wenige Stopwort-Signale."
        )
    dominant = "de" if de_hits >= en_hits else "en"
    share = max(de_hits, en_hits) / total
    ok = dominant == expected and share >= 0.6
    return MetricResult(
        "language_consistent",
        PASS if ok else FAIL,
        f"dominant={dominant} ({share:.0%} von {total} Stopwort-Treffern), "
        f"erwartet={expected}.",
    )


def no_invented_numbers(report: allowed_facts.ClaimReport) -> MetricResult:
    """Zahlen müssen im sichtbaren Request stehen (Manifest, normalisiert).

    Deterministisch ableitbare Zahlen sind KEINE Erfindung — sie erscheinen als
    ``derived_numeric_claim`` und gehen ins menschliche Review.
    """
    invented = report.invented_numbers
    detail = (
        "Keine Zahlen ausserhalb des sichtbaren Requests."
        if not invented
        else f"{len(invented)} Zahl(en) ohne Eingabe-Grundlage."
    )
    if report.derived_numbers:
        detail += (
            f" {len(report.derived_numbers)} ableitbare Zahl(en) "
            "(derived_numeric_claim) — menschliche Prüfung."
        )
    return MetricResult(
        "no_invented_numbers", PASS if not invented else FAIL, detail
    )


def no_invented_patents(report: allowed_facts.ClaimReport) -> MetricResult:
    """Erfundene Patent-ID ODER Schutzrechts-Behauptung ohne jede Grundlage."""
    if report.invented_patents:
        detail = f"{len(report.invented_patents)} Patent-ID(s) ohne Eingabe-Grundlage."
    elif report.unsupported_patent_claim:
        detail = "Patentbehauptung, obwohl der Request keine Schutzrechte nennt."
    else:
        detail = "Keine erfundene Patentbehauptung."
    return MetricResult(
        "no_invented_patents",
        FAIL if (report.invented_patents or report.unsupported_patent_claim) else PASS,
        detail,
    )


def no_invented_partners(report: allowed_facts.ClaimReport) -> MetricResult:
    invented = report.invented_organisations
    return MetricResult(
        "no_invented_partners",
        PASS if not invented else FAIL,
        "Keine Organisationsnamen ausserhalb des sichtbaren Requests."
        if not invented
        else f"{len(invented)} Organisationsname(n) ohne Eingabe-Grundlage.",
    )


def no_invented_trl(report: allowed_facts.ClaimReport) -> MetricResult:
    invented = report.invented_trl
    return MetricResult(
        "no_invented_trl",
        PASS if not invented else FAIL,
        "Keine TRL-Behauptung ausserhalb des sichtbaren Requests."
        if not invented
        else f"TRL-Behauptung(en) ohne Eingabe-Grundlage: {len(invented)}.",
    )


def no_legal_clearance_claims(text: str) -> MetricResult:
    hits = sum(1 for pattern in _LEGAL_CLAIM_PATTERNS if pattern.search(text or ""))
    return MetricResult(
        "no_legal_clearance_claims",
        PASS if hits == 0 else FAIL,
        "Keine Rechts-/Eligibility-Freigabeformulierung."
        if hits == 0
        else f"{hits} Rechts-/Eligibility-Formulierung(en) — menschliche "
             "Adjudikation erforderlich.",
    )


def sources_exist(text: str, allowed_sources: tuple[str, ...]) -> MetricResult:
    """Referenzierte URLs/Quellentitel müssen in den geseedeten Quellen existieren."""
    urls = set(_URL_RE.findall(text or ""))
    allowed_folded = tuple(_fold(s) for s in allowed_sources)
    unknown = sorted(
        url for url in urls
        if not any(_fold(url).rstrip("/.") in a or a in _fold(url) for a in allowed_folded)
    )
    if not urls:
        return MetricResult(
            "sources_exist", PASS, "Keine expliziten Quellenreferenzen im Text."
        )
    return MetricResult(
        "sources_exist",
        PASS if not unknown else FAIL,
        f"{len(urls) - len(unknown)}/{len(urls)} Quellenreferenzen existieren"
        + (f"; unbekannt: {len(unknown)}" if unknown else "."),
    )


def foreign_portal_sections(text: str, foreign_markers: tuple[str, ...]) -> MetricResult:
    """Fremde Portalabschnitte (Marker anderer Felder) dürfen nicht als
    Abschnittsüberschrift im finalen Feldtext stehen."""
    hits = [
        marker for marker in foreign_markers
        if re.search(rf"^\s*{re.escape(marker)}\b", text or "", re.M)
    ]
    return MetricResult(
        "no_foreign_portal_sections",
        PASS if not hits else FAIL,
        "Keine fremden Portalabschnitte."
        if not hits
        else f"Fremde Abschnittsmarker im Text: {', '.join(hits)}.",
    )


def a2_gate_results(
    text: str,
    *,
    schema_valid: bool,
    required_terms: tuple[str, ...],
    expected_markers: tuple[str, ...],
    char_limit: int | None,
    manifest: allowed_facts.AllowedFactsManifest,
    missing_inputs_count: int,
    human_review_required: bool,
    expected_language: str,
    allowed_sources: tuple[str, ...] = (),
) -> list[dict]:
    """Die 10 automatischen A2-Gates (Auftrag) als Statuszeilen.

    ``manifest`` ist die Erlaubt-Basis des tatsächlich sichtbaren Requests und
    ``expected_language`` die kanonisch aufgelöste Antragssprache — beide sind
    Pflicht, damit die Evaluation keine eigene, abweichende Wahrheit erfindet.

    Gate 1 (Schema) und Gate 10 (keine Auto-Freigabe) werden vom Harness
    beobachtet und hier nur berichtet.
    """
    report = allowed_facts.analyze_claims(text, manifest)
    gate_2 = mandatory_subsections_present(text, expected_markers)
    gate_3 = char_limit_respected(text, char_limit)
    gate_4 = language_consistent(text, expected_language)
    gate_5 = terms_preserved(text, required_terms)
    invented_checks = [
        no_invented_numbers(report),
        no_invented_patents(report),
        no_invented_partners(report),
        no_invented_trl(report),
        no_legal_clearance_claims(text),
        sources_exist(text, allowed_sources),
    ]
    gate_6_status = (
        FAIL if any(m.status == FAIL for m in invented_checks) else PASS
    )
    gate_7 = no_review_notes_as_prose(text)
    gate_8 = kpi_gaps_marked_open(text, missing_inputs_count)
    gate_9 = sources_exist(text, allowed_sources)
    rows = [
        {"gate": 1, "name": "valid_output_schema",
         "status": PASS if schema_valid else FAIL,
         "detail": "Gateway-Schema-Validierung."},
        {"gate": 2, "name": gate_2.name, "status": gate_2.status, "detail": gate_2.detail},
        {"gate": 3, "name": gate_3.name, "status": gate_3.status, "detail": gate_3.detail},
        {"gate": 4, "name": gate_4.name, "status": gate_4.status,
         "detail": gate_4.detail + " (Heuristik — Human-Bestätigung im Blindbogen)."},
        {"gate": 5, "name": gate_5.name, "status": gate_5.status, "detail": gate_5.detail},
        {"gate": 6, "name": "no_invented_facts",
         "status": gate_6_status,
         "detail": "; ".join(f"{m.name}={m.status}" for m in invented_checks)},
        {"gate": 7, "name": gate_7.name, "status": gate_7.status, "detail": gate_7.detail},
        {"gate": 8, "name": gate_8.name, "status": gate_8.status, "detail": gate_8.detail},
        {"gate": 9, "name": gate_9.name, "status": gate_9.status, "detail": gate_9.detail},
        {"gate": 10, "name": "no_auto_approval",
         "status": PASS if human_review_required else FAIL,
         "detail": "Vorschlag bleibt advisory («Prüfung nötig»)."},
    ]
    return rows


def gates_passed(gate_rows: list[dict]) -> bool:
    return not any(row["status"] == FAIL for row in gate_rows)


def fatal_gate_results(
    text: str,
    *,
    manifest: allowed_facts.AllowedFactsManifest,
    allowed_sources: tuple[str, ...] = (),
    evidence_ref_violations: int = 0,
    silent_fake_detected: bool = False,
    foreign_markers: tuple[str, ...] = (),
    confidential_terms: tuple[str, ...] = (),
    leak_scan_texts: tuple[str, ...] = (),
) -> list[dict]:
    """Fatal-Gates (Auftrag): ein bestätigter Verstoss schliesst den Kandidaten
    für die Rolle aus. Regex-basierte Treffer verlangen menschliche Adjudikation
    (``requires_human_adjudication``); Harness-Beobachtungen (stiller
    Fake-Wechsel, Evidence-IDs) sind hart.

    Die Erfindungs-Detektoren lesen dieselbe Erlaubt-Basis wie das
    Produktionsgate (``manifest``) — keine zweite Korpus-/Token-Logik."""
    report = allowed_facts.analyze_claims(text, manifest)
    number_check = no_invented_numbers(report)
    patent_check = no_invented_patents(report)
    partner_check = no_invented_partners(report)
    source_check = sources_exist(text, allowed_sources)
    legal_check = no_legal_clearance_claims(text)
    foreign_check = foreign_portal_sections(text, foreign_markers)
    leak_hits = 0
    for scan_text in leak_scan_texts:
        folded = _fold(scan_text)
        leak_hits += sum(1 for term in confidential_terms if _fold(term) in folded)
    rows = [
        {"name": "fatal_invented_number", "status": number_check.status,
         "detail": number_check.detail, "requires_human_adjudication": True},
        {"name": "fatal_invented_source", "status": source_check.status,
         "detail": source_check.detail, "requires_human_adjudication": True},
        {"name": "fatal_invented_partner", "status": partner_check.status,
         "detail": partner_check.detail, "requires_human_adjudication": True},
        {"name": "fatal_invented_patent", "status": patent_check.status,
         "detail": patent_check.detail, "requires_human_adjudication": True},
        {"name": "fatal_legal_clearance", "status": legal_check.status,
         "detail": legal_check.detail, "requires_human_adjudication": True},
        {"name": "fatal_confidential_leak",
         "status": PASS if leak_hits == 0 else FAIL,
         "detail": "Keine vertraulichen Marker in Query-/Log-Scans."
         if leak_hits == 0 else f"{leak_hits} vertrauliche Marker gefunden.",
         "requires_human_adjudication": False},
        {"name": "fatal_nonexistent_evidence_id",
         "status": PASS if evidence_ref_violations == 0 else FAIL,
         "detail": f"{evidence_ref_violations} ungültige Evidence-/Fragment-Referenz(en).",
         "requires_human_adjudication": False},
        {"name": "fatal_silent_fake_switch",
         "status": FAIL if silent_fake_detected else PASS,
         "detail": "Adapter-Selbstauskunft + generation_kind je Invocation geprüft.",
         "requires_human_adjudication": False},
        {"name": "fatal_foreign_portal_section", "status": foreign_check.status,
         "detail": foreign_check.detail, "requires_human_adjudication": True},
    ]
    return rows


def fatal_candidate(fatal_rows: list[dict]) -> bool:
    """True, wenn mindestens ein Fatal-Detektor angeschlagen hat (Sample ist
    ``fatal_candidate``; Ausschluss erst nach menschlicher Adjudikation für
    Regex-Detektoren)."""
    return any(row["status"] == FAIL for row in fatal_rows)


# Harte A2-Disqualifikationen (Auftrag) — ehrliche, getrennte Reason-Codes
# (Owner 2026-07-16): `dq_schema_error` NUR für tatsächlich ungültiges JSON
# oder eine echte Schema-Validierungsverletzung; valides JSON, das an einem
# fachlichen/kontextabhängigen Gate scheitert, bekommt seinen eigenen Code.
# Regex-Treffer verlangen weiterhin menschliche Adjudikation.
A2_HARD_DQ = (
    "dq_invented_fact",
    "dq_unsupported_numeric_claim",
    "dq_unsupported_partner_claim",
    "dq_unsupported_patent_claim",
    "dq_wrong_field_id",
    # Routing-IDs bindet der Caller (technisch). Widerspricht der Modellinhalt
    # dieser Bindung, ist das eine INHALTLICHE Disqualifikation — getrennt
    # geprüft und nie still überschrieben.
    "dq_wrong_section",
    "dq_no_candidate_for_field",
    "dq_tool_contract_error",
    "dq_invalid_target_section",
    "dq_wrong_language",
    "dq_review_notes_in_prose",
    "dq_char_limit",
    "dq_missing_structure",
    "dq_empty_output",
    "dq_unsupported_reference",
    "dq_truncated_output",
    "dq_schema_error",
)

_DQ_FATAL_NAMES = (
    "fatal_invented_number",
    "fatal_invented_partner",
    "fatal_invented_patent",
)
_DQ_GATE_NAMES = {
    "dq_wrong_language": "language_consistent",
    "dq_review_notes_in_prose": "no_review_notes_as_prose",
    "dq_char_limit": "char_limit",
}

# Orchestrator-/Gateway-Reason → sicherer DQ-Code. Quelle der Reasons:
# field_drafting._validate_candidate bzw. gateway._execute (Whitelist-Codes).
_REJECT_REASON_TO_DQ = {
    "invented_numeric_token": "dq_unsupported_numeric_claim",
    "invented_partner_name": "dq_unsupported_partner_claim",
    "invented_patent_claim": "dq_unsupported_patent_claim",
    "section_target_mismatch": "dq_wrong_field_id",
    "no_candidate_for_field": "dq_no_candidate_for_field",
    "provider_output_not_json": "dq_tool_contract_error",
    "provider_output_schema_invalid": "dq_schema_error",
    "output_schema_not_implemented": "dq_schema_error",
    "provider_output_truncated": "dq_truncated_output",
    "invalid_target_section": "dq_invalid_target_section",
    "all_findings_filtered": "dq_all_findings_filtered",
    "mandatory_structure_missing": "dq_missing_structure",
    "section_structure_missing": "dq_missing_structure",
    "character_limit_exceeded": "dq_char_limit",
    "empty_suggested_text": "dq_empty_output",
    "application_language_changed": "dq_wrong_language",
    "unknown_evidence_anchor": "dq_unsupported_reference",
    "unknown_research_source": "dq_unsupported_reference",
    "unknown_open_issue": "dq_unsupported_reference",
    "new_claim_without_source": "dq_unsupported_reference",
}


def a2_reject_reason_to_dq(reason: str | None) -> str | None:
    """Sicherer DQ-Code für einen Orchestrator-/Gateway-Reason (oder None)."""
    if not reason:
        return None
    if reason in _REJECT_REASON_TO_DQ:
        return _REJECT_REASON_TO_DQ[reason]
    # SectionStructureError-Codes (validate_section_candidate) sind eine
    # kleine offene Familie — konservativ als Strukturfehler klassifizieren.
    if "structure" in reason or reason.startswith("section_"):
        return "dq_missing_structure"
    return None


def a2_hard_disqualifications(
    gate_rows: list[dict],
    fatal_rows: list[dict],
    *,
    reject_reason: str | None = None,
    routing_metadata_mismatch: bool = False,
) -> list[str]:
    """Angeschlagene harte DQ-Kriterien (geordnete Teilmenge von A2_HARD_DQ).

    ``reject_reason`` ist der exakte Ablehnungsgrund des Orchestrators/
    Gateways — NUR daraus darf ``dq_schema_error``/``dq_tool_contract_error``
    etc. entstehen; die Gates liefern Sprache/Notizen/Zeichenlimit.
    ``routing_metadata_mismatch`` meldet, dass der Modellinhalt der
    Caller-Bindung widersprochen hat (eigener, inhaltlicher DQ)."""
    fired: set[str] = set()
    if routing_metadata_mismatch:
        fired.add("dq_wrong_section")
    fatal_failed = {
        row["name"] for row in fatal_rows if row["status"] == FAIL
    }
    gate_failed = {
        row["name"] for row in gate_rows if row["status"] == FAIL
    }
    if fatal_failed & set(_DQ_FATAL_NAMES):
        fired.add("dq_invented_fact")
    for dq, gate_name in _DQ_GATE_NAMES.items():
        if gate_name in gate_failed:
            fired.add(dq)
    mapped = a2_reject_reason_to_dq(reject_reason)
    if mapped:
        fired.add(mapped)
    return [dq for dq in A2_HARD_DQ if dq in fired]


# --- Drei Statusdimensionen (Owner 2026-07-17) --------------------------------
# Technische Vertragsvalidität, produktive Eignung und menschliche
# Bewertbarkeit sind DREI verschiedene Fragen. Sie zu vermischen hiess: ein
# echtes Modellverhalten (z. B. erfundene Referenzen) blockiert die technische
# Kalibrierung, und ein technisch valider Text bleibt der Blindbewertung
# vorenthalten. Inhaltliche DQs bleiben dabei vollständig erhalten.

# Inhaltliche DQ-Codes: Modellbefunde, nie technische Kalibrierungsblocker.
CONTENT_DQ = (
    "dq_invented_fact",
    "dq_unsupported_numeric_claim",
    "dq_unsupported_partner_claim",
    "dq_unsupported_patent_claim",
    "dq_unsupported_reference",
    "dq_wrong_section",
    "dq_wrong_language",
    "dq_review_notes_in_prose",
    "dq_char_limit",
)
# Technische DQ-Codes: der Vertrag selbst hat nicht getragen.
TECHNICAL_DQ = (
    "dq_schema_error",
    "dq_tool_contract_error",
    "dq_truncated_output",
    "dq_no_candidate_for_field",
    "dq_wrong_field_id",
    "dq_invalid_target_section",
    "dq_empty_output",
    "dq_missing_structure",
)


def sample_status_dimensions(
    *,
    execution: str,
    silent_fake: bool,
    schema_valid: bool,
    routing_metadata_source: str | None,
    usage: dict | None,
    hard_dq: tuple[str, ...] | list[str] = (),
    has_readable_output: bool = False,
) -> dict:
    """(technical_valid, production_eligible, human_evaluable) eines Samples.

    ``technical_valid``: echter Provider, kein Fake-Fallback, gültiges JSON im
    erwarteten Schema, caller-bound Routing, Usage/Kosten vollständig.
    ``production_eligible``: technisch valide UND ohne harte Inhalts-DQ.
    ``human_evaluable``: technisch valide UND ein lesbarer, zum Zielabschnitt
    gehörender Text bzw. ein lesbares Finding-Bundle.
    """
    dq = tuple(hard_dq or ())
    usage = usage or {}
    technical_valid = bool(
        execution == "real"
        and not silent_fake
        and schema_valid
        and routing_metadata_source == "caller_bound"
        and usage.get("cost_status") == "priced"
        and usage.get("input_tokens") is not None
        and usage.get("output_tokens") is not None
        and not any(code in TECHNICAL_DQ for code in dq)
    )
    return {
        "technical_valid": technical_valid,
        "production_eligible": bool(
            technical_valid and not any(code in CONTENT_DQ for code in dq)
        ),
        "human_evaluable": bool(technical_valid and has_readable_output),
    }


# --- A3: Critic-Scoring -------------------------------------------------------

# A3-Findings sind Hinweise — nie ein Förderentscheid. Zusätzlich zu den
# Rechts-/Eligibility-Mustern (A2) greifen hier Entscheids-Formulierungen.
_FUNDING_DECISION_PATTERNS = _LEGAL_CLAIM_PATTERNS + (
    re.compile(r"\bförderentscheid\w*\b", re.I),
    re.compile(r"\b(?:wird|werden|ist|sollte)\s+(?:nicht\s+)?(?:bewilligt|abgelehnt|gefördert)\b", re.I),
    re.compile(r"\bfunding decision\b", re.I),
    re.compile(r"\bshould (?:not )?be funded\b", re.I),
)

_FINDING_TEXT_KEYS = (
    "description", "suggested_improvement", "recommended_next_action",
)


def funding_decision_claims(findings: list[dict]) -> int:
    """Anzahl Findings, die eine Förderentscheids-Aussage formulieren."""
    hits = 0
    for finding in findings:
        text = " ".join(str(finding.get(key) or "") for key in _FINDING_TEXT_KEYS)
        if any(pattern.search(text) for pattern in _FUNDING_DECISION_PATTERNS):
            hits += 1
    return hits


def match_finding(pred: dict, gold: dict) -> bool:
    """Feld + Sektions-Präfix + Keyword-Match (Beschreibung + Vorschlag)."""
    if gold.get("field_id") and pred.get("field_id") != gold["field_id"]:
        return False
    if not section_matches(pred.get("target_section"), gold.get("target_section")):
        return False
    text = " ".join(
        str(pred.get(key) or "")
        for key in ("description", "suggested_improvement", "recommended_next_action")
    )
    return keyword_ratio(text, gold.get("keywords", [])) >= 0.34


def _near_duplicates(findings: list[dict]) -> int:
    """Anzahl Finding-Paare mit gleichem Ziel und hoher Token-Überlappung."""
    def tokens(f: dict) -> set[str]:
        return set(re.findall(r"[a-zä-ü0-9#]+", _fold(f.get("description"))))

    count = 0
    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            a, b = findings[i], findings[j]
            if (a.get("field_id"), a.get("target_section")) != (
                b.get("field_id"), b.get("target_section")
            ):
                continue
            ta, tb = tokens(a), tokens(b)
            if not ta or not tb:
                continue
            if len(ta & tb) / len(ta | tb) >= 0.6:
                count += 1
    return count


def score_a3(
    findings: list[dict],
    gold: CaseGold,
    *,
    flaw_keywords: tuple[str, ...] | None = None,
) -> dict:
    """Deterministische A3-Metriken gegen die Gold-Findings (nur a3_scope)."""
    scope_gold = tuple(g for g in gold.gold_findings if g.get("a3_scope"))
    pairs = _greedy_match(
        findings,
        tuple(dict(g, gold_id=g["finding_id"]) for g in scope_gold),
        match_finding,
    )
    total_weight = sum(
        SEVERITY_WEIGHTS.get(g["severity"], 1) for g in scope_gold
    )
    matched_weight = sum(
        SEVERITY_WEIGHTS.get(g["severity"], 1)
        for g in scope_gold if g["finding_id"] in pairs
    )
    weighted_recall = matched_weight / total_weight if total_weight else None

    unmatched = [
        f for f in findings
        if not any(match_finding(f, g) for g in scope_gold)
    ]
    fp_rate = len(unmatched) / len(findings) if findings else 0.0

    near_dups = _near_duplicates(findings)
    possible_pairs = len(findings) * (len(findings) - 1) / 2
    grouping_quality = (
        1.0 - (near_dups / possible_pairs) if possible_pairs else None
    )

    fixable = sum(
        1 for f in findings
        if (f.get("suggested_improvement") or f.get("recommended_next_action") or "").strip()
    )
    fixability_rate = fixable / len(findings) if findings else None

    false_consensus = None
    if flaw_keywords is not None:
        flaw_found = any(
            keyword_ratio(
                " ".join(str(f.get(k) or "") for k in
                         ("description", "suggested_improvement",
                          "recommended_next_action")),
                flaw_keywords,
            ) >= 0.34
            for f in findings
        )
        false_consensus = not flaw_found

    return {
        "finding_recall_weighted": (
            None if weighted_recall is None else round(weighted_recall, 4)
        ),
        "false_positive_rate": round(fp_rate, 4),
        "grouping_quality": (
            None if grouping_quality is None else round(grouping_quality, 4)
        ),
        "fixability_rate": (
            None if fixability_rate is None else round(fixability_rate, 4)
        ),
        "false_consensus": false_consensus,
        "funding_decision_claims": funding_decision_claims(findings),
        "counts": {
            "predicted_findings": len(findings),
            "gold_findings_in_scope": len(scope_gold),
            "matched_gold": len(pairs),
            "unmatched_predictions": len(unmatched),
            "near_duplicate_pairs": near_dups,
        },
        "matched_gold_ids": sorted(pairs),
        "unmatched_for_adjudication": len(unmatched),
    }


# --- Aggregation ---------------------------------------------------------------


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None, None
    mean = statistics.fmean(cleaned)
    std = statistics.stdev(cleaned) if len(cleaned) > 1 else 0.0
    return round(mean, 4), round(std, 4)


def deterministic_gate_share(gate_rows: list[dict]) -> float:
    """Anteil bestandener Gates (not_run zählt nicht in den Nenner)."""
    relevant = [r for r in gate_rows if r["status"] in (PASS, FAIL)]
    if not relevant:
        return 0.0
    return sum(1 for r in relevant if r["status"] == PASS) / len(relevant)


def weighted_a2_score(
    human_means: dict[str, float] | None,
    *,
    gate_share: float,
    cost_latency_score: float | None,
) -> dict:
    """Gewichteter A2-Qualitätswert (0–1) nach Auftrag.

    ``human_means``: Mittelwerte 1–5 je Rubrik-Kriterium (None = Rubrik offen →
    Human-Buckets werden als ``pending`` ausgewiesen, der Score ist vorläufig
    und nur über deterministische Anteile gebildet).
    """
    buckets: dict[str, list[float]] = {}
    if human_means:
        for crit, bucket in A2_RUBRIC_BUCKETS.items():
            value = human_means.get(crit)
            if value is None:
                continue
            buckets.setdefault(bucket, []).append((float(value) - 1.0) / 4.0)
    components: dict[str, float | None] = {}
    for bucket in A2_WEIGHTS:
        if bucket == "consistency_charbudget":
            components[bucket] = round(gate_share, 4)
        elif bucket == "cost_latency":
            components[bucket] = (
                None if cost_latency_score is None else round(cost_latency_score, 4)
            )
        else:
            values = buckets.get(bucket)
            components[bucket] = (
                round(statistics.fmean(values), 4) if values else None
            )
    total_weight = 0.0
    total = 0.0
    for bucket, weight in A2_WEIGHTS.items():
        value = components[bucket]
        if value is None:
            continue
        total += weight * value
        total_weight += weight
    score = round(total / total_weight, 4) if total_weight else None
    pending = sorted(b for b, v in components.items() if v is None)
    return {
        "score": score,
        "components": components,
        "covered_weight": round(total_weight, 4),
        "pending_buckets": pending,
        "provisional": bool(pending),
    }


def cost_latency_relative(values: dict[str, float | None]) -> dict[str, float | None]:
    """Relative Kosten-/Latenzwertung über Kandidaten: bester = 1.0, linear bis
    zum schlechtesten = 0.0. ``None`` (nicht bepreisbar) bleibt None."""
    present = {k: v for k, v in values.items() if v is not None}
    if not present:
        return {k: None for k in values}
    lo, hi = min(present.values()), max(present.values())
    span = hi - lo
    out: dict[str, float | None] = {}
    for key, value in values.items():
        if value is None:
            out[key] = None
        elif span == 0:
            out[key] = 1.0
        else:
            out[key] = round(1.0 - (value - lo) / span, 4)
    return out


# --- Blindung -------------------------------------------------------------------


def build_blind_assignment(candidates: list[str], nonce: str) -> dict[str, str]:
    """Deterministische, nonce-randomisierte Zuordnung Kandidat → «Model A/B/…».

    Das Mapping gehört NUR in die lokale ``mapping.json`` (gitignoriert) — nie in
    Summaries oder Reports.
    """
    labels = [f"Model {chr(ord('A') + i)}" for i in range(len(candidates))]
    shuffled = list(candidates)
    random.Random(nonce).shuffle(shuffled)
    return {candidate: labels[i] for i, candidate in enumerate(shuffled)}


def shuffle_for_review(items: list, nonce: str) -> list:
    """Randomisierte Präsentationsreihenfolge für den Blindbogen (stabil je nonce)."""
    out = list(items)
    random.Random("order:" + nonce).shuffle(out)
    return out
