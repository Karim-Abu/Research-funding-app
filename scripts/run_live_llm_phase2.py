#!/usr/bin/env python
r"""RUN 3C Phase 2: opt-in live LLM acceptance with resumable human gates.

This module is orchestration only. User-visible work is performed through the
production FastAPI routes. Direct database access is limited to disposable test
infrastructure, provider-preflight persistence, counters, and read-only review
material. The script never writes provider payloads or prompts to reports.

Usage (PowerShell, from repository root)::

    $env:RUN_REAL_PROVIDER_SMOKE = "true"
    $env:RUN_LIVE_LLM_SMOKES_APPROVED = "true"
    backend\.venv\Scripts\python.exe scripts\run_live_llm_phase2.py prepare

    backend\.venv\Scripts\python.exe scripts\run_live_llm_phase2.py resume \
      --approval "APPROVE_LIVE_E2E_ANCHORS <session> <hashes>"

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
from datetime import datetime, timezone
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
SESSION_VERSION = "run3c-phase2-session-v1"
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

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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


def _session_path(session_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise HarnessFailure("live_session_id_invalid")
    return SESSION_ROOT / session_id / "session.json"


def save_session(session: ReviewSession) -> Path:
    session.refresh_hash()
    path = _session_path(session.review_session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(asdict(session)), encoding="utf-8")
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


def _opt_in_reason(settings: Any) -> str | None:
    if os.environ.get("CI"):
        return "ci_environment_blocked"
    if os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").casefold() != "true":
        return "live_smoke_opt_in_missing"
    if os.environ.get("RUN_LIVE_LLM_SMOKES_APPROVED", "").casefold() != "true":
        return "live_llm_approval_missing"
    if settings.ai_eval_mode != "real":
        return "live_eval_mode_disabled"
    if settings.agent_fake_provider or settings.web_research_fake_provider:
        return "live_fake_conflict"
    if not settings.web_research_enabled:
        return "web_research_disabled"
    if not settings.openai_api_key or not settings.anthropic_api_key:
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
    from app.agents.a2_fields import skill_id_for
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
    ledger: BudgetLedger, *, web_counter: dict[str, Any]
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
            status = "failed"
            actual_cost = None
            input_tokens = output_tokens = None
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
                ledger.active_label = None
        return counted

    def wrap_web(kind: str, original):
        def counted(self, *args, **kwargs):
            if web_counter["calls"] >= MAX_WEB_CALLS:
                raise HarnessFailure("firecrawl_call_limit_exceeded")
            started = time.monotonic()
            web_counter["calls"] += 1
            try:
                value = original(self, *args, **kwargs)
                credits = getattr(value, "credits_used", None)
                if credits is not None:
                    web_counter["credits"] += float(credits)
                return value
            finally:
                duration = time.monotonic() - started
                web_counter["seconds"] += duration
                web_counter["kinds"].append(kind)
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
        PlannedCall("a2_preflight", a2_route.provider, a2_model, 2_000, 256),
        PlannedCall("live_02a", a2_route.provider, a2_model, context_max, 4096),
    ]
    if market_key != a2_key:
        calls.append(PlannedCall(
            "market_preflight", market_route.provider, market_model, 2_000, 256
        ))
    calls.extend([
        PlannedCall("market_comparison", market_route.provider, market_model, 90_000, 4096),
        PlannedCall("live_02b", a2_route.provider, a2_model, context_max, 4096),
        PlannedCall("live_02c", a2_route.provider, a2_model, context_max, 4096),
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
    source_text = f"{EXPECTED_QUESTION}\n{text}"
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
    _expect(client.put(
        f"/api/v1/projects/{project_id}/primary-application",
        json={"source_id": source_id, "expected_primary_source_id": None},
        headers=_mut(csrf, idem=_idem()),
    ), 200, "primary_application_select_failed")
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
    if current["text"].strip() != text.strip():
        field_view = _expect(client.patch(
            f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
            json={"base_version_id": current["draft_version_id"], "text": text},
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
    from app.evaluation.preflight import persist_route_preflight, preflight_route

    ledger.active_label = label
    result = preflight_route(route_key, settings=get_settings(), execute_live=True)
    row = persist_route_preflight(db, result, triggered_by=actor_id, settings=get_settings())
    db.commit()
    if result.status != "passed":
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
    return "\n".join(lines)


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RUN 3C Phase 2 live acceptance")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    resume = sub.add_parser("resume")
    resume.add_argument("--approval", required=True)
    sub.add_parser("cleanup-expired")
    return parser


def prepare() -> int:  # pragma: no cover - opt-in live path
    session_id = uuid.uuid4().hex
    temp_root = SESSION_ROOT / session_id
    temp_root.mkdir(parents=True, exist_ok=False)
    success_waiting = False
    started = time.monotonic()
    web_counter = {"calls": 0, "credits": 0.0, "seconds": 0.0, "kinds": []}
    try:
        _configure_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from fastapi.testclient import TestClient
        from app.config.settings import get_settings
        from app.db.session import SessionLocal
        from app.evaluation.preflight import configuration_fingerprint
        from app.evaluation.pricing import PRICE_TABLE_VERSION
        from app.main import app

        get_settings.cache_clear()
        settings = get_settings()
        reason = _opt_in_reason(settings)
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
            with instrument_live_providers(ledger, web_counter=web_counter):
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
                    ledger, web_counter=web_counter
                ):
                    a2_preflight = _run_preflight(
                        db, route_key=routes["a2"], actor_id=actor_id,
                        ledger=ledger, label="a2_preflight",
                    )
                    smoke_1 = _generate_suggestion(
                        client, csrf, cases["live_02a"],
                        mode="complete_innolink_requirements", label="live_02a",
                        ledger=ledger,
                    )
                    _assert_smoke_1(smoke_1)
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
                    if len(plan["queries"]) != 1 or not plan["queries"][0].get("approval_id"):
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
                    if routes["market"] == routes["a2"]:
                        market_preflight = a2_preflight
                    else:
                        market_preflight = _run_preflight(
                            db, route_key=routes["market"], actor_id=actor_id,
                            ledger=ledger, label="market_preflight",
                        )

                    from app.db.models import ResearchResult, SourceDocument, SourceFragment, SourceVersion
                    from app.evidence.discovery import quote_hash
                    proposals: list[AnchorProposal] = []
                    for item, document_view in zip(chosen, imported, strict=True):
                        result_row = db.get(ResearchResult, item["result_id"])
                        document = db.get(SourceDocument, document_view["source_id"])
                        version = db.get(SourceVersion, document.current_source_version_id)
                        if (
                            result_row is None or document is None or version is None
                            or version.content_safety_status != "passed"
                            or version.content_review_status != "unreviewed"
                        ):
                            raise HarnessFailure("review_source_state_invalid")
                        fragments = list(db.query(SourceFragment).filter(
                            SourceFragment.source_version_id == version.source_version_id
                        ).order_by(SourceFragment.ordinal))
                        fragment = next((f for f in fragments if len(f.original_text.strip()) >= 80), None)
                        if fragment is None:
                            raise HarnessFailure("review_fragment_missing")
                        text = fragment.original_text.strip()
                        excerpt = text[:300]
                        if len(text) > 300:
                            stop = excerpt.rfind(" ")
                            excerpt = excerpt[:stop if stop >= 80 else 300]
                        offset = fragment.original_text.find(excerpt)
                        if offset < 0:
                            raise HarnessFailure("review_excerpt_not_exact")
                        domain = _safe_domain(result_row.final_url or result_row.source_url)
                        proposals.append(AnchorProposal(
                            result_id=result_row.result_id,
                            source_id=document.source_id,
                            source_version_id=version.source_version_id,
                            fragment_id=fragment.fragment_id,
                            start_offset=offset,
                            end_offset=offset + len(excerpt),
                            domain=domain,
                            title=result_row.title or document.name,
                            excerpt=excerpt,
                            quote_hash=quote_hash(excerpt),
                            safety_status=version.content_safety_status,
                            content_review_status=version.content_review_status,
                        ))
                    expires_at = min(a2_preflight.expires_at, market_preflight.expires_at)
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
                        },
                        anchors=[item.safe_state() for item in proposals],
                        route_ids=routes,
                        model_refs=models,
                        provider_config_fingerprints={
                            key: configuration_fingerprint(route, settings=settings)
                            for key, route in routes.items()
                        },
                        preflight_fingerprints={
                            "a2": a2_preflight.configuration_fingerprint,
                            "market": market_preflight.configuration_fingerprint,
                        },
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
        print(f"LIVE_LLM_PREPARE_FAILED reason_code={exc.code}")
        return 1
    except Exception as exc:
        print(f"LIVE_LLM_PREPARE_FAILED reason_code={_redacted_error(exc)}")
        return 1
    finally:
        if not success_waiting:
            _remove_session_root(temp_root)


def resume(approval: str) -> int:  # pragma: no cover - opt-in live path
    session_id = _session_id_from_approval(approval)
    session = load_session(session_id)
    selected = validate_anchor_approval(session, approval)
    temp_root = Path(session.temp_root)
    started = time.monotonic()
    web_counter = {"calls": MAX_WEB_CALLS, "credits": 0.0, "seconds": 0.0, "kinds": []}
    final_review_artifact: Path | None = None
    try:
        _configure_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from fastapi.testclient import TestClient
        from sqlalchemy import func, select
        from app.config.settings import get_settings
        from app.db.models import (
            DraftSuggestion, DraftVersion, ProviderPreflightResult,
            SourceDocument, SourceFragment, SourceVersion, SuggestionContextManifest,
        )
        from app.db.session import SessionLocal
        from app.evaluation.preflight import configuration_fingerprint, route_preflight_reason
        from app.evaluation.pricing import PRICE_TABLE_VERSION
        from app.main import app

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
            for key, route in routes.items():
                if route_preflight_reason(db, route, settings=settings):
                    raise HarnessFailure("live_session_configuration_changed")
                row = db.query(ProviderPreflightResult).filter(
                    ProviderPreflightResult.route_key == route
                ).order_by(ProviderPreflightResult.checked_at.desc()).first()
                if row is None or row.configuration_fingerprint != session.preflight_fingerprints[key]:
                    raise HarnessFailure("live_session_configuration_changed")
            # Re-hash every approved exact passage before consuming approval.
            for item in selected:
                fragment = db.get(SourceFragment, item["fragment_id"])
                document = db.get(SourceDocument, item["source_id"])
                version = db.get(SourceVersion, item["source_version_id"])
                if (
                    fragment is None or document is None or version is None
                    or document.current_source_version_id != version.source_version_id
                    or fragment.source_version_id != version.source_version_id
                ):
                    raise HarnessFailure("live_anchor_source_changed")
                quote = fragment.original_text[item["start_offset"]:item["end_offset"]]
                if _sha256(quote) != item["quote_hash"]:
                    raise HarnessFailure("live_anchor_quote_changed")

            session.human_wait_ended_at = _iso()
            session.consumed = True
            save_session(session)
            with TestClient(app) as client, instrument_live_providers(
                ledger, web_counter=web_counter
            ):
                csrf = _login(client, session.actor_email)
                anchor_ids = []
                for item in selected:
                    _expect(client.post(
                        f"/api/v1/research-results/{item['result_id']}/review",
                        json={"decision": "supports", "confirm_untrusted_content": False},
                        headers=_mut(csrf),
                    ), 200, "content_review_failed")
                    fragment = db.get(SourceFragment, item["fragment_id"])
                    quote = fragment.original_text[item["start_offset"]:item["end_offset"]]
                    anchor = _expect(client.post(
                        f"/api/v1/research-results/{item['result_id']}/external-anchors",
                        json={"fragment_id": item["fragment_id"], "quote": quote},
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
                    raise HarnessFailure("market_comparison_not_limited")

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
                if not set(smoke_2.get("used_anchor_ids") or []).issubset(set(anchor_ids)):
                    raise HarnessFailure("live_02b_unknown_anchor")
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
                db.expire_all()
                after_versions = db.scalar(select(func.count(DraftVersion.draft_version_id)).where(
                    DraftVersion.draft_id == e2e["draft_id"]
                ))
                if after_versions != before_versions + 1 or db.get(DraftVersion, e2e["base_version_id"]) is None:
                    raise HarnessFailure("live_03_draft_history_invalid")

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
                REPORT_PATH.write_text(_render_smoke_report(summary), encoding="utf-8")
                HUMAN_REVIEW_PATH.write_text(
                    _render_review_template(review_cases), encoding="utf-8"
                )
                statuses = {
                    "live_01": "passed", "preflight": "passed",
                    "live_02a": "passed", "live_02b": "passed",
                    "live_02c": "passed", "live_03": "passed",
                }
                RUN_RESULT_PATH.write_text(
                    _render_run_result(statuses, summary), encoding="utf-8"
                )
                print(f"LOCAL_HUMAN_REVIEW_ARTIFACT={final_review_artifact}")
                print("LIVE_LLM_SMOKES_EXECUTED")
                print("READY_FOR_HUMAN_LLM_QUALITY_REVIEW")
                return 0
        finally:
            db.close()
    except HarnessFailure as exc:
        if exc.code == "live_session_configuration_changed":
            print("LIVE_SESSION_CONFIGURATION_CHANGED")
            print("FRESH_PREFLIGHT_AND_NEW_APPROVAL_REQUIRED")
        else:
            print(f"LIVE_LLM_SMOKE_FAILED reason_code={exc.code}")
        return 1
    except Exception as exc:
        print(f"LIVE_LLM_SMOKE_FAILED reason_code={_redacted_error(exc)}")
        return 1
    finally:
        _remove_session_root(temp_root)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _build_parser().parse_args(argv)
    if args.command == "cleanup-expired":
        return cleanup_expired()
    if args.command == "prepare":
        return prepare()
    return resume(args.approval)


if __name__ == "__main__":
    raise SystemExit(main())
