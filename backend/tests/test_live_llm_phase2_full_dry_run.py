"""One contiguous, process-separated offline rehearsal of Phase 2 prepare/resume.

The deterministic adapters replace transport only. The tracked harness, FastAPI
routes, model gateway, schemas, grounding, cost guards, persistence, approval and
cleanup paths remain the production implementations.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import multiprocessing
import os
import re
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path
from queue import Empty
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SCRIPT = ROOT / "scripts" / "run_live_llm_phase2.py"
SNIPPET_SENTINEL = "OFFLINE_SEARCH_SNIPPET_NEVER_EVIDENCE"
PUBLIC_SOURCES = (
    {
        "url": "https://www.kmu.admin.ch/kmu/en/home/facts-and-trends.html",
        "title": "Public Swiss SME compliance information",
        "publisher": "kmu.admin.ch",
        "text": (
            "Public Swiss market information describes recurring compliance work for "
            "small and medium-sized enterprises. The source documents demand for "
            "structured software support in Switzerland."
        ),
    },
    {
        "url": "https://www.bfs.admin.ch/bfs/en/home/statistics/industry-services.html",
        "title": "Public Swiss business statistics context",
        "publisher": "bfs.admin.ch",
        "text": (
            "Public business statistics describe digital services used by Swiss small "
            "and medium-sized enterprises. The source identifies recurring regulatory "
            "work as relevant context for software services."
        ),
    },
)


def _load_harness(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _append_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")


def _safe_ids(value: Any, found: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    result = found if found is not None else {}
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_id") and isinstance(item, str):
                result.setdefault(key, []).append(item)
            elif key.endswith("_ids") and isinstance(item, list):
                result.setdefault(key, []).extend(
                    str(entry) for entry in item if isinstance(entry, str)
                )
            else:
                _safe_ids(item, result)
    elif isinstance(value, list):
        for item in value:
            _safe_ids(item, result)
    return {key: sorted(set(items)) for key, items in result.items()}


def _safe_status(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "status", "generation_status", "last_error_code", "warnings",
        "execution_mode", "firewall_decision", "risk_label", "error",
        "error_code", "retryable", "result_count",
    }
    result = {
        key: item for key, item in value.items()
        if key in allowed and isinstance(item, (str, int, float, bool, list, type(None)))
    }
    error = value.get("error")
    if isinstance(error, dict):
        result["error_code"] = error.get("code")
    return result


def _trace_testclient(trace_path: Path) -> None:
    from fastapi.testclient import TestClient

    original = TestClient.request

    def traced(self, method, url, *args, **kwargs):
        response = original(self, method, url, *args, **kwargs)
        try:
            body = response.json()
        except Exception:
            body = None
        raw_url = str(url)
        path = raw_url.split("?", 1)[0]
        if "://" in path:
            path = "/" + path.split("/", 3)[-1]
        _append_json(trace_path, {
            "kind": "http",
            "method": str(method).upper(),
            "path": path,
            "status": response.status_code,
            "artifact_ids": _safe_ids(body),
            "safe_status": _safe_status(body),
        })
        return response

    TestClient.request = traced


def _input_payload(request) -> dict[str, Any]:
    marker = "INPUT:\n"
    if marker not in request.prompt:
        return {}
    line = request.prompt.split(marker, 1)[1].split("\n", 1)[0]
    return json.loads(line)


def _a2_output(request) -> dict[str, Any]:
    payload = _input_payload(request)
    evidence = payload.get("external_evidence") or []
    anchor_ids = sorted({
        str(item["anchor_id"]) for item in evidence
        if isinstance(item, dict) and item.get("anchor_id")
    })
    shortened = '"improvement_mode":"shorten"' in request.prompt.replace(" ", "")
    if shortened:
        suggested = (
            "3.1\nDie Lösung unterstützt Schweizer KMU bei wiederkehrenden "
            "Compliance-Arbeiten und wird als jährliche Softwarelizenz angeboten."
        )
        missing = []
        rationale = "Der Abschnitt wurde ohne neue Fakten gekürzt."
    elif anchor_ids:
        suggested = (
            "3.1\nDie synthetische Softwarelösung unterstützt Schweizer KMU bei "
            "der strukturierten Bearbeitung wiederkehrender Compliance-Aufgaben. Das "
            "Geschäftsmodell ist eine jährliche Softwarelizenz. Marktangaben werden "
            "nur über ausdrücklich freigegebene öffentliche Belegstellen ergänzt."
        )
        missing = []
        rationale = "Der Abschnitt wurde mit den ausgewählten Belegen präzisiert."
    else:
        suggested = (
            "3.1\nDie Lösung richtet sich an Schweizer KMU, soll manuelle "
            "Compliance-Arbeiten reduzieren und wird als jährliche Softwarelizenz "
            "angeboten."
        )
        missing = [{
            "label": "Marktgrösse",
            "reason": "Welche öffentlich belegte Marktgrösse gilt für die Zielgruppe?",
        }]
        rationale = "Fehlende Marktgrundlagen wurden als offene Eingabe belassen."
    return {
        "section_candidate": {
            "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            "target_section": "3.1",
            "suggested_text": suggested,
            "rationale": rationale,
            "preserved_facts": [],
            "removed_or_reframed_claims": [],
            "new_claims": [],
            "missing_inputs": missing,
            "evidence_anchor_ids": anchor_ids,
            "research_source_ids": [],
            "open_issue_ids": [],
        },
        "warnings": [],
    }


def _market_output(request) -> dict[str, Any]:
    payload = _input_payload(request)
    items = []
    for index, fragment in enumerate(payload.get("candidate_fragments") or [], start=1):
        quote = str(fragment.get("text") or "").strip()
        if not quote:
            continue
        items.append({
            "name": f"Public compliance context {index}",
            "category": "customer_problem",
            "description": "Public-source context requiring human interpretation.",
            "target_customer_segment": None,
            "offering_summary": None,
            "strengths": None,
            "weaknesses": None,
            "differentiation_relevance": "Public context only.",
            "solution_type": None,
            "centralization": "unclear",
            "data_access_model": None,
            "swiss_relevance": "Public Swiss source.",
            "core_problem_or_benefit": None,
            "relevant_functions": [],
            "price_business_model": None,
            "uncertainty": "The exact passage is the only asserted evidence.",
            "relation_to_project": "unclear",
            "source_fragment_id": fragment["fragment_id"],
            "source_document_id": fragment["source_document_id"],
            "quote": quote,
        })
    return {
        "items": items,
        "research_gaps": ["No public market size was established."],
        "warnings": ["Human review remains required."],
    }


def _install_offline_adapters(trace_path: Path, *, firecrawl_502: bool = False) -> None:
    from app.agents.providers.anthropic import AnthropicProvider
    from app.agents.providers.base import ProviderResult, ProviderUsage
    from app.agents.providers.openai import OpenAIProvider
    from app.research.providers import resolver as web_resolver
    from app.research.providers.base import (
        FetchOutcome, ProviderError, SearchCandidate, SearchOutcome,
    )
    from app.research.providers.firecrawl import FirecrawlProvider

    def llm_result(provider: str, request) -> ProviderResult:
        _append_json(trace_path, {
            "kind": "provider",
            "provider": provider,
            "model_id": request.model_id,
            "output_schema_id": request.output_schema_id,
        })
        if request.output_schema_id == "PreflightPong@v1":
            body = {"pong": True}
        elif request.output_schema_id == "PortalSectionDraftBundle@v1":
            body = _a2_output(request)
        elif request.output_schema_id == "MarketComparisonResult@v1":
            body = _market_output(request)
        else:  # fail closed on any unplanned inference
            raise AssertionError(f"unplanned output schema: {request.output_schema_id}")
        return ProviderResult(
            raw_output=json.dumps(body, ensure_ascii=False),
            usage=ProviderUsage(input_tokens=64, output_tokens=96),
            model=f"offline-{provider}-resolved",
        )

    OpenAIProvider.generate = lambda _self, request: llm_result("openai_direct", request)
    AnthropicProvider.generate = lambda _self, request: llm_result(
        "anthropic_direct", request
    )

    def search(_self, request):
        _append_json(trace_path, {
            "kind": "web_provider", "operation": "search",
            "query_hash": hashlib.sha256(request.query.encode("utf-8")).hexdigest(),
            "status": 502 if firecrawl_502 else 200,
        })
        if firecrawl_502:
            raise ProviderError("firecrawl search status 502")
        return SearchOutcome(
            candidates=[SearchCandidate(
                url=row["url"], title=row["title"],
                snippet=f"{SNIPPET_SENTINEL}_{index}", rank=index,
                publisher=row["publisher"], source_category="research",
            ) for index, row in enumerate(PUBLIC_SOURCES, start=1)],
            provider="firecrawl", latency_ms=1, credits_used=1,
        )

    def fetch(_self, requested_url, *, max_bytes):
        row = next(item for item in PUBLIC_SOURCES if item["url"] == requested_url)
        raw = row["text"].encode("utf-8")
        assert len(raw) <= max_bytes
        _append_json(trace_path, {
            "kind": "web_provider", "operation": "fetch",
            "canonical_url_hash": hashlib.sha256(requested_url.encode("utf-8")).hexdigest(),
        })
        return FetchOutcome(
            text=row["text"], final_url=requested_url,
            content_type="text/html", byte_size=len(raw),
            content_hash=hashlib.sha256(raw).hexdigest(), provider="firecrawl",
            redirect_chain=[requested_url], redirect_chain_verified=True,
            latency_ms=1, credits_used=1, title=row["title"],
            publisher=row["publisher"],
        )

    FirecrawlProvider.search = search
    FirecrawlProvider.fetch = fetch
    web_resolver.set_override((
        FirecrawlProvider(
            api_key="offline-transport-test-only",
            timeout_seconds=60,
        ),
        lambda _hostname: ["93.184.216.34"],
    ))


def _prepare_child_environment(work_root: Path) -> None:
    os.environ.pop("CI", None)
    os.environ.update({
        "RUN_REAL_PROVIDER_SMOKE": "true",
        "RUN_LIVE_LLM_SMOKES_APPROVED": "true",
        "RUN_FIRECRAWL_RECOVERY_APPROVED": "true",
        "OPENAI_API_KEY": "offline-transport-test-only",
        "ANTHROPIC_API_KEY": "offline-transport-test-only",
        "FIRECRAWL_API_KEY": "offline-transport-test-only",
        # 2026-07-26: AGENT_MODEL_PRICING_CHF_PER_MILLION bepreist seit 8416914
        # keinen Call mehr (pricing.resolve_cost ist USD-first, fail-closed).
        # Der Harness prueft vor jedem Call den Preis und bricht sonst mit
        # "unknown_price" ab — der Dry Run braucht deshalb echte Katalog-Ids.
        "AGENT_MODEL_GPT_56_TERRA_ID": "gpt-5.6-terra",
        "AGENT_MODEL_CLAUDE_SONNET_5_ID": "claude-sonnet-5",
    })
    work_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(work_root / "temporary")
    Path(tempfile.tempdir).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(BACKEND))
    # Any unexpected network escape fails before transport. TestClient uses an
    # in-process ASGI transport and therefore does not need a socket.
    socket.create_connection = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("external network disabled in Phase 2 dry run")
    )
    socket.getaddrinfo = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("DNS disabled in Phase 2 dry run")
    )


def _phase2_worker(
    mode: str,
    work_root_value: str,
    trace_path_value: str,
    approval: str | None,
    queue,
) -> None:
    work_root = Path(work_root_value)
    trace_path = Path(trace_path_value)
    try:
        _prepare_child_environment(work_root)
        harness = _load_harness(f"run_live_llm_phase2_{mode}_{os.getpid()}")
        harness.SESSION_ROOT = work_root / "sessions"
        reports = work_root / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        harness.REPORT_PATH = reports / "LIVE_LLM_SMOKE_REPORT.md"
        harness.HUMAN_REVIEW_PATH = reports / "LIVE_LLM_HUMAN_REVIEW.md"
        harness.RUN_RESULT_PATH = reports / "RUN_3_RESULT.md"
        original_budget_check = harness._assert_budget_before_call

        def traced_budget_check(ledger, **kwargs):
            try:
                estimate = original_budget_check(ledger, **kwargs)
            except Exception as exc:
                _append_json(trace_path, {
                    "kind": "budget", "label": kwargs.get("label"),
                    "status": "blocked", "reason": str(exc),
                    "record_count": ledger.actual_call_count,
                })
                raise
            _append_json(trace_path, {
                "kind": "budget", "label": kwargs.get("label"),
                "status": "allowed", "upper_cost_chf": estimate,
                "record_count": ledger.actual_call_count,
            })
            return estimate

        harness._assert_budget_before_call = traced_budget_check
        _trace_testclient(trace_path)
        _install_offline_adapters(trace_path, firecrawl_502=mode == "prepare_web_502")
        code = (
            harness.prepare_web()
            if mode in {"prepare_web", "prepare_web_502"}
            else harness.resume_llm(approval or "")
        )
        queue.put({"code": code, "error": None})
    except BaseException as exc:  # process boundary must return a safe test failure
        queue.put({"code": 99, "error": f"{type(exc).__name__}:{exc}"})


def _run_worker(
    mode: str,
    work_root: Path,
    trace_path: Path,
    approval: str | None = None,
    *,
    expected_code: int = 0,
):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_phase2_worker,
        args=(mode, str(work_root), str(trace_path), approval, queue),
    )
    started = time.monotonic()
    process.start()
    process.join(timeout=180)
    duration = time.monotonic() - started
    if process.is_alive():
        process.terminate()
        process.join(timeout=10)
        pytest.fail(f"{mode} worker timed out")
    try:
        result = queue.get(timeout=5)
    except Empty:
        pytest.fail(f"{mode} worker returned no result (exit={process.exitcode})")
    assert process.exitcode == 0, result
    assert result == {"code": expected_code, "error": None}, result
    return duration


def _read_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _http(trace: list[dict[str, Any]], method: str, pattern: str) -> list[dict[str, Any]]:
    regex = re.compile(pattern)
    return [row for row in trace if (
        row.get("kind") == "http" and row.get("method") == method
        and regex.search(row.get("path") or "")
    )]


def _artifact(row: dict[str, Any], key: str) -> str:
    values = row.get("artifact_ids", {}).get(key, [])
    assert values, (key, row)
    return values[0]


def _route_artifact_ids(
    trace: list[dict[str, Any]], method: str, pattern: str
) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = {}
    for row in _http(trace, method, pattern):
        for key, values in row.get("artifact_ids", {}).items():
            merged.setdefault(key, set()).update(values)
    return {key: sorted(values) for key, values in sorted(merged.items())}


def test_phase2_prepare_web_provider_502_is_classified_and_cleaned():
    work_root = Path(tempfile.mkdtemp(prefix="p2err-")).resolve()
    shutil.rmtree(work_root)
    trace_path = work_root / "safe-trace.jsonl"

    _run_worker(
        "prepare_web_502", work_root, trace_path, expected_code=1,
    )

    trace = _read_trace(trace_path)
    web_calls = [row for row in trace if row.get("kind") == "web_provider"]
    assert web_calls == [{
        "kind": "web_provider",
        "operation": "search",
        "query_hash": web_calls[0]["query_hash"],
        "status": 502,
    }]
    assert not [row for row in trace if row.get("kind") == "provider"]

    run_rows = _http(trace, "POST", r"/research-briefs/[^/]+/run$")
    assert len(run_rows) == 1
    assert run_rows[0]["safe_status"]["result_count"] == 0
    task_rows = _http(trace, "GET", r"/research-tasks/[^/]+$")
    operation_rows = _http(trace, "GET", r"/operations/[^/]+$")
    task_status = task_rows[0]["safe_status"]
    assert task_status["status"] == "failed"
    assert task_status["error_code"] == "provider_outage"
    assert task_status["retryable"] is True
    assert task_status["result_count"] == 0
    assert operation_rows[-1]["safe_status"]["status"] == "failed"
    assert operation_rows[-1]["safe_status"]["error_code"] == "provider_outage"
    assert not _http(trace, "GET", r"/projects/[^/]+/research-results$")
    assert not _http(trace, "POST", r"/research-results/[^/]+/import$")

    report = (work_root / "reports" / "LIVE_LLM_SMOKE_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "reason_code: `provider_outage`" in report
    assert "http_status=`502`" in report
    assert "retryable=`True`" in report
    assert "insufficient_external_evidence" not in report
    assert "fake_fallback_observed: `no`" in report
    assert "Authorization" not in report and SNIPPET_SENTINEL not in report

    assert not list((work_root / "sessions").glob("*"))
    assert not list(work_root.rglob("phase2.db"))
    assert not list(work_root.rglob("redacted-request-ledger.json"))
    assert not list(work_root.rglob("sources"))
    assert not list(work_root.rglob("checkpoints.db"))
    assert not list(work_root.rglob("exports"))
    shutil.rmtree(work_root, ignore_errors=False)


def test_phase2_prepare_web_resume_llm_full_offline_dry_run():
    configured_root = os.environ.get("PHASE2_DRY_RUN_WORK_ROOT")
    work_root = (
        Path(configured_root).resolve()
        if configured_root
        else Path(tempfile.mkdtemp(prefix="p2dry-")).resolve()
    )
    if work_root.exists():
        shutil.rmtree(work_root)
    trace_path = work_root / "safe-trace.jsonl"

    prepare_seconds = _run_worker("prepare_web", work_root, trace_path)
    session_files = list((work_root / "sessions").glob("*/session.json"))
    assert len(session_files) == 1
    session_payload = json.loads(session_files[0].read_text(encoding="utf-8"))
    session_id = session_payload["review_session_id"]
    state_hash = session_payload["state_hash"]
    quote_hashes = [item["quote_hash"] for item in session_payload["anchors"]]
    source_versions = {item["source_version_id"] for item in session_payload["anchors"]}
    assert len(quote_hashes) == 2 and len(source_versions) == 2
    assert len({item["fragment_id"] for item in session_payload["anchors"]}) == 2
    assert session_payload["human_wait_ended_at"] is None
    assert session_payload["ledger"]["records"] == []
    assert session_payload["preflight_fingerprints"] == {}
    assert session_payload["research"]["firewall_decision"] == "allow"
    assert session_payload["research"]["approval_id"]
    prepare_trace = _read_trace(trace_path)
    assert not [row for row in prepare_trace if row.get("kind") == "provider"]
    assert [row["operation"] for row in prepare_trace if row.get("kind") == "web_provider"] == [
        "search", "fetch", "fetch",
    ]

    # The same contiguous rehearsal proves tamper rejection without mutating the
    # actual session that resume must consume.
    local_harness = _load_harness("run_live_llm_phase2_parent_dry_run")
    local_harness.SESSION_ROOT = work_root / "sessions"
    loaded = local_harness.load_session(session_id)
    assert loaded.state_hash == state_hash
    tampered = copy.deepcopy(loaded)
    tampered.route_ids["a2"] = "tampered-route"
    with pytest.raises(local_harness.HarnessFailure, match="live_session_integrity_invalid"):
        tampered.verify_hash()
    bad_hash = "f" * 64
    with pytest.raises(local_harness.HarnessFailure, match="live_anchor_quote_hash_unknown"):
        local_harness.validate_anchor_approval(
            loaded,
            f"{local_harness.APPROVAL_PREFIX} {session_id} {quote_hashes[0]},{bad_hash}",
        )

    human_wait_started = time.monotonic()
    time.sleep(0.2)
    approval = f"{local_harness.APPROVAL_PREFIX} {session_id} {','.join(quote_hashes)}"
    resume_seconds = _run_worker("resume_llm", work_root, trace_path, approval)
    human_wait_seconds = time.monotonic() - human_wait_started - resume_seconds
    assert human_wait_seconds >= 0.15

    trace = _read_trace(trace_path)
    provider_calls = [row for row in trace if row.get("kind") == "provider"]
    web_calls = [row for row in trace if row.get("kind") == "web_provider"]
    assert len(provider_calls) == 6
    assert [row["output_schema_id"] for row in provider_calls] == [
        "PreflightPong@v1",
        "PortalSectionDraftBundle@v1",
        "PreflightPong@v1",
        "MarketComparisonResult@v1",
        "PortalSectionDraftBundle@v1",
        "PortalSectionDraftBundle@v1",
    ]
    assert [row["operation"] for row in web_calls] == ["search", "fetch", "fetch"]
    assert all(row["provider"] != "fake" for row in provider_calls)

    # Canonical binding and all three markers come from the real registry/config.
    sys.path.insert(0, str(BACKEND))
    from app.agents.a2_fields import resolve_field_config, skill_id_for
    from app.registry import get_registry

    registry = get_registry()
    config = resolve_field_config(local_harness.FIELD_ID)
    questions = registry.mandatory_questions(local_harness.FIELD_ID)
    markers = tuple(item.label_or_question.split(maxsplit=1)[0] for item in questions)
    assert local_harness.FIELD_ID == "VC.BUSINESS_TARGETS_MODEL.EDITOR"
    assert local_harness.MANDATORY_FIELD_ID == "VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1"
    assert registry.portal_fields[local_harness.MANDATORY_FIELD_ID].label_or_question == (
        "3.1 Describe the business targets and the business model"
    )
    assert skill_id_for(local_harness.FIELD_ID, "3.1") == "a2.value_creation_3_1"
    assert config is not None and markers == config.mandatory_markers == ("3.1", "3.2", "3.3")

    # Every user-impacting operation is observed through the in-process HTTP/BFF
    # transport. The route assertions intentionally span both child processes.
    projects = _http(trace, "POST", r"^/api/v1/projects$")
    assert len(projects) == 3
    assert len(_http(trace, "POST", r"/sources/text$")) == 3
    assert len(_http(trace, "POST", r"/projects/[^/]+/imports$")) == 3
    assert len(_http(trace, "POST", r"/imports/[^/]+/decision$")) == 3
    assert len(_http(trace, "PUT", r"/primary-application$")) == 3
    assert len(_http(trace, "POST", r"/projects/[^/]+/runs$")) == 3
    assert _http(trace, "PUT", r"/research-brief$")
    assert _http(trace, "POST", r"/queries/plan$")
    assert _http(trace, "POST", r"/search-query-approvals/[^/]+/approve$")
    assert _http(trace, "POST", r"/research-briefs/[^/]+/run$")
    imports = _http(trace, "POST", r"/research-results/[^/]+/import$")
    assert len(imports) == 2
    passages = _http(trace, "GET", r"/research-results/[^/]+/anchor-passages$")
    assert len(passages) == 4  # two in prepare, same exact two after process reload
    assert len(_http(trace, "POST", r"/research-results/[^/]+/review$")) == 2
    anchors = _http(trace, "POST", r"/research-results/[^/]+/external-anchors$")
    assert len(anchors) == 2
    market_create = _http(trace, "POST", r"/projects/[^/]+/market-comparisons$")
    market_read = _http(trace, "GET", r"/market-comparisons/[^/]+$")
    assert len(market_create) == len(market_read) == 1
    redrafts = _http(trace, "POST", r"/redrafts$")
    assert len(redrafts) == 3
    suggestion_reads = _http(trace, "GET", r"/suggestions$")
    assert len(suggestion_reads) >= 2
    accept_calls = _http(trace, "POST", r"/suggestions/[^/]+/accept$")
    assert len(accept_calls) == 2
    version_reads = _http(trace, "GET", r"/fields/[^/]+/versions/[^/]+$")
    assert len(version_reads) == 2

    # Cleanup is part of resume, not test teardown.
    assert not (work_root / "sessions" / session_id).exists()
    assert not list(work_root.rglob("phase2.db"))
    assert not list(work_root.rglob("sources"))
    assert not list(work_root.rglob("checkpoints.db"))
    assert not list(work_root.rglob("exports"))

    smoke_report = (work_root / "reports" / "LIVE_LLM_SMOKE_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "LIVE-02A" in smoke_report and "LIVE-02B" in smoke_report and "LIVE-02C" in smoke_report
    assert "request_count: `6`" in smoke_report
    assert "fake_fallback_observed: `no`" in smoke_report
    assert SNIPPET_SENTINEL not in smoke_report
    active_match = re.search(r"active_execution_seconds: `([0-9.]+)`", smoke_report)
    assert active_match
    active_seconds = float(active_match.group(1))
    assert active_seconds <= prepare_seconds + resume_seconds + 1.0

    # The full reservation blocks an unplanned repair from displacing a
    # mandatory case; an unknown price also fails closed.
    all_calls, _, _ = local_harness._planned_calls(type("S", (), {
        "agent_model_gpt_56_terra_id": "gpt-5.6-terra",
        "agent_model_claude_sonnet_5_id": "claude-sonnet-5",
        "a1_context_char_budget": 24000,
    })())
    assert [item.label for item in all_calls] == [
        "a2_preflight", "live_02a", "market_preflight",
        "market_comparison", "live_02b", "live_02c",
    ]
    full_ledger = local_harness.BudgetLedger(planned=all_calls)
    with pytest.raises(
        local_harness.HarnessFailure,
        match="live_acceptance_incomplete_budget_exhausted",
    ):
        local_harness._assert_budget_before_call(
            full_ledger, label="repair", provider="openai_direct",
            model_id="gpt-5.6-terra", prompt="repair", max_output_tokens=4096,
            settings=type("Prices", (), {"agent_model_pricing_chf_per_million": {}})(),
        )
    with pytest.raises(local_harness.HarnessFailure, match="unknown_price"):
        local_harness._assert_budget_before_call(
            local_harness.BudgetLedger(planned=[]), label="unknown",
            provider="openai_direct", model_id="unpriced",
            prompt="x", max_output_tokens=1,
            settings=type("NoPrices", (), {
                "agent_model_pricing_chf_per_million": {}
            })(),
        )

    evidence = {
        "review_session_id": session_id,
        "state_hash": state_hash,
        "quote_hashes": quote_hashes,
        "source_version_ids": sorted(source_versions),
        "project_ids": sorted({_artifact(row, "project_id") for row in projects}),
        "research_brief_id": _artifact(_http(trace, "PUT", r"/research-brief$")[0], "research_brief_id"),
        "approval_id": session_payload["research"]["approval_id"],
        "research_task_id": session_payload["research"]["task_id"],
        "source_ids": sorted(_artifact(row, "source_id") for row in imports),
        "anchor_ids": sorted(_artifact(row, "anchor_id") for row in anchors),
        "market_comparison_id": _artifact(market_create[0], "resource_id"),
        "suggestion_ids": sorted({
            item for row in suggestion_reads
            for item in row.get("artifact_ids", {}).get("suggestion_id", [])
        }),
        "accepted_draft_version_id": _artifact(accept_calls[0], "draft_version_id"),
        "original_draft_version_id": session_payload["cases"]["live_02b"]["base_version_id"],
        "provider_call_count": len(provider_calls),
        "web_call_count": len(web_calls),
        "active_execution_seconds": active_seconds,
        "human_wait_seconds": human_wait_seconds,
        "http_request_count": len([row for row in trace if row.get("kind") == "http"]),
        "route_artifact_ids": {
            "projects": _route_artifact_ids(trace, "POST", r"^/api/v1/projects$"),
            "primary_sources": _route_artifact_ids(trace, "POST", r"/sources/text$"),
            "imports": _route_artifact_ids(trace, "POST", r"/projects/[^/]+/imports$"),
            "import_decisions": _route_artifact_ids(trace, "POST", r"/imports/[^/]+/decision$"),
            "primary_application": _route_artifact_ids(trace, "PUT", r"/primary-application$"),
            "runs": _route_artifact_ids(trace, "POST", r"/projects/[^/]+/runs$"),
            "research_brief": _route_artifact_ids(trace, "PUT", r"/research-brief$"),
            "query_plan": _route_artifact_ids(trace, "POST", r"/queries/plan$"),
            "query_approval": _route_artifact_ids(
                trace, "POST", r"/search-query-approvals/[^/]+/approve$"
            ),
            "research_run": _route_artifact_ids(trace, "POST", r"/research-briefs/[^/]+/run$"),
            "source_imports": _route_artifact_ids(trace, "POST", r"/research-results/[^/]+/import$"),
            "anchor_passages": _route_artifact_ids(trace, "GET", r"/research-results/[^/]+/anchor-passages$"),
            "content_reviews": _route_artifact_ids(trace, "POST", r"/research-results/[^/]+/review$"),
            "external_anchors": _route_artifact_ids(trace, "POST", r"/research-results/[^/]+/external-anchors$"),
            "market_create": _route_artifact_ids(trace, "POST", r"/market-comparisons$"),
            "market_read": _route_artifact_ids(trace, "GET", r"/market-comparisons/[^/]+$"),
            "redrafts": _route_artifact_ids(trace, "POST", r"/redrafts$"),
            "suggestion_reads": _route_artifact_ids(trace, "GET", r"/suggestions$"),
            "accepts": _route_artifact_ids(trace, "POST", r"/suggestions/[^/]+/accept$"),
            "draft_version_reads": _route_artifact_ids(
                trace, "GET", r"/fields/[^/]+/versions/[^/]+$"
            ),
        },
    }
    evidence_path = os.environ.get("PHASE2_DRY_RUN_EVIDENCE_PATH")
    if evidence_path:
        Path(evidence_path).write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )

    # Test teardown only removes the bounded local review artifact and trace.
    shutil.rmtree(work_root, ignore_errors=False)
