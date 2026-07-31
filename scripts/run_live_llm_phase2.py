#!/usr/bin/env python
r"""RUN 3C Phase 2: opt-in live LLM acceptance with resumable human gates.

This module is orchestration only. User-visible work is performed through the
production FastAPI routes. Direct database access is limited to disposable test
infrastructure, provider-preflight persistence, counters, and read-only review
material. The script never writes provider payloads or prompts to reports.

Usage (PowerShell, from repository root)::

    $env:RUN_REAL_PROVIDER_SMOKE = "true"
    $env:RUN_LIVE_LLM_SMOKES_APPROVED = "true"
    backend\.venv\Scripts\python.exe scripts\run_live_llm_phase2.py prepare-web

    backend\.venv\Scripts\python.exe scripts\run_live_llm_phase2.py resume-llm \
      --approval "APPROVE_LIVE_E2E_ANCHORS <session> <hashes>"

    backend\.venv\Scripts\python.exe scripts\run_live_llm_phase2.py bind-refined-anchors \
      --session-id <session> --passage <version:fragment:start:end:hash>

Normal tests import only the pure helpers below and never load provider keys.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SESSION_ROOT = Path(tempfile.gettempdir()) / "innolink-live-llm-phase2"
REPORT_PATH = ROOT / "docs" / "LIVE_LLM_SMOKE_REPORT.md"
HUMAN_REVIEW_PATH = ROOT / "docs" / "LIVE_LLM_HUMAN_REVIEW.md"
RUN_RESULT_PATH = ROOT / "docs" / "RUN_3_RESULT.md"

FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
LEGACY_FIELD_ID = "VC.BMM.EDITOR"
MANDATORY_FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1"
TARGET_SECTION = "3.1"
EXPECTED_SKILL_ID = "a2.value_creation_3_1"
EXPECTED_QUESTION = "3.1 Describe the business targets and the business model"
A2_ROLE = "A2_INNOSUISSE_PROPOSAL_WRITER"
MARKET_ROLE = "RESEARCH_EVIDENCE_SYNTHESIZER"
MAX_LLM_CALLS = 6
MAX_WEB_CALLS = 3
MAX_COST_CHF = 3.0
MAX_ACTIVE_SECONDS = 600.0
POLICY_VERSION = "1.1.0"
APPROVAL_PREFIX = "APPROVE_LIVE_E2E_ANCHORS"
SWISS_MARKET_POLICY = "global-estimates-not-swiss-market-v1"
SESSION_VERSION = "run3c-phase2-session-v1"
WEB_REVIEW_SESSION_TTL_SECONDS = 3600
ORIGIN = "http://localhost:3000"
SYNTHETIC_PASSWORD = "phase2-d0-local-only"
DEMO_DOMAINS = {"example.org", "example.com", "example.net"}

SMOKE_1_TEXT = (
    "Unsere Lösung richtet sich an Schweizer KMU und soll manuelle "
    "Compliance-Arbeiten reduzieren. Das Angebot wird als jährliche "
    "Softwarelizenz vertrieben. Erste Gespräche zeigen grundsätzliches Interesse."
)
SMOKE_2_TEXT = (
    "Die synthetische Softwarelösung unterstützt Schweizer KMU bei der "
    "strukturierten Bearbeitung wiederkehrender Compliance-Aufgaben. Das "
    "Geschäftsmodell ist eine jährliche Softwarelizenz. Marktangaben werden nur "
    "über ausdrücklich freigegebene öffentliche Belegstellen ergänzt."
)
SMOKE_3_TEXT = (
    "Die Lösung richtet sich an Schweizer KMU. Die Lösung reduziert manuelle "
    "Compliance-Arbeiten. Die Lösung wird als jährliche Softwarelizenz angeboten. "
    "Schweizer KMU erhalten damit eine strukturierte Unterstützung für wiederkehrende "
    "Compliance-Arbeiten. Das Kernproblem sind wiederkehrende manuelle Compliance-"
    "Arbeiten, die Zielgruppe sind Schweizer KMU, und der Nutzen ist eine klarere "
    "strukturierte Bearbeitung."
)


class HarnessFailure(RuntimeError):
    """Log-safe harness failure carrying only a stable reason code."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat(timespec="seconds")


