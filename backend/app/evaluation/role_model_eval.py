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
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from app.agents import context as a1_context
from app.agents import gateway
from app.agents.a2_fields import resolve_field_config
from app.agents.critic_review import run_a3_evidence_consistency
from app.agents.prompt_assets import prompt_version_for
from app.agents.providers import FakeProvider
from app.agents.providers.anthropic import AnthropicProvider
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
    if inv.usage_record_id:
        rec = db.get(UsageRecord, inv.usage_record_id)
        if rec is not None:
            out["input_tokens"] = rec.input_tokens
            out["output_tokens"] = rec.output_tokens
            out["cost_chf"] = rec.cost_chf
            out["cost_status"] = rec.cost_status
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


def _a2_input_corpus(gold: scoring.CaseGold, fragments: list[dict]) -> str:
    """Eingabekontext des Falls für die Erfindungs-Detektoren: Titel/Outline,
    geseedete Quellen, die eingefrorenen Fall-Fragmente (Antragstext) und die
    Feld-Templates (Pflichtstruktur-Labels wie «Patentrecherche» sind Teil der
    Eingabe, keine Erfindung)."""
    from app.drafts.templates import build_template
    from app.registry import get_registry

    registry = get_registry()
    templates = []
    for field in registry.m6_draft_fields():
        if resolve_field_config(field.field_id) is not None:
            templates.append(build_template(field, registry))
    return "\n".join([
        gold.title_de, gold.title_en,
        f"Synthetischer Evaluationsfall {gold.case_id} "
        "(Rollen-Modell-Evaluation, D0/public).",
        "Öffentliche Marktquelle: Anbieter & Wettbewerber",
        "Öffentliche Partnerquelle: Forschungslabor Schweiz",
        scoring.fragments_corpus(fragments),
        *templates,
    ])


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

    corpus = _a2_input_corpus(gold, fragments)
    execution = _EXECUTION_FAKE if fake else _EXECUTION_REAL
    fields_out, fields_raw = [], []
    editor_markers = {
        field_id: _expected_markers(field_id)
        for field_id in A3_SCOPE_FIELDS
    }
    for item in package.fields:
        config = resolve_field_config(item.field_id)
        if config is None:
            continue  # deterministische NAME-Felder sind kein A2-LLM-Vergleich
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
            input_corpus=corpus,
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
        proxy = proxies.get(item.field_id)
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
            input_corpus=corpus,
            allowed_sources=_ALLOWED_SOURCES,
            evidence_ref_violations=violations,
            silent_fake_detected=silent,
            foreign_markers=foreign,
        )
        fields_out.append({
            "field_id": item.field_id,
            "status": item.status,
            "model": item.model,
            "gates": gates,
            "gates_passed": scoring.gates_passed(gates),
            "fatal": fatal,
            "fatal_candidate": scoring.fatal_candidate(fatal),
            "usage": usage,
            "missing_inputs_count": len(item.missing_inputs or []),
            "human_review_required": bool(item.human_review_required),
            "llm_calls": proxy.calls if proxy else 0,
        })
        fields_raw.append({
            "field_id": item.field_id,
            "suggestion_text": item.suggestion_text,
            "raw_outputs": list(proxy.raw_outputs) if proxy else [],
        })

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

    per_candidate: dict[str, dict] = {}
    with scores_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
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
    human_dir = results_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    out_path = human_dir / f"{role}_scores.json"
    out_path.write_text(
        json.dumps(
            {"role": role, "ingested_at": _now_iso(), "source_csv": scores_csv.name,
             "per_candidate": out},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return out_path


# --- Aggregation + Report -----------------------------------------------------------


def _human_scores(results_dir: Path, role: str) -> dict:
    path = results_dir / "human" / f"{role}_scores.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("per_candidate", {})


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

    return {
        "samples": len(samples),
        "fields_evaluated": len(evaluated),
        "gate_pass_rate": (
            round(len(passed) / len(evaluated), 4) if evaluated else None
        ),
        "gate_share_mean": gate_share_mean,
        "gate_share_std": gate_share_std,
        "fatal_candidate_fields": len(fatal_fields),
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
        human = _human_scores(results_dir, role)
        by_candidate: dict[str, dict] = {}
        for candidate in sorted({s["candidate"] for s in samples}):
            cand_samples = [s for s in samples if s["candidate"] == candidate]
            dev = [s for s in cand_samples if s["case"] not in HOLDOUT_CASES]
            holdout = [s for s in cand_samples if s["case"] in HOLDOUT_CASES]
            cand_human = human.get(candidate)
            if role == "a1":
                agg = {"dev": _aggregate_a1(dev)}
                if holdout:
                    agg["holdout"] = _aggregate_a1(holdout)
            elif role == "a2":
                agg = {"dev": _aggregate_a2(dev, cand_human)}
                if holdout:
                    agg["holdout"] = _aggregate_a2(holdout, cand_human)
            else:
                agg = {"dev": _aggregate_a3(dev, cand_human)}
                if holdout:
                    agg["holdout"] = _aggregate_a3(holdout, cand_human)
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
                cand_human = human.get(cand) or {}
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
