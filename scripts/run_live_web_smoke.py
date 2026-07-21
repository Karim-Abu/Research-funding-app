#!/usr/bin/env python
"""Opt-in RUN-3B live-web smoke through the production research services.

The script is orchestration only. Planning, firewall evaluation, approval,
execution, import, URL safety and ingestion remain in their existing services.
It writes a redacted metadata-only report and always removes its temporary DB
and storage directories, including on failures.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_REPORT = ROOT / "docs" / "LIVE_WEB_SMOKE_REPORT.md"
PROVIDER = "firecrawl"
MAX_PROVIDER_CALLS = 3
DEMO_DOMAINS = {"example.org", "example.com", "example.net"}


@dataclass
class SmokeResult:
    status: str = "failed"
    reason_codes: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    execution_mode: str = "not_run"
    provider_calls: int = 0
    duration_ms: int = 0
    credits: str = "not_available"
    result_id: str | None = None
    task_id: str | None = None
    approval_id: str | None = None
    source_id: str | None = None
    source_version_id: str | None = None
    domain: str | None = None
    query_hash: str | None = None
    risk_level: str | None = None
    firewall_decision: str | None = None
    approval_status: str | None = None
    preflight_fingerprint: str | None = None
    canonical_url_hash: str | None = None
    content_review_status: str | None = None
    safety_status: str | None = None
    fake_fallback_observed: bool = False


class SmokeFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_domain(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().rstrip(".")


def _is_demo_domain(domain: str) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in DEMO_DOMAINS)


def _opt_in_reason(settings) -> str | None:
    if os.environ.get("CI"):
        return "ci_environment_blocked"
    if os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").casefold() != "true":
        return "live_smoke_opt_in_missing"
    if not settings.web_research_enabled:
        return "web_research_disabled"
    if settings.web_research_fake_provider:
        return "live_fake_conflict"
    if not settings.firecrawl_api_key:
        return "firecrawl_key_missing"
    return None


def _render_report(result: SmokeResult) -> str:
    reasons = ", ".join(f"`{value}`" for value in result.reason_codes) or "none"
    value = lambda item: str(item) if item not in (None, "") else "not_available"
    return "\n".join(
        [
            "# LIVE WEB SMOKE REPORT",
            "",
            f"- Provider: `{PROVIDER}`",
            f"- Timestamp: `{result.timestamp}`",
            f"- Execution Mode: `{result.execution_mode}`",
            f"- Calls: `{result.provider_calls}`",
            f"- Duration ms: `{result.duration_ms}`",
            f"- Credits/Cost: `{result.credits}`",
            f"- Status: `{result.status}`",
            f"- Reason Codes: {reasons}",
            f"- Result ID: `{value(result.result_id)}`",
            f"- Research Task ID: `{value(result.task_id)}`",
            f"- Approval ID: `{value(result.approval_id)}`",
            f"- Source ID: `{value(result.source_id)}`",
            f"- Source Version ID: `{value(result.source_version_id)}`",
            f"- Public Domain: `{value(result.domain)}`",
            f"- query_hash: `{value(result.query_hash)}`",
            f"- risk_level: `{value(result.risk_level)}`",
            f"- firewall_decision: `{value(result.firewall_decision)}`",
            f"- approval_status: `{value(result.approval_status)}`",
            f"- preflight_fingerprint: `{value(result.preflight_fingerprint)}`",
            f"- canonical_url_hash: `{value(result.canonical_url_hash)}`",
            f"- content_review_status: `{value(result.content_review_status)}`",
            f"- safety_status: `{value(result.safety_status)}`",
            "- fake_fallback_observed: "
            f"`{'yes' if result.fake_fallback_observed else 'no'}`",
            "",
            "Der Bericht enthaelt ausschliesslich redigierte Metadaten.",
            "",
        ]
    )


def _sum_credits(task) -> str:
    usage = dict(task.provider_usage or {})
    values = [usage.get("credits_used"), usage.get("last_fetch_credits_used")]
    if any(value is None for value in values):
        return "not_available"
    try:
        return str(sum(float(value) for value in values))
    except (TypeError, ValueError):
        return "not_available"


def execute_smoke(
    db, settings, *, actor_user_id: str, preflight_provider=None
) -> SmokeResult:
    """Run the approved smoke in an already configured disposable database."""
    from sqlalchemy import func, select

    from app.config.settings import get_settings
    from app.contracts.research_brief import ResearchBriefInput
    from app.db.models import (
        EvidenceAnchor,
        FundingProfile,
        Project,
        ProviderPreflightResult,
        ResearchResult,
        ResearchTask,
        SourceDocument,
        SourceVersion,
        User,
        Workspace,
    )
    from app.evaluation.preflight import (
        firecrawl_readiness,
        persist_route_preflight,
        preflight_firecrawl,
    )
    from app.research import brief_service, import_service
    from app.security import approval_service

    if settings is not get_settings():
        raise SmokeFailure("settings_instance_mismatch")
    result = SmokeResult(execution_mode="live")
    started = time.monotonic()
    logs: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logs.append(self.format(record))

    capture = _Capture()
    logging.getLogger().addHandler(capture)
    raw_query_for_leak_check = ""
    try:
        preflight = preflight_firecrawl(
            settings=settings,
            provider=preflight_provider,
            execute_live=True,
        )
        result.provider_calls += 1
        preflight_row = persist_route_preflight(
            db, preflight, triggered_by=actor_user_id, settings=settings
        )
        db.commit()
        result.preflight_fingerprint = preflight_row.configuration_fingerprint
        readiness = firecrawl_readiness(db, settings)
        if readiness.status != "ready":
            raise SmokeFailure(readiness.reason_code or "firecrawl_preflight_failed")

        suffix = uuid.uuid4().hex[:10]
        workspace_id = f"ws-live-web-{suffix}"
        project_id = f"project-live-web-{suffix}"
        profile_id = "innosuisse_innovation_project_with_implementation_partner"
        db.add(Workspace(id=workspace_id, name="Synthetic Live Web Smoke"))
        if db.get(FundingProfile, profile_id) is None:
            db.add(FundingProfile(id=profile_id, title="Synthetic funding profile"))
        db.add(
            User(
                id=actor_user_id,
                workspace_id=workspace_id,
                name="Synthetic Smoke Actor",
                email=f"live-web-{suffix}@example.test",
                password_hash="not-a-login-secret",
                role="lead_admin",
            )
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            title="Synthetic fixture 8472",
            description="D0 smoke fixture without private project data.",
            innovation_field="Public information research",
            funding_instrument_profile_id=profile_id,
            data_classification={
                "sensitivity": "public",
                "origin": "synthetic",
                "processing_mode": "cloud_assisted",
                "web_research_mode": "validated_public",
                "nda_applies": False,
            },
            created_by=actor_user_id,
            status="draft",
        )
        db.add(project)
        db.flush()
        brief = brief_service.save(
            db,
            project,
            actor_user_id,
            ResearchBriefInput(
                research_goal=(
                    "Public market overview of energy monitoring solutions for "
                    "small businesses"
                ),
                search_tags=["energy monitoring", "small businesses"],
                region="Switzerland",
                modules=["competition_alternatives"],
            ),
        )
        brief_service.approve(db, brief, actor_user_id)
        plan = brief_service.plan_queries(db, brief, actor_user_id)
        if len(plan.queries) != 1 or not plan.queries[0].approval_id:
            raise SmokeFailure("unexpected_query_plan")
        query_view = plan.queries[0]
        approval = approval_service.get_scoped(
            db, query_view.approval_id, workspace_id
        )
        if approval is None:
            raise SmokeFailure("approval_not_found")
        raw_query_for_leak_check = approval.sanitized_query
        result.query_hash = approval.raw_query_hash
        result.risk_level = query_view.risk_label
        result.firewall_decision = approval.decision
        approval_service.decide(
            db, approval=approval, actor_user_id=actor_user_id, approve=True
        )
        result.approval_id = approval.approval_id
        result.approval_status = approval.status
        db.commit()

        run = brief_service.run(db, brief, actor_user_id, [approval.approval_id])
        result.provider_calls += 1
        if run.execution_mode != "live" or len(run.task_ids) != 1:
            raise SmokeFailure("research_execution_not_live")
        task = db.get(ResearchTask, run.task_ids[0])
        result.task_id = run.task_ids[0]
        if task is None or task.provider != PROVIDER or task.execution_mode != "live":
            result.fake_fallback_observed = bool(
                task and (task.provider == "fake" or task.execution_mode == "fake_demo")
            )
            raise SmokeFailure("live_provider_provenance_invalid")
        result.approval_status = approval.status
        candidate = db.scalar(
            select(ResearchResult)
            .where(
                ResearchResult.research_task_id == task.research_task_id,
                ResearchResult.status == "candidate",
            )
            .order_by(ResearchResult.provider_rank, ResearchResult.created_at)
        )
        if candidate is None:
            raise SmokeFailure("no_live_candidate")
        domain = _safe_domain(candidate.source_url)
        if not domain or _is_demo_domain(domain):
            result.fake_fallback_observed = _is_demo_domain(domain)
            raise SmokeFailure("live_demo_domain_rejected")
        result.result_id = candidate.result_id
        result.domain = domain

        anchors_before = db.scalar(
            select(func.count(EvidenceAnchor.anchor_id)).where(
                EvidenceAnchor.project_id == project.project_id
            )
        ) or 0
        document = import_service.import_result(
            db,
            result=candidate,
            task=task,
            project=project,
            actor_user_id=actor_user_id,
        )
        result.provider_calls += 1
        db.expire_all()
        candidate = db.get(ResearchResult, candidate.result_id)
        task = db.get(ResearchTask, task.research_task_id)
        document = db.get(SourceDocument, document.source_id)
        version = (
            db.get(SourceVersion, document.current_source_version_id)
            if document and document.current_source_version_id
            else None
        )
        if candidate is None or candidate.status != "imported" or version is None:
            raise SmokeFailure("explicit_import_incomplete")
        if result.provider_calls > MAX_PROVIDER_CALLS:
            raise SmokeFailure("provider_call_limit_exceeded")
        provenance = dict(version.retrieval_provenance or {})
        if (
            provenance.get("provider") != PROVIDER
            or provenance.get("execution_mode") != "live"
            or provenance.get("research_task_id") != task.research_task_id
            or provenance.get("query_approval_id") != approval.approval_id
        ):
            raise SmokeFailure("source_provenance_invalid")
        anchors_after = db.scalar(
            select(func.count(EvidenceAnchor.anchor_id)).where(
                EvidenceAnchor.project_id == project.project_id
            )
        ) or 0
        if anchors_after != anchors_before:
            raise SmokeFailure("search_snippet_used_as_evidence")
        if version.content_safety_status not in ("passed", "human_released"):
            raise SmokeFailure("imported_content_not_safe")
        canonical_url = str(provenance.get("canonical_url") or "")
        if not canonical_url:
            raise SmokeFailure("canonical_url_missing")
        result.source_id = document.source_id
        result.source_version_id = version.source_version_id
        result.canonical_url_hash = _sha256(canonical_url)
        result.content_review_status = version.content_review_status
        result.safety_status = version.content_safety_status
        result.credits = _sum_credits(task)
        if raw_query_for_leak_check and raw_query_for_leak_check in "\n".join(logs):
            raise SmokeFailure("raw_query_logged")
        result.status = "passed"
        return result
    except SmokeFailure as exc:
        result.reason_codes.append(exc.code)
        return result
    except Exception as exc:  # safe class only; never emit provider content
        result.reason_codes.append(
            getattr(exc, "code", None) or type(exc).__name__.casefold()
        )
        return result
    finally:
        logging.getLogger().removeHandler(capture)
        result.duration_ms = int((time.monotonic() - started) * 1000)


def _configure_temp_environment(temp_root: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{(temp_root / 'smoke.db').as_posix()}"
    os.environ["SOURCE_STORAGE_DIR"] = str(temp_root / "sources")
    os.environ["CHECKPOINT_DB_PATH"] = str(temp_root / "checkpoints.db")
    os.environ["EXPORT_STORAGE_DIR"] = str(temp_root / "exports")
    os.environ["APP_ENV"] = "test"
    os.environ["WEB_RESEARCH_ENABLED"] = "true"
    os.environ["WEB_RESEARCH_FAKE_PROVIDER"] = "false"
    os.environ["WEB_SEARCH_MAX_RESULTS"] = "1"
    os.environ["AGENT_FAKE_PROVIDER"] = "false"
    os.environ["AI_EVAL_MODE"] = "off"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    temp_root = Path(tempfile.mkdtemp(prefix="innolink-live-web-smoke-"))
    result = SmokeResult()
    db = None
    engine = None
    try:
        _configure_temp_environment(temp_root)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        from app.config.settings import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        reason = _opt_in_reason(settings)
        if reason:
            result.reason_codes.append(reason)
        else:
            from app.db.models import Base
            from app.db.session import SessionLocal, engine as app_engine

            engine = app_engine
            Base.metadata.create_all(engine)
            db = SessionLocal()
            result = execute_smoke(
                db, settings, actor_user_id=f"user-live-web-{uuid.uuid4().hex[:10]}"
            )
    finally:
        if db is not None:
            db.close()
        if engine is not None:
            engine.dispose()
        shutil.rmtree(temp_root, ignore_errors=True)
        DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_REPORT.write_text(_render_report(result), encoding="utf-8")
    print(
        "LIVE_WEB_SMOKE_PASSED" if result.status == "passed"
        else "LIVE_WEB_SMOKE_FAILED"
    )
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