def _sha256(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _safe_domain(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().rstrip(".")


def _is_demo_domain(domain: str) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in DEMO_DOMAINS)


def _redacted_error(exc: BaseException) -> str:
    return str(getattr(exc, "code", "") or type(exc).__name__).casefold()


def _idem() -> str:
    return uuid.uuid4().hex


@dataclass
class PlannedCall:
    label: str
    provider: str
    model_id: str
    max_input_chars: int
    max_output_tokens: int
    route_alias: str = "not_available"


@dataclass
class CallRecord:
    label: str
    provider: str
    model_id: str
    duration_seconds: float
    estimated_upper_cost_chf: float
    actual_cost_chf: float | None
    input_tokens: int | None
    output_tokens: int | None
    status: str


@dataclass
class RequestLedgerEntry:
    attempt_id: str
    request_sequence: int
    provider: str
    route_alias: str
    purpose: str
    started_at: str
    finished_at: str
    http_class: str
    http_status: int | str
    retryable: bool
    reason_code: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_chf: float | str
    actual_cost_chf: float | str


@dataclass
class AtomicRequestLedger:
    """Redacted request metadata persisted before a review session exists."""

    attempt_id: str
    path: Path
    entries: list[RequestLedgerEntry] = field(default_factory=list)

    def append(self, entry: RequestLedgerEntry) -> None:
        self.entries.append(entry)
        self.persist()

    def persist(self) -> None:
        payload = {
            "attempt_id": self.attempt_id,
            "requests": [asdict(item) for item in self.entries],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(_canonical_json(payload), encoding="utf-8")
        os.replace(temporary, self.path)

    @classmethod
    def load(cls, attempt_id: str, path: Path) -> "AtomicRequestLedger":
        if not path.is_file():
            return cls(attempt_id=attempt_id, path=path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("attempt_id") != attempt_id:
            raise HarnessFailure("request_ledger_attempt_mismatch")
        return cls(
            attempt_id=attempt_id,
            path=path,
            entries=[RequestLedgerEntry(**item) for item in payload.get("requests", [])],
        )


@dataclass
class BudgetLedger:
    planned: list[PlannedCall]
    records: list[CallRecord] = field(default_factory=list)
    active_label: str | None = None

    @property
    def actual_call_count(self) -> int:
        return len(self.records)

    @property
    def conservative_spent_chf(self) -> float:
        return sum(
            item.actual_cost_chf
            if item.actual_cost_chf is not None
            else item.estimated_upper_cost_chf
            for item in self.records
        )

    def remaining(self, excluding: str | None = None) -> list[PlannedCall]:
        used = [item.label for item in self.records]
        rows: list[PlannedCall] = []
        for item in self.planned:
            if item.label in used or item.label == excluding:
                continue
            rows.append(item)
        return rows

    def assert_time(self, additional: float = 0.0, *, active_seconds: float = 0.0) -> None:
        if active_seconds + additional > MAX_ACTIVE_SECONDS:
            raise HarnessFailure("live_active_time_limit_exceeded")


@dataclass
class AnchorProposal:
    result_id: str
    source_id: str
    source_version_id: str
    fragment_id: str
    start_offset: int
    end_offset: int
    domain: str
    title: str
    excerpt: str
    quote_hash: str
    safety_status: str
    content_review_status: str

    def safe_state(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("excerpt", None)
        value.pop("title", None)
        return value


@dataclass
class ReviewSession:
    review_session_id: str
    session_version: str
    created_at: str
    expires_at: str
    temp_root: str
    workspace_id: str
    actor_user_id: str
    actor_email: str
    cases: dict[str, dict[str, str]]
    research: dict[str, Any]
    anchors: list[dict[str, Any]]
    route_ids: dict[str, str]
    model_refs: dict[str, str]
    provider_config_fingerprints: dict[str, str]
    preflight_fingerprints: dict[str, str]
    policy_version: str
    pricing_version: str
    registry_version: str
    active_execution_seconds: float
    provider_call_seconds: float
    human_wait_started_at: str
    human_wait_ended_at: str | None
    ledger: dict[str, Any]
    consumed: bool = False
    state_hash: str = ""

    def payload_for_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("state_hash", None)
        # These fields change as part of the documented resume transition.
        data.pop("human_wait_ended_at", None)
        data.pop("consumed", None)
        data["anchors"] = sorted(data["anchors"], key=lambda item: item["quote_hash"])
        return data

    def refresh_hash(self) -> None:
        self.state_hash = _sha256(_canonical_json(self.payload_for_hash()))

    def verify_hash(self) -> None:
        expected = _sha256(_canonical_json(self.payload_for_hash()))
        if not hmac.compare_digest(self.state_hash, expected):
            raise HarnessFailure("live_session_integrity_invalid")


def _ledger_to_dict(ledger: BudgetLedger) -> dict[str, Any]:
    return {
        "planned": [asdict(item) for item in ledger.planned],
        "records": [asdict(item) for item in ledger.records],
        "active_label": None,
    }


def _ledger_from_dict(value: dict[str, Any]) -> BudgetLedger:
    return BudgetLedger(
        planned=[PlannedCall(**item) for item in value.get("planned", [])],
        records=[CallRecord(**item) for item in value.get("records", [])],
    )


def _request_ledger_path(temp_root: Path) -> Path:
    return temp_root / "redacted-request-ledger.json"


def _request_diagnosis(exc: BaseException | None):
    if exc is None:
        return None
    from app.provider_errors import classify_provider_failure

    return classify_provider_failure(
        str(exc), source_code=getattr(exc, "code", None),
        http_status=getattr(exc, "http_status", None),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _session_path(session_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise HarnessFailure("live_session_id_invalid")
    return SESSION_ROOT / session_id / "session.json"


def save_session(session: ReviewSession) -> Path:
    session.refresh_hash()
    path = _session_path(session.review_session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(path, _canonical_json(asdict(session)))
    return path


def load_session(session_id: str) -> ReviewSession:
    path = _session_path(session_id)
    if not path.is_file():
        raise HarnessFailure("live_session_not_found")
    session = ReviewSession(**json.loads(path.read_text(encoding="utf-8")))
    session.verify_hash()
    if session.session_version != SESSION_VERSION:
        raise HarnessFailure("live_session_version_invalid")
    expires = datetime.fromisoformat(session.expires_at)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _utcnow():
        raise HarnessFailure("live_session_expired")
    if session.consumed:
        raise HarnessFailure("live_session_already_consumed")
    return session


def parse_anchor_approval(value: str) -> tuple[str, list[str]]:
    parts = value.strip().split(maxsplit=2)
    if len(parts) != 3 or parts[0] != APPROVAL_PREFIX:
        raise HarnessFailure("live_anchor_approval_invalid")
    session_id = parts[1]
    hashes = [item.strip().casefold() for item in parts[2].split(",") if item.strip()]
    if not hashes or len(set(hashes)) != len(hashes):
        raise HarnessFailure("live_anchor_approval_invalid")
    if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in hashes):
        raise HarnessFailure("live_anchor_quote_hash_invalid")
    return session_id, hashes


def validate_anchor_approval(
    session: ReviewSession, value: str
) -> list[dict[str, Any]]:
    session_id, hashes = parse_anchor_approval(value)
    if session_id != session.review_session_id:
        raise HarnessFailure("live_anchor_session_mismatch")
    proposals = {item["quote_hash"]: item for item in session.anchors}
    if any(item not in proposals for item in hashes):
        raise HarnessFailure("live_anchor_quote_hash_unknown")
    selected = [proposals[item] for item in hashes]
    if len({item["source_version_id"] for item in selected}) < 2:
        raise HarnessFailure("insufficient_approved_source_versions")
    return selected


def parse_refined_passage(value: str) -> dict[str, Any]:
    """Parse a content-free exact-passage selector for an existing review session."""
    parts = value.strip().split(":")
    if len(parts) != 5:
        raise HarnessFailure("live_anchor_passage_selector_invalid")
    source_version_id, fragment_id, raw_start, raw_end, quote_hash = parts
    try:
        start_offset, end_offset = int(raw_start), int(raw_end)
    except ValueError as exc:
        raise HarnessFailure("live_anchor_passage_selector_invalid") from exc
    if (
        not source_version_id
        or not fragment_id
        or start_offset < 0
        or end_offset <= start_offset
        or end_offset - start_offset > 300
        or not re.fullmatch(r"[0-9a-f]{64}", quote_hash)
    ):
        raise HarnessFailure("live_anchor_passage_selector_invalid")
    return {
        "source_version_id": source_version_id,
        "fragment_id": fragment_id,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "quote_hash": quote_hash,
    }


def _opt_in_reason(settings: Any, *, require_llm: bool = True) -> str | None:
    if os.environ.get("CI"):
        return "ci_environment_blocked"
    if os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").casefold() != "true":
        return "live_smoke_opt_in_missing"
    approval_variable = (
        "RUN_LIVE_LLM_SMOKES_APPROVED" if require_llm
        else "RUN_FIRECRAWL_RECOVERY_APPROVED"
    )
    if os.environ.get(approval_variable, "").casefold() != "true":
        return (
            "live_llm_approval_missing" if require_llm
            else "firecrawl_recovery_approval_missing"
        )
    if settings.ai_eval_mode != "real":
        return "live_eval_mode_disabled"
    if settings.agent_fake_provider or settings.web_research_fake_provider:
        return "live_fake_conflict"
    if not settings.web_research_enabled:
        return "web_research_disabled"
    if require_llm and (not settings.openai_api_key or not settings.anthropic_api_key):
        return "live_provider_key_missing"
    if not settings.firecrawl_api_key:
        return "firecrawl_key_missing"
    return None


def _configure_environment(temp_root: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{(temp_root / 'phase2.db').as_posix()}"
    os.environ["SOURCE_STORAGE_DIR"] = str(temp_root / "sources")
    os.environ["CHECKPOINT_DB_PATH"] = str(temp_root / "checkpoints.db")
    os.environ["EXPORT_STORAGE_DIR"] = str(temp_root / "exports")
    os.environ["COOKIE_SECURE"] = "false"
    os.environ["APP_ENV"] = "test"
    os.environ["AI_EVAL_MODE"] = "real"
    os.environ["AGENT_FAKE_PROVIDER"] = "false"
    os.environ["WEB_RESEARCH_ENABLED"] = "true"
    os.environ["WEB_RESEARCH_FAKE_PROVIDER"] = "false"
    os.environ["WEB_SEARCH_MAX_RESULTS"] = "5"


def _mut(csrf: str, *, idem: str | None = None) -> dict[str, str]:
    result = {"X-CSRF-Token": csrf, "Origin": ORIGIN}
    if idem:
        result["Idempotency-Key"] = idem
    return result


def _expect(response: Any, status: int, code: str) -> dict[str, Any]:
    if response.status_code != status:
        raise HarnessFailure(code)
    try:
        return response.json()
    except Exception as exc:  # pragma: no cover - defensive live boundary
        raise HarnessFailure(f"{code}_invalid_json") from exc


def _assert_registry_contract() -> None:
    from app.agents.a2_fields import resolve_field_config, skill_id_for
    from app.registry import get_registry

    registry = get_registry()
    field = registry.portal_fields.get(FIELD_ID)
    mandatory = registry.portal_fields.get(MANDATORY_FIELD_ID)
    if field is None or mandatory is None:
        raise HarnessFailure("canonical_field_contract_missing")
    if getattr(mandatory, "label_or_question", None) != EXPECTED_QUESTION:
        raise HarnessFailure("canonical_field_instruction_changed")
    if skill_id_for(FIELD_ID, TARGET_SECTION) != EXPECTED_SKILL_ID:
        raise HarnessFailure("canonical_field_skill_changed")
    if LEGACY_FIELD_ID in registry.portal_fields:
        raise HarnessFailure("legacy_field_became_canonical")
    questions = registry.mandatory_questions(FIELD_ID)
    registry_markers = tuple(
        item.label_or_question.strip().split(maxsplit=1)[0] for item in questions
    )
    config = resolve_field_config(FIELD_ID)
    if config is None or registry_markers != config.mandatory_markers:
        raise HarnessFailure("canonical_field_markers_changed")


def _future_upper_cost(spec: PlannedCall, settings: Any) -> float:
    from app.evaluation.pricing import resolve_cost

    value = resolve_cost(
        provider=spec.provider,
        model_id=spec.model_id,
        input_tokens=spec.max_input_chars,
        output_tokens=spec.max_output_tokens,
        settings=settings,
    )
    if value.cost_status != "priced":
        raise HarnessFailure("unknown_price")
    return float(value.cost_chf)


def _assert_budget_before_call(
    ledger: BudgetLedger,
    *, label: str,
    provider: str,
    model_id: str,
    prompt: str,
    max_output_tokens: int,
    settings: Any,
) -> float:
    current = PlannedCall(
        label=label,
        provider=provider,
        model_id=model_id,
        max_input_chars=len(prompt),
        max_output_tokens=max_output_tokens,
    )
    estimate = _future_upper_cost(current, settings)
    reserve = sum(_future_upper_cost(item, settings) for item in ledger.remaining(label))
    if ledger.actual_call_count + 1 + len(ledger.remaining(label)) > MAX_LLM_CALLS:
        raise HarnessFailure("live_acceptance_incomplete_budget_exhausted")
    if ledger.conservative_spent_chf + estimate + reserve > MAX_COST_CHF:
        raise HarnessFailure("live_acceptance_incomplete_budget_exhausted")
    return estimate


@contextmanager
def instrument_live_providers(
    ledger: BudgetLedger, *, web_counter: dict[str, Any],
    request_ledger: AtomicRequestLedger | None = None,
) -> Iterator[None]:
    """Count unchanged production adapter calls without wrapping adapter objects."""
    from app.agents.providers.anthropic import AnthropicProvider
    from app.agents.providers.openai import OpenAIProvider
    from app.config.settings import get_settings
    from app.evaluation.pricing import resolve_cost
    from app.research.providers.firecrawl import FirecrawlProvider

    settings = get_settings()
    originals = {
        (OpenAIProvider, "generate"): OpenAIProvider.generate,
        (AnthropicProvider, "generate"): AnthropicProvider.generate,
        (FirecrawlProvider, "search"): FirecrawlProvider.search,
        (FirecrawlProvider, "fetch"): FirecrawlProvider.fetch,
    }

    def wrap_generate(provider_name: str, original):
        def counted(self, request):
            label = ledger.active_label
            if not label:
                raise HarnessFailure("unplanned_live_llm_call")
            max_output = int(request.max_output_tokens or 4096)
            estimate = _assert_budget_before_call(
                ledger,
                label=label,
                provider=provider_name,
                model_id=request.model_id,
                prompt=request.prompt,
                max_output_tokens=max_output,
                settings=settings,
            )
            started = time.monotonic()
            started_at = _iso()
            status = "failed"
            actual_cost = None
            input_tokens = output_tokens = None
            failure: BaseException | None = None
            try:
                result = original(self, request)
                status = "succeeded"
                input_tokens = int(result.usage.input_tokens)
                output_tokens = int(result.usage.output_tokens)
                priced = resolve_cost(
                    provider=provider_name,
                    model_id=request.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    adapter_name=self.name,
                    settings=settings,
                )
                if priced.cost_status != "priced":
                    raise HarnessFailure("unknown_price")
                actual_cost = float(priced.cost_chf)
                return result
            except BaseException as exc:
                failure = exc
                raise
            finally:
                duration = time.monotonic() - started
                ledger.records.append(CallRecord(
                    label=label,
                    provider=provider_name,
                    model_id=request.model_id,
                    duration_seconds=duration,
                    estimated_upper_cost_chf=estimate,
                    actual_cost_chf=actual_cost,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    status=status,
                ))
                if request_ledger is not None:
                    diagnosis = _request_diagnosis(failure)
                    spec = next((item for item in ledger.planned if item.label == label), None)
                    request_ledger.append(RequestLedgerEntry(
                        attempt_id=request_ledger.attempt_id,
                        request_sequence=len(request_ledger.entries) + 1,
                        provider=provider_name,
                        route_alias=(spec.route_alias if spec is not None else "not_available"),
                        purpose=label,
                        started_at=started_at,
                        finished_at=_iso(),
                        http_class=(diagnosis.http_class if diagnosis else "2xx"),
                        http_status=(diagnosis.http_status if diagnosis and diagnosis.http_status else "not_available"),
                        retryable=bool(diagnosis.retryable) if diagnosis else False,
                        reason_code=(diagnosis.reason_code if diagnosis else "none"),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_chf=estimate,
                        actual_cost_chf=(actual_cost if actual_cost is not None else "not_available"),
                    ))
                ledger.active_label = None
        return counted

    def wrap_web(kind: str, original):
        def counted(self, *args, **kwargs):
            if web_counter["calls"] >= MAX_WEB_CALLS:
                raise HarnessFailure("firecrawl_call_limit_exceeded")
            started = time.monotonic()
            started_at = _iso()
            web_counter["calls"] += 1
            failure: BaseException | None = None
            try:
                value = original(self, *args, **kwargs)
                credits = getattr(value, "credits_used", None)
                if credits is not None:
                    web_counter["credits"] += float(credits)
                return value
            except BaseException as exc:
                failure = exc
                raise
            finally:
                duration = time.monotonic() - started
                web_counter["seconds"] += duration
                web_counter["kinds"].append(kind)
                if request_ledger is not None:
                    diagnosis = _request_diagnosis(failure)
                    request_ledger.append(RequestLedgerEntry(
                        attempt_id=request_ledger.attempt_id,
                        request_sequence=len(request_ledger.entries) + 1,
                        provider="firecrawl",
                        route_alias="firecrawl",
                        purpose=f"public_{kind}",
                        started_at=started_at,
                        finished_at=_iso(),
                        http_class=(diagnosis.http_class if diagnosis else "2xx"),
                        http_status=(diagnosis.http_status if diagnosis and diagnosis.http_status else "not_available"),
                        retryable=bool(diagnosis.retryable) if diagnosis else False,
                        reason_code=(diagnosis.reason_code if diagnosis else "none"),
                        input_tokens=None,
                        output_tokens=None,
                        estimated_cost_chf="not_available",
                        actual_cost_chf="not_available",
                    ))
        return counted

    OpenAIProvider.generate = wrap_generate("openai_direct", originals[(OpenAIProvider, "generate")])
    AnthropicProvider.generate = wrap_generate(
        "anthropic_direct", originals[(AnthropicProvider, "generate")]
    )
    FirecrawlProvider.search = wrap_web("search", originals[(FirecrawlProvider, "search")])
    FirecrawlProvider.fetch = wrap_web("fetch", originals[(FirecrawlProvider, "fetch")])
    try:
        yield
    finally:
        for (cls, name), original in originals.items():
            setattr(cls, name, original)


def _planned_calls(settings: Any) -> tuple[list[PlannedCall], dict[str, str], dict[str, str]]:
    from app.agents.registry import get_agent_registry

    registry = get_agent_registry()
    a2_role = registry.role_routes[A2_ROLE]
    market_role = registry.role_routes[MARKET_ROLE]
    a2_key, market_key = a2_role.primary, market_role.primary
    a2_route, market_route = registry.route(a2_key), registry.route(market_key)
    a2_model = a2_route.requested_model_id(settings)
    market_model = market_route.requested_model_id(settings)
    if not a2_model or not market_model:
        raise HarnessFailure("live_model_id_missing")
    context_max = int(settings.a1_context_char_budget) + 30_000
    calls = [
        PlannedCall("a2_preflight", a2_route.provider, a2_model, 2_000, 256, a2_key),
        PlannedCall("live_02a", a2_route.provider, a2_model, context_max, 4096, a2_key),
    ]
    if market_key != a2_key:
        calls.append(PlannedCall(
            "market_preflight", market_route.provider, market_model, 2_000, 256, market_key
        ))
    calls.extend([
        PlannedCall("market_comparison", market_route.provider, market_model, 90_000, 4096, market_key),
        PlannedCall("live_02b", a2_route.provider, a2_model, context_max, 4096, a2_key),
        PlannedCall("live_02c", a2_route.provider, a2_model, context_max, 4096, a2_key),
    ])
    return calls, {"a2": a2_key, "market": market_key}, {
        "a2": a2_model, "market": market_model,
    }


def _seed_infrastructure() -> tuple[str, str, str]:
    from app.db.models import Base, FundingProfile, User, Workspace
    from app.db.session import SessionLocal, engine
    from app.security.passwords import hash_password

    Base.metadata.create_all(engine)
    suffix = uuid.uuid4().hex[:10]
    workspace_id = f"ws-phase2-{suffix}"
    actor_id = f"user-phase2-{suffix}"
    email = f"phase2-{suffix}@example.test"
    db = SessionLocal()
    try:
        db.add(Workspace(id=workspace_id, name="RUN 3C Phase 2 D0"))
        if db.get(FundingProfile, "innosuisse_innovation_project_with_implementation_partner") is None:
            db.add(FundingProfile(
                id="innosuisse_innovation_project_with_implementation_partner",
                title="Innosuisse Innovation Project",
            ))
        db.add(User(
            id=actor_id,
            workspace_id=workspace_id,
            name="Synthetic Phase 2 Reviewer",
            email=email,
            password_hash=hash_password(SYNTHETIC_PASSWORD),
            role="lead_admin",
        ))
        db.commit()
    finally:
        db.close()
    return workspace_id, actor_id, email


def _login(client: Any, email: str) -> str:
    response = client.post(
        "/api/v1/session", json={"email": email, "password": SYNTHETIC_PASSWORD}
    )
    return _expect(response, 200, "synthetic_login_failed")["csrf_token"]


def _select_current_primary_application(
    client: Any, csrf: str, *, project_id: str, source_id: str
) -> dict[str, Any]:
    """Select against the current value so auto-assignment remains idempotent."""
    current = _expect(
        client.get(f"/api/v1/projects/{project_id}"),
        200,
        "project_read_before_primary_selection_failed",
    )
    return _expect(client.put(
        f"/api/v1/projects/{project_id}/primary-application",
        json={
            "source_id": source_id,
            "expected_primary_source_id": current.get("primary_application_source_id"),
        },
        headers=_mut(csrf, idem=_idem()),
    ), 200, "primary_application_select_failed")


def _canonical_composite_field_text(target_answer: str) -> str:
    """Build the D0 editor value from the current portal registry questions."""
    from app.registry import get_registry

    questions = get_registry().mandatory_questions(FIELD_ID)
    if not questions or not any(
        question.field_id == MANDATORY_FIELD_ID for question in questions
    ):
        raise HarnessFailure("canonical_field_questions_missing")
    parts: list[str] = []
    for question in questions:
        parts.append(question.label_or_question.strip())
        parts.append(
            target_answer.strip()
            if question.field_id == MANDATORY_FIELD_ID
            else "Synthetischer D0-Testfall: keine zusÃ¤tzlichen Angaben."
        )
    return "\n".join(parts)


def _bootstrap_case(client: Any, csrf: str, *, label: str, text: str) -> dict[str, str]:
    classification = {
        "sensitivity": "public",
        "origin": "synthetic",
        "processing_mode": "cloud_assisted",
        "web_research_mode": "validated_public",
        "nda_applies": False,
    }
    project = _expect(client.post(
        "/api/v1/projects",
        json={
            "title": f"Synthetic {label}",
            "description": "D0 synthetic live acceptance fixture.",
            "innovation_field": "Public compliance software",
            "funding_instrument_profile_id": (
                "innosuisse_innovation_project_with_implementation_partner"
            ),
            "data_classification": classification,
        },
        headers=_mut(csrf, idem=_idem()),
    ), 201, "project_create_failed")
    project_id = project["project_id"]
    source_text = _canonical_composite_field_text(text)
    source = _expect(client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "synthetic-primary-application.txt", "text": source_text,
              "data_classification": classification},
        headers=_mut(csrf, idem=_idem()),
    ), 201, "primary_source_create_failed")
    source_id = source["source_id"]
    source_version_id = source["current_source_version_id"]
    candidates = _expect(client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": source_id}, headers=_mut(csrf, idem=_idem()),
    ), 201, "primary_import_mapping_failed")
    target = next((item for item in candidates if item["field_id"] == FIELD_ID), None)
    if target is None:
        raise HarnessFailure("canonical_import_candidate_missing")
    _expect(client.post(
        f"/api/v1/imports/{target['import_candidate_id']}/decision",
        json={
            "decision": "accepted",
            "project_id": project_id,
            "source_id": source_id,
            "expected_revision_id": target["current_revision_id"],
        },
        headers=_mut(csrf, idem=_idem()),
    ), 200, "primary_import_accept_failed")
    _select_current_primary_application(
        client, csrf, project_id=project_id, source_id=source_id
    )
    confirmation = _expect(client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={
            "processing_mode": "live",
            "source_version_ids": [source_version_id],
            "accepted_policy_version": POLICY_VERSION,
            "purpose": "RUN 3C Phase 2 D0 live acceptance",
            "expires_after_one_run": True,
        },
        headers=_mut(csrf, idem=_idem()),
    ), 201, "processing_confirmation_failed")
    run = _expect(client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {
            "processing_mode": "live",
            "max_cost_chf": MAX_COST_CHF,
            "max_llm_calls": 1,
            "max_web_calls": 0,
            "source_version_ids": [source_version_id],
            "internal_cloud_confirmation_id": confirmation["confirmation_id"],
        }},
        headers=_mut(csrf, idem=_idem()),
    ), 202, "run_create_failed")
    run_id = run["resource_id"]
    run_view = _expect(client.get(f"/api/v1/runs/{run_id}"), 200, "run_read_failed")
    if run_view["status"] not in {"completed", "paused_for_review"}:
        raise HarnessFailure("run_bootstrap_not_terminal")
    field_view = _expect(
        client.get(f"/api/v1/runs/{run_id}/fields/{FIELD_ID}"),
        200,
        "field_read_failed",
    )
    current = field_view["current_version"]
    if current["text"].strip() != source_text.strip():
        field_view = _expect(client.patch(
            f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
            json={
                "base_version_id": current["draft_version_id"],
                "text": source_text,
            },
            headers=_mut(csrf),
        ), 200, "field_seed_patch_failed")
        current = field_view["current_version"]
    return {
        "project_id": project_id,
        "source_id": source_id,
        "source_version_id": source_version_id,
        "run_id": run_id,
        "draft_id": field_view["draft_id"],
        "base_version_id": current["draft_version_id"],
    }


def _run_preflight(
    db: Any, *, route_key: str, actor_id: str, ledger: BudgetLedger, label: str
) -> Any:
    from app.config.settings import get_settings
    from app.evaluation.preflight import PASS, persist_route_preflight, preflight_route

    ledger.active_label = label
    result = preflight_route(route_key, settings=get_settings(), execute_live=True)
    row = persist_route_preflight(db, result, triggered_by=actor_id, settings=get_settings())
    db.commit()
    if result.status != PASS:
        raise HarnessFailure(result.error_class or "live_llm_preflight_failed")
    return row


def _generate_suggestion(
    client: Any,
    csrf: str,
    case: dict[str, str],
    *,
    mode: str,
    label: str,
    ledger: BudgetLedger,
    anchor_ids: list[str] | None = None,
) -> dict[str, Any]:
    ledger.active_label = label
    response = client.post(
        f"/api/v1/runs/{case['run_id']}/fields/{FIELD_ID}/redrafts",
        json={
            "base_version_id": case["base_version_id"],
            "target_section": TARGET_SECTION,
            "improvement_mode": mode,
            "selected_anchor_ids": anchor_ids or [],
            "language": "de",
            "model_preference": "primary",
        },
        headers=_mut(csrf, idem=_idem()),
    )
    accepted = _expect(response, 202, f"{label}_request_failed")
    operation = _expect(
        client.get(f"/api/v1/operations/{accepted['operation_id']}"),
        200,
        f"{label}_operation_read_failed",
    )
    if operation["status"] != "succeeded" or not operation.get("result"):
        raise HarnessFailure(f"{label}_failed")
    result = operation["result"]
    if result.get("generation_kind") != "model_generated":
        raise HarnessFailure(f"{label}_not_model_generated")
    if not result.get("manifest_id"):
        raise HarnessFailure(f"{label}_manifest_missing")
    return result


def _assert_smoke_1(result: dict[str, Any]) -> None:
    missing = _canonical_json(result.get("missing_inputs") or []).casefold()
    if not any(item in missing for item in ("marktgr", "market_size", "markt")):
        raise HarnessFailure("live_02a_missing_input_not_detected")
    suggestion = str(result.get("suggested_text") or "")
    forbidden = [
        r"\b(?:chf|fr\.)\s*\d",
        r"\b\d+(?:[.,]\d+)?\s*%",
        r"\b\d+(?:[.,]\d+)?\s*(?:mio|million|mrd|billion)\b",
    ]
    if any(re.search(pattern, suggestion, flags=re.IGNORECASE) for pattern in forbidden):
        raise HarnessFailure("critical_unsupported_fact")


def _assert_smoke_3(result: dict[str, Any]) -> None:
    suggestion = str(result.get("suggested_text") or "")
    if len(suggestion) >= len(SMOKE_3_TEXT):
        raise HarnessFailure("live_02c_not_shorter")
    for phrase in ("Schweizer KMU", "Compliance", "Softwarelizenz"):
        if phrase.casefold() not in suggestion.casefold():
            raise HarnessFailure("live_02c_meaning_not_preserved")
    if re.search(r"\b(?:chf|fr\.)\s*\d|\b\d+(?:[.,]\d+)?\s*%", suggestion, re.I):
        raise HarnessFailure("live_02c_new_fact")


def _assert_swiss_market_usage_policy(
    value: Any,
    *,
    require_missing_input: bool,
    require_attribution: bool,
) -> None:
    """Fail closed on the human-approved scope of the two market estimates."""
    scoped_value = (
        str(value.get("suggested_text") or "")
        if require_missing_input and isinstance(value, dict)
        else value
    )
    serialized = _canonical_json(scoped_value)
    if re.search(r"\b(?:chf|fr\.)\s*\d", serialized, re.IGNORECASE):
        raise HarnessFailure("live_anchor_policy_chf_derivation_forbidden")
    if re.search(r"\b(?:tam|sam|som)\b", serialized, re.IGNORECASE):
        raise HarnessFailure("live_anchor_policy_swiss_market_derivation_forbidden")
    if require_missing_input:
        missing = _canonical_json(value.get("missing_inputs") or []).casefold()
        if not (
            any(item in missing for item in ("schweiz", "swiss"))
            and any(item in missing for item in ("marktgr", "market_size", "market size"))
        ):
            raise HarnessFailure("live_02b_swiss_market_missing_input_absent")

    strings: list[str] = []

    def collect(item: Any) -> None:
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, dict):
            for nested in item.values():
                collect(nested)
        elif isinstance(item, list):
            for nested in item:
                collect(nested)

    collect(scoped_value)
    numeric = re.compile(
        r"(?:\b(?:usd|chf)\b|\b\d+(?:[.,]\d+)?\s*%|"
        r"\b\d+(?:[.,]\d+)?\s*(?:mio|million|mrd|billion)\b)",
        re.IGNORECASE,
    )
    source_fact = re.compile(
        r"(?:35[.,]8|39[.,]3|78[.,]9|10[.,]5\s*%|12[.,]96\s*%)",
        re.IGNORECASE,
    )
    attribution = re.compile(
        r"(?:grand view|mordor|marktstudie|market study|laut|sch[aä]tz|estimate)",
        re.IGNORECASE,
    )
    for text in strings:
        if re.search(r"(?:schweiz|swiss)", text, re.IGNORECASE) and numeric.search(text):
            raise HarnessFailure("live_anchor_policy_swiss_market_derivation_forbidden")
        if require_attribution and source_fact.search(text) and not attribution.search(text):
            raise HarnessFailure("live_anchor_policy_attribution_missing")
    if re.search(
        r"(?:umsatzprognose|revenue projection)[^\n]{0,80}\d",
        serialized,
        re.IGNORECASE,
    ):
        raise HarnessFailure("live_anchor_policy_revenue_projection_forbidden")


