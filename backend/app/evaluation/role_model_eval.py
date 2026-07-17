"""Rollen-Modell-Evaluation (A1/A2/A3) — Harness, Blindung, Ingest, Aggregation.

Vergleicht Kandidaten-Modellrouten je Agentenrolle über die PRODUKTIVEN Pfade
(``gateway.invoke`` mit Produktiv-Profilen/Prompt-Assets, ``run_integrated_draft``,
``run_a3_evidence_consistency``) auf den synthetischen Fällen F1/F2 (Dev) und H1
(Holdout). Keine parallele Provider-Logik — der Kandidat wird ausschliesslich über
eine abgeleitete In-Memory-Registry (``role_routes[role].primary=<kandidat>``,
``fallback=None`` ⇒ kein stiller Fallback) und den bestehenden Resolver-Seam
erzwungen; die Contract-YAML bleibt unangetastet.

Manual Mode — reale Calls nur wenn ALLE Guards erfüllt sind (``guard_refusal``,
wiederverwendet aus EVAL.2): ``CI`` nicht gesetzt, ``RUN_REAL_PROVIDER_SMOKE=true``,
``AI_EVAL_MODE=real``, API-Key vorhanden; ``evaluation_only``-Routen zusätzlich
``AGENT_QUALITY_CEILING_ENABLED=true``. Je Kandidaten-Route ist ein bestandener
Route-Preflight Pflicht (Gateway erzwingt ``route_preflight_passed``).

``--fake``-Dry-Run: injizierte deterministische Fake-Adapter durch das ECHTE
Gateway (Live-Routing, Gates, Blindung, Ingest, Aggregation) — kostenlos, ohne
Keys; Samples sind unübersehbar als ``execution="fake_dryrun"`` markiert und
werden nie als durchgeführte Live-Evaluation berichtet.

Holdout-Disziplin: H1 verlangt ``allow_holdout=True``; der Prompt-Hash wird je
Lauf manifestiert und muss zwischen Dev- und Holdout-Läufen identisch sein.

Rohe Modelloutputs bleiben NUR im gitignorierten
``backend/var/evaluation/role_model_eval/`` (backend/.gitignore: ``var/``);
Summaries enthalten ausschliesslich Status, Zählwerte, Metriken, Modell-IDs und
Hashes. Die blinde Human-Rubrik wird nie KI-bewertet (Ingest ausgefüllter CSV).
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import random
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from app.agents import context as a1_context
from app.agents import field_drafting
from app.agents import gateway
from app.agents.a2_fields import resolve_field_config
from app.agents.critic_review import run_a3_evidence_consistency
from app.agents.prompt_assets import prompt_version_for
from app.agents.providers import FakeProvider
from app.agents.providers.anthropic import (
    NATIVE_STRUCTURED_OUTPUT,
    AnthropicProvider,
)
from app.agents.providers.base import ProviderRequest
from app.agents.providers.openai import OpenAIProvider
from app.agents.registry import AgentRegistry, get_agent_registry
from app.config.settings import get_settings
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    DraftVersion,
    EvidenceAnchor,
    PortalFieldDraft,
    ProcessingConfirmation,
    Project,
    ResearchResult,
    ResearchTask,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
    UsageRecord,
)
from app.evaluation import preflight
from app.evaluation import role_model_scoring as scoring
from app.evaluation.field_real_smoke import _CountingAdapter
from app.evaluation.model_quality import _expected_markers
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.real_smoke import guard_refusal
from app.evaluation.usage_smoke import ACTOR, WS, SmokeFailure, _ensure_base_rows
from app.integrated_draft.runner import run_integrated_draft
from app.runs.cloud_policy import REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION

ROLE_IDS = {
    "a1": "A1_FACT_EVIDENCE_ANALYST",
    "a2": "A2_INNOSUISSE_PROPOSAL_WRITER",
    "a3": "A3_INNOSUISSE_CRITICAL_REVIEWER",
}
DEFAULT_CANDIDATES = {
    "a1": ("openai_gpt_56_luna_candidate", "anthropic_haiku_45_candidate"),
    "a2": (
        "anthropic_sonnet_5_candidate",
        "openai_gpt_56_terra_candidate",
        # Quality-Ceiling (evaluation_only; braucht AGENT_QUALITY_CEILING_ENABLED):
        "anthropic_fable_5_candidate",
        "openai_gpt_56_sol_candidate",
    ),
    "a3": (
        "openai_gpt_56_terra_candidate",
        "anthropic_sonnet_5_candidate",
        "openai_gpt_56_sol_candidate",
    ),
}
DEV_CASES = ("F1", "F2")
HOLDOUT_CASES = ("H1",)

A1_PROFILE = "A1.project_fact_extraction"
A3_SCOPE_FIELDS = (
    "SOL.INNOVATION_SOLUTION.EDITOR",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR",
)
_FIELD_NAME = {
    "SOL.INNOVATION_SOLUTION.EDITOR": "Innovation & Lösung",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": "Business-Ziele & Geschäftsmodell",
}

# Absichtlich fehlerhafte A3-Testvariante: injizierte, unbelegte Zahlen. Ein
# Kandidat, der diese Schwäche NICHT meldet, erzeugt ein False-Consensus-Event.
FLAW_SENTENCE = (
    "\n\nDer erwartete Marktanteil liegt bei 47 Prozent, entsprechend "
    "CHF 9'750'000 Umsatz im ersten Jahr nach Projektende."
)
FLAW_KEYWORDS = ("Marktanteil", "47", "9'750'000", "Umsatz")

_EXECUTION_REAL = "real"
_EXECUTION_FAKE = "fake_dryrun"


class EvalRefusal(RuntimeError):
    """Guard-/Konfigurationsverweigerung — nie ein stiller Fallback."""


def default_results_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "var" / "evaluation" / "role_model_eval"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Prompt-Freeze ------------------------------------------------------------


def prompt_fingerprint() -> str:
    """sha256 über alle versionierten Prompt-Assets (role/skill/legacy) — friert
    die Promptversion während eines Vergleichslaufs ein (Dev == Holdout)."""
    base = Path(gateway.__file__).resolve().parent
    digest = hashlib.sha256()
    for sub in ("role_prompts", "skill_prompts", "prompts"):
        directory = base / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            digest.update(f"{sub}/{path.name}\n".encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


# --- Registry-Ableitung + Resolver ---------------------------------------------


def provider_of(route) -> str:
    return {"openai_direct": "openai", "anthropic_direct": "anthropic"}.get(
        route.provider, route.provider
    )


def derived_registry(role: str, candidate_key: str) -> AgentRegistry:
    """In-Memory-Kopie: Kandidat als einzige Route der Rolle (kein Fallback).

    Budgets (``max_cost_chf``/``max_latency_seconds``) der Original-RoleRoute
    bleiben erhalten — die Kostenbremse gilt auch für Kandidaten.
    """
    base = get_agent_registry()
    role_id = ROLE_IDS[role]
    base.route(candidate_key)  # fail-closed bei unbekannter Route
    base_role = (base.role_routes or {})[role_id]
    patched = dataclasses.replace(
        base_role, primary=candidate_key, fallback=None, comparison=None
    )
    return AgentRegistry(
        base.model_routes, base.agents, base.profiles,
        {**(base.role_routes or {}), role_id: patched},
    )


def _forcing_resolver(route, *, limit: int, fake_adapter=None):
    """(resolver, proxy): liefert den gezählten Adapter NUR für die Kandidaten-
    Route (``route.key``-Match) — jede andere Route bleibt None (kein
    Cross-Kandidat-Fallback)."""
    inner = fake_adapter or (
        OpenAIProvider() if route.provider == "openai_direct" else AnthropicProvider()
    )
    proxy = _CountingAdapter(inner, limit=limit, adapter_name=route.provider)
    if fake_adapter is not None:
        proxy._hermetic_test_model_id = "role-eval-fake"
    return (lambda r: proxy if r.key == route.key else None), proxy


# --- Guards + Preflight ---------------------------------------------------------


def guard_for_candidate(route, *, env, settings, fake: bool) -> str | None:
    """Refusal-Grund oder None. Fake-Dry-Run braucht keine Keys/Preise."""
    if fake:
        return None
    refusal = guard_refusal(
        provider=provider_of(route), env=env, settings=settings
    )
    if refusal:
        return refusal
    if route.evaluation_only and not getattr(
        settings, "agent_quality_ceiling_enabled", False
    ):
        return (
            f"Route {route.key} ist evaluation_only — "
            "AGENT_QUALITY_CEILING_ENABLED=true fehlt"
        )
    if not route.requested_model_id(settings):
        return (
            f"Modell-ID für Route {route.key} nicht aufgelöst "
            f"(env {route.model_setting or 'model_id'} leer)"
        )
    return None


def ensure_route_preflight(db, route_key: str, *, fake: bool) -> str:
    """Frischer (oder gecachter) Route-Preflight in der Harness-DB — das Gateway
    verlangt ``route_preflight_passed`` je Kandidaten-Route."""
    if fake:
        return "skipped_fake"
    if preflight.route_preflight_passed(db, route_key):
        return "pass_cached"
    result = preflight.preflight_route(route_key)
    preflight.persist_route_preflight(db, result, triggered_by="role_model_eval")
    db.commit()
    if result.status != preflight.PASS:
        raise EvalRefusal(
            f"Preflight für Route {route_key} nicht bestanden "
            f"({result.status}/{result.error_class or '—'})"
        )
    return "pass_fresh"


# --- Fake-Payloads (Dry-Run) -----------------------------------------------------


def _fake_a1_payload(gold: scoring.CaseGold, *, id_suffix: str = "") -> dict:
    facts = []
    for i, g in enumerate(gold.gold_facts, start=1):
        statement = " ".join(g.get("keywords", [])[:3]) or g.get("gold_id", "")
        if g.get("normalized_value"):
            statement = f"{statement}: {g['normalized_value']}"
        facts.append({
            "fact_id": f"fake-{i:03d}",
            "statement": statement,
            "fact_type": g.get("fact_type"),
            "normalized_value": g.get("normalized_value"),
            "target_ref": g.get("target_ref"),
            "source_fragment_ids": [
                f"{fid}{id_suffix}" for fid in list(g.get("fragment_ids", []))[:1]
            ],
        })
    missing = [
        {"target_ref": m["target_ref"], "description": " ".join(m["keywords"][:3])}
        for m in gold.gold_missing
    ]
    return {"facts": facts, "conflicts": [], "missing_information": missing}


def _fake_a2_adapters(gold: scoring.CaseGold) -> dict[str, object]:
    """Ein schema-valider Fake je A2-Feld (Registry-Marker-erhaltender fake_text
    plus Pflichtbegriff des Falls)."""
    adapters: dict[str, object] = {}
    from app.agents.a2_fields import A2_FIELD_PROFILES

    for field_id in A2_FIELD_PROFILES:
        config = resolve_field_config(field_id)
        if config is None:
            continue
        text = config.fake_text
        if gold.required_terms:
            text = f"{gold.required_terms[0]}: {text}"
        bundle = {
            "draft_candidates": [{
                "field_id": field_id,
                "suggested_text": text[: config.char_limit],
                "rationale": "Dry-Run-Fake (role_model_eval).",
                "evidence_anchor_ids": [],
                "open_issue_ids": [],
            }],
            "placeholders": [],
            "field_level_warnings": [],
        }
        adapters[field_id] = FakeProvider(raw_output=json.dumps(bundle))
    return adapters


def _fake_a3_payload(gold: scoring.CaseGold, *, flawed: bool) -> dict:
    # Produktions-Validierung verlangt gültige Registry-Marker als target_section
    # (4.5 ist nur ein Gold-Präfix für 4.5.1–4.5.4).
    section_fix = {"4.5": "4.5.2"}
    findings = []
    for g in gold.gold_findings:
        if not g.get("a3_scope"):
            continue
        findings.append({
            "origin_profile_id": "A3.evidence_consistency",
            "severity": "warning",
            "status": "open",
            "field_id": g["field_id"],
            "target_section": section_fix.get(g["target_section"], g["target_section"]),
            "description": " ".join(g["keywords"][:4]),
            "suggested_improvement": "Angabe belegen oder als offen kennzeichnen.",
            "recommended_next_action": "Beleg ergänzen.",
        })
    if flawed:
        findings.append({
            "origin_profile_id": "A3.evidence_consistency",
            "severity": "warning",
            "status": "open",
            "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            "target_section": "3.1",
            "description": (
                "Der Marktanteilsclaim von 47 Prozent und der Umsatz sind unbelegt."
            ),
            "suggested_improvement": "Unbelegte Zahlen entfernen oder belegen.",
            "recommended_next_action": "Quelle ergänzen oder Zahl streichen.",
        })
    return {
        "findings": findings,
        "profile_summaries": [{
            "profile_id": "A3.evidence_consistency",
            "finding_count": len(findings),
        }],
        "overall_limitations": [],
    }


# --- Gemeinsames Seeding ----------------------------------------------------------


def _classification() -> dict:
    return {
        "sensitivity": "public",
        "origin": "synthetic",
        "processing_mode": "cloud_assisted",
        "web_research_mode": "off",
        "nda_applies": False,
    }


def _seed_project(db, gold: scoring.CaseGold, tag: str) -> Project:
    project = Project(
        project_id=f"rme-{tag}-{uuid.uuid4().hex[:8]}",
        workspace_id=WS,
        title=gold.title_de,
        description=(
            f"Synthetischer Evaluationsfall {gold.case_id} "
            "(Rollen-Modell-Evaluation, D0/public)."
        ),
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=_classification(),
        created_by=ACTOR,
        status="draft",
    )
    db.add(project)
    db.flush()
    return project


def _seed_run(db, project: Project, *, stage: str, confirm: bool) -> AnalysisRun:
    run = AnalysisRun(
        run_id=f"rme-run-{uuid.uuid4().hex[:8]}",
        project_id=project.project_id,
        workspace_id=WS,
        created_by=ACTOR,
        status="running",
        current_stage=stage,
        progress_percent=50,
        processing_mode="cloud_assisted",
        effective_data_classification=dict(project.data_classification or {}),
        snapshot_versions={},
    )
    db.add(run)
    if confirm:
        db.add(ProcessingConfirmation(
            confirmation_id=f"rme-confirm-{uuid.uuid4().hex[:8]}",
            project_id=project.project_id, workspace_id=WS, created_by=ACTOR,
            status="used", processing_mode="cloud_assisted",
            source_version_ids=[], accepted_policy_version="1.1.0",
            purpose="Explizit freigegebener synthetischer Evaluationslauf",
            provider_route_class="direct_eval",
            confirmation_text_version=REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION,
            data_classification_shown=dict(project.data_classification or {}),
            expires_after_one_run=True, used_by_run_id=run.run_id,
            decided_at=datetime.now(timezone.utc),
        ))
    db.flush()
    return run


def _seed_snapshot_fragments(db, run: AnalysisRun, fragments: list[dict], tag: str):
    """Fall-Fragmente als eingefrorenen RunSourceSnapshot seeden (A1-Kontext)."""
    cls = _classification()
    doc_id, sv_id = f"rme-{tag}-doc", f"rme-{tag}-sv"
    full_text = scoring.fragments_corpus(fragments)
    db.add(SourceDocument(
        source_id=doc_id, project_id=run.project_id, workspace_id=WS,
        name="Antrag (synthetischer Evaluationsfall).pdf", type="pdf",
        status="processed", data_classification=cls, created_by=ACTOR,
    ))
    db.add(SourceVersion(
        source_version_id=sv_id, source_document_id=doc_id, version_number=1,
        original_content_hash=hashlib.sha256(full_text.encode()).hexdigest(),
        normalized_content_hash=hashlib.sha256(full_text.encode()).hexdigest(),
        normalized_text=full_text, parser_version="parser-1",
        normalizer_version="normalizer-1", chunker_version="chunker-1",
        processing_status="processed", data_classification=cls,
        storage_ref="0" * 32, original_filename="eval_case.pdf",
        byte_size=len(full_text), mime_type="application/pdf",
    ))
    offset = 0
    for ordinal, frag in enumerate(fragments):
        text = frag["text"]
        # fragment_id ist DB-weit unique — je Lauf namespacen («@tag»); vor dem
        # Gold-Scoring wird der Suffix wieder entfernt (_canonical_fragment_id).
        db.add(SourceFragment(
            fragment_id=f"{frag['fragment_id']}@{tag}", source_version_id=sv_id,
            ordinal=ordinal, original_text=text, normalized_text=text,
            start_offset=offset, end_offset=offset + len(text),
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        ))
        offset += len(text) + 2
    db.add(RunSourceSnapshot(
        id=f"rme-{tag}-snap", run_id=run.run_id,
        source_version_id=sv_id, source_id=doc_id,
    ))
    db.flush()


def _canonical_fragment_id(fragment_id: str) -> str:
    return fragment_id.split("@", 1)[0]


def _usage_for_invocation(db, invocation_id: str | None) -> dict:
    out = {
        "latency_ms": None, "input_tokens": None, "output_tokens": None,
        "cost_chf": None, "cost_status": None,
        "actual_model_id": None, "actual_adapter": None, "generation_kind": None,
        "termination_reason": None, "attempts": None,
    }
    if not invocation_id:
        return out
    inv = db.get(AgentInvocation, invocation_id)
    if inv is None:
        return out
    out["latency_ms"] = inv.latency_ms
    meta = inv.context_meta or {}
    out["actual_adapter"] = meta.get("actual_adapter")
    out["generation_kind"] = meta.get("generation_kind")
    out["actual_model_id"] = getattr(inv, "actual_model_id", None)
    out["termination_reason"] = getattr(inv, "termination_reason", None)
    if inv.usage_record_id:
        rec = db.get(UsageRecord, inv.usage_record_id)
        if rec is not None:
            out["input_tokens"] = rec.input_tokens
            out["output_tokens"] = rec.output_tokens
            out["cost_chf"] = rec.cost_chf
            out["cost_status"] = rec.cost_status
        return out
    # Fehlerpfad: inv.usage_record_id bleibt leer, aber das Gateway metert
    # JEDEN beantworteten Versuch (AgentInvocationAttempt.usage_record_id) —
    # Tokens/Kosten werden hier über die Versuche aggregiert, damit auch
    # truncated/schema_invalid-Läufe nie als «kostenlos» erscheinen.
    from app.db.models import AgentInvocationAttempt

    attempts = list(
        db.query(AgentInvocationAttempt)
        .filter(AgentInvocationAttempt.invocation_id == invocation_id)
        .order_by(AgentInvocationAttempt.attempt_index)
    )
    out["attempts"] = len(attempts) or None
    input_t = output_t = 0
    cost = 0.0
    statuses: set[str] = set()
    metered = False
    for attempt in attempts:
        if attempt.actual_model_id and not out["actual_model_id"]:
            out["actual_model_id"] = attempt.actual_model_id
        if not attempt.usage_record_id:
            continue
        rec = db.get(UsageRecord, attempt.usage_record_id)
        if rec is None:
            continue
        metered = True
        input_t += rec.input_tokens or 0
        output_t += rec.output_tokens or 0
        if rec.cost_chf is not None:
            cost += rec.cost_chf
        statuses.add(rec.cost_status or "unknown_price")
    if metered:
        out["input_tokens"] = input_t
        out["output_tokens"] = output_t
        out["cost_status"] = (
            "priced" if statuses == {"priced"} else "/".join(sorted(statuses))
        )
        out["cost_chf"] = cost if statuses == {"priced"} else (cost or None)
    return out


def _silent_fake(usage: dict, *, execution: str) -> bool:
    """Stiller Fake-Wechsel: nur in REAL-Läufen relevant — jede gewertete
    Invocation muss von einem echten Direkt-Adapter bedient worden sein."""
    if execution != _EXECUTION_REAL:
        return False
    return not (
        usage.get("actual_adapter") in ("openai_direct", "anthropic_direct")
        and usage.get("generation_kind") == "model_generated"
    )


# --- A1-Sample ---------------------------------------------------------------------


def run_a1_sample(
    db, *, case_id: str, candidate_key: str, rep: int, fake: bool,
    cases_dir: Path | None = None,
) -> dict:
    gold = scoring.load_case_gold(case_id, cases_dir)
    fragments = scoring.load_case_fragments(case_id, cases_dir)
    registry = derived_registry("a1", candidate_key)
    route = registry.route(candidate_key)
    profile = registry.profile(A1_PROFILE)
    limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
    tag = f"a1-{case_id.lower()}-r{rep}-{uuid.uuid4().hex[:6]}"
    fake_adapter = (
        FakeProvider(
            raw_output=json.dumps(_fake_a1_payload(gold, id_suffix=f"@{tag}"))
        )
        if fake else None
    )
    resolver, proxy = _forcing_resolver(route, limit=limit, fake_adapter=fake_adapter)

    _ensure_base_rows(db)
    project = _seed_project(db, gold, tag)
    run = _seed_run(db, project, stage="extract_facts_and_map_evidence", confirm=True)
    _seed_snapshot_fragments(db, run, fragments, tag)

    max_fragments = int(profile.invocation_limits.get("max_input_fragments", 80))
    ctx = a1_context.assemble_a1_context(db, run, max_fragments=max_fragments)
    request = gateway.ModelRequest(
        profile_id=A1_PROFILE,
        workspace_id=WS,
        input_payload={
            "run_id": run.run_id,
            "fragment_ids": ctx.selected_fragment_ids,
            "active_requirement_ids": [d["requirement_id"] for d in ctx.requirement_defs],
            "active_field_ids": [d["field_id"] for d in ctx.field_defs],
            "data_classification": {
                "sensitivity": "public", "origin": "synthetic",
                "processing_mode": "cloud_assisted",
            },
        },
        classification=dict(run.effective_data_classification or {}),
        processing_mode="cloud_assisted",
        run_id=run.run_id,
        project_id=project.project_id,
        allowed_fragment_ids=frozenset(ctx.selected_fragment_ids),
        # Eval-only: bewusste Owner-Freigabe über die CLI-Guards (wie EVAL.1/2) —
        # der produktive A1-Orchestrator bleibt bei run_confirmation=False.
        run_confirmation=True,
        prompt_version=prompt_version_for(A1_PROFILE),
        context_text=ctx.context_text,
        context_hash=ctx.context_hash,
        context_meta=ctx.meta,
        skill_id="a1.fact_extraction",
    )
    with mock.patch("app.agents.gateway.get_agent_registry", return_value=registry):
        result = gateway.invoke(
            db, request, provider_resolver=resolver, registry=registry
        )
    db.commit()

    seeded_ids = {f"{frag['fragment_id']}@{tag}" for frag in fragments}
    sample = {
        "role": "a1", "candidate": candidate_key, "case": case_id, "rep": rep,
        "execution": _EXECUTION_FAKE if fake else _EXECUTION_REAL,
        "requested_model_id": route.requested_model_id(get_settings()),
        "llm_calls": proxy.calls,
    }
    if isinstance(result, gateway.SafeFailure):
        usage = _usage_for_invocation(db, result.invocation_id)
        sample.update({
            "status": result.status, "reason": result.error_code,
            # Konkreter Blockgrund (z. B. provider_outage/provider_output_
            # truncated) — Whitelist-Code, nie Rohinhalt.
            "safe_detail": getattr(result, "safe_detail", None),
            "schema_valid": False, "scores": None, "usage": usage,
            "fatal": [], "silent_fake": _silent_fake(usage, execution=sample["execution"]),
            "raw": {"raw_outputs": list(proxy.raw_outputs)},
        })
        return sample

    payload = result.output.model_dump()
    usage = _usage_for_invocation(db, result.invocation_id)
    violations = sum(
        1 for fact in payload.get("facts", [])
        if any(fid not in seeded_ids for fid in fact.get("source_fragment_ids", []))
    )
    # Namespace-Suffix («@tag») entfernen — der Goldstandard kennt die
    # kanonischen Fragment-IDs des Falls.
    for fact in payload.get("facts", []):
        fact["source_fragment_ids"] = [
            _canonical_fragment_id(fid)
            for fid in fact.get("source_fragment_ids", [])
        ]
    silent = _silent_fake(usage, execution=sample["execution"])
    sample.update({
        "status": "succeeded", "schema_valid": True,
        "scores": scoring.score_a1(payload, gold),
        "evidence_ref_violations": violations,
        "silent_fake": silent,
        "fatal": [
            {"name": "fatal_nonexistent_evidence_id",
             "status": "pass" if violations == 0 else "fail",
             "detail": f"{violations} ungültige Fragment-Referenz(en).",
             "requires_human_adjudication": False},
            {"name": "fatal_silent_fake_switch",
             "status": "fail" if silent else "pass",
             "detail": "Adapter-Selbstauskunft + generation_kind geprüft.",
             "requires_human_adjudication": False},
        ],
        "usage": usage,
        "raw": {"output": payload, "raw_outputs": list(proxy.raw_outputs)},
    })
    return sample


# --- A2-Sample ---------------------------------------------------------------------


# ``_a2_input_corpus`` ist am 2026-07-17 ersatzlos entfallen (Owner Block 4):
# ein eigener Evaluations-Korpus ist eine zweite Wahrheit neben dem, was das
# Modell tatsächlich gesehen hat — er hat bekannte Fixture-Angaben als
# Erfindung markiert (und hätte unsichtbare Angaben als belegt durchgelassen).
# Erlaubt-Basis ist ausschliesslich das AllowedFactsManifest des realen
# Requests (``_a2_manifest_and_language`` / ``_a2_field_manifest``).


_ALLOWED_SOURCES = (
    "https://research.example.org/r/1",
    "Öffentliche Marktquelle: Anbieter & Wettbewerber",
    "Öffentliche Partnerquelle: Forschungslabor Schweiz",
)
_MARKET_PURPOSE = "market_comparison"
_PARTNER_PURPOSE = "partner_research_org_topic"


def _seed_research_context(db, field_id: str, project: Project) -> None:
    """Advisory Research-Kontext für VC/SOL (identisch je Kandidat — gleiche
    Quellenlage für jeden Vergleichslauf)."""
    purpose_title = {
        "VC.BUSINESS_TARGETS_MODEL.EDITOR": (
            _MARKET_PURPOSE, "Öffentliche Marktquelle: Anbieter & Wettbewerber"
        ),
        "SOL.INNOVATION_SOLUTION.EDITOR": (
            _PARTNER_PURPOSE, "Öffentliche Partnerquelle: Forschungslabor Schweiz"
        ),
    }.get(field_id)
    if purpose_title is None:
        return
    purpose, title = purpose_title
    task_id = "rme-rt-" + uuid.uuid4().hex[:8]
    db.add(ResearchTask(
        research_task_id=task_id, project_id=project.project_id,
        workspace_id=project.workspace_id, created_by=ACTOR, purpose=purpose,
        subject_type="topic", query_text="öffentliche Themen-/Organisationssuche",
        normalized_query_hash="qh", status="succeeded",
    ))
    db.add(ResearchResult(
        result_id="rme-rr-" + uuid.uuid4().hex[:8], research_task_id=task_id,
        workspace_id=project.workspace_id,
        source_url="https://research.example.org/r/1",
        title=title, snippet="Öffentlich zugänglicher Auszug (Snippet ist kein Beleg).",
        provider_rank=1, status="candidate",
    ))
    db.flush()


def _a2_field_manifest(db, base_project_id: str, field_id: str):
    """Erlaubt-Basis + Sprache eines Ganzfeld-Laufs (run_integrated_draft).

    Der Runner klont je Feld ein Kindprojekt mit deterministischer ID und genau
    einem Run — dessen Kontext montieren wir identisch nach (reiner Lesevorgang,
    kein Provider-Call), damit die Evaluation exakt gegen das prüft, was das
    Modell gesehen hat.
    """
    from app.agents import field_drafting_context as a2_context
    from app.integrated_draft.runner import _slug

    config = resolve_field_config(field_id)
    child_id = f"{base_project_id}-{_slug(field_id)}"[:120]
    run = db.scalar(
        select(AnalysisRun).where(AnalysisRun.project_id == child_id)
    )
    if run is None:
        raise SmokeFailure(
            f"Kein Run für {field_id} ({child_id}) — Erlaubt-Basis nicht "
            "rekonstruierbar; keine Bewertung gegen einen Ersatzkorpus."
        )
    ctx = a2_context.assemble_a2_context(
        db, run, field_id=field_id, profile_id=config.profile_id,
        section_markers=config.mandatory_markers,
    )
    manifest = a2_context.build_allowed_facts(
        ctx, a2_context.build_input_payload(ctx, run.run_id)
    )
    return manifest, ctx.language


def _evaluate_a2_field_item(
    db, item, *, gold: scoring.CaseGold, manifest, expected_language: str,
    proxy, route, execution: str,
) -> tuple[dict, dict]:
    """Gates/Fatals/DQs/Usage eines A2-FieldDraftItem — gemeinsame Auswertung
    für den Voll-Benchmark (run_integrated_draft) und den Live-Pilot."""
    editor_markers = {
        field_id: _expected_markers(field_id)
        for field_id in A3_SCOPE_FIELDS
    }
    config = resolve_field_config(item.field_id)
    text = item.suggestion_text or ""
    schema_valid = item.status in ("generated", "missing_inputs")
    foreign = tuple(
        marker for fid, markers in editor_markers.items()
        if fid != item.field_id for marker in markers
    )
    gates = scoring.a2_gate_results(
        text,
        schema_valid=schema_valid,
        required_terms=gold.required_terms,
        expected_markers=_expected_markers(item.field_id),
        char_limit=config.char_limit,
        manifest=manifest,
        expected_language=expected_language,
        missing_inputs_count=len(item.missing_inputs or []),
        human_review_required=bool(item.human_review_required),
        allowed_sources=_ALLOWED_SOURCES,
    )
    anchor_ids = list(
        (item.draft_proposal or {}).get("evidence_anchor_ids") or []
    )
    violations = sum(
        1 for anchor_id in anchor_ids
        if db.get(EvidenceAnchor, anchor_id) is None
    )
    usage = {
        "latency_ms": item.latency_ms,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "cost_chf": None,
        "cost_status": item.cost_status,
        "actual_adapter": route.provider if (proxy and proxy.calls) else None,
        "generation_kind": (item.generation_kind or None),
        "actual_model_id": item.model,
    }
    if item.usage_record_id:
        rec = db.get(UsageRecord, item.usage_record_id)
        if rec is not None:
            usage["cost_chf"] = rec.cost_chf
    silent = (
        execution == _EXECUTION_REAL
        and item.status == "generated"
        and (item.generation_kind or "") != "model_generated"
    )
    fatal = scoring.fatal_gate_results(
        text,
        manifest=manifest,
        allowed_sources=_ALLOWED_SOURCES,
        evidence_ref_violations=violations,
        silent_fake_detected=silent,
        foreign_markers=foreign,
    )
    evaluated = {
        "field_id": item.field_id,
        "status": item.status,
        "model": item.model,
        "gates": gates,
        "gates_passed": scoring.gates_passed(gates),
        "fatal": fatal,
        "fatal_candidate": scoring.fatal_candidate(fatal),
        "hard_dq": scoring.a2_hard_disqualifications(gates, fatal),
        "usage": usage,
        "missing_inputs_count": len(item.missing_inputs or []),
        "human_review_required": bool(item.human_review_required),
        "llm_calls": proxy.calls if proxy else 0,
    }
    raw = {
        "field_id": item.field_id,
        "suggestion_text": item.suggestion_text,
        "raw_outputs": list(proxy.raw_outputs) if proxy else [],
    }
    return evaluated, raw


def run_a2_sample(
    db, *, case_id: str, candidate_key: str, rep: int, fake: bool,
    cases_dir: Path | None = None,
) -> dict:
    gold = scoring.load_case_gold(case_id, cases_dir)
    fragments = scoring.load_case_fragments(case_id, cases_dir)
    registry = derived_registry("a2", candidate_key)
    route = registry.route(candidate_key)
    fake_adapters = _fake_a2_adapters(gold) if fake else None

    def resolver_for(field_id: str):
        config = resolve_field_config(field_id)
        profile = registry.profile(config.profile_id)
        limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
        resolver, proxy = _forcing_resolver(
            route, limit=limit,
            fake_adapter=(fake_adapters or {}).get(field_id),
        )
        proxies[field_id] = proxy
        return resolver

    proxies: dict[str, _CountingAdapter] = {}
    _ensure_base_rows(db)
    project = _seed_project(db, gold, f"a2-{case_id.lower()}-r{rep}")
    with mock.patch("app.agents.gateway.get_agent_registry", return_value=registry):
        package = run_integrated_draft(
            db, base_project=project, actor_user_id=ACTOR, case_id=case_id,
            provider_mode=provider_of(route), data_mode="synthetic_eval",
            resolver_for=resolver_for, seed_context=_seed_research_context,
            title_en=gold.title_en, real_eval_confirmation=True,
        )
    db.commit()

    if not fake and sum(p.calls for p in proxies.values()) == 0:
        raise SmokeFailure(
            "Kein einziger Provider-Call über die A2-Felder — Policy/"
            "Verfügbarkeit hat den gesamten Lauf blockiert."
        )

    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL
    fields_out, fields_raw = [], []
    for item in package.fields:
        if resolve_field_config(item.field_id) is None:
            continue  # deterministische NAME-Felder sind kein A2-LLM-Vergleich
        manifest, draft_language = _a2_field_manifest(
            db, project.project_id, item.field_id
        )
        expected_language, _source = scoring.resolve_expected_language(
            gold, draft_language=draft_language
        )
        evaluated, raw = _evaluate_a2_field_item(
            db, item, gold=gold, manifest=manifest,
            expected_language=expected_language,
            proxy=proxies.get(item.field_id), route=route, execution=execution,
        )
        fields_out.append(evaluated)
        fields_raw.append(raw)

    return {
        "role": "a2", "candidate": candidate_key, "case": case_id, "rep": rep,
        "execution": execution,
        "requested_model_id": route.requested_model_id(get_settings()),
        "status": "succeeded",
        "fields": fields_out,
        "usage_summary": package.usage_summary,
        "raw": {"fields": fields_raw},
    }


# --- A3-Sample ---------------------------------------------------------------------


def a3_draft_texts(fragments: list[dict]) -> dict[str, str]:
    """VC-/SOL-Feldtexte des Falls aus den eingefrorenen Fragmenten (Sektion 3/4)."""
    out: dict[str, str] = {}
    for frag in fragments:
        section = frag.get("section", "")
        if section.startswith("3 Value Creation"):
            out["VC.BUSINESS_TARGETS_MODEL.EDITOR"] = frag["text"]
        elif section.startswith("4 Solution"):
            out["SOL.INNOVATION_SOLUTION.EDITOR"] = frag["text"]
    missing = [f for f in A3_SCOPE_FIELDS if f not in out]
    if missing:
        raise scoring.GoldError(f"A3-Feldtexte fehlen in den Fragmenten: {missing}")
    return out


def _seed_a3_drafts(db, run: AnalysisRun, drafts: dict[str, str]) -> None:
    from app.registry import get_registry

    for field_id, text in drafts.items():
        draft_id = "rme-draft-" + uuid.uuid4().hex[:8]
        version_id = "rme-ver-" + uuid.uuid4().hex[:8]
        db.add(DraftVersion(
            draft_version_id=version_id, draft_id=draft_id, text=text,
            character_count=len(text), created_by="import",
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        ))
        db.add(PortalFieldDraft(
            draft_id=draft_id, run_id=run.run_id, workspace_id=WS,
            field_id=field_id, field_name=_FIELD_NAME[field_id], status="draft",
            character_limit=get_registry().portal_fields[field_id].character_limit,
            current_version_id=version_id, open_issue_count=0,
            template_catalog_version="tpl-1",
        ))
    db.flush()


def _run_a3_variant(
    db, *, gold, drafts, registry, route, fake, flawed,
) -> dict:
    profile = registry.profile("A3.evidence_consistency")
    limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
    fake_adapter = (
        FakeProvider(raw_output=json.dumps(_fake_a3_payload(gold, flawed=flawed)))
        if fake else None
    )
    resolver, proxy = _forcing_resolver(route, limit=limit, fake_adapter=fake_adapter)
    project = _seed_project(db, gold, f"a3-{'flawed' if flawed else 'base'}")
    run = _seed_run(db, project, stage="critic_review", confirm=True)
    _seed_a3_drafts(db, run, drafts)
    with mock.patch("app.agents.gateway.get_agent_registry", return_value=registry):
        outcome = run_a3_evidence_consistency(db, run, provider_resolver=resolver)
    db.commit()
    usage = _usage_for_invocation(db, outcome.invocation_id)
    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL
    findings = [dict(f.__dict__) for f in outcome.findings]
    variant = {
        "variant": "flawed" if flawed else "baseline",
        "status": outcome.status,
        "reason": outcome.reason,
        "llm_calls": proxy.calls,
        "usage": usage,
        "silent_fake": _silent_fake(usage, execution=execution),
        "scores": None,
        "raw": {"findings": findings, "raw_outputs": list(proxy.raw_outputs)},
    }
    if outcome.status == "succeeded":
        variant["scores"] = scoring.score_a3(
            findings, gold,
            flaw_keywords=FLAW_KEYWORDS if flawed else None,
        )
    return variant


def run_a3_sample(
    db, *, case_id: str, candidate_key: str, rep: int, fake: bool,
    cases_dir: Path | None = None,
) -> dict:
    """Ein A3-Sample = identische eingefrorene Drafts (Baseline) + absichtlich
    fehlerhafte Variante (False-Consensus-Ziel) für denselben Kandidaten."""
    gold = scoring.load_case_gold(case_id, cases_dir)
    fragments = scoring.load_case_fragments(case_id, cases_dir)
    base_drafts = a3_draft_texts(fragments)
    flawed_drafts = dict(base_drafts)
    flawed_drafts["VC.BUSINESS_TARGETS_MODEL.EDITOR"] += FLAW_SENTENCE
    registry = derived_registry("a3", candidate_key)
    route = registry.route(candidate_key)
    _ensure_base_rows(db)

    variants = [
        _run_a3_variant(
            db, gold=gold, drafts=base_drafts, registry=registry, route=route,
            fake=fake, flawed=False,
        ),
        _run_a3_variant(
            db, gold=gold, drafts=flawed_drafts, registry=registry, route=route,
            fake=fake, flawed=True,
        ),
    ]
    return {
        "role": "a3", "candidate": candidate_key, "case": case_id, "rep": rep,
        "execution": _EXECUTION_FAKE if fake else _EXECUTION_REAL,
        "requested_model_id": route.requested_model_id(get_settings()),
        "status": "succeeded" if all(
            v["status"] == "succeeded" for v in variants
        ) else "partial",
        "variants": variants,
    }


# --- Lauf-Orchestrierung -------------------------------------------------------------

_SAMPLE_RUNNERS = {"a1": run_a1_sample, "a2": run_a2_sample, "a3": run_a3_sample}


def execute_run(
    db,
    *,
    role: str,
    candidate_key: str,
    cases: tuple[str, ...],
    reps: int,
    fake: bool,
    allow_holdout: bool,
    results_dir: Path | None = None,
    cases_dir: Path | None = None,
    env: dict | None = None,
) -> list[Path]:
    """Führt ``reps`` Wiederholungen je Fall aus und schreibt Sample-Artefakte.

    Bereits vorhandene Sample-Dateien werden übersprungen (Kostenbremse wie
    R5.9-REAL: Re-Run erfordert das Löschen der Datei).
    """
    import os

    if role not in ROLE_IDS:
        raise EvalRefusal(f"Unbekannte Rolle: {role}")
    settings = get_settings()
    registry = derived_registry(role, candidate_key)
    route = registry.route(candidate_key)
    refusal = guard_for_candidate(
        route, env=env if env is not None else os.environ,
        settings=settings, fake=fake,
    )
    if refusal:
        raise EvalRefusal(refusal)

    for case_id in cases:
        gold = scoring.load_case_gold(case_id, cases_dir)
        if gold.holdout and not allow_holdout:
            raise EvalRefusal(
                f"{case_id} ist HOLDOUT — Ausführung nur mit --allow-holdout "
                "(nie für Prompt-Tuning verwenden)."
            )

    preflight_status = ensure_route_preflight(db, candidate_key, fake=fake)
    prompt_sha = prompt_fingerprint()
    results_dir = results_dir or default_results_dir()
    written: list[Path] = []
    runner = _SAMPLE_RUNNERS[role]

    for case_id in cases:
        for rep in range(1, reps + 1):
            sample_path = (
                results_dir / "runs" / role / candidate_key / case_id
                / f"rep{rep}.json"
            )
            if sample_path.exists():
                continue
            # Prompt-Freeze: Drift zwischen Wiederholungen bricht den Lauf ab.
            current_sha = prompt_fingerprint()
            if current_sha != prompt_sha:
                raise EvalRefusal(
                    "Prompt-Assets haben sich während des Vergleichslaufs "
                    "geändert — Lauf abgebrochen (Prompt-Freeze)."
                )
            sample = runner(
                db, case_id=case_id, candidate_key=candidate_key, rep=rep,
                fake=fake, cases_dir=cases_dir,
            )
            sample["manifest"] = {
                "generated_at": _now_iso(),
                "prompt_sha": prompt_sha,
                "prompt_version": prompt_version_for(A1_PROFILE),
                "price_table_version": PRICE_TABLE_VERSION,
                "preflight": preflight_status,
                "quality_ceiling_route": bool(route.evaluation_only),
                "quality_ceiling_enabled": bool(
                    getattr(settings, "agent_quality_ceiling_enabled", False)
                ),
                "ai_eval_mode": settings.ai_eval_mode,
                "agent_fake_provider": bool(settings.agent_fake_provider),
                "holdout": case_id in HOLDOUT_CASES,
            }
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            sample_path.write_text(
                json.dumps(sample, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            written.append(sample_path)
    return written


# --- Blind-Pack + Ingest ---------------------------------------------------------------


def _load_samples(results_dir: Path, role: str) -> list[dict]:
    samples = []
    base = results_dir / "runs" / role
    if not base.is_dir():
        return samples
    for path in sorted(base.rglob("rep*.json")):
        samples.append(json.loads(path.read_text(encoding="utf-8")))
    return samples


_A2_SHEET_COLUMNS = (
    "case_id", "field_id", "label", "rep",
    *(crit for crit in scoring.A2_RUBRIC_BUCKETS),
    "language_ok", "fatal_suspicion", "review_time_min", "rework_needed", "comments",
)
_A3_SHEET_COLUMNS = (
    "case_id", "variant", "label", "rep",
    *scoring.A3_RUBRIC_CRITERIA,
    "fatal_suspicion", "review_time_min", "rework_needed", "comments",
)


def build_blind_pack(role: str, *, results_dir: Path | None = None) -> Path:
    """Anonymisierte Bewertungsunterlagen (Model A/B/C/…, randomisierte
    Reihenfolge) + CSV-Bogen. ``mapping.json`` bleibt lokal in ``var/`` —
    nie in Summaries/Reports."""
    if role not in ("a2", "a3"):
        raise EvalRefusal("Blind-Packs gibt es für die Rollen a2 und a3.")
    results_dir = results_dir or default_results_dir()
    samples = _load_samples(results_dir, role)
    if not samples:
        raise EvalRefusal(f"Keine Samples für Rolle {role} unter {results_dir}.")
    candidates = sorted({s["candidate"] for s in samples})
    nonce = uuid.uuid4().hex
    assignment = scoring.build_blind_assignment(candidates, nonce)
    blind_dir = results_dir / "blind" / role
    blind_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    if role == "a2":
        units = []
        for sample in samples:
            label = assignment[sample["candidate"]]
            raw_fields = {
                f["field_id"]: f for f in sample.get("raw", {}).get("fields", [])
            }
            for field in sample.get("fields", []):
                text = (raw_fields.get(field["field_id"]) or {}).get("suggestion_text")
                if not (text or "").strip():
                    continue
                units.append({
                    "case_id": sample["case"], "field_id": field["field_id"],
                    "label": label, "rep": sample["rep"], "text": text,
                })
        for unit in scoring.shuffle_for_review(units, nonce):
            slug = re.sub(r"[^a-z0-9]+", "-", unit["field_id"].lower()).strip("-")
            name = (
                f"{unit['case_id']}__{slug}__{unit['label'].replace(' ', '')}"
                f"__rep{unit['rep']}.md"
            )
            (blind_dir / name).write_text(
                f"# {unit['case_id']} — {unit['field_id']} — {unit['label']} "
                f"(Wiederholung {unit['rep']})\n\n"
                "_Blind-Bewertung: Herkunftsmodell absichtlich anonymisiert._\n\n"
                "---\n\n" + unit["text"] + "\n",
                encoding="utf-8",
            )
            rows.append({
                "case_id": unit["case_id"], "field_id": unit["field_id"],
                "label": unit["label"], "rep": unit["rep"],
            })
        columns = _A2_SHEET_COLUMNS
    else:
        units = []
        for sample in samples:
            label = assignment[sample["candidate"]]
            for variant in sample.get("variants", []):
                findings = variant.get("raw", {}).get("findings", [])
                lines = [
                    f"# {sample['case']} — A3-Findings — {label} "
                    f"({variant['variant']}, Wiederholung {sample['rep']})",
                    "",
                    "_Blind-Bewertung: Herkunftsmodell absichtlich anonymisiert._",
                    "",
                ]
                if not findings:
                    lines.append("_(keine Findings)_")
                for i, f in enumerate(findings, start=1):
                    lines += [
                        f"## Finding {i} — {f.get('field_id')} / "
                        f"{f.get('target_section')} — Severity {f.get('severity')}",
                        "",
                        str(f.get("description") or ""),
                        "",
                        f"*Vorschlag:* {f.get('suggested_improvement') or '—'}",
                        f"*Nächste Aktion:* {f.get('recommended_next_action') or '—'}",
                        "",
                    ]
                units.append({
                    "case_id": sample["case"], "variant": variant["variant"],
                    "label": label, "rep": sample["rep"],
                    "content": "\n".join(lines),
                })
        for unit in scoring.shuffle_for_review(units, nonce):
            name = (
                f"{unit['case_id']}__{unit['variant']}"
                f"__{unit['label'].replace(' ', '')}__rep{unit['rep']}.md"
            )
            (blind_dir / name).write_text(unit["content"] + "\n", encoding="utf-8")
            rows.append({
                "case_id": unit["case_id"], "variant": unit["variant"],
                "label": unit["label"], "rep": unit["rep"],
            })
        columns = _A3_SHEET_COLUMNS

    sheet_path = blind_dir / f"{role}_scoring_sheet.csv"
    with sheet_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})

    (blind_dir / "mapping.json").write_text(
        json.dumps(
            {"role": role, "nonce": nonce, "assignment": assignment,
             "generated_at": _now_iso()},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return blind_dir


def ingest_scores(
    role: str, scores_csv: Path, *, results_dir: Path | None = None
) -> Path:
    """Ausgefüllten Blindbogen einlesen und über ``mapping.json`` je Kandidat
    aggregieren (Mittelwerte je Kriterium, Review-Zeit, Rework)."""
    results_dir = results_dir or default_results_dir()
    mapping_path = results_dir / "blind" / role / "mapping.json"
    if not mapping_path.exists():
        raise EvalRefusal(f"mapping.json fehlt: erst `blind` ausführen ({mapping_path}).")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    label_to_candidate = {v: k for k, v in mapping["assignment"].items()}
    criteria = (
        tuple(scoring.A2_RUBRIC_BUCKETS) if role == "a2" else scoring.A3_RUBRIC_CRITERIA
    )

    def _collect(rows: list[dict]) -> dict:
        per_candidate: dict[str, dict] = {}
        for row in rows:
            label = (row.get("label") or "").strip()
            candidate = label_to_candidate.get(label)
            if candidate is None:
                raise EvalRefusal(f"Unbekanntes Blind-Label in CSV: {label!r}")
            bucket = per_candidate.setdefault(candidate, {
                "rows": 0, "criteria": {c: [] for c in criteria},
                "review_time_min": [], "rework_count": 0, "fatal_suspicions": 0,
            })
            bucket["rows"] += 1
            for crit in criteria:
                value = (row.get(crit) or "").strip()
                if value:
                    bucket["criteria"][crit].append(float(value))
            time_value = (row.get("review_time_min") or "").strip()
            if time_value:
                bucket["review_time_min"].append(float(time_value))
            if (row.get("rework_needed") or "").strip().lower() in ("1", "ja", "yes", "true"):
                bucket["rework_count"] += 1
            if (row.get("fatal_suspicion") or "").strip():
                bucket["fatal_suspicions"] += 1
        out = {}
        for candidate, bucket in per_candidate.items():
            crit_means = {}
            for crit, values in bucket["criteria"].items():
                mean, _ = scoring.mean_std(values)
                crit_means[crit] = mean
            time_mean, _ = scoring.mean_std(bucket["review_time_min"])
            out[candidate] = {
                "rows": bucket["rows"],
                "criteria_means": crit_means,
                "review_time_min_mean": time_mean,
                "rework_count": bucket["rework_count"],
                "fatal_suspicions": bucket["fatal_suspicions"],
            }
        return out

    with scores_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))

    # Dev-/Holdout-Trennung: die Auswahl stützt sich auf die Holdout-Zeilen —
    # ohne Split würden Dev-Werte still auch als Holdout-Human-Werte gelten.
    dev_rows: list[dict] = []
    holdout_rows: list[dict] = []
    for row in all_rows:
        is_holdout = (row.get("case_id") or "").strip() in HOLDOUT_CASES
        (holdout_rows if is_holdout else dev_rows).append(row)
    out = _collect(all_rows)
    split = {"dev": _collect(dev_rows), "holdout": _collect(holdout_rows)}

    human_dir = results_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    out_path = human_dir / f"{role}_scores.json"
    out_path.write_text(
        json.dumps(
            {"role": role, "ingested_at": _now_iso(), "source_csv": scores_csv.name,
             "per_candidate": out, "per_candidate_split": split},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return out_path


# --- Aggregation + Report -----------------------------------------------------------


def _human_scores(results_dir: Path, role: str) -> dict:
    """Volles Ingest-Payload: {"per_candidate": …, "per_candidate_split": …}."""
    path = results_dir / "human" / f"{role}_scores.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _aggregate_a1(samples: list[dict]) -> dict:
    metric_keys = (
        "fact_precision", "fact_recall", "field_accuracy", "boundary_accuracy",
        "entity_preservation", "portal_text_adoption_rate", "missing_recall",
    )
    schema_ok = sum(1 for s in samples if s.get("schema_valid"))
    out = {
        "samples": len(samples),
        "schema_success_rate": round(schema_ok / len(samples), 4) if samples else None,
    }
    for key in metric_keys:
        values = [
            (s.get("scores") or {}).get(key) for s in samples if s.get("scores")
        ]
        mean, std = scoring.mean_std([v for v in values if v is not None])
        out[key] = {"mean": mean, "std": std}
    out["fatal_events"] = sum(
        1 for s in samples for f in s.get("fatal", []) if f["status"] == "fail"
    )
    return out


def _aggregate_a2(samples: list[dict], human: dict | None) -> dict:
    fields = [f for s in samples for f in s.get("fields", [])]
    evaluated = [f for f in fields if f["status"] in ("generated", "missing_inputs")]
    passed = [f for f in evaluated if f["gates_passed"]]
    fatal_fields = [f for f in fields if f.get("fatal_candidate")]
    gate_share_values = [
        scoring.deterministic_gate_share(f["gates"]) for f in evaluated
    ]
    gate_share_mean, gate_share_std = scoring.mean_std(gate_share_values)

    latencies = [
        f["usage"]["latency_ms"] for f in fields
        if f["usage"].get("latency_ms") is not None
    ]
    latency_mean, latency_std = scoring.mean_std([float(v) for v in latencies])
    costs = [
        f["usage"]["cost_chf"] for f in passed
        if f["usage"].get("cost_chf") is not None
    ]
    tokens = [
        (f["usage"].get("input_tokens") or 0) + (f["usage"].get("output_tokens") or 0)
        for f in passed
    ]
    all_priced = bool(passed) and all(
        f["usage"].get("cost_status") == "priced" for f in passed
    )
    cost_per_acceptable = (
        round(sum(costs) / len(passed), 4) if passed and all_priced else None
    )
    tokens_per_acceptable = (
        round(sum(tokens) / len(passed), 1) if passed else None
    )

    # Varianz über Wiederholungen: Gate-Flips je (case, field).
    by_unit: dict[tuple[str, str], list[bool]] = {}
    for sample in samples:
        for f in sample.get("fields", []):
            if f["status"] not in ("generated", "missing_inputs"):
                continue
            by_unit.setdefault((sample["case"], f["field_id"]), []).append(
                f["gates_passed"]
            )
    gate_flips = sum(
        1 for outcomes in by_unit.values() if len(set(outcomes)) > 1
    )

    # Harte DQs (Auftrag): Felder mit mindestens einem angeschlagenen
    # DQ-Kriterium plus Zählwerte je Kriterium (Whitelist: nur Counts/Namen).
    hard_dq_by_name: dict[str, int] = {}
    for f in fields:
        for dq in f.get("hard_dq", []):
            hard_dq_by_name[dq] = hard_dq_by_name.get(dq, 0) + 1

    return {
        "samples": len(samples),
        "fields_evaluated": len(evaluated),
        "gate_pass_rate": (
            round(len(passed) / len(evaluated), 4) if evaluated else None
        ),
        "gate_share_mean": gate_share_mean,
        "gate_share_std": gate_share_std,
        "fatal_candidate_fields": len(fatal_fields),
        "hard_dq_fields": sum(1 for f in fields if f.get("hard_dq")),
        "hard_dq_by_name": hard_dq_by_name,
        "gate_flips_across_reps": gate_flips,
        "latency_ms": {"mean": latency_mean, "std": latency_std},
        "cost_per_acceptable_chf": cost_per_acceptable,
        "tokens_per_acceptable": tokens_per_acceptable,
        "cost_basis": (
            "priced" if cost_per_acceptable is not None
            else "tokens_only (nicht bepreisbar — nie 0 CHF)"
        ),
        "human": human or None,
    }


def _aggregate_a3(samples: list[dict], human: dict | None) -> dict:
    variants = [v for s in samples for v in s.get("variants", [])]
    succeeded = [v for v in variants if v["status"] == "succeeded"]
    metric_keys = (
        "finding_recall_weighted", "false_positive_rate", "grouping_quality",
        "fixability_rate",
    )
    out = {
        "samples": len(samples),
        "variants_succeeded": len(succeeded),
        "false_consensus_events": sum(
            1 for v in succeeded
            if (v.get("scores") or {}).get("false_consensus") is True
        ),
        "unmatched_for_adjudication": sum(
            (v.get("scores") or {}).get("unmatched_for_adjudication", 0)
            for v in succeeded
        ),
        "funding_decision_claims": sum(
            (v.get("scores") or {}).get("funding_decision_claims", 0)
            for v in succeeded
        ),
        "silent_fake_events": sum(1 for v in variants if v.get("silent_fake")),
    }
    for key in metric_keys:
        values = [
            (v.get("scores") or {}).get(key) for v in succeeded if v.get("scores")
        ]
        mean, std = scoring.mean_std([x for x in values if x is not None])
        out[key] = {"mean": mean, "std": std}
    latencies = [
        v["usage"]["latency_ms"] for v in variants
        if v.get("usage", {}).get("latency_ms") is not None
    ]
    out["latency_ms"] = dict(zip(("mean", "std"), scoring.mean_std(
        [float(v) for v in latencies]
    )))
    out["human"] = human or None
    return out


def aggregate(results_dir: Path | None = None) -> dict:
    """Whitelist-Aggregation über alle vorhandenen Samples (keine Rohtexte)."""
    results_dir = results_dir or default_results_dir()
    summary: dict = {
        "generated_at": _now_iso(),
        "price_table_version": PRICE_TABLE_VERSION,
        "prompt_sha": prompt_fingerprint(),
        "roles": {},
    }
    executions: set[str] = set()
    prompt_shas: set[str] = set()
    for role in ROLE_IDS:
        samples = _load_samples(results_dir, role)
        if not samples:
            continue
        executions.update(s.get("execution", "?") for s in samples)
        prompt_shas.update(
            (s.get("manifest") or {}).get("prompt_sha", "?") for s in samples
        )
        human_payload = _human_scores(results_dir, role)
        human_flat = human_payload.get("per_candidate", {})
        # Split-Werte (S3): Dev-Aggregat erhält Dev-Human, Holdout-Aggregat NUR
        # Holdout-Human. Ältere Ingests ohne Split: Dev fällt auf flach zurück,
        # Holdout bleibt ehrlich leer (nie stille Dev-Wiederverwendung).
        human_split = human_payload.get("per_candidate_split") or {}
        human_dev = human_split.get("dev") or human_flat
        human_holdout = human_split.get("holdout") or {}
        by_candidate: dict[str, dict] = {}
        for candidate in sorted({s["candidate"] for s in samples}):
            cand_samples = [s for s in samples if s["candidate"] == candidate]
            dev = [s for s in cand_samples if s["case"] not in HOLDOUT_CASES]
            holdout = [s for s in cand_samples if s["case"] in HOLDOUT_CASES]
            dev_human = human_dev.get(candidate)
            holdout_human = human_holdout.get(candidate)
            if role == "a1":
                agg = {"dev": _aggregate_a1(dev)}
                if holdout:
                    agg["holdout"] = _aggregate_a1(holdout)
            elif role == "a2":
                agg = {"dev": _aggregate_a2(dev, dev_human)}
                if holdout:
                    agg["holdout"] = _aggregate_a2(holdout, holdout_human)
            else:
                agg = {"dev": _aggregate_a3(dev, dev_human)}
                if holdout:
                    agg["holdout"] = _aggregate_a3(holdout, holdout_human)
            agg["requested_model_id"] = cand_samples[0].get("requested_model_id")
            agg["executions"] = sorted({s.get("execution") for s in cand_samples})
            by_candidate[candidate] = agg
        # A2: gewichteter Score inkl. relativer Kosten-/Latenzwertung.
        if role == "a2":
            latency_values = {
                cand: (agg["dev"].get("latency_ms") or {}).get("mean")
                for cand, agg in by_candidate.items()
            }
            cost_values = {
                cand: agg["dev"].get("cost_per_acceptable_chf")
                for cand, agg in by_candidate.items()
            }
            latency_rel = scoring.cost_latency_relative(latency_values)
            cost_rel = scoring.cost_latency_relative(cost_values)
            for cand, agg in by_candidate.items():
                parts = [v for v in (cost_rel.get(cand), latency_rel.get(cand))
                         if v is not None]
                cl_score = round(sum(parts) / len(parts), 4) if parts else None
                cand_human = human_dev.get(cand) or {}
                agg["weighted_score"] = scoring.weighted_a2_score(
                    cand_human.get("criteria_means"),
                    gate_share=agg["dev"].get("gate_share_mean") or 0.0,
                    cost_latency_score=cl_score,
                )
        summary["roles"][role] = by_candidate

    if not summary["roles"]:
        summary["status"] = "not_run"
    elif executions == {_EXECUTION_REAL}:
        summary["status"] = "durchgeführt"
    elif _EXECUTION_REAL in executions:
        summary["status"] = "partial (enthält Dry-Run-Samples)"
    else:
        summary["status"] = "dry_run (Fake-Adapter — keine Live-Evaluation)"
    summary["prompt_sha_consistent"] = len(prompt_shas) <= 1
    return summary


def render_summary_md(summary: dict) -> str:
    lines = [
        "# Rollen-Modell-Evaluation — Summary",
        "",
        f"*Generiert:* {summary['generated_at']} · *Status:* **{summary['status']}** · "
        f"*Preistabelle:* `{summary['price_table_version']}`",
        f"*Prompt-SHA:* `{summary['prompt_sha'][:16]}…` · "
        f"Prompt-Freeze konsistent: {'ja' if summary.get('prompt_sha_consistent') else 'NEIN'}",
        "",
        "`not_run`/Dry-Run heisst: nicht (live) durchgeführt — nie bestanden. "
        "Human-Rubrik-Werte stammen ausschliesslich aus dem Blind-Ingest.",
        "",
    ]
    for role, by_candidate in summary.get("roles", {}).items():
        lines += [f"## Rolle {role.upper()} ({ROLE_IDS[role]})", ""]
        for candidate, agg in by_candidate.items():
            lines += [
                f"### Kandidat `{candidate}` — Modell "
                f"`{agg.get('requested_model_id') or '—'}` — "
                f"Ausführung: {', '.join(agg.get('executions', []))}",
                "",
                "```json",
                json.dumps(
                    {k: v for k, v in agg.items() if k not in ("executions",)},
                    ensure_ascii=False, indent=2,
                ),
                "```",
                "",
            ]
    return "\n".join(lines)


def write_summary(results_dir: Path | None = None) -> tuple[Path, Path]:
    results_dir = results_dir or default_results_dir()
    summary = aggregate(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / "summary.json"
    md_path = results_dir / "summary.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_summary_md(summary), encoding="utf-8")
    return json_path, md_path


# ---------------------------------------------------------------------------
# Live-Pilot (Owner-Auftrag 2026-07-16): begrenzter A2/A3-Vergleich VOR dem
# grossen Benchmark. Harte Limits: max 24 echte Provider-Calls, max CHF 12.
# Eigenes Results-Verzeichnis — verify_all liest weiterhin NUR
# role_model_eval/summary.json (der Pilot erzeugt dort keinen Mischstatus).
# ---------------------------------------------------------------------------

ANTHROPIC_CANDIDATE = "anthropic_sonnet_5_candidate"
PILOT_A2_CANDIDATES = (
    ANTHROPIC_CANDIDATE,
    "openai_gpt_56_terra_candidate",
)
PILOT_CASES = ("F1", "F2", "H1")  # Dev F1/F2 + Holdout H1 (Owner 2026-07-16)
PILOT_FIELDS = A3_SCOPE_FIELDS  # VC (Kern 3.1) + SOL (Kern 4.2)
# Kanonische Kernabschnitte je Feld (Owner): die Feld-ID/Section wird dem
# Modell im Structured-Output-Schema als const vorgegeben (Pilot-Variante).
PILOT_SECTIONS = {
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": "3.1",
    "SOL.INNOVATION_SOLUTION.EDITOR": "4.2",
}
SECTION_OUTPUT_SCHEMA_ID = "PortalSectionDraftBundle@v1"
A3_OUTPUT_SCHEMA_ID = "ReviewFindingBundle@v1"
PILOT_REPS = 2
# Session-Limits (Owner 2026-07-16, zweite Erhöhung — kumulativ, kein Reset):
PILOT_MAX_CALLS = 160
PILOT_MAX_COST_CHF = 80.0
PILOT_MAX_COST_PER_CALL_CHF = 8.0

# Fixed Drafts für den fairen A3-Vergleich: je (Feld, Kernabschnitt) drei
# goldmarkierte, injizierte Schwächen (Keywords = deterministische Referenz).
PILOT_FIXED_FLAWS: dict[str, tuple[tuple[str, str, tuple[str, ...]], ...]] = {
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": (
        ("unsupported_market_number",
         "3.1-Zusatz: Das adressierbare Marktvolumen beträgt CHF 12'400'000 "
         "pro Jahr.",
         ("Marktvolumen", "12'400'000", "unbelegt", "Quelle")),
        ("contradictory_market_share",
         "3.1-Zusatz: Wir erreichen im dritten Jahr 18 Prozent Marktanteil; "
         "gleichzeitig gehen wir von 31 Prozent Marktanteil im dritten Jahr "
         "aus.",
         ("Marktanteil", "18", "31", "widersprüchlich")),
        ("kpi_without_baseline",
         "3.1-Zusatz: Die Lösung senkt die Ausschussquote um 25 Prozent.",
         ("Ausschussquote", "25", "Baseline", "Ausgangswert")),
    ),
    "SOL.INNOVATION_SOLUTION.EDITOR": (
        ("method_what_not_how",
         "4.2-Zusatz: Wir optimieren die Erkennung mit künstlicher "
         "Intelligenz und verbessern damit die Qualität deutlich.",
         ("Methodik", "wie", "konkret", "Verfahren")),
        ("missing_sota_delimitation",
         "4.2-Zusatz: Unser Ansatz ist völlig neuartig und weltweit "
         "einzigartig.",
         ("Stand der Technik", "Abgrenzung", "neuartig", "Vergleich")),
        ("review_note_in_prose",
         "4.2-Zusatz: TODO: diesen Absatz nach Rücksprache mit dem Reviewer "
         "noch überarbeiten.",
         ("TODO", "Review", "Notiz", "Prosa")),
    ),
}


def pilot_fixed_draft(
    case_id: str, field_id: str, *, cases_dir: Path | None = None
) -> tuple[str, tuple[tuple[str, str, tuple[str, ...]], ...]]:
    """Eingefrorener fehlerhafter Draft je (Fall, Feld): Falltext des Feldes
    plus die goldmarkierten injizierten Schwächen. Identisch für beide
    A3-Kandidaten (fairer Vergleich)."""
    fragments = scoring.load_case_fragments(case_id, cases_dir)
    base_text = a3_draft_texts(fragments)[field_id]
    flaws = PILOT_FIXED_FLAWS[field_id]
    text = base_text + "\n\n" + "\n".join(flaw[1] for flaw in flaws)
    return text, flaws
# Pilot-/Derived-Registry-Konfiguration (NUR Pilotpfad; Contract unverändert):
PILOT_MAX_OUTPUT_TOKENS = 25000
_PILOT_PROFILE_IDS = (
    "A2.value_creation_market_logic",
    "A2.solution_innovation",
    "A2.introduction_public_summary",
    "A3.evidence_consistency",
)

# Getrennte Owner-Rubriken (je 1–5; nur menschlich, blind).
PILOT_A2_RUBRIC = (
    "crit_1_projektspezifitaet",
    "crit_2_abdeckung_portalfeld",
    "crit_3_innosuisse_reviewer_passung",
    "crit_4_fachliche_plausibilitaet",
    "crit_5_argumentationslogik",
    "crit_6_markt_nutzerorientierung",
    "crit_7_praezision_lesbarkeit",
    "crit_8_faktentreue_evidenzdisziplin",
    "crit_9_qualitaet_offene_fragen",
    "crit_10_nachbearbeitungsaufwand",
)
PILOT_A3_RUBRIC = (
    "crit_1_relevante_schwaechen_erkannt",
    "crit_2_geringe_false_positive_rate",
    "crit_3_priorisierung_nach_relevanz",
    "crit_4_symptome_sinnvoll_gruppiert",
    "crit_5_konkrete_naechste_aktion",
    "crit_6_evidence_unsicherheitsbewusstsein",
    "crit_7_kein_foerder_rechts_fto_entscheid",
    "crit_8_praktischer_nutzen_ueberarbeitung",
)

_PILOT_SHEET_BASE = (
    "case_id", "unit_kind", "unit_ref", "label", "rep",
)
_PILOT_SHEET_TAIL = (
    "fatal_suspicion", "review_time_min", "rework_needed", "comments",
)


class _SchemaPatchAdapter:
    """Pilot-Wrapper um einen Provider-Adapter: patcht NUR das native
    ``output_json_schema`` des Requests (field_id/target_section als
    const/enum — Owner Block 3/5), sammelt request_ids und Envelope-
    Normalisierungen als sichere Metadaten. Die Gateway-Pydantic-Validierung
    (Basis-Schema) bleibt unverändert die einzige inhaltliche Autorität."""

    def __init__(self, inner, patch) -> None:
        self._inner = inner
        self._patch = patch
        self.request_ids: list[str] = []
        self.wrapper_normalized = 0
        self.patched_schema_sha: str | None = None

    @property
    def name(self) -> str:
        return self._inner.name

    def available(self) -> bool:
        return self._inner.available()

    def generate(self, request):
        if self._patch is not None and request.output_json_schema is not None:
            patched = self._patch(request.output_json_schema)
            self.patched_schema_sha = hashlib.sha256(
                json.dumps(patched, sort_keys=True).encode("utf-8")
            ).hexdigest()
            request = dataclasses.replace(request, output_json_schema=patched)
        try:
            result = self._inner.generate(request)
        except Exception as exc:
            rid = getattr(exc, "request_id", None)
            if rid:
                self.request_ids.append(rid)
            raise
        if result.request_id:
            self.request_ids.append(result.request_id)
        if getattr(result, "tool_wrapper_normalized", False):
            self.wrapper_normalized += 1
        return result


def _patch_field_section_const(field_id: str, target_section: str):
    """Schema-Patch: in jedem Objekt, das field_id UND target_section als
    Properties trägt, beide auf const setzen (eng, deterministisch; keine
    anderen Änderungen). Pilot-Variante «pilot-const-v1» des Basis-Schemas."""

    def patch(schema: dict) -> dict:
        def walk(node):
            if isinstance(node, list):
                return [walk(item) for item in node]
            if not isinstance(node, dict):
                return node
            out = {key: walk(value) for key, value in node.items()}
            props = out.get("properties")
            if (
                isinstance(props, dict)
                and "field_id" in props and "target_section" in props
            ):
                props["field_id"] = {
                    "type": "string", "const": field_id,
                    "description": "Kanonische Portalfeld-ID (vorgegeben).",
                }
                props["target_section"] = {
                    "type": "string", "enum": [target_section],
                    "description": (
                        "Zulässiger kanonischer Registry-Marker des geprüften "
                        f"Abschnitts: {target_section}."
                    ),
                }
            return out

        return walk(json.loads(json.dumps(schema)))

    return patch


def _seed_case_facts(db, run: AnalysisRun, gold: scoring.CaseGold, tag: str) -> int:
    """Gold-Fakten des Falls als advisory A1-Fakten seeden (Status proposed,
    Provenienz auf die geseedeten Fragmente) — Antragstellerangaben als
    Projektinput, NIE als extern verifizierte Evidenz."""
    from app.db.models import ExtractedFact

    count = 0
    for i, g in enumerate(gold.gold_facts, start=1):
        fragment_ids = [f"{fid}@{tag}" for fid in (g.get("fragment_ids") or [])]
        if not fragment_ids:
            continue
        statement = " ".join(g.get("keywords", [])[:4]) or g.get("gold_id", "")
        if g.get("normalized_value"):
            statement = f"{statement}: {g['normalized_value']}"
        db.add(ExtractedFact(
            fact_id=f"rme-fact-{tag}-{i:03d}",
            run_id=run.run_id,
            workspace_id=run.workspace_id,
            fact_type=str(g.get("fact_type") or "other"),
            normalized_value=g.get("normalized_value"),
            original_statement=statement,
            status="proposed",
            requirement_id=None,
            field_id=g.get("target_ref"),
            source_fragment_ids=fragment_ids,
            source_version_ids=[],
            profile_id=A1_PROFILE,
            fact_fingerprint=f"{tag}-{i:03d}",
        ))
        count += 1
    db.flush()
    return count


def _seed_field_draft(
    db, run: AnalysisRun, field_id: str, text: str
) -> tuple[str, str]:
    """Feld-Draft mit dem eingefrorenen Falltext seeden (Produktivfluss:
    importierter Antragstext ist die Draft-Basis) → (draft_id, version_id)."""
    from app.registry import get_registry

    draft_id = "rme-pd-" + uuid.uuid4().hex[:8]
    version_id = "rme-pv-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=version_id, draft_id=draft_id, text=text,
        character_count=len(text), created_by="import",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    ))
    db.add(PortalFieldDraft(
        draft_id=draft_id, run_id=run.run_id, workspace_id=WS,
        field_id=field_id, field_name=_FIELD_NAME[field_id], status="draft",
        character_limit=get_registry().portal_fields[field_id].character_limit,
        current_version_id=version_id, open_issue_count=0,
        template_catalog_version="tpl-1",
    ))
    db.flush()
    return draft_id, version_id


def _pilot_registry(role: str, candidate_key: str) -> AgentRegistry:
    """Abgeleitete Pilot-Registry (Owner 2026-07-16/17, NUR Pilotpfad):
    ``max_output_tokens=25000`` für die A2-/A3-Profile, ``reasoning_effort=
    high`` nur für den OpenAI-Kandidaten (Anthropic bleibt adaptiver
    Modell-Standard — der Adapter überträgt effort ohnehin nicht),
    ``max_cost_chf`` je Invocation auf der Rollenroute und für Anthropic die
    native Structured-Output-Oberfläche (``output_config.format`` statt forced
    tool use). Contract-YAML, Produktivrouten, Prompt-Fingerprints und
    Gateway-Defaults bleiben unverändert."""
    base = derived_registry(role, candidate_key)
    provider = base.route(candidate_key).provider
    model_routes = dict(base.model_routes)
    if provider == "anthropic_direct":
        route = model_routes[candidate_key]
        model_routes[candidate_key] = dataclasses.replace(
            route,
            capabilities={
                **(route.capabilities or {}),
                "structured_output_mode": NATIVE_STRUCTURED_OUTPUT,
            },
        )
    profiles = dict(base.profiles)
    for profile_id in _PILOT_PROFILE_IDS:
        profile = profiles[profile_id]
        profiles[profile_id] = dataclasses.replace(
            profile,
            invocation_limits={
                **profile.invocation_limits,
                "max_output_tokens": PILOT_MAX_OUTPUT_TOKENS,
                # effort=high nur für den OpenAI-Kandidaten; Anthropic bleibt
                # adaptiver Modell-Standard (Adapter überträgt effort nie).
                **(
                    {"reasoning_effort": "high"}
                    if provider == "openai_direct" else {}
                ),
            },
        )
    role_id = ROLE_IDS[role]
    role_routes = dict(base.role_routes or {})
    role_routes[role_id] = dataclasses.replace(
        role_routes[role_id], max_cost_chf=PILOT_MAX_COST_PER_CALL_CHF
    )
    return AgentRegistry(
        model_routes, base.agents, profiles, role_routes
    )


def default_pilot_results_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "var" / "evaluation" / "role_model_eval_pilot"
    )


def _pilot_sample_paths(results_dir: Path) -> list[Path]:
    """Alle Call-tragenden Artefakte — inkl. archivierter, als ungültig
    markierter Läufe (`invalid_harness_run_*`): deren Calls/Kosten bleiben
    im kumulativen Budget (kein Zähler-Reset), zählen aber nie zur Bewertung."""
    paths: list[Path] = []
    bases = [results_dir]
    bases.extend(sorted(results_dir.glob("invalid_harness_run_*")))
    for base_dir in bases:
        for sub in ("smoke", "runs"):
            base = base_dir / sub
            if base.is_dir():
                paths.extend(sorted(base.rglob("*.json")))
    return paths


def pilot_totals(results_dir: Path) -> dict:
    """Bisherige echte Calls/Kosten über alle Pilot-Artefakte (Cap-Wächter).

    Fake-Dry-Run-Samples zählen nicht gegen das Live-Budget. Zusätzlich fliesst
    ``reconciliation.json`` ein: manuell nachgetragene Calls/konservative
    Kostenreservierungen für Läufe ohne gemetertes Usage (nie 0 annehmen).
    """
    calls = 0
    cost = 0.0
    priced_all = True
    for path in _pilot_sample_paths(results_dir):
        sample = json.loads(path.read_text(encoding="utf-8"))
        if sample.get("execution") != _EXECUTION_REAL:
            continue
        calls += _sample_llm_calls(sample)
        sample_cost, sample_priced = _sample_cost(sample)
        cost += sample_cost
        priced_all = priced_all and sample_priced
    reserved = 0.0
    reconciled_calls = 0
    recon_path = results_dir / "reconciliation.json"
    if recon_path.exists():
        recon = json.loads(recon_path.read_text(encoding="utf-8"))
        for entry in recon.get("entries", []):
            reconciled_calls += int(entry.get("llm_calls") or 0)
            reserved += float(entry.get("cost_chf_reserved") or 0.0)
    return {
        "real_llm_calls": calls + reconciled_calls,
        "cost_chf_priced": round(cost, 4),
        "cost_chf_reserved_unmetered": round(reserved, 4),
        "cost_chf_total_conservative": round(cost + reserved, 4),
        "all_priced": priced_all and reserved == 0.0,
    }


def _sample_llm_calls(sample: dict) -> int:
    if "fields" in sample:
        return sum(int(f.get("llm_calls") or 0) for f in sample["fields"])
    if "variants" in sample:
        return sum(int(v.get("llm_calls") or 0) for v in sample["variants"])
    return int(sample.get("llm_calls") or 0)


def _sample_cost(sample: dict) -> tuple[float, bool]:
    """(summierte priced-Kosten, alles bepreist?) eines Pilot-Artefakts."""
    usages: list[dict] = []
    if "fields" in sample:
        usages = [f.get("usage") or {} for f in sample["fields"]]
    elif "variants" in sample:
        usages = [v.get("usage") or {} for v in sample["variants"]]
    elif sample.get("usage"):
        usages = [sample["usage"]]
    cost = 0.0
    priced = True
    for usage in usages:
        if usage.get("cost_chf") is not None:
            cost += float(usage["cost_chf"])
        elif usage.get("cost_status") not in (None, "priced", "not_applicable"):
            priced = False
    return cost, priced


def _pilot_budget_guard(
    results_dir: Path, *, planned_calls: int, fake: bool
) -> dict:
    """Verweigert VOR einem Live-Block, wenn Cap/Budget überschritten würde."""
    totals = pilot_totals(results_dir)
    if fake:
        return totals
    if totals["real_llm_calls"] + planned_calls > PILOT_MAX_CALLS:
        raise EvalRefusal(
            f"Pilot-Call-Cap: {totals['real_llm_calls']} bisher + "
            f"{planned_calls} geplant > {PILOT_MAX_CALLS} — Stopp."
        )
    if totals["cost_chf_priced"] >= PILOT_MAX_COST_CHF:
        raise EvalRefusal(
            f"Pilot-Kostenlimit erreicht: {totals['cost_chf_priced']} CHF "
            f"≥ {PILOT_MAX_COST_CHF} CHF — Stopp."
        )
    return totals


def _write_pilot_sample(path: Path, sample: dict, *, prompt_sha: str) -> None:
    sample["manifest"] = {
        "generated_at": _now_iso(),
        "prompt_sha": prompt_sha,
        "price_table_version": PRICE_TABLE_VERSION,
        "pilot": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sample, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def execute_pilot_smoke(
    db, *, fake: bool, results_dir: Path | None = None,
    cases_dir: Path | None = None, env: dict | None = None,
    candidates: tuple[str, ...] | None = None,
) -> list[Path]:
    """Phase 1: je Kandidatenroute Route-Preflight + genau EIN strukturierter
    Smoke-Call (A1-Profil über die Kandidatenroute — Schema, Tokens, Kosten,
    tatsächliche Modell-ID). Danach ist ein STOPP mit Zwischenbericht Pflicht."""
    import os

    settings = get_settings()
    results_dir = results_dir or default_pilot_results_dir()
    prompt_sha = prompt_fingerprint()
    written: list[Path] = []
    for candidate in (candidates or PILOT_A2_CANDIDATES):
        path = results_dir / "smoke" / f"{candidate}.json"
        if path.exists():
            continue
        registry = derived_registry("a1", candidate)
        route = registry.route(candidate)
        refusal = guard_for_candidate(
            route, env=env if env is not None else os.environ,
            settings=settings, fake=fake,
        )
        if refusal:
            raise EvalRefusal(refusal)
        _pilot_budget_guard(results_dir, planned_calls=2, fake=fake)
        preflight_status = ensure_route_preflight(db, candidate, fake=fake)
        sample = run_a1_sample(
            db, case_id="F1", candidate_key=candidate, rep=1, fake=fake,
            cases_dir=cases_dir,
        )
        sample["phase"] = "pilot_smoke"
        sample["preflight"] = preflight_status
        _write_pilot_sample(path, sample, prompt_sha=prompt_sha)
        written.append(path)
    return written


def archive_pilot_run(
    results_dir: Path, *, name: str, reason: str
) -> Path | None:
    """Laufartefakte als Auditspur wegarchivieren (nie löschen, nie bewerten).

    Die Calls/Kosten bleiben über ``_pilot_sample_paths`` im kumulativen
    Budget; die Bewertungspfade sehen die Artefakte nicht mehr, sodass alte
    und neue Vertragsstände nie vermischt werden."""
    import shutil

    runs = results_dir / "runs"
    if not runs.is_dir() or not any(runs.rglob("*.json")):
        return None
    target = results_dir / name
    target.mkdir(parents=True, exist_ok=True)
    shutil.move(str(runs), str(target / "runs"))
    for extra in ("calibration_report.json", "pilot_summary.json", "pilot_summary.md"):
        source = results_dir / extra
        if source.exists():
            shutil.move(str(source), str(target / extra))
    (target / "INVALID.json").write_text(
        json.dumps({
            "invalid_harness_run": True,
            "archived_at": _now_iso()[:10],
            "reason": reason,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def execute_structured_output_smokes(
    *, fake: bool, results_dir: Path | None = None, env: dict | None = None,
) -> list[Path]:
    """Owner Block 1/6: genau ein A2- und ein A3-Structured-Output-Smoke auf
    der Anthropic-Kandidatenroute, BEVOR kalibriert wird. Danach ist ein STOPP
    Pflicht, wenn einer nicht besteht."""
    results_dir = results_dir or default_pilot_results_dir()
    written: list[Path] = []
    for spec in STRUCTURED_OUTPUT_SMOKE_SPECS:
        path = run_pilot_smoke_call(
            candidate_key=ANTHROPIC_CANDIDATE, spec=spec, fake=fake,
            results_dir=results_dir, env=env,
        )
        written.append(path)
    return written


def structured_output_smokes_passed(
    results_dir: Path | None = None,
) -> tuple[bool, dict]:
    """Prüfkriterien der zwei Structured-Output-Smokes (Owner Block 1).

    Bestanden nur mit: HTTP erfolgreich, bestätigte Modell-ID, kein
    Tool-Envelope, Schema erfüllt, Usage/Kosten/Latenz/Request-ID vorhanden.
    """
    results_dir = results_dir or default_pilot_results_dir()
    report: dict = {"smokes": {}}
    problems: list[str] = []
    for spec in STRUCTURED_OUTPUT_SMOKE_SPECS:
        path = results_dir / "smoke" / f"{ANTHROPIC_CANDIDATE}__{spec.slug}.json"
        if not path.exists():
            problems.append(f"{spec.slug}: Smoke fehlt")
            report["smokes"][spec.slug] = "fehlt"
            continue
        sample = json.loads(path.read_text(encoding="utf-8"))
        usage = sample.get("usage") or {}
        last = (sample.get("attempts") or [{}])[-1]
        report["smokes"][spec.slug] = {
            "status": sample.get("status"),
            "schema_valid": sample.get("schema_valid"),
            "structured_output_mode": sample.get("structured_output_mode"),
            "tool_envelope_used": sample.get("tool_envelope_used"),
            "actual_model_id": usage.get("actual_model_id"),
            "request_id": last.get("request_id"),
            "http_status": last.get("http_status"),
            "provider_error_type": last.get("provider_error_type"),
            "provider_message": last.get("provider_message"),
            "cost_status": usage.get("cost_status"),
            "cost_chf": usage.get("cost_chf"),
            "latency_ms": usage.get("latency_ms"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }
        if sample.get("execution") != _EXECUTION_REAL:
            problems.append(f"{spec.slug}: kein Real-Lauf")
            continue
        if sample.get("status") != "succeeded" or not sample.get("schema_valid"):
            problems.append(
                f"{spec.slug}: nicht bestanden (status={sample.get('status')}, "
                f"http={last.get('http_status')}, "
                f"type={last.get('provider_error_type')}, "
                f"request_id={last.get('request_id')})"
            )
        if sample.get("structured_output_mode") != NATIVE_STRUCTURED_OUTPUT:
            problems.append(f"{spec.slug}: nicht über output_config.format")
        if sample.get("tool_envelope_used"):
            problems.append(f"{spec.slug}: Tool-Envelope verwendet")
        if not usage.get("actual_model_id"):
            problems.append(f"{spec.slug}: keine bestätigte Modell-ID")
        if usage.get("cost_status") != "priced":
            problems.append(f"{spec.slug}: Usage/Kosten unvollständig")
        if not last.get("request_id"):
            problems.append(f"{spec.slug}: keine Request-ID")
    report["problems"] = problems
    report["passed"] = not problems
    return (not problems), report


def _pilot_smoke_passed(results_dir: Path) -> tuple[bool, list[str]]:
    """Beide Provider-Smokes vorhanden, succeeded, schema-valide, echt?

    Je Kandidat gilt die jüngste Smoke-Evidenz: der A2-Mini-Smoke
    (``<candidate>__a2mini.json``, Owner-Entscheid nach der A1-Truncation)
    hat Vorrang vor dem A1-Smoke; ältere Fehlversuche bleiben als Historie
    (und im Call-Zähler) liegen.
    """
    problems: list[str] = []
    for candidate in PILOT_A2_CANDIDATES:
        mini = results_dir / "smoke" / f"{candidate}__a2mini.json"
        path = mini if mini.exists() else (
            results_dir / "smoke" / f"{candidate}.json"
        )
        if not path.exists():
            problems.append(f"{candidate}: Smoke fehlt ({path.name})")
            continue
        sample = json.loads(path.read_text(encoding="utf-8"))
        if sample.get("status") != "succeeded" or not sample.get("schema_valid"):
            problems.append(
                f"{candidate}: Smoke nicht bestanden "
                f"(status={sample.get('status')}, reason={sample.get('reason')})"
            )
        if sample.get("silent_fake"):
            problems.append(f"{candidate}: stiller Fake-Wechsel im Smoke")
    return (not problems), problems


# --- A2-Mini-Smoke (Owner-Entscheid 2026-07-16, ersetzt den OpenAI-A1-Smoke) --

PILOT_A2_MINI_PROFILE = "A2.introduction_public_summary"
PILOT_A2_MINI_MAX_OUTPUT = 25000
PILOT_A2_MINI_EFFORT = "low"  # nur OpenAI; Anthropic bleibt Modell-Standard
_A2_MINI_FIELD_ID = "INTRO.APP.ABSTRACT"
# 529-Policy (Owner 2026-07-16): transiente Providerfehler sind kein
# Qualitätsfehler — max 4 Gesamtversuche, Backoff ~10/~30/~60 s mit Jitter,
# Retry-After hat Vorrang; jeder HTTP-Request zählt zum Call-Cap.
_A2_MINI_MAX_ATTEMPTS = 4
_A2_MINI_BACKOFF_SECONDS = (10.0, 30.0, 60.0)

# Kurzer, rein synthetischer D0-Antragstext — keine echten Namen/Zahlenbasen.
_A2_MINI_PROMPT = (
    "Synthetischer Evaluations-Kurzantrag (D0, frei erfunden):\n"
    "Das Projekt QUALIMON entwickelt ein KI-gestütztes Qualitätsmonitoring "
    "für industrielle Fertigungslinien in der Schweiz. Ein Forschungspartner "
    "und ein Umsetzungspartner erproben die Lösung in einer Pilotlinie. "
    "Messbare Zielwerte und Marktzahlen liegen noch nicht vor.\n\n"
    "Aufgabe: Erstelle für das Portalfeld INTRO.APP.ABSTRACT einen kurzen, "
    "öffentlich formulierten Abstract-Vorschlag als strukturiertes JSON gemäss "
    "dem vorgegebenen Schema (draft_candidates mit field_id "
    "INTRO.APP.ABSTRACT, suggested_text max. 300 Zeichen, rationale, leere "
    "evidence_anchor_ids/open_issue_ids; fehlende Angaben als Platzhalter "
    "markieren, keine Zahlen erfinden)."
)


def _a2_mini_fake_bundle() -> str:
    config = resolve_field_config(_A2_MINI_FIELD_ID)
    return json.dumps({
        "draft_candidates": [{
            "field_id": _A2_MINI_FIELD_ID,
            "suggested_text": config.fake_text[: config.char_limit],
            "rationale": "Dry-Run-Fake (pilot a2-mini smoke).",
            "evidence_anchor_ids": [],
            "open_issue_ids": [],
        }],
        "placeholders": [],
        "field_level_warnings": [],
    })


@dataclasses.dataclass(frozen=True)
class _SmokeSpec:
    """Ein kleiner, evaluation-only Smoke-Call gegen ein produktionsnahes
    Schema. ``slug`` bestimmt den Artefaktnamen (``<candidate>__<slug>.json``)."""

    slug: str
    role: str
    profile_id: str
    prompt: str
    # Lazy: der Fake-Bundle-Builder liest die Registry erst beim Dry-Run.
    fake_bundle: Callable[[], str]
    schema_id: str | None = None


# --- Structured-Output-Smokes (Owner 2026-07-17) ------------------------------
# Je ein kleiner Call gegen GENAU die zwei Schemata der Kalibrierung, damit die
# native Oberfläche vor dem Lauf verifiziert ist. Rein synthetisch (D0).

_SO_A2_SECTION = "3.1"
_SO_A2_PROMPT = (
    "Synthetischer Evaluations-Kurzantrag (D0, frei erfunden):\n"
    "Das Projekt QUALIMON entwickelt ein KI-gestütztes Qualitätsmonitoring "
    "für industrielle Fertigungslinien in der Schweiz. Marktzahlen und "
    "Zielwerte liegen noch nicht vor.\n\n"
    "Aufgabe: Liefere für das Portalfeld "
    "VC.BUSINESS_TARGETS_MODEL.EDITOR, Abschnitt 3.1, einen kurzen "
    "Abschnittsvorschlag als strukturiertes JSON gemäss dem vorgegebenen "
    "Schema. Der Text beginnt mit der Abschnittsnummer 3.1, bleibt unter 800 "
    "Zeichen, erfindet keine Zahlen und markiert fehlende Angaben als "
    "missing_inputs."
)
_SO_A3_PROMPT = (
    "Synthetischer Evaluations-Prüftext (D0, frei erfunden):\n"
    "«3.1 Der Zielmarkt wächst stark. Wir erreichen einen Marktanteil von "
    "40 Prozent. Diese Angabe ist noch nicht belegt.»\n\n"
    "Aufgabe: Liefere einen kritischen Review-Hinweis zu diesem Abschnitt als "
    "strukturiertes JSON gemäss dem vorgegebenen Schema (findings mit "
    "severity, description, recommended_next_action; profile_summaries). "
    "Hinweise sind Empfehlungen, nie ein Förderentscheid."
)


def _so_a2_fake_bundle() -> str:
    return json.dumps({
        "section_candidate": {
            "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            "target_section": _SO_A2_SECTION,
            "suggested_text": (
                f"{_SO_A2_SECTION} Zielmarkt und Kundennutzen: "
                "[Angabe ergänzen] — keine belegten Marktzahlen vorhanden."
            ),
            "rationale": "Dry-Run-Fake (structured-output smoke a2).",
            "preserved_facts": [], "removed_or_reframed_claims": [],
            "new_claims": [], "missing_inputs": [],
            "evidence_anchor_ids": [], "research_source_ids": [],
            "open_issue_ids": [],
        },
        "warnings": [],
    })


def _so_a3_fake_bundle() -> str:
    return json.dumps({
        "findings": [{
            "origin_profile_id": "A3.evidence_consistency",
            "severity": "warning", "status": "open",
            "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            "target_section": _SO_A2_SECTION,
            "description": "Marktanteil ist nicht belegt.",
            "suggested_improvement": "Angabe belegen oder als offen markieren.",
            "recommended_next_action": "Beleg ergänzen.",
        }],
        "profile_summaries": [{
            "profile_id": "A3.evidence_consistency", "finding_count": 1,
        }],
        "overall_limitations": [],
    })


_A2_MINI_SPEC = _SmokeSpec(
    slug="a2mini", role="a2", profile_id=PILOT_A2_MINI_PROFILE,
    prompt=_A2_MINI_PROMPT, fake_bundle=_a2_mini_fake_bundle,
)
_SO_A2_SPEC = _SmokeSpec(
    slug="so_a2", role="a2", profile_id="A2.value_creation_market_logic",
    prompt=_SO_A2_PROMPT, fake_bundle=_so_a2_fake_bundle,
    schema_id=SECTION_OUTPUT_SCHEMA_ID,
)
_SO_A3_SPEC = _SmokeSpec(
    slug="so_a3", role="a3", profile_id="A3.evidence_consistency",
    prompt=_SO_A3_PROMPT, fake_bundle=_so_a3_fake_bundle,
    schema_id=A3_OUTPUT_SCHEMA_ID,
)
STRUCTURED_OUTPUT_SMOKE_SPECS = (_SO_A2_SPEC, _SO_A3_SPEC)


def run_pilot_a2_mini_smoke(
    *, candidate_key: str, fake: bool, results_dir: Path | None = None,
    env: dict | None = None,
) -> Path:
    return run_pilot_smoke_call(
        candidate_key=candidate_key, spec=_A2_MINI_SPEC, fake=fake,
        results_dir=results_dir, env=env,
    )


def run_pilot_smoke_call(
    *, candidate_key: str, spec: _SmokeSpec, fake: bool,
    results_dir: Path | None = None, env: dict | None = None,
) -> Path:
    """Evaluation-only Smoke über den produktiven Provider-Adapter: kurzer
    synthetischer Text, ein ECHTES Produktionsschema inkl. produktiver
    Schema-Validierung, reasoning.effort=low (nur OpenAI),
    max_output_tokens=25000, maximal 1 Versuch + 1 Contract-Retry. Die
    Schema-Oberfläche kommt aus der abgeleiteten Pilot-Registry (Anthropic:
    native Structured Outputs). Kein Gateway-/Contract-/Prompt-Asset-Eingriff —
    Konfiguration ausschliesslich in diesem Pilot-Pfad.

    ``response.status=incomplete`` mit ``incomplete_details.reason=
    max_output_tokens`` (Adapter: ``termination_reason``) wird ausdrücklich
    als ``truncated`` klassifiziert. Vor dem Call wird eine konservative
    Kostenreservierung (Invocation-Maximum) gegen das Budget geprüft und
    nach dem Call mit der gemessenen Usage reconciliert.
    """
    import os
    import time as _time

    from app.agents import cost_guard
    from app.agents.gateway import json_schema_for, validate_payload

    settings = get_settings()
    results_dir = results_dir or default_pilot_results_dir()
    path = results_dir / "smoke" / f"{candidate_key}__{spec.slug}.json"
    if path.exists():
        return path
    registry = _pilot_registry(spec.role, candidate_key)
    route = registry.route(candidate_key)
    refusal = guard_for_candidate(
        route, env=env if env is not None else os.environ,
        settings=settings, fake=fake,
    )
    if refusal:
        raise EvalRefusal(refusal)
    requested = route.requested_model_id(settings) or "role-eval-fake"

    # Konservative Vorab-Reservierung (Invocation-Maximum) gegen das Budget.
    if not fake:
        estimate = cost_guard.estimated_upper_cost(
            provider=route.provider, model_id=requested,
            prompt=spec.prompt,
            max_output_tokens=PILOT_A2_MINI_MAX_OUTPUT,
        )
        if estimate.cost_status != "priced":
            raise EvalRefusal(
                f"Smoke {spec.slug}: Kostenobergrenze nicht bepreisbar "
                f"({estimate.cost_status}) — kein Blindflug."
            )
        if estimate.cost_chf > PILOT_MAX_COST_PER_CALL_CHF:
            raise EvalRefusal(
                f"Smoke {spec.slug}: Invocation-Obergrenze über dem Limit von "
                f"{PILOT_MAX_COST_PER_CALL_CHF} CHF."
            )
        totals = _pilot_budget_guard(
            results_dir, planned_calls=_A2_MINI_MAX_ATTEMPTS, fake=fake
        )
        if (
            totals["cost_chf_total_conservative"]
            + _A2_MINI_MAX_ATTEMPTS * estimate.cost_chf
            > PILOT_MAX_COST_CHF
        ):
            raise EvalRefusal(
                f"Smoke {spec.slug}: konservative Reservierung überschreitet "
                f"das Kostenlimit ({PILOT_MAX_COST_CHF} CHF)."
            )

    schema_id = spec.schema_id or registry.profile(spec.profile_id).output_schema
    structured_output_mode = (route.capabilities or {}).get(
        "structured_output_mode"
    )
    request = ProviderRequest(
        model_id=requested,
        prompt=spec.prompt,
        output_schema_id=schema_id,
        timeout_seconds=180,
        max_output_tokens=PILOT_A2_MINI_MAX_OUTPUT,
        output_json_schema=json_schema_for(schema_id),
        # Owner-Vorgabe: effort=low nur für OpenAI; Anthropic ohne manuelles
        # effort-Feld (adaptiver Modell-Standard; Adapter überträgt es nie).
        reasoning_effort=(
            PILOT_A2_MINI_EFFORT
            if route.provider == "openai_direct" else None
        ),
        structured_output_mode=structured_output_mode,
    )
    adapter = (
        FakeProvider(raw_output=spec.fake_bundle())
        if fake
        else (
            OpenAIProvider()
            if route.provider == "openai_direct" else AnthropicProvider()
        )
    )

    attempts: list[dict] = []
    status, schema_valid = "failed", False
    schema_retry_used = False
    for attempt_no in range(1, _A2_MINI_MAX_ATTEMPTS + 1):
        started = _time.monotonic()
        entry: dict = {"attempt": attempt_no}
        try:
            result = adapter.generate(request)
        except Exception as exc:  # ProviderError/Timeout — nie Rohinhalte
            code = getattr(exc, "code", "provider_error")
            retry_after = getattr(exc, "retry_after_seconds", None)
            entry.update({
                "status": "failed", "error_code": code,
                "request_id": getattr(exc, "request_id", None),
                "retry_after_seconds": retry_after,
                "latency_ms": int((_time.monotonic() - started) * 1000),
                # 4xx-Diagnose (Owner): Status, Typ, redigierte Meldung.
                "http_status": getattr(exc, "status_code", None),
                "provider_error_type": getattr(exc, "error_type", None),
                "provider_message": getattr(exc, "provider_message", None),
            })
            attempts.append(entry)
            # 529-Policy: transiente Fehler mit Backoff+Jitter erneut versuchen.
            if (
                getattr(exc, "retryable", False)
                and attempt_no < _A2_MINI_MAX_ATTEMPTS
                and not fake
            ):
                backoff = _A2_MINI_BACKOFF_SECONDS[
                    min(attempt_no - 1, len(_A2_MINI_BACKOFF_SECONDS) - 1)
                ]
                delay = (
                    float(retry_after)
                    if retry_after
                    else backoff + random.uniform(0.0, 3.0)
                )
                entry["retry_delay_seconds"] = round(delay, 1)
                _time.sleep(delay)
                continue
            break
        latency_ms = int((_time.monotonic() - started) * 1000)
        cost = cost_guard.resolve_cost(
            provider=route.provider, model_id=requested,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            adapter_name=getattr(adapter, "name", None),
        )
        truncated = result.termination_reason in (
            "max_tokens", "max_output_tokens"
        )
        entry.update({
            "latency_ms": latency_ms,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "reasoning_tokens": result.usage.reasoning_tokens,
            "cost_chf": cost.cost_chf,
            "cost_status": cost.cost_status,
            "actual_model_id": result.model,
            "request_id": result.request_id,
            "termination_reason": result.termination_reason,
        })
        if truncated:
            entry["status"] = "truncated"
            attempts.append(entry)
            status = "truncated"
            break  # Retry mit identischem Budget wäre Geldverbrennung.
        try:
            validate_payload(schema_id, json.loads(result.raw_output))
            entry["status"] = "succeeded"
            attempts.append(entry)
            status, schema_valid = "succeeded", True
            break
        except Exception:
            entry["status"] = "schema_invalid"
            attempts.append(entry)
            # Genau EIN Contract-Retry bei Schema-Fehlern (wie im Gateway).
            if not schema_retry_used and attempt_no < _A2_MINI_MAX_ATTEMPTS:
                schema_retry_used = True
                continue
            break

    priced = [a for a in attempts if a.get("cost_status") == "priced"]
    sample = {
        "role": f"{spec.role}_smoke" if spec.slug != "a2mini" else "a2_mini_smoke",
        "smoke_slug": spec.slug,
        "candidate": candidate_key,
        "phase": "pilot_smoke",
        "execution": _EXECUTION_FAKE if fake else _EXECUTION_REAL,
        "api_surface": (
            "openai responses (adapter openai_direct)"
            if route.provider == "openai_direct"
            else "anthropic messages (adapter anthropic_direct)"
        ),
        "structured_output_mode": _route_structured_output_mode(route),
        "tool_envelope_used": (
            route.provider == "anthropic_direct"
            and structured_output_mode != NATIVE_STRUCTURED_OUTPUT
        ),
        "profile_id": spec.profile_id,
        "output_schema": schema_id,
        "reasoning_effort": PILOT_A2_MINI_EFFORT,
        "max_output_tokens": PILOT_A2_MINI_MAX_OUTPUT,
        "requested_model_id": (
            route.requested_model_id(settings) if not fake else requested
        ),
        "status": status,
        "schema_valid": schema_valid,
        "llm_calls": len(attempts),
        "attempts": attempts,
        "usage": {
            "input_tokens": sum(a.get("input_tokens") or 0 for a in attempts),
            "output_tokens": sum(a.get("output_tokens") or 0 for a in attempts),
            "reasoning_tokens": sum(
                a.get("reasoning_tokens") or 0 for a in attempts
            ),
            "cost_chf": (
                round(sum(a.get("cost_chf") or 0.0 for a in priced), 6)
                if priced else None
            ),
            "cost_status": (
                "priced" if priced and len(priced) == len([
                    a for a in attempts if "input_tokens" in a
                ]) else ("not_applicable" if fake else "unknown_price")
            ),
            "actual_model_id": next(
                (a.get("actual_model_id") for a in reversed(attempts)
                 if a.get("actual_model_id")), None
            ),
            "latency_ms": sum(a.get("latency_ms") or 0 for a in attempts),
        },
        "silent_fake": bool(fake) is False and isinstance(adapter, FakeProvider),
    }
    _write_pilot_sample(path, sample, prompt_sha=prompt_fingerprint())
    return path


def _fake_a2_section_adapter(gold: scoring.CaseGold, field_id: str, section: str):
    term = gold.required_terms[0] if gold.required_terms else "Projekt"
    text = (
        f"{section} {term}: kompakter, strukturierter Abschnittsvorschlag "
        "auf Basis der vorliegenden Angaben; fehlende Angaben bleiben als "
        "[Platzhalter] markiert, ohne neue Zahlen oder Organisationen."
    )
    bundle = {
        "section_candidate": {
            "field_id": field_id,
            "target_section": section,
            "suggested_text": text,
            "rationale": "Dry-Run-Fake (pilot a2 section).",
            "preserved_facts": [],
            "removed_or_reframed_claims": [],
            "new_claims": [],
            "missing_inputs": [],
            "evidence_anchor_ids": [],
            "research_source_ids": [],
            "open_issue_ids": [],
        },
        "warnings": [],
    }
    return FakeProvider(raw_output=json.dumps(bundle))


def _a2_text_from_raw(raw_outputs) -> str:
    """Vorschlagstext aus dem Roh-Bundle — auch wenn ein INHALTS-Gate den
    Output abgelehnt hat (Owner Block 5/8).

    Ein erfundener Referenz-Identifier macht den Text nicht unlesbar: er bleibt
    technisch valide und blind bewertbar. Ohne diese Bergung fiele genau die
    Textqualität aus der Blindbewertung, die beurteilt werden soll. Für
    schema-invalide Ausgaben gibt es keinen Text — dann bleibt es dabei.
    """
    for raw in reversed(list(raw_outputs or [])):
        try:
            candidate = (json.loads(raw) or {}).get("section_candidate") or {}
        except (json.JSONDecodeError, TypeError):
            continue
        text = str(candidate.get("suggested_text") or "").strip()
        if text:
            return text
    return ""


def _route_structured_output_mode(route) -> str:
    """Wie das Schema an den Provider geht — Auditspur im Artefakt."""
    mode = (route.capabilities or {}).get("structured_output_mode")
    if mode:
        return mode
    return (
        "openai_responses_strict_json_schema"
        if route.provider == "openai_direct" else "anthropic_forced_tool_use"
    )


def _pilot_provider(route, *, fake_adapter, schema_patch, limit):
    """Pilot-Resolver: echter/fake Adapter → Schema-Patch-Wrapper →
    Counting-Cap. Liefert (resolver, counting_proxy, patch_proxy)."""
    inner = fake_adapter or (
        OpenAIProvider() if route.provider == "openai_direct"
        else AnthropicProvider()
    )
    patch_proxy = _SchemaPatchAdapter(inner, schema_patch)
    proxy = _CountingAdapter(patch_proxy, limit=limit, adapter_name=route.provider)
    if fake_adapter is not None:
        proxy._hermetic_test_model_id = "role-eval-fake"
    return (lambda r: proxy if r.key == route.key else None), proxy, patch_proxy


@dataclasses.dataclass(frozen=True)
class _SeededA2Section:
    """Der geseedete Fall EINES A2-Abschnittslaufs — identisch für den
    Live-Lauf und die Offline-Neubewertung (kein Provider-Call nötig)."""

    gold: scoring.CaseGold
    fragments: list[dict]
    section: str
    config: object
    run: AnalysisRun
    draft_id: str
    version_id: str
    fact_count: int
    draft_normalized: bool


def _seed_a2_section_case(
    db, *, case_id: str, field_id: str, rep: int, cases_dir: Path | None = None,
) -> _SeededA2Section:
    """Fall, Fakten, Quellen, Draft und Research-Kontext eines A2-Abschnitts-
    laufs seeden. Rein deterministisch bis auf den Namensraum-Tag der IDs."""
    gold = scoring.load_case_gold(case_id, cases_dir)
    fragments = scoring.load_case_fragments(case_id, cases_dir)
    section = PILOT_SECTIONS[field_id]
    config = resolve_field_config(field_id)
    tag = (
        f"a2s-{case_id.lower()}-{section.replace('.', '')}-"
        f"r{rep}-{uuid.uuid4().hex[:6]}"
    )

    _ensure_base_rows(db)
    project = _seed_project(db, gold, tag)
    run = _seed_run(db, project, stage="draft_fields", confirm=True)
    _seed_snapshot_fragments(db, run, fragments, tag)
    fact_count = _seed_case_facts(db, run, gold, tag)
    full_text = a3_draft_texts(fragments)[field_id]
    # Altstruktur-Fälle: die Falltexte tragen die Registry-Marker nicht
    # vollständig (F1: gar keine; F2/H1-SOL: Altschema 4.5 statt 4.5.1–4.6).
    # Der produktive Section-Pfad verlangt die VOLLSTÄNDIGE, geordnete
    # Markerstruktur. Deterministische Normalisierung (Registry-Reihenfolge,
    # Volltext unter dem Ziel-Marker), identisch für beide Kandidaten;
    # ausgewiesen im Sample. Vollständig strukturierte Texte bleiben unberührt.
    def _has_marker(text: str, marker: str) -> bool:
        return bool(re.search(rf"^\s*{re.escape(marker)}\b", text, re.M))

    present = [m for m in config.mandatory_markers if _has_marker(full_text, m)]
    missing = [m for m in config.mandatory_markers if m not in present]
    draft_normalized = bool(missing)
    if missing and present:
        # Teilstruktur (Altschema, z. B. 4.5 statt 4.5.1–4.6): nur die
        # fehlenden Marker mit ehrlichem Hinweis anhängen.
        full_text = full_text.rstrip() + "".join(
            f"\n\n{marker} [Kein separater Abschnitt im Altantrag.]"
            for marker in missing
        )
    elif missing:
        # Gar keine Marker (F1-Altstruktur): Registry-Rahmen, Volltext unter
        # dem Ziel-Marker.
        parts = []
        for marker in config.mandatory_markers:
            if marker == section:
                parts.append(f"{marker} {full_text.strip()}")
            else:
                parts.append(
                    f"{marker} [Kein separater Abschnitt im Altantrag — "
                    f"Inhalt siehe {section}.]"
                )
        full_text = "\n\n".join(parts)
    draft_id, version_id = _seed_field_draft(db, run, field_id, full_text)
    _seed_research_context(db, field_id, project)
    return _SeededA2Section(
        gold=gold, fragments=fragments, section=section, config=config,
        run=run, draft_id=draft_id, version_id=version_id,
        fact_count=fact_count, draft_normalized=draft_normalized,
    )


def _a2_manifest_and_language(
    db, seeded: _SeededA2Section, *, field_id: str
) -> tuple[object, str, str]:
    """Erlaubt-Basis + kanonische Sprache EXAKT so, wie sie der produktive
    Lauf gesehen hat: dieselbe Kontextmontage (reiner Lesevorgang auf dem
    geseedeten Stand), dieselben Helfer, keine Evaluations-Zweitwahrheit."""
    from app.agents import field_drafting_context as a2_context

    ctx = a2_context.assemble_a2_context(
        db, seeded.run, field_id=field_id,
        profile_id=seeded.config.profile_id,
        target_section=seeded.section,
        section_markers=seeded.config.mandatory_markers,
    )
    manifest = a2_context.build_allowed_facts(
        ctx, a2_context.build_input_payload(ctx, seeded.run.run_id)
    )
    language, language_source = scoring.resolve_expected_language(
        seeded.gold, draft_language=ctx.language,
    )
    return manifest, language, language_source


def run_pilot_a2_section_sample(
    db, *, case_id: str, candidate_key: str, field_id: str, rep: int,
    fake: bool, cases_dir: Path | None = None,
) -> dict:
    """A2-Pilot auf Abschnittsebene (Owner Block 2/3): der PRODUKTIVE
    Section-Redraft-Pfad (``run_a2_field_drafting`` mit ``target_section``)
    auf dem eingefrorenen Falltext als Draft-Basis; Fall-Fragmente als
    versionierter Quellenkontext + Gold-Fakten als advisory (applicant)
    Facts; Feld-ID/Section im nativen Schema als const gebunden."""
    seeded = _seed_a2_section_case(
        db, case_id=case_id, field_id=field_id, rep=rep, cases_dir=cases_dir,
    )
    gold, section, config = seeded.gold, seeded.section, seeded.config
    run, draft_id, version_id = seeded.run, seeded.draft_id, seeded.version_id
    registry = _pilot_registry("a2", candidate_key)
    route = registry.route(candidate_key)
    profile = registry.profile(config.profile_id)
    limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL

    resolver, proxy, patch_proxy = _pilot_provider(
        route,
        fake_adapter=(
            _fake_a2_section_adapter(gold, field_id, section) if fake else None
        ),
        schema_patch=_patch_field_section_const(field_id, section),
        limit=limit,
    )
    with mock.patch(
        "app.agents.gateway.get_agent_registry", return_value=registry
    ):
        outcome = field_drafting.run_a2_field_drafting(
            db, run, field_id=field_id, draft_id=draft_id,
            base_version_id=version_id,
            operation_id="rme-op-" + uuid.uuid4().hex[:8],
            target_section=section, provider_resolver=resolver,
        )
    db.commit()
    if not fake and proxy.calls == 0:
        raise SmokeFailure(
            f"Pilot-A2 {field_id}/{section}: kein Provider-Call — Policy/"
            "Verfügbarkeit hat blockiert (kein stiller Fallback)."
        )

    usage = _usage_for_invocation(db, outcome.invocation_id)
    view = outcome.view or {}
    text = view.get("suggested_text") or ""
    valid_output = outcome.status in ("succeeded", "reused") and bool(text.strip())
    reject_reason = None if valid_output else (outcome.reason or outcome.status)
    # An einem Inhaltsgate abgelehnte Vorschläge tragen weiterhin einen
    # lesbaren Text — er wird geborgen, bewertet und blind vorgelegt.
    blind_text = text.strip() or _a2_text_from_raw(proxy.raw_outputs)
    manifest, expected_language, language_source = _a2_manifest_and_language(
        db, seeded, field_id=field_id
    )
    if valid_output:
        gates = scoring.a2_gate_results(
            text,
            schema_valid=True,
            required_terms=gold.required_terms,
            expected_markers=(section,),
            char_limit=config.char_limit,
            manifest=manifest,
            expected_language=expected_language,
            missing_inputs_count=len(
                (view.get("proposal") or {}).get("missing_inputs") or []
            ),
            human_review_required=bool(
                (view.get("proposal") or {}).get("human_review_required", True)
            ),
            allowed_sources=_ALLOWED_SOURCES,
        )
        fatal = scoring.fatal_gate_results(
            text, manifest=manifest, allowed_sources=_ALLOWED_SOURCES,
            evidence_ref_violations=0, silent_fake_detected=_silent_fake(
                usage, execution=execution
            ),
            foreign_markers=tuple(
                m for fid, m_sec in PILOT_SECTIONS.items()
                if fid != field_id for m in (m_sec,)
            ),
        )
    else:
        gates, fatal = [], []
    claim_check = dict(outcome.claim_check or {})
    hard_dq = scoring.a2_hard_disqualifications(
        gates, fatal, reject_reason=reject_reason,
        routing_metadata_mismatch=bool(claim_check.get("routing_metadata_mismatch")),
    )
    # Technische Schemavalidität ist NICHT «alle Gates grün»: ein Bundle, das
    # der Gateway-Validierung standhielt, ist schema-valide — auch wenn es
    # danach an einem Inhaltsgate scheitert (Owner 2026-07-17, Option A).
    schema_valid = bool(proxy.raw_outputs) and scoring.a2_reject_reason_to_dq(
        reject_reason
    ) not in ("dq_schema_error", "dq_tool_contract_error", "dq_truncated_output")
    dimensions = scoring.sample_status_dimensions(
        execution=execution,
        silent_fake=_silent_fake(usage, execution=execution),
        schema_valid=schema_valid,
        routing_metadata_source=claim_check.get("routing_metadata_source"),
        usage=usage,
        hard_dq=hard_dq,
        has_readable_output=bool(blind_text),
    )
    field_entry = {
        "field_id": field_id,
        "target_section": section,
        "status": "generated" if valid_output else "failed",
        "valid_output": valid_output,
        "reject_reason": reject_reason,
        "claim_check": claim_check,
        "model": usage.get("actual_model_id"),
        "gates": gates,
        "gates_passed": scoring.gates_passed(gates) if valid_output else False,
        "fatal": fatal,
        "fatal_candidate": scoring.fatal_candidate(fatal),
        "hard_dq": hard_dq,
        "usage": usage,
        "missing_inputs_count": len(
            (view.get("proposal") or {}).get("missing_inputs") or []
        ),
        "human_review_required": True,
        "llm_calls": proxy.calls,
        **dimensions,
    }
    return {
        "role": "a2", "candidate": candidate_key, "case": case_id, "rep": rep,
        "field_id": field_id, "target_section": section,
        "phase": "pilot", "execution": execution,
        "requested_model_id": route.requested_model_id(get_settings()),
        "status": "succeeded" if valid_output else "invalid_output",
        "reject_reason": reject_reason,
        "hard_dq": hard_dq,
        **dimensions,
        "seeded_fact_count": seeded.fact_count,
        "draft_marker_normalized": seeded.draft_normalized,
        "structured_output_mode": _route_structured_output_mode(route),
        "routing_metadata_source": claim_check.get("routing_metadata_source"),
        "expected_language": expected_language,
        "language_source": language_source,
        "claim_check": claim_check,
        "allowed_facts": manifest.meta(),
        "schema_patch": {
            "base": SECTION_OUTPUT_SCHEMA_ID,
            "variant": "pilot-const-v1",
            "sha256": patch_proxy.patched_schema_sha,
        },
        "request_ids": list(patch_proxy.request_ids),
        "tool_wrapper_normalized": patch_proxy.wrapper_normalized,
        "fields": [field_entry],
        "raw": {"fields": [{
            "field_id": field_id,
            "suggestion_text": blind_text or None,
            "suggestion_text_source": (
                "accepted_view" if valid_output and text.strip()
                else ("recovered_from_rejected_bundle" if blind_text else None)
            ),
            "raw_outputs": list(proxy.raw_outputs),
        }]},
    }


def _fake_a3_fixed_adapter(field_id: str, section: str, flaws) -> FakeProvider:
    findings = [{
        "origin_profile_id": "A3.evidence_consistency",
        "severity": "warning", "status": "open",
        "field_id": field_id, "target_section": section,
        "description": "Bekannte Schwäche: " + " ".join(kw[:3]),
        "suggested_improvement": "Angabe belegen oder als offen kennzeichnen.",
        "recommended_next_action": "Beleg ergänzen oder Aussage streichen.",
    } for _flaw_id, _sentence, kw in flaws]
    return FakeProvider(raw_output=json.dumps({
        "findings": findings,
        "profile_summaries": [{
            "profile_id": "A3.evidence_consistency",
            "finding_count": len(findings),
        }],
        "overall_limitations": [],
    }))


def run_pilot_a3_fixed_sample(
    db, *, case_id: str, candidate_key: str, field_id: str, rep: int,
    fake: bool, cases_dir: Path | None = None,
) -> dict:
    """Fairer A3-Vergleich (Owner Block 5/6): beide Kandidaten prüfen je Fall
    DENSELBEN eingefrorenen Fixed Draft (Falltext + goldmarkierte injizierte
    Schwächen). target_section ist im nativen Schema auf den kanonischen
    Marker beschränkt; der Produktionsfilter wird transparent gezählt.

    Verwirft der Filter ALLE empfangenen Findings, ist der Status
    ``not_evaluable`` — NIE false_consensus; Schwächen-Detektion wird nur bei
    evaluierbarem Output berechnet."""
    gold = scoring.load_case_gold(case_id, cases_dir)
    section = PILOT_SECTIONS[field_id]
    text, flaws = pilot_fixed_draft(case_id, field_id, cases_dir=cases_dir)
    registry = _pilot_registry("a3", candidate_key)
    route = registry.route(candidate_key)
    profile = registry.profile("A3.evidence_consistency")
    limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL

    _ensure_base_rows(db)
    project = _seed_project(db, gold, f"a3x-{case_id.lower()}-r{rep}")
    run = _seed_run(db, project, stage="critic_review", confirm=True)
    _seed_a3_drafts(db, run, {field_id: text})
    resolver, proxy, patch_proxy = _pilot_provider(
        route,
        fake_adapter=(
            _fake_a3_fixed_adapter(field_id, section, flaws) if fake else None
        ),
        schema_patch=_patch_field_section_const(field_id, section),
        limit=limit,
    )
    with mock.patch(
        "app.agents.gateway.get_agent_registry", return_value=registry
    ):
        outcome = run_a3_evidence_consistency(
            db, run, provider_resolver=resolver,
            # Review EINES Abschnitts ⇒ der Caller bindet die Routing-IDs.
            bound_routing={"field_id": field_id, "target_section": section},
        )
    db.commit()

    usage = _usage_for_invocation(db, outcome.invocation_id)
    stats = dict(outcome.filter_stats or {})
    findings = [dict(f.__dict__) for f in outcome.findings]
    if outcome.status != "succeeded":
        status = "invalid_output"
        reject_reason = outcome.reason or "invalid_output"
    elif stats.get("received", 0) > 0 and stats.get("accepted", 0) == 0:
        # Owner: alle Findings gefiltert ⇒ not_evaluable, nie false_consensus.
        status = "not_evaluable"
        reject_reason = "all_findings_filtered"
    else:
        status = "succeeded"
        reject_reason = None
    evaluable = status == "succeeded"
    flaw_detection = None
    if evaluable:
        flaw_detection = {}
        for flaw_id, _sentence, keywords in flaws:
            flaw_detection[flaw_id] = any(
                scoring.keyword_ratio(
                    " ".join(str(f.get(k) or "") for k in (
                        "description", "suggested_improvement",
                        "recommended_next_action",
                    )),
                    keywords,
                ) >= 0.34
                for f in findings
            )
    dq = scoring.a2_reject_reason_to_dq(reject_reason)
    dimensions = scoring.sample_status_dimensions(
        execution=execution,
        silent_fake=_silent_fake(usage, execution=execution),
        # Ein Bundle, das die Gateway-Validierung passiert hat, ist
        # schema-valide — auch wenn der Filter danach alles verwirft.
        schema_valid=outcome.status == "succeeded",
        routing_metadata_source=stats.get("routing_metadata_source"),
        usage=usage,
        hard_dq=(dq,) if dq else (),
        has_readable_output=bool(findings),
    )
    return {
        "role": "a3_fair", "candidate": candidate_key, "case": case_id,
        "rep": rep, "field_id": field_id, "target_section": section,
        "phase": "pilot", "execution": execution,
        "requested_model_id": route.requested_model_id(get_settings()),
        "status": status,
        "reject_reason": reject_reason,
        "dq": dq,
        **dimensions,
        "structured_output_mode": _route_structured_output_mode(route),
        "routing_metadata_source": stats.get("routing_metadata_source"),
        "filter_stats": stats,
        "flaw_detection": flaw_detection,
        "flaws_detected": (
            sum(1 for hit in (flaw_detection or {}).values() if hit)
            if evaluable else None
        ),
        "flaws_total": len(flaws),
        "funding_decision_claims": scoring.funding_decision_claims(findings),
        "finding_count": len(findings),
        "llm_calls": proxy.calls,
        "usage": usage,
        "silent_fake": _silent_fake(usage, execution=execution),
        "schema_patch": {
            "base": A3_OUTPUT_SCHEMA_ID,
            "variant": "pilot-const-v1",
            "sha256": patch_proxy.patched_schema_sha,
        },
        "request_ids": list(patch_proxy.request_ids),
        "tool_wrapper_normalized": patch_proxy.wrapper_normalized,
        "raw": {
            "findings": findings,
            "raw_outputs": list(proxy.raw_outputs),
        },
    }


def run_pilot_a3_cross(
    db, *, case_id: str, a2_candidate: str, critic_candidate: str,
    field_id: str, draft_text: str, fake: bool,
    cases_dir: Path | None = None,
) -> dict:
    """Workflow-Smoke (Multi-Agent-Nachweis): der jeweils ANDERE Kandidat
    prüft einen VALIDEN A2-Abschnittsvorschlag. NIE eine alleinige
    A3-Rangfolge-Quelle; keine Gold-/Flaw-Referenz (frischer Modelltext)."""
    gold = scoring.load_case_gold(case_id, cases_dir)
    section = PILOT_SECTIONS[field_id]
    registry = _pilot_registry("a3", critic_candidate)
    route = registry.route(critic_candidate)
    profile = registry.profile("A3.evidence_consistency")
    limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL

    _ensure_base_rows(db)
    project = _seed_project(db, gold, f"a3w-{case_id.lower()}")
    run = _seed_run(db, project, stage="critic_review", confirm=True)
    _seed_a3_drafts(db, run, {field_id: draft_text})
    resolver, proxy, patch_proxy = _pilot_provider(
        route,
        fake_adapter=(
            _fake_a3_fixed_adapter(
                field_id, section, PILOT_FIXED_FLAWS[field_id][:1]
            ) if fake else None
        ),
        schema_patch=_patch_field_section_const(field_id, section),
        limit=limit,
    )
    with mock.patch(
        "app.agents.gateway.get_agent_registry", return_value=registry
    ):
        outcome = run_a3_evidence_consistency(
            db, run, provider_resolver=resolver,
            bound_routing={"field_id": field_id, "target_section": section},
        )
    db.commit()
    usage = _usage_for_invocation(db, outcome.invocation_id)
    findings = [dict(f.__dict__) for f in outcome.findings]
    return {
        "role": "a3_cross", "candidate": critic_candidate,
        "reviewed_candidate": a2_candidate, "case": case_id, "rep": 1,
        "field_id": field_id, "target_section": section,
        "phase": "pilot", "execution": execution,
        "requested_model_id": route.requested_model_id(get_settings()),
        "status": outcome.status,
        "reason": outcome.reason or None,
        "gold_scoring": "not_applicable (Workflow-Smoke über A2-Output)",
        "filter_stats": dict(outcome.filter_stats or {}),
        "finding_count": len(findings),
        "funding_decision_claims": scoring.funding_decision_claims(findings),
        "llm_calls": proxy.calls,
        "usage": usage,
        "silent_fake": _silent_fake(usage, execution=execution),
        "request_ids": list(patch_proxy.request_ids),
        "tool_wrapper_normalized": patch_proxy.wrapper_normalized,
        "raw": {
            "findings": findings,
            "raw_outputs": list(proxy.raw_outputs),
        },
    }


def _pilot_alias(route_key: str) -> str:
    # Kurzalias für Verzeichnisnamen (Windows-MAX_PATH; OneDrive-Basis
    # ist bereits lang) — eindeutig, da die Kandidaten-Keys es sind.
    return route_key.removesuffix("_candidate")


def execute_pilot_run(
    db_factory, *, fake: bool, allow_holdout: bool,
    results_dir: Path | None = None, cases_dir: Path | None = None,
    env: dict | None = None,
    cases: tuple[str, ...] | None = None,
    reps: int | None = None,
    include_cross: bool = True,
) -> list[Path]:
    """Erweiterte Phase 2 (Owner 2026-07-16, korrigierter Harness):

    - A2: Kandidat × Fall × Section (VC 3.1 / SOL 4.2) × Replikationen über
      den produktiven Section-Redraft-Pfad (identischer Snapshot/Fakten/
      Quellen/Skill/Schema/Zeichenbudget; Feld-ID im Schema const-gebunden).
    - A3 fair: identische Fixed Drafts (goldmarkierte Schwächen) je (Fall,
      Section) für beide Kandidaten; not_evaluable statt false_consensus bei
      vollständig gefiltertem Output.
    - Workflow-Smoke (optional): genau 2 Cross-Läufe auf je einem VALIDEN
      A2-Output — Multi-Agent-Nachweis, nie Rangfolge.

    ``db_factory`` liefert je Sample eine frische Session (wie die CLI-Läufe).
    ``cases``/``reps``/``include_cross`` erlauben den Kalibrierungs-Teilraum
    (F1, rep 1) — die Artefaktpfade sind identisch, der Voll-Lauf überspringt
    Kalibrierungs-Samples (Idempotenz, keine Doppel-Calls)."""
    import os

    settings = get_settings()
    results_dir = results_dir or default_pilot_results_dir()
    if not fake:
        ok, problems = _pilot_smoke_passed(results_dir)
        if not ok:
            raise EvalRefusal(
                "Pilot-Phase 2 verweigert — Phase-1-Smokes nicht bestanden: "
                + "; ".join(problems)
            )
    if "H1" in (cases or PILOT_CASES) and not allow_holdout:
        raise EvalRefusal(
            "H1 ist HOLDOUT — Pilot-Ausführung nur mit --allow-holdout."
        )
    for route_key in PILOT_A2_CANDIDATES:
        registry = _pilot_registry("a2", route_key)
        refusal = guard_for_candidate(
            registry.route(route_key),
            env=env if env is not None else os.environ,
            settings=settings, fake=fake,
        )
        if refusal:
            raise EvalRefusal(refusal)
    prompt_sha = prompt_fingerprint()
    written: list[Path] = []

    def _run_sample(path: Path, planned_calls: int, runner) -> None:
        if path.exists():
            return
        if prompt_fingerprint() != prompt_sha:
            raise EvalRefusal("Prompt-Freeze verletzt — Pilot-Stopp.")
        _pilot_budget_guard(
            results_dir, planned_calls=planned_calls, fake=fake
        )
        db = db_factory()
        try:
            sample = runner(db)
        finally:
            db.close()
        _write_pilot_sample(path, sample, prompt_sha=prompt_sha)
        written.append(path)

    def _sec_slug(field_id: str) -> str:
        return PILOT_SECTIONS[field_id].replace(".", "")

    def _a2_path(candidate, case_id, field_id, rep) -> Path:
        return (
            results_dir / "runs" / "a2" / _pilot_alias(candidate)
            / case_id / f"s{_sec_slug(field_id)}_rep{rep}.json"
        )

    def _a3_path(candidate, case_id, field_id, rep) -> Path:
        return (
            results_dir / "runs" / "a3_fair" / _pilot_alias(candidate)
            / case_id / f"s{_sec_slug(field_id)}_rep{rep}.json"
        )

    cases = cases or PILOT_CASES
    reps = reps or PILOT_REPS

    # --- A2: Kandidaten × Fälle × Sections × Replikationen -------------------
    for case_id in cases:
        for candidate in PILOT_A2_CANDIDATES:
            for field_id in PILOT_FIELDS:
                for rep in range(1, reps + 1):
                    def _a2_runner(
                        db, case_id=case_id, candidate=candidate,
                        field_id=field_id, rep=rep,
                    ):
                        ensure_route_preflight(db, candidate, fake=fake)
                        return run_pilot_a2_section_sample(
                            db, case_id=case_id, candidate_key=candidate,
                            field_id=field_id, rep=rep, fake=fake,
                            cases_dir=cases_dir,
                        )

                    _run_sample(
                        _a2_path(candidate, case_id, field_id, rep),
                        2, _a2_runner,
                    )

    # --- A3 fair: identische Fixed Drafts je (Fall, Section) -----------------
    for case_id in cases:
        for candidate in PILOT_A2_CANDIDATES:
            for field_id in PILOT_FIELDS:
                for rep in range(1, reps + 1):
                    def _a3_runner(
                        db, case_id=case_id, candidate=candidate,
                        field_id=field_id, rep=rep,
                    ):
                        ensure_route_preflight(db, candidate, fake=fake)
                        return run_pilot_a3_fixed_sample(
                            db, case_id=case_id, candidate_key=candidate,
                            field_id=field_id, rep=rep, fake=fake,
                            cases_dir=cases_dir,
                        )

                    _run_sample(
                        _a3_path(candidate, case_id, field_id, rep),
                        2, _a3_runner,
                    )

    if not include_cross:
        return written

    # --- Workflow-Smoke: je Richtung genau EIN Cross-Lauf auf einem VALIDEN
    #     A2-Output (bevorzugt F1; nie alleinige Rangfolge-Quelle) -----------
    for candidate in PILOT_A2_CANDIDATES:
        critic = next(c for c in PILOT_A2_CANDIDATES if c != candidate)
        cross_path = (
            results_dir / "runs" / "a3x"
            / f"{_pilot_alias(critic)}__on__{_pilot_alias(candidate)}"
            / "rep1.json"
        )
        if cross_path.exists():
            continue
        chosen = None
        for case_id in cases:
            for field_id in PILOT_FIELDS:
                for rep in range(1, reps + 1):
                    path = _a2_path(candidate, case_id, field_id, rep)
                    if not path.exists():
                        continue
                    sample = json.loads(path.read_text(encoding="utf-8"))
                    text = (
                        (sample.get("raw", {}).get("fields") or [{}])[0]
                        .get("suggestion_text") or ""
                    )
                    if sample.get("status") == "succeeded" and text.strip():
                        chosen = (case_id, field_id, text)
                        break
                if chosen:
                    break
            if chosen:
                break
        if chosen is None:
            _write_pilot_sample(cross_path, {
                "role": "a3_cross", "candidate": critic,
                "reviewed_candidate": candidate, "case": None, "rep": 1,
                "phase": "pilot",
                "execution": _EXECUTION_FAKE if fake else _EXECUTION_REAL,
                "status": "skipped_missing_a2_output",
            }, prompt_sha=prompt_sha)
            written.append(cross_path)
            continue
        case_id, field_id, text = chosen

        def _cross_runner(
            db, candidate=candidate, critic=critic,
            case_id=case_id, field_id=field_id, text=text,
        ):
            ensure_route_preflight(db, critic, fake=fake)
            return run_pilot_a3_cross(
                db, case_id=case_id, a2_candidate=candidate,
                critic_candidate=critic, field_id=field_id,
                draft_text=text, fake=fake, cases_dir=cases_dir,
            )

        _run_sample(cross_path, 2, _cross_runner)
    return written


def _blind_admissible(sample: dict) -> bool:
    """Darf dieses Sample blind bewertet werden? (Owner Block 8)

    Ja für technisch valide UND menschlich auswertbare Outputs — inklusive
    ``production_eligible=false`` (ein erfundener Referenz-Identifier macht den
    Text nicht unlesbar; seine sprachliche Qualität bleibt beurteilbar).
    Nein für schema-invalide, leere, fremdfeldbezogene oder technisch nicht
    auswertbare Outputs.

    Fake-Dry-Run-Samples sind nie technisch valide (kein echter Provider). Sie
    dürfen die Maschinerie proben — der Lauf bleibt durchgehend als
    ``dry_run`` gekennzeichnet und wird nie als Bewertung berichtet. Ältere
    Artefakte ohne die Statusdimensionen fallen auf ``status`` zurück.
    """
    if sample.get("execution") == _EXECUTION_FAKE or "technical_valid" not in sample:
        return sample.get("status") == "succeeded"
    return bool(sample.get("technical_valid") and sample.get("human_evaluable"))


def _a3_findings_markdown(
    title: str, findings: list[dict], *, note: str = ""
) -> str:
    lines = [
        f"# {title}", "",
        "_Blind-Bewertung: Herkunftsmodelle absichtlich anonymisiert._",
    ]
    if note:
        lines += ["", f"_{note}_"]
    lines.append("")
    if not findings:
        lines.append("_(keine Findings)_")
    for i, f in enumerate(findings, start=1):
        lines += [
            f"## Finding {i} — {f.get('field_id')} / "
            f"{f.get('target_section')} — Severity {f.get('severity')}",
            "",
            str(f.get("description") or ""),
            "",
            f"*Vorschlag:* {f.get('suggested_improvement') or '—'}",
            f"*Nächste Aktion:* {f.get('recommended_next_action') or '—'}",
            "",
        ]
    return "\n".join(lines)


def calibration_check(results_dir: Path | None = None) -> tuple[bool, dict]:
    """Objektive Kalibrierungskriterien auf dem F1/rep1-Teilraum.

    Geprüft wird die **technische Vertragsvalidität** (Owner-Entscheid
    2026-07-17, Option A): echter Provider, kein Fake-Fallback, gültiges JSON
    im erwarteten Schema, caller-bound Routing, vollständige Usage/Kosten.

    Inhaltliche DQs (erfundene Fakten, ungültige Referenzen, falsche Sprache,
    Review-Notizen, Zeichenlimit) sind **Modellbefunde** und blockieren die
    Kalibrierung NICHT — sie bleiben vollständig erhalten, werden je Modell
    berichtet und fliessen in die gestufte Auswahl ein. Andernfalls würde ein
    echtes Modellverhalten den Vergleich verhindern, den es belegen soll.

    Liefert (bestanden, Detailbericht) — nur Whitelist-Daten."""
    results_dir = results_dir or default_pilot_results_dir()
    report: dict = {"criteria": {}, "samples": {}, "content_findings": {}}
    problems: list[str] = []

    def _load(kind: str, candidate: str, field_id: str) -> dict | None:
        slug = PILOT_SECTIONS[field_id].replace(".", "")
        path = (
            results_dir / "runs" / kind / _pilot_alias(candidate)
            / "F1" / f"s{slug}_rep1.json"
        )
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _check(kind: str, role_key: str) -> int:
        """Technische Vertragsvalidität EINER Rolle über die 4 Zellen."""
        valid = 0
        for candidate in PILOT_A2_CANDIDATES:
            for field_id in PILOT_FIELDS:
                sample = _load(kind, candidate, field_id)
                key = (
                    f"{role_key}:{_pilot_alias(candidate)}:"
                    f"{PILOT_SECTIONS[field_id]}"
                )
                if sample is None:
                    problems.append(f"{key}: Sample fehlt")
                    report["samples"][key] = "fehlt"
                    continue
                entry = (sample.get("fields") or [{}])[0]
                usage = (
                    entry.get("usage") if kind == "a2" else sample.get("usage")
                ) or {}
                dq = list(sample.get("hard_dq") or [])
                if sample.get("dq"):
                    dq.append(sample["dq"])
                report["samples"][key] = {
                    "technical_valid": sample.get("technical_valid"),
                    "production_eligible": sample.get("production_eligible"),
                    "human_evaluable": sample.get("human_evaluable"),
                    "status": sample.get("status"),
                    "reject_reason": sample.get("reject_reason"),
                    "hard_dq": dq,
                    "structured_output_mode": sample.get("structured_output_mode"),
                    "routing_metadata_source": sample.get("routing_metadata_source"),
                    "expected_language": sample.get("expected_language"),
                    "cost_status": usage.get("cost_status"),
                    "actual_model_id": usage.get("actual_model_id"),
                    "tool_wrapper_normalized": sample.get("tool_wrapper_normalized"),
                    "filter_stats": sample.get("filter_stats"),
                }
                # Inhaltliche Befunde: berichtet, nie ein technischer Blocker.
                content = [code for code in dq if code in scoring.CONTENT_DQ]
                if content:
                    report["content_findings"][key] = content
                if sample.get("technical_valid"):
                    valid += 1
                    continue
                if sample.get("execution") != _EXECUTION_REAL:
                    problems.append(f"{key}: kein Real-Lauf")
                elif sample.get("silent_fake"):
                    problems.append(f"{key}: Fake-Fallback erkannt")
                elif usage.get("cost_status") != "priced":
                    problems.append(f"{key}: Usage/Kosten unvollständig")
                elif sample.get("routing_metadata_source") != "caller_bound":
                    problems.append(f"{key}: Routing nicht caller-bound")
                else:
                    problems.append(
                        f"{key}: technisch ungültig "
                        f"({sample.get('reject_reason')})"
                    )
        return valid

    a2_valid = _check("a2", "a2")
    a3_valid = _check("a3_fair", "a3")
    report["criteria"]["a2_technical_valid"] = f"{a2_valid}/4"
    report["criteria"]["a3_technical_valid"] = f"{a3_valid}/4"
    report["criteria"]["problems"] = problems
    passed = a2_valid == 4 and a3_valid == 4 and not problems
    report["passed"] = passed
    report["note"] = (
        "Kalibrierung prüft NUR die technische Vertragsvalidität. Inhaltliche "
        "DQs stehen unter content_findings und gehen in die gestufte Auswahl."
    )
    return passed, report


def rescore_pilot_samples(
    db_factory, *, results_dir: Path | None = None,
    cases_dir: Path | None = None,
) -> dict:
    """Gespeicherte A2-/A3-Samples OFFLINE mit dem aktuellen Scoring neu
    bewerten — ohne einen einzigen Provider-Call (Owner Block 6).

    Zulässig, weil sich Modellinput, Prompt, Schema, Providerparameter und
    Outputtext nicht ändern: nur die Bewertung der gespeicherten Ausgabe wird
    korrigiert. Die Erlaubt-Basis wird dazu aus derselben Fallkonfiguration neu
    montiert (reiner Lesevorgang auf frisch geseedeten Fixtures).

    Grenze der Reproduktion: die Namensraum-Tags der geseedeten IDs sind je
    Lauf zufällig, die aus IDs stammenden Ziffernfolgen im Manifest können
    darum abweichen. Inhaltszahlen, Partner und Patente sind identisch — die
    Bewertung der Modelltexte ist davon unberührt; das Sample weist die
    Neuableitung als ``manifest_source=rederived_offline`` aus.
    """
    results_dir = results_dir or default_pilot_results_dir()
    runs_dir = results_dir / "runs"
    if not runs_dir.is_dir():
        raise EvalRefusal(f"Keine Pilot-Samples unter {runs_dir}.")
    summary: dict = {"rescored": [], "skipped": [], "unchanged": []}
    for path in sorted((runs_dir / "a2").rglob("*.json")) if (
        runs_dir / "a2"
    ).is_dir() else []:
        sample = json.loads(path.read_text(encoding="utf-8"))
        raw = (sample.get("raw", {}).get("fields") or [{}])[0]
        text = (raw.get("suggestion_text") or "").strip()
        if not text:
            # Ältere Artefakte haben den Text bei einem Inhalts-Reject nicht
            # persistiert — er steckt im Roh-Bundle und gehört in den Bogen.
            text = _a2_text_from_raw(raw.get("raw_outputs"))
            if text:
                raw["suggestion_text"] = text
                raw["suggestion_text_source"] = "recovered_from_rejected_bundle"
        field_id = sample.get("field_id")
        if not field_id or sample.get("case") is None:
            summary["skipped"].append({"path": path.name, "reason": "kein Fallbezug"})
            continue
        db = db_factory()
        try:
            seeded = _seed_a2_section_case(
                db, case_id=sample["case"], field_id=field_id,
                rep=sample.get("rep", 1), cases_dir=cases_dir,
            )
            manifest, expected_language, language_source = (
                _a2_manifest_and_language(db, seeded, field_id=field_id)
            )
        finally:
            db.close()
        entry = (sample.get("fields") or [{}])[0]
        usage = entry.get("usage") or {}
        claim_check = dict(entry.get("claim_check") or sample.get("claim_check") or {})
        reject_reason = sample.get("reject_reason")
        gates, fatal = [], []
        if text:
            gates = scoring.a2_gate_results(
                text,
                schema_valid=True,
                required_terms=seeded.gold.required_terms,
                expected_markers=(seeded.section,),
                char_limit=seeded.config.char_limit,
                manifest=manifest,
                expected_language=expected_language,
                missing_inputs_count=entry.get("missing_inputs_count") or 0,
                human_review_required=True,
                allowed_sources=_ALLOWED_SOURCES,
            )
            fatal = scoring.fatal_gate_results(
                text, manifest=manifest, allowed_sources=_ALLOWED_SOURCES,
                evidence_ref_violations=0,
                silent_fake_detected=bool(sample.get("silent_fake")),
                foreign_markers=tuple(
                    m_sec for fid, m_sec in PILOT_SECTIONS.items()
                    if fid != field_id
                ),
            )
        hard_dq = scoring.a2_hard_disqualifications(
            gates, fatal, reject_reason=reject_reason,
            routing_metadata_mismatch=bool(
                claim_check.get("routing_metadata_mismatch")
            ),
        )
        schema_valid = bool(raw.get("raw_outputs")) and (
            scoring.a2_reject_reason_to_dq(reject_reason) not in (
                "dq_schema_error", "dq_tool_contract_error",
                "dq_truncated_output",
            )
        )
        dimensions = scoring.sample_status_dimensions(
            execution=sample.get("execution", ""),
            silent_fake=bool(sample.get("silent_fake")),
            schema_valid=schema_valid,
            routing_metadata_source=sample.get("routing_metadata_source")
            or claim_check.get("routing_metadata_source"),
            usage=usage,
            hard_dq=hard_dq,
            has_readable_output=bool(text),
        )
        before = {
            "hard_dq": entry.get("hard_dq"),
            "technical_valid": sample.get("technical_valid"),
        }
        entry.update(
            gates=gates, fatal=fatal, hard_dq=hard_dq,
            gates_passed=scoring.gates_passed(gates) if text else False,
            fatal_candidate=scoring.fatal_candidate(fatal), **dimensions,
        )
        sample.update(
            hard_dq=hard_dq, expected_language=expected_language,
            language_source=language_source,
            allowed_facts=manifest.meta(),
            manifest_source="rederived_offline",
            rescored_at=_now_iso(), **dimensions,
        )
        _write_pilot_sample(path, sample, prompt_sha=prompt_fingerprint())
        summary["rescored"].append({
            "path": str(path.relative_to(results_dir)),
            "candidate": _pilot_alias(sample["candidate"]),
            "section": sample.get("target_section"),
            "before": before,
            "after": {"hard_dq": hard_dq, **dimensions},
        })

    a3_dir = runs_dir / "a3_fair"
    for path in sorted(a3_dir.rglob("*.json")) if a3_dir.is_dir() else []:
        sample = json.loads(path.read_text(encoding="utf-8"))
        dq = sample.get("dq")
        dimensions = scoring.sample_status_dimensions(
            execution=sample.get("execution", ""),
            silent_fake=bool(sample.get("silent_fake")),
            schema_valid=sample.get("status") in ("succeeded", "not_evaluable"),
            routing_metadata_source=sample.get("routing_metadata_source"),
            usage=sample.get("usage") or {},
            hard_dq=(dq,) if dq else (),
            has_readable_output=bool(sample.get("raw", {}).get("findings")),
        )
        if all(sample.get(k) == v for k, v in dimensions.items()):
            summary["unchanged"].append(str(path.relative_to(results_dir)))
            continue
        sample.update(rescored_at=_now_iso(), **dimensions)
        _write_pilot_sample(path, sample, prompt_sha=prompt_fingerprint())
        summary["rescored"].append({
            "path": str(path.relative_to(results_dir)),
            "candidate": _pilot_alias(sample["candidate"]),
            "section": sample.get("target_section"),
            "after": dimensions,
        })
    return summary


def execute_pilot_calibration(
    db_factory, *, fake: bool, results_dir: Path | None = None,
    cases_dir: Path | None = None, env: dict | None = None,
) -> tuple[bool, dict, list[Path]]:
    """Kalibrierungslauf (Owner Block 7/8): F1, Sections 3.1+4.2, beide
    Kandidaten, je 1 Replikation für A2 und A3-fixed (ohne Cross). Artefakte
    liegen in der normalen runs/-Struktur — der Voll-Lauf überspringt sie.

    Vorbedingung im Live-Modus: die beiden Anthropic-Structured-Output-Smokes
    sind bestanden (sonst gäbe es keinen technisch validen gemeinsamen
    Vertrag, unter dem verglichen werden dürfte)."""
    results_dir = results_dir or default_pilot_results_dir()
    if not fake:
        ok, so_report = structured_output_smokes_passed(results_dir)
        if not ok:
            raise EvalRefusal(
                "Kalibrierung verweigert — Structured-Output-Smokes nicht "
                "bestanden: " + "; ".join(so_report["problems"])
            )
    written = execute_pilot_run(
        db_factory, fake=fake, allow_holdout=True, results_dir=results_dir,
        cases_dir=cases_dir, env=env,
        cases=("F1",), reps=1, include_cross=False,
    )
    passed, report = calibration_check(results_dir)
    if fake:
        report["note"] = "Dry-Run — Kalibrierung gilt nur für Real-Läufe."
    (results_dir / "calibration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return passed, report, written


def build_pilot_blind_pack(*, results_dir: Path | None = None) -> Path:
    """Anonymisierte Pilot-Bewertungsunterlagen mit GETRENNTEN Bögen:
    A2 (10 Kriterien) für die Vorschlagstexte, A3 (8 Kriterien) für die
    fairen Critic-Läufe; Workflow-Smoke-Einheiten sind im A3-Bogen als
    ``a3_workflow_smoke`` gekennzeichnet (nie alleinige Rangfolge-Quelle).
    mapping.json bleibt lokal."""
    results_dir = results_dir or default_pilot_results_dir()
    runs_dir = results_dir / "runs"
    if not runs_dir.is_dir():
        raise EvalRefusal(f"Keine Pilot-Samples unter {runs_dir}.")
    samples = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(runs_dir.rglob("*.json"))
    ]
    if not samples:
        raise EvalRefusal(f"Keine Pilot-Samples unter {runs_dir}.")
    nonce = uuid.uuid4().hex
    assignment = scoring.build_blind_assignment(
        sorted(PILOT_A2_CANDIDATES), nonce
    )
    blind_dir = results_dir / "blind"
    blind_dir.mkdir(parents=True, exist_ok=True)

    a2_units: list[dict] = []
    a3_units: list[dict] = []
    for sample in samples:
        label = assignment[sample["candidate"]]
        rep = sample.get("rep", 1)
        section = sample.get("target_section") or ""
        if sample["role"] == "a2":
            # Owner Block 8: alles technisch valide UND lesbare kommt in den
            # Bogen — auch production_eligible=false, damit die sprachliche und
            # fachliche Textqualität blind beurteilt werden kann. Der Bogen
            # verrät weder DQ noch Eignung; die Zusammenführung erfolgt erst
            # nach dem Ingest.
            if not _blind_admissible(sample):
                continue
            for raw in sample.get("raw", {}).get("fields", []):
                text = (raw.get("suggestion_text") or "").strip()
                if not text:
                    continue
                a2_units.append({
                    "case_id": sample["case"], "unit_kind": "a2",
                    "unit_ref": f"{raw['field_id']}#{section}",
                    "label": label, "rep": rep,
                    "content": (
                        f"# {sample['case']} — A2-Abschnittsvorschlag "
                        f"{section} — {label} (Replikation {rep})\n\n"
                        "_Blind-Bewertung: Herkunftsmodell absichtlich "
                        "anonymisiert._\n\n---\n\n" + text
                    ),
                })
        elif sample["role"] == "a3_fair":
            if not _blind_admissible(sample):
                continue  # nicht auswertbar → Report, nie Blind-Rangfolge
            findings = sample.get("raw", {}).get("findings", [])
            a3_units.append({
                "case_id": sample["case"], "unit_kind": "a3_fair",
                "unit_ref": f"fixed_draft#{section}", "label": label,
                "rep": rep,
                "content": _a3_findings_markdown(
                    f"{sample['case']} — A3-Findings {section} — {label} "
                    f"(identischer Fixed Draft, Replikation {rep})",
                    findings,
                ),
            })
        elif sample["role"] == "a3_cross":
            if not _blind_admissible(sample):
                continue
            reviewed_label = assignment[sample["reviewed_candidate"]]
            findings = sample.get("raw", {}).get("findings", [])
            a3_units.append({
                "case_id": sample.get("case") or "-",
                "unit_kind": "a3_workflow_smoke",
                "unit_ref": f"prueft_{reviewed_label.replace(' ', '')}#{section}",
                "label": label, "rep": rep,
                "content": _a3_findings_markdown(
                    f"{sample.get('case')} — Workflow-Smoke {section} — {label} "
                    f"(prüft A2-Entwurf von {reviewed_label})",
                    findings,
                    note=(
                        "Nur Multi-Agent-Workflow-Nachweis — nicht für die "
                        "A3-Modellrangfolge verwenden."
                    ),
                ),
            })

    def _write_units(units: list[dict], sheet_name: str, rubric: tuple) -> None:
        rows = []
        for unit in scoring.shuffle_for_review(units, nonce):
            slug = re.sub(
                r"[^a-z0-9]+", "-", unit["unit_ref"].lower()
            ).strip("-")
            name = (
                f"{unit['case_id']}__{unit['unit_kind']}__{slug}"
                f"__{unit['label'].replace(' ', '')}__rep{unit['rep']}.md"
            )
            (blind_dir / name).write_text(
                unit["content"] + "\n", encoding="utf-8"
            )
            rows.append({
                key: unit[key]
                for key in ("case_id", "unit_kind", "unit_ref", "label", "rep")
            })
        columns = (*_PILOT_SHEET_BASE, *rubric, *_PILOT_SHEET_TAIL)
        sheet_path = blind_dir / sheet_name
        with sheet_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in columns})

    _write_units(a2_units, "pilot_a2_scoring_sheet.csv", PILOT_A2_RUBRIC)
    _write_units(a3_units, "pilot_a3_scoring_sheet.csv", PILOT_A3_RUBRIC)

    (blind_dir / "mapping.json").write_text(
        json.dumps(
            {"pilot": True, "nonce": nonce, "assignment": assignment,
             "generated_at": _now_iso()},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return blind_dir


_PILOT_INGEST_KINDS = {
    "a2": ("a2",),
    "a3": ("a3_fair", "a3_workflow_smoke"),
}


def ingest_pilot_scores(
    role: str, scores_csv: Path, *, results_dir: Path | None = None
) -> Path:
    """Ausgefüllten Pilot-Blindbogen einlesen (Owner scort selbst — nie KI).

    ``role``: ``a2`` (10-Kriterien-Bogen) oder ``a3`` (8-Kriterien-Bogen;
    Workflow-Smoke-Zeilen werden GETRENNT aggregiert und fliessen nie in die
    A3-Rangfolge ein). Aggregation je Kandidat und unit_kind."""
    if role not in _PILOT_INGEST_KINDS:
        raise EvalRefusal(f"Unbekannte Pilot-Rolle: {role!r} (a2|a3).")
    criteria = PILOT_A2_RUBRIC if role == "a2" else PILOT_A3_RUBRIC
    allowed_kinds = _PILOT_INGEST_KINDS[role]
    results_dir = results_dir or default_pilot_results_dir()
    mapping_path = results_dir / "blind" / "mapping.json"
    if not mapping_path.exists():
        raise EvalRefusal(
            f"mapping.json fehlt: erst `pilot blind` ausführen ({mapping_path})."
        )
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    label_to_candidate = {v: k for k, v in mapping["assignment"].items()}

    raw_buckets: dict[tuple[str, str], dict] = {}
    with scores_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip()
            candidate = label_to_candidate.get(label)
            if candidate is None:
                raise EvalRefusal(f"Unbekanntes Blind-Label in CSV: {label!r}")
            unit_kind = (row.get("unit_kind") or "").strip()
            if unit_kind not in allowed_kinds:
                raise EvalRefusal(
                    f"unit_kind {unit_kind!r} gehört nicht zum {role}-Bogen."
                )
            bucket = raw_buckets.setdefault((unit_kind, candidate), {
                "rows": 0, "criteria": {c: [] for c in criteria},
                "review_time_min": [], "rework_count": 0, "fatal_suspicions": 0,
            })
            bucket["rows"] += 1
            for crit in criteria:
                value = (row.get(crit) or "").strip()
                if value:
                    bucket["criteria"][crit].append(float(value))
            time_value = (row.get("review_time_min") or "").strip()
            if time_value:
                bucket["review_time_min"].append(float(time_value))
            if (row.get("rework_needed") or "").strip().lower() in (
                "1", "ja", "yes", "true"
            ):
                bucket["rework_count"] += 1
            if (row.get("fatal_suspicion") or "").strip():
                bucket["fatal_suspicions"] += 1

    out: dict[str, dict[str, dict]] = {kind: {} for kind in allowed_kinds}
    for (unit_kind, candidate), bucket in raw_buckets.items():
        crit_means = {}
        for crit, values in bucket["criteria"].items():
            mean, _ = scoring.mean_std(values)
            crit_means[crit] = mean
        time_mean, _ = scoring.mean_std(bucket["review_time_min"])
        out[unit_kind][candidate] = {
            "rows": bucket["rows"],
            "criteria_means": crit_means,
            "review_time_min_mean": time_mean,
            "rework_count": bucket["rework_count"],
            "fatal_suspicions": bucket["fatal_suspicions"],
        }

    human_dir = results_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    out_path = human_dir / f"pilot_{role}_scores.json"
    out_path.write_text(
        json.dumps(
            {"pilot": True, "role": role, "ingested_at": _now_iso(),
             "source_csv": scores_csv.name, "per_kind": out},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return out_path


def pilot_summary(results_dir: Path | None = None) -> dict:
    """Whitelist-Zusammenfassung des Piloten (Status, Zählwerte, Metriken,
    Modell-IDs, Hashes — nie Rohtexte, nie Blind-Mapping)."""
    results_dir = results_dir or default_pilot_results_dir()
    summary: dict = {
        "generated_at": _now_iso(),
        "pilot": True,
        "limits": {
            "max_real_llm_calls": PILOT_MAX_CALLS,
            "max_cost_chf": PILOT_MAX_COST_CHF,
        },
        "totals": pilot_totals(results_dir),
        "prompt_sha": prompt_fingerprint(),
        "smoke": {},
        "a2": {},
        "a3_cross": {},
    }
    executions: set[str] = set()
    for candidate in PILOT_A2_CANDIDATES:
        for suffix, key in (("", candidate), ("__a2mini", f"{candidate}__a2mini")):
            path = results_dir / "smoke" / f"{candidate}{suffix}.json"
            if not path.exists():
                if suffix == "":
                    summary["smoke"][key] = {"status": "not_run"}
                continue
            sample = json.loads(path.read_text(encoding="utf-8"))
            executions.add(sample.get("execution", "?"))
            summary["smoke"][key] = {
                "kind": sample.get("role") or "a1_smoke",
                "status": sample.get("status"),
                "execution": sample.get("execution"),
                "schema_valid": sample.get("schema_valid"),
                "requested_model_id": sample.get("requested_model_id"),
                "actual_model_id": (sample.get("usage") or {}).get("actual_model_id"),
                "latency_ms": (sample.get("usage") or {}).get("latency_ms"),
                "input_tokens": (sample.get("usage") or {}).get("input_tokens"),
                "output_tokens": (sample.get("usage") or {}).get("output_tokens"),
                "reasoning_tokens": (sample.get("usage") or {}).get("reasoning_tokens"),
                "cost_chf": (sample.get("usage") or {}).get("cost_chf"),
                "cost_status": (sample.get("usage") or {}).get("cost_status"),
                "silent_fake": sample.get("silent_fake"),
                "reason": sample.get("reason"),
            }

    runs_dir = results_dir / "runs"
    a2_samples: dict[str, list[dict]] = {}
    a3_fair_samples: dict[str, list[dict]] = {}
    cross_samples: list[dict] = []
    if runs_dir.is_dir():
        for path in sorted(runs_dir.rglob("*.json")):
            sample = json.loads(path.read_text(encoding="utf-8"))
            executions.add(sample.get("execution", "?"))
            if sample.get("role") == "a2":
                a2_samples.setdefault(sample["candidate"], []).append(sample)
            elif sample.get("role") == "a3_fair":
                a3_fair_samples.setdefault(
                    sample["candidate"], []
                ).append(sample)
            elif sample.get("role") == "a3_cross":
                cross_samples.append(sample)

    def _human(role: str, kind: str) -> dict:
        path = results_dir / "human" / f"pilot_{role}_scores.json"
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return (payload.get("per_kind") or {}).get(kind, {})

    human_a2 = _human("a2", "a2")
    human_a3_fair = _human("a3", "a3_fair")
    human_a3_smoke = _human("a3", "a3_workflow_smoke")

    def _reason_counts(samples: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in samples:
            reason = s.get("reject_reason")
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items()))

    for candidate, samples in sorted(a2_samples.items()):
        agg = _aggregate_a2(samples, human_a2.get(candidate))
        agg["requested_model_id"] = samples[0].get("requested_model_id")
        agg["cases"] = sorted({s["case"] for s in samples})
        agg["reps"] = sorted({s.get("rep", 1) for s in samples})
        agg["valid_outputs"] = sum(
            1 for s in samples if s.get("status") == "succeeded"
        )
        agg["invalid_outputs"] = sum(
            1 for s in samples if s.get("status") != "succeeded"
        )
        agg["reject_reason_counts"] = _reason_counts(samples)
        agg["tool_wrapper_normalized"] = sum(
            int(s.get("tool_wrapper_normalized") or 0) for s in samples
        )
        summary["a2"][candidate] = agg

    summary["a3_fair"] = {}
    for candidate, samples in sorted(a3_fair_samples.items()):
        evaluable = [s for s in samples if s.get("status") == "succeeded"]
        stats_sum = {"received": 0, "accepted": 0, "rejected": 0}
        rejected_reasons: dict[str, int] = {}
        for s in samples:
            stats = s.get("filter_stats") or {}
            for key in stats_sum:
                stats_sum[key] += int(stats.get(key) or 0)
            for code, count in (stats.get("rejected_reasons") or {}).items():
                rejected_reasons[code] = rejected_reasons.get(code, 0) + count
        flaw_rates: dict[str, str] = {}
        for s in evaluable:
            for flaw_id, hit in (s.get("flaw_detection") or {}).items():
                got, total = map(int, flaw_rates.get(flaw_id, "0/0").split("/"))
                flaw_rates[flaw_id] = f"{got + int(bool(hit))}/{total + 1}"
        latencies = [
            float((s.get("usage") or {}).get("latency_ms"))
            for s in samples
            if (s.get("usage") or {}).get("latency_ms") is not None
        ]
        lat_mean, lat_std = scoring.mean_std(latencies)
        summary["a3_fair"][candidate] = {
            "requested_model_id": samples[0].get("requested_model_id"),
            "cases": sorted({s["case"] for s in samples}),
            "reps": sorted({s.get("rep", 1) for s in samples}),
            "samples": len(samples),
            "valid_outputs": len(evaluable),
            "not_evaluable": sum(
                1 for s in samples if s.get("status") == "not_evaluable"
            ),
            "invalid_outputs": sum(
                1 for s in samples if s.get("status") == "invalid_output"
            ),
            "reject_reason_counts": _reason_counts(samples),
            "filter_stats_sum": {**stats_sum, "rejected_reasons": dict(
                sorted(rejected_reasons.items())
            )},
            "flaw_detection_rates": dict(sorted(flaw_rates.items())),
            "funding_decision_claims": sum(
                int(s.get("funding_decision_claims") or 0) for s in evaluable
            ),
            "silent_fake_events": sum(
                1 for s in samples if s.get("silent_fake")
            ),
            "tool_wrapper_normalized": sum(
                int(s.get("tool_wrapper_normalized") or 0) for s in samples
            ),
            "latency_ms": {"mean": lat_mean, "std": lat_std},
            "human": human_a3_fair.get(candidate),
        }

    for sample in sorted(
        cross_samples, key=lambda s: (s["candidate"], str(s.get("case")))
    ):
        key = f"{sample['candidate']}__prueft__{sample['reviewed_candidate']}"
        summary["a3_cross"][key] = {
            "note": "Workflow-Smoke — nie alleinige A3-Rangfolge-Quelle",
            "critic": sample["candidate"],
            "reviewed": sample["reviewed_candidate"],
            "requested_model_id": sample.get("requested_model_id"),
            "case": sample.get("case"),
            "target_section": sample.get("target_section"),
            "status": sample.get("status"),
            "finding_count": sample.get("finding_count"),
            "filter_stats": sample.get("filter_stats"),
            "funding_decision_claims": sample.get("funding_decision_claims"),
            "latency_ms": (sample.get("usage") or {}).get("latency_ms"),
            "cost_chf": (sample.get("usage") or {}).get("cost_chf"),
            "silent_fake": sample.get("silent_fake"),
            "human": human_a3_smoke.get(sample["candidate"]),
        }

    calib_path = results_dir / "calibration_report.json"
    if calib_path.exists():
        summary["calibration"] = json.loads(
            calib_path.read_text(encoding="utf-8")
        )

    if not executions:
        summary["status"] = "not_run"
    elif executions == {_EXECUTION_REAL}:
        summary["status"] = "durchgeführt"
    elif _EXECUTION_REAL in executions:
        summary["status"] = "partial (enthält Dry-Run-Samples)"
    else:
        summary["status"] = "dry_run (Fake-Adapter — keine Live-Evaluation)"
    return summary


def write_pilot_summary(results_dir: Path | None = None) -> tuple[Path, Path]:
    results_dir = results_dir or default_pilot_results_dir()
    summary = pilot_summary(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / "pilot_summary.json"
    md_path = results_dir / "pilot_summary.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        "# Rollen-Modell-Evaluation — Live-Pilot (A2/A3)\n\n"
        f"*Generiert:* {summary['generated_at']} · *Status:* "
        f"**{summary['status']}** · Calls (real): "
        f"{summary['totals']['real_llm_calls']}/{PILOT_MAX_CALLS} · "
        f"Kosten (priced): {summary['totals']['cost_chf_priced']} CHF / "
        f"max {PILOT_MAX_COST_CHF} CHF\n"
        f"*Prompt-SHA:* `{summary['prompt_sha'][:16]}…`\n\n"
        "`not_run`/Dry-Run heisst: nicht (live) durchgeführt — nie bestanden. "
        "Human-Werte stammen ausschliesslich aus dem Blind-Ingest.\n\n"
        "```json\n"
        + json.dumps(
            {k: v for k, v in summary.items() if k != "generated_at"},
            ensure_ascii=False, indent=2,
        )
        + "\n```\n",
        encoding="utf-8",
    )
    return json_path, md_path
