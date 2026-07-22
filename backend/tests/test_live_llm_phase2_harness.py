"""Offline, no-network contracts for the RUN 3C Phase 2 harness."""
from __future__ import annotations

import importlib.util
import json
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_live_llm_phase2.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_live_llm_phase2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _session(module, tmp_path, anchors=None):
    session = module.ReviewSession(
        review_session_id="a" * 32,
        session_version=module.SESSION_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        temp_root=str(tmp_path),
        workspace_id="ws", actor_user_id="user", actor_email="user@example.test",
        cases={}, research={}, anchors=anchors or [],
        route_ids={"a2": "r1", "market": "r2"},
        model_refs={"a2": "m1", "market": "m2"},
        provider_config_fingerprints={"a2": "f1", "market": "f2"},
        preflight_fingerprints={"a2": "p1", "market": "p2"},
        policy_version="1.1.0", pricing_version="pv", registry_version="rv",
        active_execution_seconds=1.0, provider_call_seconds=0.5,
        human_wait_started_at=datetime.now(timezone.utc).isoformat(),
        human_wait_ended_at=None, ledger={"planned": [], "records": []},
    )
    session.refresh_hash()
    return session


def test_no_network_without_both_explicit_opt_ins(monkeypatch):
    module = _module()

    class Settings:
        ai_eval_mode = "real"
        agent_fake_provider = False
        web_research_fake_provider = False
        web_research_enabled = True
        openai_api_key = "test"
        anthropic_api_key = "test"
        firecrawl_api_key = "test"

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("RUN_REAL_PROVIDER_SMOKE", raising=False)
    monkeypatch.delenv("RUN_LIVE_LLM_SMOKES_APPROVED", raising=False)
    monkeypatch.delenv("RUN_FIRECRAWL_RECOVERY_APPROVED", raising=False)
    assert module._opt_in_reason(Settings()) == "live_smoke_opt_in_missing"
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    assert module._opt_in_reason(Settings()) == "live_llm_approval_missing"
    monkeypatch.setenv("RUN_LIVE_LLM_SMOKES_APPROVED", "true")
    assert module._opt_in_reason(Settings()) is None
    assert module._opt_in_reason(Settings(), require_llm=False) == (
        "firecrawl_recovery_approval_missing"
    )
    monkeypatch.setenv("RUN_FIRECRAWL_RECOVERY_APPROVED", "true")
    assert module._opt_in_reason(Settings(), require_llm=False) is None


def test_parser_exposes_web_first_commands_only():
    module = _module()
    parser = module._build_parser()
    assert parser.parse_args(["prepare-web"]).command == "prepare-web"
    parsed = parser.parse_args(["resume-llm", "--approval", "approval"])
    assert (parsed.command, parsed.approval) == ("resume-llm", "approval")
    refined = parser.parse_args([
        "bind-refined-anchors", "--session-id", "a" * 32,
        "--passage", f"sv:fragment:10:20:{'1' * 64}",
    ])
    assert refined.command == "bind-refined-anchors"
    assert refined.usage_policy == module.SWISS_MARKET_POLICY
    with pytest.raises(SystemExit):
        parser.parse_args(["prepare"])


def test_redacted_request_ledger_is_atomic_and_content_free(tmp_path):
    module = _module()
    path = tmp_path / "attempt" / "redacted-request-ledger.json"
    ledger = module.AtomicRequestLedger("a" * 32, path)
    ledger.append(module.RequestLedgerEntry(
        attempt_id="a" * 32,
        request_sequence=1,
        provider="firecrawl",
        route_alias="firecrawl",
        purpose="public_search",
        started_at="2026-07-22T00:00:00+00:00",
        finished_at="2026-07-22T00:00:01+00:00",
        http_class="5xx",
        http_status=502,
        retryable=True,
        reason_code="provider_outage",
        input_tokens=None,
        output_tokens=None,
        estimated_cost_chf="not_available",
        actual_cost_chf="not_available",
    ))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["requests"][0]["reason_code"] == "provider_outage"
    assert payload["requests"][0]["retryable"] is True
    assert not path.with_suffix(".tmp").exists()
    serialized = path.read_text(encoding="utf-8")
    assert "Authorization" not in serialized
    assert "raw_query" not in serialized
    assert "provider_response" not in serialized


def test_unlabelled_bootstrap_inference_is_blocked_before_adapter(monkeypatch):
    module = _module()
    from app.agents.providers.openai import OpenAIProvider

    adapter_called = False

    def unexpected_adapter_call(_self, _request):
        nonlocal adapter_called
        adapter_called = True
        raise AssertionError("adapter must not be reached")

    monkeypatch.setattr(OpenAIProvider, "generate", unexpected_adapter_call)
    ledger = module.BudgetLedger(planned=[])
    web_counter = {"calls": 0, "credits": 0.0, "seconds": 0.0, "kinds": []}
    request = SimpleNamespace(max_output_tokens=1, model_id="unused", prompt="unused")
    with module.instrument_live_providers(ledger, web_counter=web_counter):
        with pytest.raises(module.HarnessFailure, match="unplanned_live_llm_call"):
            OpenAIProvider.generate(object(), request)
    assert adapter_called is False
    assert ledger.actual_call_count == 0