def _save_review_artifact(path: Path, cases: list[dict[str, Any]]) -> None:
    payload = {
        "created_at": _iso(),
        "expires_at": _iso(datetime.fromtimestamp(time.time() + 6 * 3600, timezone.utc)),
        "cases": cases,
    }
    path.write_text(_canonical_json(payload), encoding="utf-8")


def _render_review_template(cases: list[dict[str, Any]]) -> str:
    lines = [
        "# LIVE LLM HUMAN REVIEW",
        "",
        "Die vollständigen D0-Texte liegen ausschließlich im lokalen, zeitlich begrenzten Review-Artefakt.",
        "Die Coding-KI trägt keine Bewertungen ein.",
        "",
    ]
    categories = (
        "Feldbezug, Faktentreue, Innolink-Anforderungsabdeckung, Klarheit, "
        "Präzision, Nutzbarkeit, Bedeutungserhalt, geringe KI-Sprache, Belegnachvollziehbarkeit"
    )
    for case in cases:
        lines.extend([
            f"## {case['case_id']}", "",
            f"- Suggestion-ID: `{case['suggestion_id']}`",
            f"- Field-ID: `{FIELD_ID}`",
            f"- Modus: `{case['mode']}`",
            f"- Zeichen vorher/nachher: `{case['before']}` / `{case['after']}`",
            f"- Missing-Input-Keys: `{','.join(case.get('missing_input_keys', [])) or 'none'}`",
            f"- Anchor-IDs: `{','.join(case.get('anchor_ids', [])) or 'none'}`",
            f"- Rubrikkategorien: {categories}", "",
        ])
        for reviewer in ("Reviewer 1", "Reviewer 2"):
            lines.extend([
                f"### {reviewer}", "",
                "- Scores 1–5:",
                "- critical_hallucination (yes/no):",
                "- usable (directly/minor_edits/major_edits/unusable):",
                "- Kommentar:", "",
            ])
    return "\n".join(lines)


