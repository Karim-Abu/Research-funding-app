"""R5.5-REAL — Manueller Real-Provider-Feld-Smoke (Abstract & Executive Summary).

Fährt die zwei A2-Felder ``INTRO.APP.ABSTRACT`` und
``INTRO.APP.EXECUTIVE_SUMMARY`` manuell gegen echte Provider (OpenAI + Anthropic)
über die bestehende Grenze ``run_a2_field_drafting`` → ``gateway.invoke`` und misst
Provider/Modell/Tokens/Latenz/cost_status/usage_record_id/AIProposal-Validität/
missing_inputs/human_review_required. Kein CI-Test, kein Produktivlauf.

Manual Mode — reale Calls nur wenn ALLE Guards erfüllt sind (``guard_refusal``,
wiederverwendet aus EVAL.2): ``CI`` nicht gesetzt, ``RUN_REAL_PROVIDER_SMOKE=true``,
``AI_EVAL_MODE=real``, abgeleiteter ``data_mode == synthetic_eval``, Provider
explizit, API-Key vorhanden. Max 1 Lauf pro (Provider, Feld) (Artefakt-Existenz).
Der Provider wird über einen Route-Filter erzwungen; die Ziel-Route ist durch
``max_retries=1`` natürlich auf ≤2 reale Calls begrenzt — ein Schema-Failure metert
trotzdem in EINEN UsageRecord (EVAL.2-Gateway-Pfad).

Daten: F1-abgeleitete synthetische D0-Variante (public/synthetic). Keine echten
D2-Daten, keine Partnernamen, keine Budgetzahlen. Roh-Outputs (suggested_text,
voller Bundle-Output) NUR als Eval-Artefakt im git-ignorierten
``backend/var/evaluation/r5_5/`` — nie in Report/Logs/Audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.proposal import AIProposal
from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.base import ProviderUnavailable
from app.agents.providers.openai import OpenAIProvider
from app.agents.schemas import validate_payload
from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    ExtractedFact,
    PortalFieldDraft,
    ProcessingConfirmation,
    Project,
    RequirementAssessment,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
    UsageRecord,
)
from app.evaluation.data_mode import derive_data_mode
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.real_smoke import ROUTE_FOR, _ARTIFACT_KEY, guard_refusal
from app.evaluation.usage import run_usage_totals
from app.evaluation.usage_smoke import (
    ACTOR,
    F1_SMOKE_CLASSIFICATION,
    WS,
    SmokeFailure,
    _ensure_base_rows,
)
from app.registry import get_registry
from app.runs.cloud_policy import REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION

PROFILE = "A2.introduction_public_summary"
PROVIDERS = ("openai", "anthropic")
FIELDS = {
    "abstract": "INTRO.APP.ABSTRACT",
    "exec": "INTRO.APP.EXECUTIVE_SUMMARY",
}
_FIELD_NAME = {
    "INTRO.APP.ABSTRACT": "Abstract",
    "INTRO.APP.EXECUTIVE_SUMMARY": "Executive Summary",
}
NORMALIZER = "normalizer-1"
REQ_ID = "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"

# Public-safe synthetic seed content — no partner names, no budget, no D2.
_DRAFT_TEXT = {
    "INTRO.APP.ABSTRACT": "Erster Entwurf des öffentlichen Abstracts.",
    "INTRO.APP.EXECUTIVE_SUMMARY": "Erster Entwurf der Executive Summary.",
}
_EVIDENCE_QUOTE = "Öffentliche, synthetische Belegstelle ohne vertrauliche Angaben."
_FACT_STATEMENT = "Synthetische Projektangabe (advisory, nicht bestätigt)."


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _target_route_model(target_route_provider: str) -> str | None:
    """model_id der A2-Route, die auf den Ziel-Provider zeigt (primary/fallback) —
    Fallback, falls kein UsageRecord entstand (Transportfehler)."""
    registry = get_agent_registry()
    profile = registry.profile(PROFILE)
    for route_key in (profile.primary_model, profile.fallback_model):
        if route_key and registry.route(route_key).provider == target_route_provider:
            return registry.route(route_key).model_id
    return None


def _max_calls() -> int:
    """1 + max_retries des Profils — natürliche Obergrenze realer Calls je Route."""
    profile = get_agent_registry().profile(PROFILE)
    return 1 + int(profile.invocation_limits.get("max_retries", 0))


class _CountingAdapter:
    """Zählt generate()-Calls und cappt defensiv bei ``limit`` (Kostenbremse).

    ``name``/``available`` werden durchgereicht (ProviderPolicy/_try_route lesen
    ``adapter.name``). Der Cap liegt bei ``1+max_retries`` und greift daher NICHT
    in die legitimen Schema-Retry-Versuche ein — er verhindert nur einen Runaway.

    R5.5b: schneidet zusätzlich die rohen Provider-Antworten mit
    (``raw_outputs``) — das Gateway persistiert bei einem Schema-Failure kein
    Failure-Detail (der Fallback-Versuch überschreibt den Grund), also ist der
    Proxy die einzige Diagnose-Quelle. Nur fürs git-ignorierte Artefakt.
    """

    def __init__(self, inner, *, limit: int, adapter_name: str | None = None) -> None:
        self._inner = inner
        self._limit = limit
        self._adapter_name = adapter_name
        self.calls = 0
        self.raw_outputs: list[str] = []

    @property
    def name(self) -> str:
        return self._adapter_name or self._inner.name

    def available(self) -> bool:
        return self._inner.available()

    def generate(self, request):
        if self.calls >= self._limit:
            raise ProviderUnavailable("r5_5_call_cap_reached")
        self.calls += 1
        result = self._inner.generate(request)
        self.raw_outputs.append(result.raw_output)
        return result


def _failure_category(
    raw_outputs: list[str], field_id: str, status: str
) -> tuple[str, str | None]:
    """Deterministische, whitelist-sichere Schema-Fehlerkategorie (R5.5b).

    Reines Diagnose-Label für den Report: enthält nur Kategorien, Feldnamen aus
    dem eigenen Schema (Repo-öffentlich) und Zählwerte — nie Modell-Output
    (unbekannte Key-NAMEN des Modells werden nur gezählt). Zweiter Rückgabewert
    ist das volle Fehlerdetail — NUR fürs git-ignorierte Artefakt. Kein
    permissives Parsing: akzeptiert wird weiterhin ausschliesslich, was das
    Gateway (pydantic) validiert hat.
    """
    if status == "proposal_valid":
        return "none", None
    if not raw_outputs:
        return "no_provider_output", None
    raw = raw_outputs[-1]
    stripped = raw.strip()
    if not stripped:
        return "empty_output", None
    if stripped.startswith("```"):
        return "markdown_fence", None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Truncation-Signal: der Parser lief bis ans Input-Ende (oder ein String
        # blieb offen) — Fehler mitten im Text ist dagegen schlicht kein JSON.
        truncated = exc.msg.startswith("Unterminated") or exc.pos >= len(raw.rstrip())
        return ("json_truncated" if truncated else "not_json"), str(exc)[:2000]
    try:
        bundle = validate_payload("PortalFieldDraftBundle@v1", parsed)
    except ValidationError as exc:
        missing = sorted(
            {str(e["loc"][-1]) for e in exc.errors() if e["type"] == "missing"}
        )
        extra_count = sum(1 for e in exc.errors() if e["type"] == "extra_forbidden")
        parts = []
        if missing:  # fehlende Keys = Namen aus unserem Schema (whitelist-safe)
            parts.append("missing_required:" + "+".join(missing))
        if extra_count:  # Namen der Fremd-Keys nur im Artefakt-Detail
            parts.append(f"unknown_keys:{extra_count}")
        if not parts:
            kinds = sorted({e["type"] for e in exc.errors()})
            parts.append("type_error:" + "+".join(kinds))
        return "; ".join(parts), str(exc)[:2000]
    if not bundle.draft_candidates:
        return "no_candidate", None
    if not any(c.field_id == field_id for c in bundle.draft_candidates):
        return "wrong_field_id", None
    if len(bundle.draft_candidates) > 1:
        return "multiple_candidates", None
    # Bundle schema-valide — der Kandidat scheiterte an Feldregeln (siehe reason,
    # z. B. character_limit_exceeded/unknown_evidence_anchor).
    return "candidate_rejected", None


def _forcing_resolver(provider: str, *, adapter=None):
    """Resolver, der den (gezählten) Adapter NUR für die Ziel-Route liefert, sonst
    ``None`` (blockt Cross-Provider-Fallback). Gibt (resolver, proxy) zurück."""
    target_route = ROUTE_FOR[provider]
    inner = adapter or (
        OpenAIProvider() if provider == "openai" else AnthropicProvider()
    )
    proxy = _CountingAdapter(
        inner, limit=_max_calls(), adapter_name=target_route
    )
    return (lambda route: proxy if route.provider == target_route else None), proxy


def _seed_a2_run(db, field_id: str) -> tuple[AnalysisRun, str, str]:
    """Frische synthetische F1-D0-Run + Draft + verified Evidence + advisory Fact
    für genau ein A2-Feld. Returns (run, draft_id, base_version_id)."""
    sfx = uuid.uuid4().hex[:8]
    project_id, doc_id, sv_id, run_id = (
        f"r5_5-{sfx}-{k}" for k in ("project", "doc", "sv", "run")
    )
    frag_id = f"r5_5-{sfx}-frag"
    ctx_text = "Öffentlicher synthetischer Projektkontext."
    cls = dict(F1_SMOKE_CLASSIFICATION)

    db.add(Project(
        project_id=project_id, workspace_id=WS,
        title="F1 QUALIMON (R5.5-REAL, synthetisch)",
        description="Synthetischer F1-abgeleiteter Feld-Real-Smoke.",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=cls, created_by=ACTOR, status="draft",
    ))
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=WS,
        name="Projektbeschreibung.txt", type="txt", status="processed",
        data_classification=cls, created_by=ACTOR,
    ))
    db.add(SourceVersion(
        source_version_id=sv_id, source_document_id=doc_id, version_number=1,
        original_content_hash="h", normalized_content_hash="h2",
        normalized_text=ctx_text, parser_version="parser-1",
        normalizer_version=NORMALIZER, chunker_version="chunker-1",
        processing_status="processed", data_classification=cls,
        storage_ref="a" * 32, original_filename="p.txt", byte_size=len(ctx_text),
        mime_type="text/plain",
    ))
    db.add(SourceFragment(
        fragment_id=frag_id, source_version_id=sv_id, ordinal=0,
        original_text=ctx_text, normalized_text=ctx_text,
        start_offset=0, end_offset=len(ctx_text), content_hash="fh",
    ))
    db.add(AnalysisRun(
        run_id=run_id, project_id=project_id, workspace_id=WS, created_by=ACTOR,
        status="running", current_stage="draft_fields", progress_percent=50,
        processing_mode="cloud_assisted", effective_data_classification=cls,
        snapshot_versions={"normalizer_version": NORMALIZER},
        recheck_required=False, semantic_findings_stale=False,
    ))
    db.add(ProcessingConfirmation(
        confirmation_id=f"r5_5-{sfx}-confirm",
        project_id=project_id, workspace_id=WS, created_by=ACTOR,
        status="used", processing_mode="cloud_assisted",
        source_version_ids=[sv_id], accepted_policy_version="1.1.0",
        purpose="Explizit freigegebener synthetischer Evaluationslauf",
        provider_route_class="direct_eval",
        confirmation_text_version=REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION,
        data_classification_shown=cls, expires_after_one_run=True,
        used_by_run_id=run_id, decided_at=datetime.now(timezone.utc),
    ))
    db.add(RunSourceSnapshot(
        id=f"r5_5-{sfx}-snap", run_id=run_id, source_version_id=sv_id, source_id=doc_id,
    ))

    draft_id, version_id = f"r5_5-{sfx}-draft", f"r5_5-{sfx}-ver"
    draft_text = _DRAFT_TEXT[field_id]
    db.add(DraftVersion(
        draft_version_id=version_id, draft_id=draft_id, text=draft_text,
        character_count=len(draft_text), created_by="template",
        content_hash=_hash(draft_text),
    ))
    db.add(PortalFieldDraft(
        draft_id=draft_id, run_id=run_id, workspace_id=WS, field_id=field_id,
        field_name=_FIELD_NAME[field_id], status="draft",
        character_limit=get_registry().portal_fields[field_id].character_limit,
        current_version_id=version_id, open_issue_count=0,
        template_catalog_version="tpl-1",
    ))

    anchor_id, assess_id = f"r5_5-{sfx}-anchor", f"r5_5-{sfx}-assess"
    db.add(EvidenceAnchor(
        anchor_id=anchor_id, run_id=run_id, workspace_id=WS,
        source_version_id=sv_id, source_id=doc_id,
        source_name="Projektbeschreibung.txt", source_type="txt", fragment_id=frag_id,
        quote=_EVIDENCE_QUOTE, quote_hash=_hash(_EVIDENCE_QUOTE),
        match_type="exact_normalized", normalizer_version=NORMALIZER,
        verification_status="exact_verified",
    ))
    db.add(RequirementAssessment(
        assessment_id=assess_id, run_id=run_id, requirement_id=REQ_ID,
        requirement_version="1.0.0", status="met", basis="deterministic_rule",
        reasoning="synthetic",
    ))
    db.add(EvidenceLink(
        evidence_link_id=f"r5_5-{sfx}-link", run_id=run_id, workspace_id=WS,
        anchor_id=anchor_id, target_type="requirement_assessment",
        target_id=assess_id, status="active",
    ))
    db.add(ExtractedFact(
        fact_id=f"r5_5-{sfx}-fact", run_id=run_id, workspace_id=WS,
        fact_type="project_fact", normalized_value=None,
        original_statement=_FACT_STATEMENT, status="proposed",
        source_fragment_ids=[frag_id], source_version_ids=[sv_id],
        profile_id="A1.project_fact_extraction", fact_fingerprint=f"r5_5-{sfx}-fp",
    ))
    db.flush()
    return db.get(AnalysisRun, run_id), draft_id, version_id


def run_field_case(db, provider: str, field_id: str, *, adapter=None) -> dict:
    """Ein A2-Feld über einen erzwungenen Provider fahren und Metriken erfassen.

    ``adapter`` injiziert für Tests einen FakeProvider (kein Netz); ohne ihn werden
    die realen Adapter konstruiert. Two-Key-Envelope: ``report`` (Whitelist) +
    git-ignoriertes ``artifact`` (roher Output).
    """
    _ensure_base_rows(db)
    run, draft_id, base_version_id = _seed_a2_run(db, field_id)
    resolver, proxy = _forcing_resolver(provider, adapter=adapter)

    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft_id,
        base_version_id=base_version_id,
        operation_id=f"r5_5-{provider}-{uuid.uuid4().hex[:6]}",
        provider_resolver=resolver,
    )
    db.commit()

    totals = run_usage_totals(db, run.run_id)
    inv = db.scalar(select(AgentInvocation).where(AgentInvocation.run_id == run.run_id))
    # Modell + usage_record_id aus dem tatsächlich gemeterten UsageRecord lesen:
    # das Gateway koppelt ``inv.usage_record_id`` nur auf dem Erfolgspfad; auf einem
    # Schema-Failure wird der Record trotzdem geschrieben (run-scoped).
    metered = db.execute(
        select(UsageRecord.usage_record_id, UsageRecord.model).where(
            UsageRecord.run_id == run.run_id
        )
    ).first()
    metered_usage_id = metered[0] if metered else None
    metered_model = metered[1] if metered else None

    if proxy.calls == 0:
        raise SmokeFailure(
            f"Kein Provider-Call ausgeführt (status={outcome.status}, "
            f"reason={outcome.reason}) — Policy/Verfügbarkeit hat blockiert."
        )

    view = outcome.view or {}
    proposal = view.get("ai_proposal")
    if outcome.status == "succeeded" and proposal is not None:
        AIProposal.model_validate(proposal)  # muss valide sein (build_proposal)
        status = "proposal_valid"
    elif totals["usage_record_count"] > 0:
        status = "schema_failed"  # Provider antwortete, Output verfehlte das Schema
    else:
        status = "provider_error"  # Transportfehler, keine gemetere Antwort

    # Metering-Pflicht: nur ein reiner Transportfehler darf 0 UsageRecords haben.
    if totals["usage_record_count"] == 0 and status != "provider_error":
        raise SmokeFailure("Metering-Lücke: kein UsageRecord trotz Provider-Call")

    failure_category, failure_detail = _failure_category(
        proxy.raw_outputs, field_id, status
    )

    return {
        "report": {
            "field": field_id,
            "provider": provider,
            "route_provider": ROUTE_FOR[provider],
            "model": metered_model or _target_route_model(ROUTE_FOR[provider]),
            "data_mode": derive_data_mode(
                ai_eval_mode=get_settings().ai_eval_mode, origin="synthetic"
            ),
            "status": status,
            "reason": outcome.reason or None,
            "failure_category": failure_category,
            "llm_calls": proxy.calls,
            "latency_ms": inv.latency_ms if inv else None,
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "total_tokens": totals["input_tokens"] + totals["output_tokens"],
            "usage_record_count": totals["usage_record_count"],
            "usage_record_id": metered_usage_id,
            "cost_status_counts": totals["cost_status_counts"],
            "cost_chf_priced": totals["cost_chf_priced"],
            "price_table_version": PRICE_TABLE_VERSION,
            "missing_inputs_count": len(proposal.get("missing_inputs", [])) if proposal else 0,
            "human_review_required": (
                proposal.get("human_review_required") if proposal else None
            ),
            "suggested_text_length": len(view.get("suggested_text") or ""),
        },
        _ARTIFACT_KEY: {
            # Nur var/-Eval-Artefakt: roher Vorschlagstext + Proposal + Fehlerdetail
            # + Roh-Antworten aller Versuche (R5.5b-Diagnose-Mitschnitt).
            "suggested_text": view.get("suggested_text"),
            "ai_proposal": proposal,
            "reason": outcome.reason or None,
            "raw_outputs": list(proxy.raw_outputs),
            "failure_detail": failure_detail,
        },
    }


def _fmt_cost(report: dict) -> str:
    counts = report.get("cost_status_counts") or {}
    if counts.get("priced"):
        return f"{report['cost_chf_priced']} CHF (nur priced summiert)"
    return "nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen"


def _fmt_counts(counts: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "—"


def render_report(results: dict, *, generated_at: str) -> str:
    """Whitelist-Report je Feld × Provider. Liest NUR ``entry['report']`` —
    das ``artifact`` (Rohoutput) bleibt strukturell aussen vor."""
    lines = [
        "# R5.5-REAL — Real-Provider-Feld-Report (Abstract & Executive Summary)",
        "",
        f"*Generiert:* {generated_at} · *Preistabelle:* `{PRICE_TABLE_VERSION}`",
        "",
        "## Pflichthinweise",
        "",
        "- Nur **synthetic_eval** (F1-abgeleitet, D0 public). Keine echten",
        "  D2-Daten, keine Partnernamen, keine Budgetzahlen.",
        "- Keine Rohprompts und keine vollständigen Rohantworten in diesem Report;",
        "  suggested_text/Bundle-Output liegen nur als Eval-Artefakt im",
        "  git-ignorierten `backend/var/evaluation/r5_5/`. Keine API-Keys.",
        "- Ein **Schema-Failure ist ein messbares Ergebnis** (Provider hat",
        "  geantwortet, Output verfehlte `PortalFieldDraftBundle@v1`), kein",
        "  Implementierungsfehler — der UsageRecord wird trotzdem ausgewiesen.",
        "- Kostenstatus ist Mess-Pipeline, keine Kostenrechnung: `cost_chf` wird",
        "  nur über `cost_status='priced'` summiert; 0.0 nie als gratis lesen.",
        "- Alle Calls über die bestehende Grenze `run_a2_field_drafting` →",
        "  `gateway.invoke`. Kein Azure, kein Firecrawl in diesem Smoke.",
        "",
    ]
    for key, field_id in FIELDS.items():
        lines += [f"## {field_id}", ""]
        for provider in PROVIDERS:
            lines += [f"### {provider}", ""]
            entry = results.get(f"{key}_{provider}")
            if entry is None:
                lines += ["**ausstehend** — dieser Smoke wurde noch nicht ausgeführt.", ""]
                continue
            r = entry["report"]
            rows = [
                ("data_mode", r["data_mode"]),
                ("Modell", r["model"]),
                ("Route", r["route_provider"]),
                ("Status", r["status"]),
                ("reason / error_code", r.get("reason") or "—"),
                ("Schema-Fehlerkategorie", r.get("failure_category") or "—"),
                ("LLM-Calls", r["llm_calls"]),
                ("input_tokens", r["input_tokens"]),
                ("output_tokens", r["output_tokens"]),
                ("total_tokens", r["total_tokens"]),
                ("Latenz (ms)", r["latency_ms"]),
                ("UsageRecords", r["usage_record_count"]),
                ("usage_record_id", r["usage_record_id"] or "—"),
                ("cost_status", _fmt_counts(r["cost_status_counts"])),
                ("Kosten", _fmt_cost(r)),
                ("missing_inputs", r["missing_inputs_count"]),
                ("human_review_required", r["human_review_required"]),
                ("Output-Länge (Zeichen)", r["suggested_text_length"]),
                ("Qualitätsnotiz (manuell)", "_vom Reviewer auszufüllen_"),
            ]
            lines += ["| Feld | Wert |", "| --- | --- |"]
            lines += [f"| {k} | {v} |" for k, v in rows]
            lines.append("")
    lines += [
        "---",
        "",
        "Erzeugt mit `RUN_REAL_PROVIDER_SMOKE=true AI_EVAL_MODE=real python "
        "scripts/run_r5_5_field_smoke.py --provider <openai|anthropic>` (Manual",
        "Mode: CI ungesetzt), frische Temp-SQLite-DB, Keys aus `backend/.env`,",
        "max 1 Lauf pro (Provider, Feld).",
        "",
    ]
    return "\n".join(lines)


def _default_results_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "var" / "evaluation" / "r5_5"


def _default_report_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs" / "evaluation" / "r5_5_real_provider_field_report.md"
    )


def _load_results(results_dir: Path) -> dict:
    results: dict = {}
    for key in FIELDS:
        for provider in PROVIDERS:
            path = results_dir / f"{key}_{provider}.json"
            if path.exists():
                results[f"{key}_{provider}"] = json.loads(
                    path.read_text(encoding="utf-8")
                )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "R5.5-REAL manueller Real-Provider-Feld-Smoke — nur mit explizitem "
            "Manual-Mode-Opt-in; nie in CI."
        )
    )
    parser.add_argument("--provider", required=True, choices=list(PROVIDERS))
    parser.add_argument("--fields", default="both", choices=["both", *FIELDS])
    parser.add_argument("--results-dir", default=str(_default_results_dir()))
    parser.add_argument("--out", default=str(_default_report_path()))
    parser.add_argument(
        "--generated-at", default=datetime.now(timezone.utc).date().isoformat()
    )
    args = parser.parse_args(argv)

    refusal = guard_refusal(
        provider=args.provider, env=os.environ, settings=get_settings()
    )
    if refusal:
        print(f"r5_5-smoke: verweigert — {refusal}", file=sys.stderr)
        return 2

    results_dir = Path(args.results_dir)
    field_keys = list(FIELDS) if args.fields == "both" else [args.fields]

    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(engine)
    written: list[str] = []
    for key in field_keys:
        result_path = results_dir / f"{key}_{args.provider}.json"
        if result_path.exists():
            print(
                f"r5_5-smoke: {key}/{args.provider} bereits ausgeführt "
                f"({result_path}) — Datei löschen für einen Re-Run. Übersprungen.",
                file=sys.stderr,
            )
            continue
        db = SessionLocal()
        try:
            result = run_field_case(db, args.provider, FIELDS[key])
        except SmokeFailure as exc:
            print(f"r5_5-smoke: {key}/{args.provider}: {exc}", file=sys.stderr)
            return 2
        finally:
            db.close()
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        r = result["report"]
        print(
            f"r5_5-smoke: {key}/{args.provider}: status={r['status']} "
            f"model={r['model']} tokens={r['total_tokens']} calls={r['llm_calls']}"
        )
        written.append(key)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_report(_load_results(results_dir), generated_at=args.generated_at),
        encoding="utf-8",
    )
    print(f"r5_5-smoke: Report aktualisiert: {out} (neu: {written or 'nichts'})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
