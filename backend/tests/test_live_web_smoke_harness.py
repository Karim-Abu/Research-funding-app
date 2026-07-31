"""Offline contract tests for scripts/run_live_web_smoke.py."""
from __future__ import annotations

import importlib.util
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_live_web_smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_live_web_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_smoke_report_is_metadata_only():
    module = _module()
    result = module.SmokeResult(
        status="passed",
        execution_mode="live",
        provider_calls=3,
        domain="www.admin.ch",
        query_hash="a" * 64,
        canonical_url_hash="b" * 64,
        risk_level="low",
        firewall_decision="allow",
        approval_status="used",
        preflight_fingerprint="c" * 64,
        content_review_status="unreviewed",
        safety_status="safe",
    )
    report = module._render_report(result)
    assert "www.admin.ch" in report
    assert "query_hash" in report
    assert "canonical_url_hash" in report
    assert "fake_fallback_observed: `no`" in report
    assert "Authorization" not in report
    assert "https://" not in report
    assert "energy monitoring" not in report


def test_live_smoke_requires_explicit_opt_in(monkeypatch):
    module = _module()

    class Settings:
        web_research_enabled = True
        web_research_fake_provider = False
        firecrawl_api_key = "synthetic-test-value"

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("RUN_REAL_PROVIDER_SMOKE", raising=False)
    assert module._opt_in_reason(Settings()) == "live_smoke_opt_in_missing"
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    assert module._opt_in_reason(Settings()) is None
    Settings.web_research_fake_provider = True
    assert module._opt_in_reason(Settings()) == "live_fake_conflict"


def test_demo_domains_are_rejected():
    module = _module()
    assert module._is_demo_domain("example.org")
    assert module._is_demo_domain("www.example.com")
    assert not module._is_demo_domain("www.admin.ch")


def test_harness_orchestrates_existing_services_with_offline_adapter(monkeypatch):
    module = _module()
    from app.config.settings import get_settings
    from app.db.models import ProviderPreflightResult
    from app.db.session import SessionLocal
    from app.research.providers.base import (
        FetchOutcome,
        SearchCandidate,
        SearchOutcome,
    )
    from app.research import executor, import_service

    url = "https://www.admin.ch/gov/en/start/documentation.html"
    content = (
        "Public information about energy monitoring solutions for small "
        "businesses in Switzerland."
    )

    class OfflineFirecrawl:
        name = "firecrawl"

        def __init__(self):
            self.search_calls = 0
            self.fetch_calls = 0

        def available(self):
            return True

        def search(self, request):
            self.search_calls += 1
            return SearchOutcome(
                candidates=[SearchCandidate(
                    url=url,
                    title="Public energy monitoring information",
                    snippet="Candidate metadata only.",
                    rank=1,
                    publisher="admin.ch",
                )],
                provider=self.name,
                latency_ms=2,
                credits_used=1,
            )

        def fetch(self, requested_url, *, max_bytes):
            assert requested_url == url
            self.fetch_calls += 1
            raw = content.encode("utf-8")
            return FetchOutcome(
                text=content,
                final_url=url,
                content_type="text/html",
                byte_size=len(raw),
                content_hash=hashlib.sha256(raw).hexdigest(),
                provider=self.name,
                redirect_chain=[url],
                redirect_chain_verified=True,
                latency_ms=3,
                credits_used=1,
                title="Public energy monitoring information",
                publisher="admin.ch",
            )

    provider = OfflineFirecrawl()
    resolver = lambda _host: ["8.8.8.8"]
    monkeypatch.setattr(executor, "get_web_provider", lambda _settings: (provider, resolver))
    monkeypatch.setattr(
        import_service, "get_web_provider", lambda _settings: (provider, resolver)
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "web_research_enabled", True)
    monkeypatch.setattr(settings, "web_research_fake_provider", False)
    monkeypatch.setattr(settings, "firecrawl_api_key", "synthetic-test-value")
    monkeypatch.setattr(settings, "web_search_max_results", 1)
    monkeypatch.setattr(settings, "agent_fake_provider", False)
    monkeypatch.setattr(settings, "ai_eval_mode", "off")

    actor_user_id = "user-live-web-offline"
    db = SessionLocal()
    try:
        result = module.execute_smoke(
            db,
            settings,
            actor_user_id=actor_user_id,
            preflight_provider=provider,
        )
    finally:
        # The suite shares one temporary DB. A successful readiness row must not
        # make later capability tests believe a real preflight was performed.
        db.query(ProviderPreflightResult).filter(
            ProviderPreflightResult.triggered_by == actor_user_id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()

    assert result.status == "passed", result.reason_codes
    assert result.execution_mode == "live"
    assert result.provider_calls == 3
    assert provider.search_calls == 2
    assert provider.fetch_calls == 1
    assert result.fake_fallback_observed is False
    # Import auto-reviews a non-quarantined AI-found result (2026-07-26).
    assert result.content_review_status == "reviewed"
    assert result.safety_status == "passed"
