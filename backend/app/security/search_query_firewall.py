"""Search Query Firewall (Milestone 9J).

Deterministic, local, no-LLM screening of a web-research query **before** it can reach
Firecrawl. Detects project-confidential content (partner names, project title/aliases,
representatives, budget figures), generic sensitive patterns (e-mail, phone, currency
amounts), NDA markers and confidential keywords; produces a sanitized public-safe query,
a risk score, and an allow / require_human_approval / block decision.

Guarantees:
  * The raw query is hashed for correlation; the raw text is **never** returned for
    persistence beyond the in-session preview, never logged.
  * For D1/D2 the project-specific lexicon is applied (those names are confidential).
    For D0 only the generic detectors run (a public project's names are public).
  * Block-on-uncertainty (binding correction 9): for D1/D2, if the query reads like a
    free-form idea, or if sanitization cannot leave a usable public-safe query, the
    decision is ``block`` — never auto-sanitize-and-send.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Partner, Project
from app.evidence.tokenize import STOPWORDS, normalize_for_match
from app.security.confidential_terms import (
    BUDGET_RE,
    BUDGET_WORD_RE,
    CATEGORY_LABELS,
    CATEGORY_WEIGHTS,
    CONFIDENTIAL_KEYWORDS,
    EMAIL_RE,
    NAME_TOKEN_IGNORE,
    NDA_MARKERS,
    PHONE_RE,
)
from app.security.data_class import DataClass

# A query longer than this many tokens reads as a free-form description, not a search
# query — for confidential classes that cannot be confidently sanitized.
_FREE_FORM_TOKEN_THRESHOLD = 14
# Minimum usable sanitized query length (content chars) for a confidential class.
_MIN_SANITIZED_CHARS = 4
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class FirewallResult:
    raw_query_hash: str
    sanitized_query: str
    redaction_summary: list[dict]  # [{category, label, count}] — never raw values
    risk_score: int
    decision: str  # allow | require_human_approval | block
    reasons: list[str]
    detected_sensitive_categories: list[str]


@dataclass
class _LexEntry:
    category: str
    pattern: re.Pattern[str]


@dataclass
class Lexicon:
    entries: list[_LexEntry] = field(default_factory=list)


def raw_query_hash(raw_query: str) -> str:
    """Stable, opaque hash of the query (NFKC + casefold + whitespace-collapsed). The raw
    text is never persisted; this hash correlates preview ↔ create without leaking it."""
    normalized = re.sub(r"\s+", " ", normalize_for_match(raw_query)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _phrase_pattern(phrase: str) -> re.Pattern[str] | None:
    """Case-insensitive, whitespace-flexible pattern for a multi-word phrase."""
    parts = [re.escape(p) for p in phrase.split() if p]
    if not parts:
        return None
    return re.compile(r"(?i)\b" + r"\s+".join(parts) + r"\b")


def _token_pattern(token: str) -> re.Pattern[str] | None:
    if len(token) < 4 or token in STOPWORDS or token in NAME_TOKEN_IGNORE:
        return None
    return re.compile(r"(?i)\b" + re.escape(token) + r"\b")


def _significant_tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in _WORD_RE.findall(normalize_for_match(text)):
        if len(tok) >= 4 and tok not in STOPWORDS and tok not in NAME_TOKEN_IGNORE:
            out.append(tok)
    return out


def build_lexicon(db: Session, *, project_id: str, workspace_id: str) -> Lexicon:
    """Per-project confidential lexicon from LOCAL data only (never fetched).

    Sources (binding correction 10): project title, partner names, organization
    representatives, project-specific aliases (where available), budget values, plus
    user-maintained sensitive terms if such a mechanism exists (future hook).
    """
    lex = Lexicon()
    seen: set[str] = set()

    def add(category: str, pattern: re.Pattern[str] | None) -> None:
        if pattern is None:
            return
        key = f"{category}:{pattern.pattern}"
        if key in seen:
            return
        seen.add(key)
        lex.entries.append(_LexEntry(category, pattern))

    project = db.scalar(
        select(Project).where(
            Project.project_id == project_id, Project.workspace_id == workspace_id
        )
    )
    if project is not None:
        add("project_name", _phrase_pattern(project.title or ""))
        for tok in _significant_tokens(project.title or ""):
            add("project_name", _token_pattern(tok))
        if project.budget_framework_chf:
            add("budget_amount", _budget_value_pattern(project.budget_framework_chf))

    partners = db.scalars(
        select(Partner).where(
            Partner.project_id == project_id, Partner.workspace_id == workspace_id
        )
    )
    for partner in partners:
        add("partner_name", _phrase_pattern(partner.name or ""))
        for tok in _significant_tokens(partner.name or ""):
            add("partner_name", _token_pattern(tok))
        rep = partner.official_representative or {}
        for value in _representative_names(rep):
            add("person_name", _phrase_pattern(value))
    return lex


def _budget_value_pattern(amount: float) -> re.Pattern[str] | None:
    """Match the concrete project budget figure with common groupings."""
    whole = int(round(amount))
    if whole <= 0:
        return None
    plain = str(whole)
    grouped_apos = f"{whole:,}".replace(",", "'")
    grouped_dot = f"{whole:,}".replace(",", ".")
    grouped_space = f"{whole:,}".replace(",", " ")
    variants = sorted({plain, grouped_apos, grouped_dot, grouped_space}, key=len, reverse=True)
    alts = "|".join(re.escape(v) for v in variants)
    return re.compile(r"(?i)(?<!\d)(?:" + alts + r")(?!\d)")


def _representative_names(rep: dict) -> list[str]:
    out: list[str] = []
    for key in ("name", "full_name", "first_name", "last_name", "display_name"):
        value = rep.get(key)
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
    return out


def _looks_free_form(raw_query: str) -> bool:
    tokens = _WORD_RE.findall(raw_query)
    return len(tokens) > _FREE_FORM_TOKEN_THRESHOLD


def _scrub(text: str) -> str:
    """Collapse whitespace and dangling punctuation left by removals."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    return text.strip(" -–—,;:.")