def test_primary_application_selection_uses_current_auto_assignment(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_idem", lambda: "idem-primary")

    class Response:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class Client:
        put_payload = None

        def get(self, path):
            assert path == "/api/v1/projects/project-1"
            return Response({"primary_application_source_id": "source-1"})

        def put(self, path, *, json, headers):
            assert path == "/api/v1/projects/project-1/primary-application"
            assert headers["Idempotency-Key"] == "idem-primary"
            self.put_payload = json
            return Response({"primary_application_source_id": "source-1"})

    client = Client()
    result = module._select_current_primary_application(
        client, "csrf", project_id="project-1", source_id="source-1"
    )
    assert result["primary_application_source_id"] == "source-1"
    assert client.put_payload == {
        "source_id": "source-1",
        "expected_primary_source_id": "source-1",
    }


def test_harness_uses_the_canonical_preflight_pass_literal():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from app.evaluation.preflight import PASS" in source
    assert 'result.status != PASS' in source
    assert 'result.status != "passed"' not in source


def test_d0_editor_seed_preserves_all_registry_section_markers():
    module = _module()
    from app.agents.a2_fields import resolve_field_config
    from app.drafts.sections import extract_section, section_spans

    config = resolve_field_config(module.FIELD_ID)
    assert config is not None
    value = module._canonical_composite_field_text(module.SMOKE_1_TEXT)
    spans = section_spans(value, config.mandatory_markers)
    assert [span.marker for span in spans] == list(config.mandatory_markers)
    target = extract_section(value, config.mandatory_markers, module.TARGET_SECTION)
    assert target.startswith(module.EXPECTED_QUESTION)
    assert module.SMOKE_1_TEXT in target


def test_anchor_approval_is_exact_scoped_and_needs_two_versions(tmp_path):
    module = _module()
    hashes = ["1" * 64, "2" * 64]
    session = _session(module, tmp_path, anchors=[
        {"quote_hash": hashes[0], "source_version_id": "sv1"},
        {"quote_hash": hashes[1], "source_version_id": "sv2"},
    ])
    value = f"{module.APPROVAL_PREFIX} {session.review_session_id} {','.join(hashes)}"
    assert len(module.validate_anchor_approval(session, value)) == 2
    with pytest.raises(module.HarnessFailure, match="live_anchor_quote_hash_unknown"):
        module.validate_anchor_approval(
            session,
            f"{module.APPROVAL_PREFIX} {session.review_session_id} {'3' * 64}",
        )
    with pytest.raises(module.HarnessFailure, match="insufficient_approved_source_versions"):
        module.validate_anchor_approval(
            session,
            f"{module.APPROVAL_PREFIX} {session.review_session_id} {hashes[0]}",
        )


def test_refined_passage_selector_and_swiss_market_policy_fail_closed():
    module = _module()
    selector = module.parse_refined_passage(
        f"source-version:fragment:1337:1540:{'a' * 64}"
    )
    assert selector == {
        "source_version_id": "source-version",
        "fragment_id": "fragment",
        "start_offset": 1337,
        "end_offset": 1540,
        "quote_hash": "a" * 64,
    }
    with pytest.raises(module.HarnessFailure, match="live_anchor_passage_selector_invalid"):
        module.parse_refined_passage(f"source:fragment:0:301:{'a' * 64}")

    valid = {
        "suggested_text": (
            "Laut der Marktstudie von Grand View Research wird der globale Markt "
            "auf USD 35,8 Milliarden geschätzt."
        ),
        "missing_inputs": [{"key": "schweizer_tam_marktgroesse_chf"}],
    }
    module._assert_swiss_market_usage_policy(
        valid, require_missing_input=True, require_attribution=True
    )
    with pytest.raises(
        module.HarnessFailure,
        match="live_anchor_policy_swiss_market_derivation_forbidden",
    ):
        module._assert_swiss_market_usage_policy(
            {
                "suggested_text": "Der Schweizer Markt beträgt USD 35,8 Milliarden.",
                "missing_inputs": [{"key": "schweizer_marktgroesse"}],
            },
            require_missing_input=True,
            require_attribution=True,
        )
    with pytest.raises(
        module.HarnessFailure,
        match="live_02b_swiss_market_missing_input_absent",
    ):
        module._assert_swiss_market_usage_policy(
            {"suggested_text": "Laut Mordor wächst das globale KMU-Segment um 12,96 %."},
            require_missing_input=True,
            require_attribution=True,
        )


def test_session_hash_detects_route_or_quote_tampering(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "SESSION_ROOT", tmp_path)
    session = _session(module, tmp_path, anchors=[
        {"quote_hash": "1" * 64, "source_version_id": "sv1"},
        {"quote_hash": "2" * 64, "source_version_id": "sv2"},
    ])
    module.save_session(session)
    path = tmp_path / session.review_session_id / "session.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["route_ids"]["a2"] = "changed"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(module.HarnessFailure, match="live_session_integrity_invalid"):
        module.load_session(session.review_session_id)


def test_consumed_or_expired_session_fails_closed(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "SESSION_ROOT", tmp_path)
    session = _session(module, tmp_path)
    session.consumed = True
    module.save_session(session)
    with pytest.raises(module.HarnessFailure, match="live_session_already_consumed"):
        module.load_session(session.review_session_id)

    session.consumed = False
    session.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    module.save_session(session)
    with pytest.raises(module.HarnessFailure, match="live_session_expired"):
        module.load_session(session.review_session_id)


def test_budget_reserves_all_mandatory_calls_and_fails_closed():
    module = _module()
    planned = [
        module.PlannedCall(f"c{i}", "p", "m", 1, 1) for i in range(6)
    ]
    ledger = module.BudgetLedger(planned=planned)

    class Cost:
        cost_status = "priced"
        cost_chf = 0.49

    class Settings:
        pass

    original = module._future_upper_cost
    module._future_upper_cost = lambda _spec, _settings: 0.49
    try:
        assert module._assert_budget_before_call(
            ledger, label="c0", provider="p", model_id="m", prompt="x",
            max_output_tokens=1, settings=Settings(),
        ) == 0.49
        module._future_upper_cost = lambda _spec, _settings: 0.51
        with pytest.raises(
            module.HarnessFailure,
            match="live_acceptance_incomplete_budget_exhausted",
        ):
            module._assert_budget_before_call(
                ledger, label="c0", provider="p", model_id="m", prompt="x",
                max_output_tokens=1, settings=Settings(),
            )
    finally:
        module._future_upper_cost = original


def test_reports_are_metadata_only():
    module = _module()
    report = module._render_smoke_report({
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "status": "passed",
        "provider_routes": {"a2": "route"},
        "model_refs": {"a2": "model"},
        "cases": [{
            "case_id": "LIVE-02A", "status": "passed",
            "suggestion_id": "s1", "manifest_id": "m1",
            "missing_input_keys": ["market_size"], "used_anchor_ids": [],
        }],
    })
    assert "suggestion_id" in report
    assert "market_size" in report
    assert "Authorization" not in report
    assert "https://" not in report
    assert module.SMOKE_1_TEXT not in report


def test_review_template_has_two_blank_human_sets_without_text():
    module = _module()
    review = module._render_review_template([{
        "case_id": "LIVE-02A", "suggestion_id": "s1",
        "mode": "complete_innolink_requirements", "before": 10, "after": 20,
        "missing_input_keys": ["market_size"], "anchor_ids": [],
        "suggestion_text": "must not be rendered",
    }])
    assert "Reviewer 1" in review and "Reviewer 2" in review
    assert "critical_hallucination" in review
    assert "must not be rendered" not in review


def test_cleanup_rejects_targets_outside_session_root(tmp_path, monkeypatch):
    module = _module()
    session_root = tmp_path / "sessions"
    session_root.mkdir()
    monkeypatch.setattr(module, "SESSION_ROOT", session_root)
    with pytest.raises(module.HarnessFailure, match="cleanup_target_outside_session_root"):
        module._remove_session_root(tmp_path / "outside")


def test_cleanup_closes_checkpoint_before_removing_session(tmp_path, monkeypatch):
    module = _module()
    session_root = tmp_path / "sessions"
    temp_root = session_root / ("f" * 32)
    temp_root.mkdir(parents=True)
    checkpoint_path = temp_root / "checkpoints.db"
    monkeypatch.setattr(module, "SESSION_ROOT", session_root)
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(checkpoint_path))

    from app.config.settings import get_settings
    from app.runs import graph as runs_graph

    runs_graph.close_checkpointer()
    get_settings.cache_clear()
    try:
        runs_graph.get_checkpointer()
        assert checkpoint_path.is_file()

        module._close_runtime_resources()
        assert runs_graph._checkpointer is None
        assert runs_graph._graph is None
        module._remove_session_root(temp_root)
        assert not temp_root.exists()
    finally:
        runs_graph.close_checkpointer()
        get_settings.cache_clear()


def test_live03_user_operations_are_declared_as_http_routes():
    source = SCRIPT.read_text(encoding="utf-8")
    required_route_fragments = {
        "/api/v1/projects",
        "/sources/text",
        "/imports",
        "/primary-application",
        "/processing-confirmations",
        "/runs",
        "/research-brief",
        "/queries/plan",
        "/search-query-approvals/",
        "/research-results/",
        "/review",
        "/external-anchors",
        "/market-comparisons",
        "/suggestion-context-options",
        "/redrafts",
        "/suggestions/",
        "/accept",
    }
    assert required_route_fragments <= {
        marker for marker in required_route_fragments if marker in source
    }