def _render_smoke_report(summary: dict[str, Any]) -> str:
    lines = ["# LIVE LLM SMOKE REPORT", ""]
    for key in (
        "timestamp_utc", "status", "provider_routes", "model_refs",
        "preflight_status", "preflight_fingerprints", "execution_mode",
        "request_count", "provider_call_seconds", "active_execution_seconds",
        "cost_chf", "web_calls", "web_credits", "fake_fallback_observed",
        "reason_code",
    ):
        value = summary.get(key, "not_available")
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    for case in summary.get("cases", []):
        lines.extend([
            f"## {case['case_id']}", "",
            f"- status: `{case['status']}`",
            f"- suggestion_id: `{case.get('suggestion_id', 'not_available')}`",
            f"- manifest_id: `{case.get('manifest_id', 'not_available')}`",
            f"- schema_status: `{case.get('schema_status', 'not_available')}`",
            f"- grounding_status: `{case.get('grounding_status', 'not_available')}`",
            f"- missing_input_keys: `{case.get('missing_input_keys', [])}`",
            f"- used_anchor_ids: `{case.get('used_anchor_ids', [])}`",
            f"- character_count: `{case.get('character_count', 'not_available')}`",
            f"- reason_code: `{case.get('reason_code', 'none')}`",
            "",
        ])
    entries = summary.get("request_ledger") or []
    if entries:
        lines.extend(["## Redacted request ledger", ""])
        for entry in entries:
            lines.append(
                "- " + ", ".join(
                    f"{key}=`{entry.get(key, 'not_available')}`" for key in (
                        "attempt_id", "request_sequence", "provider", "route_alias",
                        "purpose", "started_at", "finished_at", "http_class",
                        "http_status", "retryable", "reason_code", "input_tokens",
                        "output_tokens", "estimated_cost_chf", "actual_cost_chf",
                    )
                )
            )
        lines.append("")
    return "\n".join(lines)