def evaluate_query(
    db: Session,
    *,
    project_id: str,
    workspace_id: str,
    actor_user_id: str,
    raw_query: str,
    data_class: DataClass,
    intended_tool: str,
    purpose: str | None = None,
    source_context_ids: list[str] | None = None,
    apply_project_lexicon: bool = False,
) -> FirewallResult:
    """Screen ``raw_query`` and return a sanitized query + decision. Pure w.r.t. the DB
    (reads project/partners for the lexicon; writes nothing).

    ``apply_project_lexicon=True`` wendet das Projekt-Lexikon (Partnernamen,
    Projekttitel/-kürzel, Budgetzahl) zusätzlich auch für D0 an — genutzt von der
    Markt-Query-Freigabe (R8), damit editierte Queries eines öffentlichen Projekts
    diese Bezeichner ebenfalls nie nach aussen tragen. Nur Verschärfung; das
    Standardverhalten (D1/D2-only) bleibt unverändert."""
    qhash = raw_query_hash(raw_query)
    detected: dict[str, int] = {}
    working = raw_query

    def apply(pattern: re.Pattern[str], category: str) -> None:
        nonlocal working
        matches = pattern.findall(working)
        if matches:
            detected[category] = detected.get(category, 0) + len(matches)
            working = pattern.sub(" ", working)

    # Generic detectors (all classes).
    apply(EMAIL_RE, "email")
    apply(PHONE_RE, "phone")
    apply(BUDGET_RE, "budget_amount")
    apply(BUDGET_WORD_RE, "budget_amount")
    for marker in NDA_MARKERS:
        p = _phrase_pattern(marker)
        if p is not None:
            apply(p, "nda_marker")
    for keyword in CONFIDENTIAL_KEYWORDS:
        p = _phrase_pattern(keyword)
        if p is not None:
            apply(p, "confidential_keyword")

    # Project-specific lexicon — confidential classes only (D0 names are public),
    # ausser der Aufrufer verlangt es ausdrücklich (Markt-Query-Freigabe, R8).
    if apply_project_lexicon or data_class in (
        DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA
    ):
        lexicon = build_lexicon(db, project_id=project_id, workspace_id=workspace_id)
        for entry in lexicon.entries:
            apply(entry.pattern, entry.category)

    sanitized = _scrub(working)

    # Free-form idea heuristic (confidential classes can't be confidently sanitized).
    free_form = data_class in (
        DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA
    ) and _looks_free_form(raw_query)
    if free_form:
        detected["free_form_idea"] = detected.get("free_form_idea", 0) + 1

    risk = min(10, sum(CATEGORY_WEIGHTS.get(cat, 1) for cat in detected))
    categories = sorted(detected)
    summary = [
        {"category": cat, "label": CATEGORY_LABELS.get(cat, cat), "count": detected[cat]}
        for cat in categories
    ]

    decision, reasons = _decide(
        data_class=data_class,
        risk=risk,
        free_form=free_form,
        sanitized=sanitized,
        categories=categories,
    )
    return FirewallResult(
        raw_query_hash=qhash,
        sanitized_query=sanitized,
        redaction_summary=summary,
        risk_score=risk,
        decision=decision,
        reasons=reasons,
        detected_sensitive_categories=categories,
    )


def _content_len(text: str) -> int:
    return sum(len(t) for t in _WORD_RE.findall(text))


def _decide(
    *, data_class: DataClass, risk: int, free_form: bool, sanitized: str, categories: list[str]
) -> tuple[str, list[str]]:
    # D3/UNKNOWN: never reach any external tool.
    if data_class == DataClass.D3_NDA_BLOCKED:
        return "block", ["data_class_d3_nda_blocked"]
    if data_class == DataClass.UNKNOWN:
        return "block", ["data_class_unknown_blocked"]

    if data_class == DataClass.D0_PUBLIC:
        if risk <= 2:
            return "allow", ["d0_low_risk_allowed"]
        if risk <= 5:
            return "require_human_approval", ["d0_medium_risk_requires_approval"]
        return "block", ["d0_high_risk_blocked"]

    # D1 / D2 — confidential: never allow without preview + approval.
    reasons: list[str] = []
    if risk >= 6:
        return "block", ["confidential_high_risk_blocked"]
    # Block-on-uncertainty (correction 9): a free-form idea or an unusably-short
    # sanitized result cannot be confidently turned into a safe public query.
    if free_form:
        return "block", ["free_form_idea_cannot_be_sanitized"]
    if _content_len(sanitized) < _MIN_SANITIZED_CHARS:
        return "block", ["nothing_safe_left_after_sanitization"]
    reasons.append("confidential_requires_sanitized_approval")
    return "require_human_approval", reasons