def _write_early_failure_report(
    request_ledger: AtomicRequestLedger,
    *,
    reason_code: str,
) -> None:
    summary = {
        "timestamp_utc": _iso(),
        "status": "failed",
        "execution_mode": "live",
        "request_count": len(request_ledger.entries),
        "web_calls": sum(1 for item in request_ledger.entries if item.provider == "firecrawl"),
        "fake_fallback_observed": "no",
        "reason_code": reason_code,
        "request_ledger": [asdict(item) for item in request_ledger.entries],
    }
    _write_text_atomic(REPORT_PATH, _render_smoke_report(summary))


def _render_run_result(statuses: dict[str, str], summary: dict[str, Any]) -> str:
    return "\n".join([
        "# RUN 3 RESULT (vorläufig – Human Review offen)", "",
        "- Offline baseline: `passed`",
        f"- Live web smoke: `{statuses['live_01']}`",
        f"- Live LLM preflight: `{statuses['preflight']}`",
        f"- LIVE-02A: `{statuses['live_02a']}`",
        f"- LIVE-02B: `{statuses['live_02b']}`",
        f"- LIVE-02C: `{statuses['live_02c']}`",
        f"- LIVE-03 API/BFF E2E: `{statuses['live_03']}`",
        "- Browser E2E: `pending`",
        "- Human quality review: `pending`",
        f"- Fake fallback observed: `{summary.get('fake_fallback_observed', 'no')}`",
        f"- Actual LLM cost CHF: `{summary.get('cost_chf', 'not_available')}`",
        "- Secrets/raw prompts logged: `no`", "",
        "## Matrixkorrektur", "",
        "- `AI-04`: Draft-/Run-/Source-/Registry-/Market-Änderung macht Suggestion stale.",
        "- `AI-Q06`: Accept erzeugt idempotent genau eine neue DraftVersion.", "",
        "## Finaler Status", "",
        "`HUMAN_QUALITY_ACCEPTANCE_PENDING`", "",
    ])


def _remove_session_root(temp_root: Path) -> None:
    resolved = temp_root.resolve()
    allowed = SESSION_ROOT.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise HarnessFailure("cleanup_target_outside_session_root")
    shutil.rmtree(resolved, ignore_errors=True)


def _close_runtime_resources(engine: Any | None = None) -> None:
    """Close process-global SQLite handles before Windows session cleanup."""
    try:
        graph_module = sys.modules.get("app.runs.graph")
        if graph_module is not None:
            graph_module.close_checkpointer()
    finally:
        if engine is not None:
            engine.dispose()


def cleanup_expired() -> int:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    now = _utcnow()
    removed = 0
    for entry in SESSION_ROOT.iterdir():
        if not entry.is_dir():
            continue
        state = entry / "session.json"
        remove = not state.is_file()
        if not remove:
            try:
                data = json.loads(state.read_text(encoding="utf-8"))
                expires = datetime.fromisoformat(data["expires_at"])
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                remove = expires <= now or bool(data.get("consumed"))
            except Exception:
                remove = True
        if remove:
            _remove_session_root(entry)
            removed += 1
    print(f"CLEANUP_EXPIRED_COMPLETE count={removed}")
    return 0


def _session_id_from_approval(value: str) -> str:
    return parse_anchor_approval(value)[0]


def _read_research_execution(client: Any, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Read persisted task and operation truth before considering result count."""
    from app.provider_errors import provider_reason_is_retryable

    states: list[dict[str, Any]] = []
    for task_id in run.get("task_ids") or []:
        task = _expect(
            client.get(f"/api/v1/research-tasks/{task_id}"),
            200,
            "research_task_read_failed",
        )
        operation_id = task.get("operation_id")
        if not operation_id:
            raise HarnessFailure("research_operation_id_missing")
        operation = _expect(
            client.get(f"/api/v1/operations/{operation_id}"),
            200,
            "research_operation_read_failed",
        )
        task_code = task.get("error_code")
        operation_error = operation.get("error") or {}
        operation_code = operation_error.get("code") if isinstance(operation_error, dict) else None
        if task_code and operation_code and task_code != operation_code:
            raise HarnessFailure("research_failure_code_mismatch")
        reason_code = task_code or operation_code
        failed = task.get("status") == "failed" or operation.get("status") == "failed"
        if failed:
            safe_code = str(reason_code or "research_execution_failed")
            retryable = bool(task.get("retryable")) or provider_reason_is_retryable(safe_code)
            raise HarnessFailure(safe_code, retryable=retryable)
        if task.get("status") != "succeeded" or operation.get("status") != "succeeded":
            raise HarnessFailure("research_execution_not_terminal")
        states.append({"task": task, "operation": operation})
    return states


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RUN 3C Phase 2 live acceptance")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare-web")
    resume = sub.add_parser("resume-llm")
    resume.add_argument("--approval", required=True)
    refine = sub.add_parser("bind-refined-anchors")
    refine.add_argument("--session-id", required=True)
    refine.add_argument("--passage", action="append", required=True)
    refine.add_argument(
        "--usage-policy",
        choices=[SWISS_MARKET_POLICY],
        default=SWISS_MARKET_POLICY,
    )
    sub.add_parser("cleanup-expired")
    return parser


def prepare_web() -> int:  # pragma: no cover - opt-in live path
    session_id = uuid.uuid4().hex
    temp_root = SESSION_ROOT / session_id
    temp_root.mkdir(parents=True, exist_ok=False)
    success_waiting = False
    runtime_engine = None
    started = time.monotonic()
    web_counter = {"calls": 0, "credits": 0.0, "seconds": 0.0, "kinds": []}
    request_ledger = AtomicRequestLedger(session_id, _request_ledger_path(temp_root))
    request_ledger.persist()
    try:
        _configure_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from fastapi.testclient import TestClient
        from app.config.settings import get_settings
        from app.db.session import SessionLocal, engine
        from app.evaluation.preflight import configuration_fingerprint
        from app.evaluation.pricing import PRICE_TABLE_VERSION
        from app.main import app

        runtime_engine = engine
        get_settings.cache_clear()
        settings = get_settings()
        reason = _opt_in_reason(settings, require_llm=False)
        if reason:
            raise HarnessFailure(reason)
        _assert_registry_contract()
        calls, routes, models = _planned_calls(settings)
        ledger = BudgetLedger(planned=calls)
        workspace_id, actor_id, email = _seed_infrastructure()
        with TestClient(app) as client:
            csrf = _login(client, email)
            # Instrument the bootstrap as well. With no active budget label, an
            # attempted provider inference is rejected before the adapter can
            # issue a network request.
            with instrument_live_providers(
                ledger, web_counter=web_counter, request_ledger=request_ledger
            ):
                cases = {
                    "live_02a": _bootstrap_case(client, csrf, label="LIVE-02A", text=SMOKE_1_TEXT),
                    "live_02b": _bootstrap_case(client, csrf, label="LIVE-02B", text=SMOKE_2_TEXT),
                    "live_02c": _bootstrap_case(client, csrf, label="LIVE-02C", text=SMOKE_3_TEXT),
                }
            # Preflight absence must make bootstrap fail closed before the adapters.
            if ledger.actual_call_count != 0:
                raise HarnessFailure("run_bootstrap_external_call_observed")
            db = SessionLocal()
            try:
                with instrument_live_providers(
                    ledger, web_counter=web_counter, request_ledger=request_ledger
                ):
                    brief = _expect(client.put(
                        f"/api/v1/projects/{cases['live_02b']['project_id']}/research-brief",
                        json={
                            "research_goal": (
                                "Öffentliche Schweizer Markt- und Kundeninformationen zu "
                                "Compliance-Software für KMU"
                            ),
                            "search_tags": ["Schweiz", "KMU", "Compliance Software"],
                            "region": "Schweiz",
                            "modules": ["market_growth"],
                        }, headers=_mut(csrf),
                    ), 200, "research_brief_save_failed")
                    brief = _expect(client.post(
                        f"/api/v1/research-briefs/{brief['research_brief_id']}/approve",
                        headers=_mut(csrf),
                    ), 200, "research_brief_approve_failed")
                    plan = _expect(client.post(
                        f"/api/v1/research-briefs/{brief['research_brief_id']}/queries/plan",
                        headers=_mut(csrf),
                    ), 200, "research_query_plan_failed")
                    # The registry-backed planner may emit more than one
                    # purpose for a module. This bounded smoke executes exactly
                    # the first approved plan row instead of requiring the
                    # planner itself to collapse valid purposes.
                    if not plan["queries"] or not plan["queries"][0].get("approval_id"):
                        raise HarnessFailure("research_query_plan_invalid")
                    query = plan["queries"][0]
                    approval = _expect(client.post(
                        f"/api/v1/search-query-approvals/{query['approval_id']}/approve",
                        headers=_mut(csrf, idem=_idem()),
                    ), 200, "research_query_approval_failed")
                    run = _expect(client.post(
                        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
                        json={"approval_ids": [approval["approval_id"]]},
                        headers=_mut(csrf, idem=_idem()),
                    ), 200, "research_live_run_failed")
                    if run["execution_mode"] != "live" or len(run["task_ids"]) != 1:
                        raise HarnessFailure("research_not_live")
                    _read_research_execution(client, run)
                    results = _expect(client.get(
                        f"/api/v1/projects/{cases['live_02b']['project_id']}/research-results"
                    ), 200, "research_result_read_failed")
                    chosen = []
                    seen_domains: set[str] = set()
                    for item in results:
                        domain = _safe_domain(item.get("source_url") or "")
                        if (
                            item.get("status") == "candidate" and domain
                            and not _is_demo_domain(domain) and domain not in seen_domains
                        ):
                            chosen.append(item)
                            seen_domains.add(domain)
                        if len(chosen) == 2:
                            break
                    if len(chosen) < 2:
                        raise HarnessFailure("live_e2e_blocked_insufficient_external_evidence")
                    imported = []
                    for item in chosen:
                        imported.append(_expect(client.post(
                            f"/api/v1/research-results/{item['result_id']}/import",
                            headers=_mut(csrf, idem=_idem()),
                        ), 201, "research_result_import_failed"))
                    if web_counter["calls"] != 3 or web_counter["kinds"] != ["search", "fetch", "fetch"]:
                        raise HarnessFailure("firecrawl_call_plan_mismatch")
                    proposals: list[AnchorProposal] = []
                    for item, document_view in zip(chosen, imported, strict=True):
                        passages = _expect(client.get(
                            f"/api/v1/research-results/{item['result_id']}/anchor-passages"
                        ), 200, "review_passage_read_failed")
                        passage = next(
                            (row for row in passages if len(row.get("excerpt") or "") >= 80),
                            None,
                        )
                        if passage is None:
                            raise HarnessFailure("review_fragment_missing")
                        if (
                            passage["source_id"] != document_view["source_id"]
                            or passage["safety_status"] != "passed"
                            or passage["content_review_status"] not in ("unreviewed", "reviewed")
                            or _sha256(passage["excerpt"]) != passage["quote_hash"]
                        ):
                            raise HarnessFailure("review_source_state_invalid")
                        proposals.append(AnchorProposal(
                            result_id=passage["result_id"],
                            source_id=passage["source_id"],
                            source_version_id=passage["source_version_id"],
                            fragment_id=passage["fragment_id"],
                            start_offset=passage["start_offset"],
                            end_offset=passage["end_offset"],
                            domain=passage["public_domain"],
                            title=passage["page_title"],
                            excerpt=passage["excerpt"],
                            quote_hash=passage["quote_hash"],
                            safety_status=passage["safety_status"],
                            content_review_status=passage["content_review_status"],
                        ))
                    expires_at = _utcnow() + timedelta(seconds=WEB_REVIEW_SESSION_TTL_SECONDS)
                    session = ReviewSession(
                        review_session_id=session_id,
                        session_version=SESSION_VERSION,
                        created_at=_iso(),
                        expires_at=_iso(expires_at),
                        temp_root=str(temp_root),
                        workspace_id=workspace_id,
                        actor_user_id=actor_id,
                        actor_email=email,
                        cases=cases,
                        research={
                            "brief_id": brief["research_brief_id"],
                            "task_id": run["task_ids"][0],
                            "approval_id": approval["approval_id"],
                            "query_hash": _sha256(query["query_text"]),
                            "risk_level": query["risk_label"],
                            "firewall_decision": query["firewall_decision"],
                            "request_ledger_hash": _sha256(
                                request_ledger.path.read_bytes()
                            ),
                        },
                        anchors=[item.safe_state() for item in proposals],
                        route_ids=routes,
                        model_refs=models,
                        provider_config_fingerprints={
                            key: configuration_fingerprint(route, settings=settings)
                            for key, route in routes.items()
                        },
                        preflight_fingerprints={},
                        policy_version=POLICY_VERSION,
                        pricing_version=PRICE_TABLE_VERSION,
                        registry_version=settings.agent_registry_version,
                        active_execution_seconds=time.monotonic() - started,
                        provider_call_seconds=sum(item.duration_seconds for item in ledger.records),
                        human_wait_started_at=_iso(),
                        human_wait_ended_at=None,
                        ledger=_ledger_to_dict(ledger),
                    )
                    save_session(session)
                    for proposal in proposals:
                        print(_canonical_json({
                            "review_session_id": session_id,
                            "source_version_id": proposal.source_version_id,
                            "fragment_id": proposal.fragment_id,
                            "start_offset": proposal.start_offset,
                            "end_offset": proposal.end_offset,
                            "public_domain": proposal.domain,
                            "page_title": proposal.title,
                            "excerpt": proposal.excerpt,
                            "quote_hash": proposal.quote_hash,
                            "safety_status": proposal.safety_status,
                            "content_review_status": proposal.content_review_status,
                        }))
                    print(
                        f"{APPROVAL_PREFIX} {session_id} "
                        + ",".join(item.quote_hash for item in proposals)
                    )
                    success_waiting = True
                    return 0
            finally:
                db.close()
    except HarnessFailure as exc:
        _write_early_failure_report(request_ledger, reason_code=exc.code)
        print(
            f"LIVE_WEB_PREPARE_FAILED reason_code={exc.code} "
            f"retryable={str(exc.retryable).lower()}"
        )
        return 1
    except Exception as exc:
        reason_code = _redacted_error(exc)
        _write_early_failure_report(request_ledger, reason_code=reason_code)
        print(f"LIVE_WEB_PREPARE_FAILED reason_code={reason_code} retryable=false")
        return 1
    finally:
        _close_runtime_resources(runtime_engine)
        if not success_waiting:
            _remove_session_root(temp_root)


def bind_refined_anchors(
    session_id: str,
    passage_values: list[str],
    *,
    usage_policy: str,
) -> int:  # pragma: no cover - local human-review transition
    """Bind already reviewed exact passages without any provider operation."""
    session = load_session(session_id)
    selectors = [parse_refined_passage(value) for value in passage_values]
    if len({item["source_version_id"] for item in selectors}) < 2:
        raise HarnessFailure("insufficient_approved_source_versions")
    existing_by_version = {
        item["source_version_id"]: item for item in session.anchors
    }
    if any(item["source_version_id"] not in existing_by_version for item in selectors):
        raise HarnessFailure("live_anchor_source_version_unknown")

    temp_root = Path(session.temp_root)
    runtime_engine = None
    original_cwd = Path.cwd()
    try:
        _configure_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from fastapi.testclient import TestClient
        from app.config.settings import get_settings
        from app.db.session import engine
        from app.main import app

        runtime_engine = engine
        get_settings.cache_clear()
        refined: list[dict[str, Any]] = []
        with TestClient(app) as client:
            _login(client, session.actor_email)
            for selector in selectors:
                base = existing_by_version[selector["source_version_id"]]
                rows = _expect(client.get(
                    f"/api/v1/research-results/{base['result_id']}/anchor-passages",
                    params={
                        "fragment_id": selector["fragment_id"],
                        "start_offset": selector["start_offset"],
                        "end_offset": selector["end_offset"],
                        "quote_hash": selector["quote_hash"],
                    },
                ), 200, "refined_review_passage_read_failed")
                if len(rows) != 1:
                    raise HarnessFailure("refined_review_passage_not_unique")
                passage = rows[0]
                if any(passage[key] != selector[key] for key in (
                    "source_version_id", "fragment_id", "start_offset",
                    "end_offset", "quote_hash",
                )):
                    raise HarnessFailure("refined_review_passage_mismatch")
                if (
                    passage["source_id"] != base["source_id"]
                    or passage["safety_status"] != "passed"
                    or passage["content_review_status"] not in ("unreviewed", "reviewed")
                    or _sha256(passage["excerpt"]) != passage["quote_hash"]
                ):
                    raise HarnessFailure("refined_review_source_state_invalid")
                refined.append(AnchorProposal(
                    result_id=passage["result_id"],
                    source_id=passage["source_id"],
                    source_version_id=passage["source_version_id"],
                    fragment_id=passage["fragment_id"],
                    start_offset=passage["start_offset"],
                    end_offset=passage["end_offset"],
                    domain=passage["public_domain"],
                    title=passage["page_title"],
                    excerpt=passage["excerpt"],
                    quote_hash=passage["quote_hash"],
                    safety_status=passage["safety_status"],
                    content_review_status=passage["content_review_status"],
                ).safe_state())

        session.anchors = refined
        session.research["anchor_usage_policy"] = usage_policy
        session.expires_at = _iso(
            _utcnow() + timedelta(seconds=WEB_REVIEW_SESSION_TTL_SECONDS)
        )
        session.human_wait_started_at = _iso()
        session.human_wait_ended_at = None
        save_session(session)
        print(_canonical_json({
            "review_session_id": session.review_session_id,
            "quote_hashes": [item["quote_hash"] for item in refined],
            "source_version_ids": [item["source_version_id"] for item in refined],
            "usage_policy": usage_policy,
            "expires_at": session.expires_at,
        }))
        print("REFINED_ANCHOR_SESSION_BOUND")
        return 0
    finally:
        os.chdir(original_cwd)
        _close_runtime_resources(runtime_engine)


def resume_llm(approval: str) -> int:  # pragma: no cover - opt-in live path
    session_id = _session_id_from_approval(approval)
    session = load_session(session_id)
    selected = validate_anchor_approval(session, approval)
    temp_root = Path(session.temp_root)
    started = time.monotonic()
    request_ledger = AtomicRequestLedger.load(
        session.review_session_id, _request_ledger_path(temp_root)
    )
    prior_web_calls = sum(1 for item in request_ledger.entries if item.provider == "firecrawl")
    web_counter = {
        "calls": prior_web_calls, "credits": 0.0, "seconds": 0.0,
        "kinds": [item.purpose.removeprefix("public_") for item in request_ledger.entries
                  if item.provider == "firecrawl"],
    }
    final_review_artifact: Path | None = None
    runtime_engine = None
    try:
        if not request_ledger.path.is_file() or not hmac.compare_digest(
            str(session.research.get("request_ledger_hash") or ""),
            _sha256(request_ledger.path.read_bytes()),
        ):
            raise HarnessFailure("request_ledger_integrity_invalid")
        _configure_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from fastapi.testclient import TestClient
        from sqlalchemy import func, select
        from app.config.settings import get_settings
        from app.db.models import (
            DraftSuggestion, DraftVersion, EvidenceAnchor, ResearchResult,
            SuggestionContextManifest,
        )
        from app.db.session import SessionLocal, engine
        from app.evaluation.preflight import configuration_fingerprint
        from app.evaluation.pricing import PRICE_TABLE_VERSION
        from app.main import app

        runtime_engine = engine
        get_settings.cache_clear()
        settings = get_settings()
        reason = _opt_in_reason(settings)
        if reason:
            raise HarnessFailure(reason)
        _assert_registry_contract()
        calls, routes, models = _planned_calls(settings)
        if routes != session.route_ids or models != session.model_refs:
            raise HarnessFailure("live_session_configuration_changed")
        if PRICE_TABLE_VERSION != session.pricing_version or settings.agent_registry_version != session.registry_version:
            raise HarnessFailure("live_session_configuration_changed")
        for key, route in routes.items():
            if configuration_fingerprint(route, settings=settings) != session.provider_config_fingerprints[key]:
                raise HarnessFailure("live_session_configuration_changed")
        ledger = _ledger_from_dict(session.ledger)
        db = SessionLocal()
        try:
            with TestClient(app) as client, instrument_live_providers(
                ledger, web_counter=web_counter, request_ledger=request_ledger
            ):
                csrf = _login(client, session.actor_email)
                a2_preflight = _run_preflight(
                    db, route_key=routes["a2"], actor_id=session.actor_user_id,
                    ledger=ledger, label="a2_preflight",
                )
                smoke_1 = _generate_suggestion(
                    client, csrf, session.cases["live_02a"],
                    mode="complete_innolink_requirements", label="live_02a",
                    ledger=ledger,
                )
                _assert_smoke_1(smoke_1)
                if routes["market"] == routes["a2"]:
                    market_preflight = a2_preflight
                else:
                    market_preflight = _run_preflight(
                        db, route_key=routes["market"], actor_id=session.actor_user_id,
                        ledger=ledger, label="market_preflight",
                    )
                session.preflight_fingerprints = {
                    "a2": a2_preflight.configuration_fingerprint,
                    "market": market_preflight.configuration_fingerprint,
                }
                approved_quotes: dict[str, str] = {}
                # Reload the exact bounded review projection through HTTP after
                # the process boundary; only an unchanged hash can consume the
                # one-time approval.
                for item in selected:
                    passages = _expect(client.get(
                        f"/api/v1/research-results/{item['result_id']}/anchor-passages",
                        params={
                            "fragment_id": item["fragment_id"],
                            "start_offset": item["start_offset"],
                            "end_offset": item["end_offset"],
                            "quote_hash": item["quote_hash"],
                        },
                    ), 200, "review_passage_reload_failed")
                    passage = next((row for row in passages if (
                        row["source_id"] == item["source_id"]
                        and row["source_version_id"] == item["source_version_id"]
                        and row["fragment_id"] == item["fragment_id"]
                        and row["start_offset"] == item["start_offset"]
                        and row["end_offset"] == item["end_offset"]
                        and row["quote_hash"] == item["quote_hash"]
                    )), None)
                    if passage is None or _sha256(passage["excerpt"]) != item["quote_hash"]:
                        raise HarnessFailure("live_anchor_quote_changed")
                    approved_quotes[item["quote_hash"]] = passage["excerpt"]

                session.human_wait_ended_at = _iso()
                session.consumed = True
                session.ledger = _ledger_to_dict(ledger)
                session.provider_call_seconds = sum(
                    item.duration_seconds for item in ledger.records
                )
                save_session(session)
                anchor_ids = []
                for item in selected:
                    _expect(client.post(
                        f"/api/v1/research-results/{item['result_id']}/review",
                        json={"decision": "supports", "confirm_untrusted_content": False},
                        headers=_mut(csrf),
                    ), 200, "content_review_failed")
                    anchor = _expect(client.post(
                        f"/api/v1/research-results/{item['result_id']}/external-anchors",
                        json={
                            "fragment_id": item["fragment_id"],
                            "quote": approved_quotes[item["quote_hash"]],
                        },
                        headers=_mut(csrf),
                    ), 200, "external_anchor_create_failed")
                    anchor_ids.append(anchor["anchor_id"])

                e2e = session.cases["live_02b"]
                ledger.active_label = "market_comparison"
                market_accepted = _expect(client.post(
                    f"/api/v1/projects/{e2e['project_id']}/market-comparisons",
                    headers=_mut(csrf, idem=_idem()),
                ), 202, "market_comparison_request_failed")
                market = _expect(client.get(
                    f"/api/v1/market-comparisons/{market_accepted['resource_id']}"
                ), 200, "market_comparison_read_failed")
                if market["status"] != "limited" or "limited_external_evidence" not in market.get("warnings", []):
                    raise HarnessFailure(
                        "market_comparison_not_limited_"
                        f"{market['status']}_{market.get('error') or 'no_error'}"
                    )
                usage_policy = session.research.get("anchor_usage_policy")
                if usage_policy == SWISS_MARKET_POLICY:
                    _assert_swiss_market_usage_policy(
                        market,
                        require_missing_input=False,
                        require_attribution=False,
                    )
                market_anchor_ids = {
                    anchor_id
                    for market_item in market.get("items", [])
                    for anchor_id in market_item.get("external_evidence_anchor_ids", [])
                }
                if not market_anchor_ids or not market_anchor_ids <= set(anchor_ids):
                    raise HarnessFailure("market_comparison_anchor_scope_invalid")

                options = _expect(client.get(
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}/suggestion-context-options"
                ), 200, "suggestion_context_options_failed")
                allowed = {item["anchor_id"] for item in options["anchors"]}
                if not set(anchor_ids).issubset(allowed) or options.get("market_comparison_id") != market["comparison_id"]:
                    raise HarnessFailure("suggestion_context_handoff_invalid")
                smoke_2 = _generate_suggestion(
                    client, csrf, e2e, mode="complete_innolink_requirements",
                    label="live_02b", ledger=ledger, anchor_ids=anchor_ids,
                )
                if usage_policy == SWISS_MARKET_POLICY:
                    _assert_swiss_market_usage_policy(
                        smoke_2,
                        require_missing_input=True,
                        require_attribution=True,
                    )
                if not set(smoke_2.get("used_anchor_ids") or []).issubset(set(anchor_ids)):
                    raise HarnessFailure("live_02b_unknown_anchor")
                suggestion_read = _expect(client.get(
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}/suggestions"
                ), 200, "live_02b_suggestion_read_failed")
                if smoke_2["suggestion_id"] not in {
                    row["suggestion_id"] for row in suggestion_read["suggestions"]
                }:
                    raise HarnessFailure("live_02b_suggestion_read_missing")
                db.expire_all()
                suggestion_row = db.get(DraftSuggestion, smoke_2["suggestion_id"])
                manifest = db.get(SuggestionContextManifest, suggestion_row.manifest_id)
                if manifest.market_comparison_id != market["comparison_id"]:
                    raise HarnessFailure("live_02b_market_manifest_missing")

                smoke_3 = _generate_suggestion(
                    client, csrf, session.cases["live_02c"], mode="shorten",
                    label="live_02c", ledger=ledger,
                )
                _assert_smoke_3(smoke_3)

                before_versions = db.scalar(select(func.count(DraftVersion.draft_version_id)).where(
                    DraftVersion.draft_id == e2e["draft_id"]
                ))
                accept_key = _idem()
                accept_path = (
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}/suggestions/"
                    f"{smoke_2['suggestion_id']}/accept"
                )
                accepted = _expect(client.post(
                    accept_path,
                    json={"base_version_id": e2e["base_version_id"]},
                    headers=_mut(csrf, idem=accept_key),
                ), 200, "suggestion_accept_failed")
                replay = _expect(client.post(
                    accept_path,
                    json={"base_version_id": e2e["base_version_id"]},
                    headers=_mut(csrf, idem=accept_key),
                ), 200, "suggestion_accept_replay_failed")
                if accepted["draft_version_id"] != replay["draft_version_id"] or not replay["idempotent_replay"]:
                    raise HarnessFailure("suggestion_accept_not_idempotent")
                current_field = _expect(client.get(
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}"
                ), 200, "accepted_draft_read_failed")
                if current_field["current_version"]["draft_version_id"] != accepted["draft_version_id"]:
                    raise HarnessFailure("accepted_draft_version_not_current")
                accepted_version = _expect(client.get(
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}/versions/"
                    f"{accepted['draft_version_id']}"
                ), 200, "accepted_draft_version_read_failed")
                original_version = _expect(client.get(
                    f"/api/v1/runs/{e2e['run_id']}/fields/{FIELD_ID}/versions/"
                    f"{e2e['base_version_id']}"
                ), 200, "original_draft_version_read_failed")
                if (
                    accepted_version["draft_version_id"] != accepted["draft_version_id"]
                    or original_version["draft_version_id"] != e2e["base_version_id"]
                ):
                    raise HarnessFailure("live_03_draft_version_read_invalid")
                db.expire_all()
                after_versions = db.scalar(select(func.count(DraftVersion.draft_version_id)).where(
                    DraftVersion.draft_id == e2e["draft_id"]
                ))
                if after_versions != before_versions + 1 or db.get(DraftVersion, e2e["base_version_id"]) is None:
                    raise HarnessFailure("live_03_draft_history_invalid")
                external_anchors = list(db.scalars(select(EvidenceAnchor).where(
                    EvidenceAnchor.project_id == e2e["project_id"],
                    EvidenceAnchor.scope == "external",
                )))
                if {row.anchor_id for row in external_anchors} != set(anchor_ids):
                    raise HarnessFailure("live_anchor_approval_scope_invalid")
                snippets = {
                    row for row in db.scalars(select(ResearchResult.snippet).where(
                        ResearchResult.research_task_id == session.research["task_id"]
                    )) if row
                }
                if snippets & {row.quote for row in external_anchors}:
                    raise HarnessFailure("search_snippet_became_evidence")
                review_cases = []
                for case_id, mode, base_text, result in (
                    ("LIVE-02A", "complete_innolink_requirements", SMOKE_1_TEXT, None),
                    ("LIVE-02B", "complete_innolink_requirements", SMOKE_2_TEXT, smoke_2),
                    ("LIVE-02C", "shorten", SMOKE_3_TEXT, smoke_3),
                ):
                    if result is None:
                        suggestions = _expect(client.get(
                            f"/api/v1/runs/{session.cases['live_02a']['run_id']}/fields/{FIELD_ID}/suggestions"
                        ), 200, "live_02a_read_failed")["suggestions"]
                        result = suggestions[0]
                        if not result.get("missing_inputs") or not result.get("open_issue_ids"):
                            raise HarnessFailure("live_02a_missing_issue_not_persisted")
                    suggestion_text = str(result.get("suggested_text") or "")
                    missing = result.get("missing_inputs") or []
                    review_cases.append({
                        "case_id": case_id,
                        "suggestion_id": result["suggestion_id"],
                        "mode": mode,
                        "original_text": base_text,
                        "suggestion_text": suggestion_text,
                        "before": len(base_text),
                        "after": len(suggestion_text),
                        "missing_inputs": missing,
                        "missing_input_keys": [
                            str(item.get("key") or item.get("label") or "missing")
                            for item in missing if isinstance(item, dict)
                        ],
                        "anchor_ids": result.get("used_anchor_ids") or [],
                        "warnings": result.get("unsupported_claim_warnings") or [],
                    })

                final_review_artifact = Path(tempfile.mkdtemp(
                    prefix="innolink-live-llm-human-review-"
                )) / "review.json"
                _save_review_artifact(final_review_artifact, review_cases)
                summary = {
                    "timestamp_utc": _iso(),
                    "status": "live_technical_acceptance_complete",
                    "provider_routes": session.route_ids,
                    "model_refs": session.model_refs,
                    "preflight_status": "passed",
                    "preflight_fingerprints": session.preflight_fingerprints,
                    "execution_mode": "live",
                    "request_count": ledger.actual_call_count,
                    "provider_call_seconds": round(sum(r.duration_seconds for r in ledger.records), 3),
                    "active_execution_seconds": round(
                        session.active_execution_seconds + (time.monotonic() - started), 3
                    ),
                    "cost_chf": round(ledger.conservative_spent_chf, 6),
                    "web_calls": MAX_WEB_CALLS,
                    "web_credits": "not_available",
                    "fake_fallback_observed": "no",
                    "reason_code": "none",
                    "request_ledger": [asdict(item) for item in request_ledger.entries],
                    "cases": [{
                        "case_id": item["case_id"], "status": "passed",
                        "suggestion_id": item["suggestion_id"],
                        "manifest_id": (
                            db.get(DraftSuggestion, item["suggestion_id"]).manifest_id
                        ),
                        "schema_status": "passed", "grounding_status": "passed",
                        "missing_input_keys": item["missing_input_keys"],
                        "used_anchor_ids": item["anchor_ids"],
                        "character_count": item["after"], "reason_code": "none",
                    } for item in review_cases],
                }
                _write_text_atomic(REPORT_PATH, _render_smoke_report(summary))
                _write_text_atomic(HUMAN_REVIEW_PATH, _render_review_template(review_cases))
                statuses = {
                    "live_01": "passed", "preflight": "passed",
                    "live_02a": "passed", "live_02b": "passed",
                    "live_02c": "passed", "live_03": "passed",
                }
                _write_text_atomic(RUN_RESULT_PATH, _render_run_result(statuses, summary))
                print(f"LOCAL_HUMAN_REVIEW_ARTIFACT={final_review_artifact}")
                print("LIVE_LLM_SMOKES_EXECUTED")
                print("READY_FOR_HUMAN_LLM_QUALITY_REVIEW")
                return 0
        finally:
            db.close()
    except HarnessFailure as exc:
        _write_early_failure_report(request_ledger, reason_code=exc.code)
        if exc.code == "live_session_configuration_changed":
            print("LIVE_SESSION_CONFIGURATION_CHANGED")
            print("FRESH_PREFLIGHT_AND_NEW_APPROVAL_REQUIRED")
        else:
            print(f"LIVE_LLM_SMOKE_FAILED reason_code={exc.code}")
        return 1
    except Exception as exc:
        reason_code = _redacted_error(exc)
        _write_early_failure_report(request_ledger, reason_code=reason_code)
        print(f"LIVE_LLM_SMOKE_FAILED reason_code={reason_code}")
        return 1
    finally:
        _close_runtime_resources(runtime_engine)
        _remove_session_root(temp_root)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _build_parser().parse_args(argv)
    if args.command == "cleanup-expired":
        return cleanup_expired()
    if args.command == "prepare-web":
        return prepare_web()
    if args.command == "bind-refined-anchors":
        return bind_refined_anchors(
            args.session_id,
            args.passage,
            usage_policy=args.usage_policy,
        )
    return resume_llm(args.approval)


if __name__ == "__main__":
    raise SystemExit(main())
