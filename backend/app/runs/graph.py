"""Minimal LangGraph technical workflow: initialize → validate_source_snapshot
→ finalize_run, with an official SQLite checkpointer. No LLM/agent/network.

The app DB run status is authoritative; checkpoints are diagnostic/position only.
Each node reloads the run and short-circuits on cancellation (clar. #2).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import critic_review, evidence_mapping, fact_extraction, field_drafting
from app.agents.a3_review import A3_PROFILE_ID
from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    Project,
    RunPolicySnapshot,
    RunProjectSnapshot,
    RunSourceSnapshot,
)
from app.db.session import SessionLocal
from app.drafts import pipeline as drafts_pipeline
from app.evidence import pipeline as evidence_pipeline
from app.repositories import audit, controls
from app.review import package as review_package
from app.runs import evaluation
from app.runs import phases as run_phases
from app.runs.constants import STAGE_PROGRESS
from app.runs.transitions import transition_run

logger = logging.getLogger("app.runs.graph")


class RunState(TypedDict):
    run_id: str
    project_id: str
    workspace_id: str
    cancelled: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_cancelled(run: AnalysisRun) -> bool:
    return run is None or run.cancel_requested or run.status == "cancelled"


def _set_stage(db, run: AnalysisRun, stage: str) -> None:
    run.current_stage = stage
    run.progress_percent = STAGE_PROGRESS[stage]
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=None,
        action="run.stage_changed",
        target_type="run",
        target_id=run.run_id,
        detail={"stage": stage},
    )


def node_initialize(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        _set_stage(db, run, "initialize")
        run_phases.ensure_pending(db, run)
        run_phases.start(db, run, "prepare_documents")
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.operation_state", status="passed",
            detail="initialized",
        )
        db.commit()
        return state
    finally:
        db.close()


def node_validate_source_snapshot(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        count = len(
            list(
                db.scalars(
                    select(RunSourceSnapshot.id).where(
                        RunSourceSnapshot.run_id == run.run_id
                    )
                )
            )
        )
        # Intake-only-Läufe sind gültig: die strukturierte Projektbeschreibung
        # ist der versionierte Input (eingefroren im RunProjectSnapshot).
        project_snapshot = db.get(RunProjectSnapshot, run.run_id)
        has_description = bool(
            str(((project_snapshot.project_json if project_snapshot else {}) or {})
                .get("description") or "").strip()
        )
        valid = count > 0 or has_description
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.source_snapshot",
            status="passed" if valid else "failed",
            detail=f"frozen_versions={count} intake_description="
                   f"{'present' if has_description else 'absent'}",
        )
        _set_stage(db, run, "validate_source_snapshot")
        run_phases.finish(
            db, run, "prepare_documents", "succeeded",
            detail={"sources_frozen": count, "intake_description": has_description},
        )
        db.commit()
        return state
    finally:
        db.close()


def node_extract_facts_and_map_evidence(state: RunState) -> RunState:
    """M9B: run advisory A1 fact extraction (safe, never fails the run), then the
    deterministic lexical evidence baseline. A1 ExtractedFacts are advisory only
    and are NEVER consumed by the deterministic evidence/requirements pipeline."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        run_phases.start(db, run, "detect_facts")
        a1 = fact_extraction.run_a1_fact_extraction(db, run)
        count = evidence_pipeline.run_discovery(db, run)
        # M9C: advisory A1 evidence-candidate mapping (safe; never fails the run).
        # Persists agent-origin EvidenceCandidates that the unchanged deterministic
        # verify/link stages then process. Deterministic baseline is unaffected.
        mapping = evidence_mapping.run_a1_evidence_mapping(db, run)
        _set_stage(db, run, "extract_facts_and_map_evidence")
        run_phases.finish(
            db, run, "detect_facts", "succeeded",
            detail={
                "a1_status": a1.status,
                "facts_created": a1.facts_persisted,
                "evidence_candidates": count + mapping.candidates_persisted,
            },
        )
        db.commit()
        logger.info(
            "A1 facts=%s/%d evidence candidates=%d mapping=%s/+%d run=%s",
            a1.status, a1.facts_persisted, count, mapping.status,
            mapping.candidates_persisted, run.run_id,
        )
        return state
    finally:
        db.close()


def node_verify_evidence(state: RunState) -> RunState:
    """Deterministic exact-quote verification → EvidenceAnchors. Continues even
    when individual candidates remain unverified or none were found."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        run_phases.start(db, run, "formal_checks")
        counts = evidence_pipeline.run_verification(db, run)
        _set_stage(db, run, "verify_evidence")
        db.commit()
        logger.info("evidence verification %s run=%s", counts, run.run_id)
        return state
    finally:
        db.close()


def node_evaluate_requirements_and_rules(state: RunState) -> RunState:
    """Deterministic formal-eligibility precheck: run the 12 official core rules
    against the frozen project+partner snapshot, persist RuleResults +
    RequirementAssessments + OpenIssues; then materialize supplementary evidence
    links. No LLM, no network, no source text."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        counts = evaluation.evaluate_run(db, run.run_id)
        # Link verified/unverified anchors to the assessments now that they
        # exist. Supplementary only — never changes a deterministic status.
        evidence_pipeline.materialize_links(db, run)
        # M9C: complete the agent evidence-proposal evaluation trail (verification
        # status + linked assessment). Internal only; idempotent under replay.
        evidence_mapping.backfill_agent_evaluation(db, run)
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.requirements_evaluated",
            status="passed",
            detail=(
                f"blocker={counts['blocker']} warning={counts['warning']} "
                f"info={counts['info']}"
            ),
        )
        _set_stage(db, run, "evaluate_requirements_and_rules")
        run_phases.finish(
            db, run, "formal_checks", "succeeded", detail=dict(counts)
        )
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="run.requirements_evaluated", target_type="run",
            target_id=run.run_id, detail=counts,
        )
        db.commit()
        return state
    finally:
        db.close()


def node_web_research(state: RunState) -> RunState:
    """Öffentliche Webrecherche im Lauf (Owner-Entscheid; Freigabepflicht R8):
    nur wenn das Web-Budget des Laufs > 0 ist, die Webrecherche verfügbar ist,
    ein freigegebener public-safe Brief UND freigegebene Suchanfragen vorliegen
    — sonst ehrlicher Skip. Ausgeführt wird exakt der
    freigegebene Text (Single-Use im Firewall-Chokepoint), begrenzt durch
    max_web_calls. Wiederverwendet das BESTEHENDE Research-Vertikal
    (Search Query Firewall im Service → Executor → Fake/Firecrawl).
    Ergebnisse bleiben ResearchResult-Kandidaten — nie Evidenz/Anker. Ein
    Fehler markiert nur die Phase als fehlgeschlagen (Partial Success)."""
    from app.db.models import ResearchBrief, SearchQueryApproval
    from app.research import brief_service
    from app.research.service import ResearchBlocked
    from app.security.data_class import derive_data_class, is_external_blocked

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        run_phases.start(db, run, "web_research")
        settings = get_settings()
        policy = db.get(RunPolicySnapshot, run.run_id)
        project = db.get(Project, run.project_id)
        class_blocked = is_external_blocked(
            derive_data_class(project.data_classification if project else {})
        )
        max_web_calls = policy.max_web_calls if policy is not None else 0
        mode = brief_service.provider_mode()
        active_brief = db.scalar(
            select(ResearchBrief)
            .where(
                ResearchBrief.project_id == run.project_id,
                ResearchBrief.workspace_id == run.workspace_id,
                ResearchBrief.status == "approved",
            )
            .order_by(ResearchBrief.version.desc())
        )
        # Der Lauf führt nur Approvals der aktiven Briefversion aus. Querytext
        # stammt damit ausschliesslich aus dem menschlich freigegebenen Brief.
        approvals = list(
            db.scalars(
                select(SearchQueryApproval)
                .where(
                    SearchQueryApproval.project_id == run.project_id,
                    SearchQueryApproval.workspace_id == run.workspace_id,
                    SearchQueryApproval.status == "approved",
                    SearchQueryApproval.research_brief_id == (
                        active_brief.research_brief_id if active_brief else ""
                    ),
                )
                .order_by(SearchQueryApproval.created_at, SearchQueryApproval.approval_id)
            )
        )
        skip_reason = None
        if max_web_calls <= 0:
            skip_reason = "web_research_not_requested"
        elif class_blocked:
            skip_reason = "web_research_class_blocked"
        elif mode == "unavailable":
            skip_reason = "web_research_unavailable"
        elif active_brief is None:
            skip_reason = "research_brief_required"
        elif not approvals:
            skip_reason = "approval_required"
        if skip_reason is not None:
            run_phases.finish(
                db, run, "web_research", "skipped",
                detail={"reason": skip_reason},
            )
            db.commit()
            return state

        try:
            outcome = brief_service.run(
                db, active_brief, run.created_by,
                [approval.approval_id for approval in approvals[:max_web_calls]],
            )
            run_phases.finish(
                db, run, "web_research", "succeeded",
                detail={
                    "approved_queries": len(approvals),
                    "web_queries": len(outcome.task_ids),
                    "results_found": outcome.result_count,
                    "execution_mode": outcome.execution_mode,
                },
            )
            db.commit()
            logger.info(
                "web research queries=%d results=%d run=%s",
                len(outcome.task_ids), outcome.result_count, run.run_id,
            )
        except (ResearchBlocked, brief_service.BriefError) as blocked:
            # Firewall hat das letzte Wort — Phase ehrlich übersprungen.
            run_phases.finish(
                db, run, "web_research", "skipped",
                detail={"reason": blocked.code},
            )
            db.commit()
        except Exception:  # Partial Success: der Lauf geht weiter.
            logger.exception("web research failed; continuing run %s", run.run_id)
            db.rollback()
            run = db.get(AnalysisRun, state["run_id"])
            run_phases.finish(
                db, run, "web_research", "failed",
                error_code="web_research_failed",
            )
            db.commit()
        return state
    finally:
        db.close()


def node_create_template_drafts(state: RunState) -> RunState:
    """Create deterministic PortalFieldDraft templates + initial DraftVersions
    idempotently from the immutable run inputs. Runs BEFORE the A2 drafting
    stage so advisory suggestions can reference an existing base version."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        run_phases.start(db, run, "draft_fields")
        count = drafts_pipeline.create_template_drafts(db, run)
        _set_stage(db, run, "create_template_drafts")
        run_phases.add_detail(db, run, "draft_fields", {"template_drafts": count})
        db.commit()
        logger.info("template drafts created=%d run=%s", count, run.run_id)
        return state
    finally:
        db.close()


def node_draft_fields(state: RunState) -> RunState:
    """A2-Feldvorschläge im normalen Lauf: je A2-fähigem Feld eine echte
    AsyncOperation über den gemeinsamen Redraft-Kern. Nur advisory
    DraftSuggestions (proposed) — nie Auto-Übernahme, nie DraftVersions.
    Läuft nur, wenn der Modus KI erlaubt (cloud_assisted bzw. local_only mit
    konsumierter Opt-in-Bestätigung); sonst ehrlicher Skip. Feld-Fehler
    stoppen weder die übrigen Felder noch den Lauf (Partial Success)."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        mode = run.processing_mode
        ai_enabled = mode == "cloud_assisted" or (
            mode == "local_only" and field_drafting.local_ai_confirmed(run)
        )
        if not ai_enabled:
            reason = f"mode_{mode}"
            drafts_pipeline.record_a2_skipped(db, run, reason)
            _set_stage(db, run, "draft_fields")
            run_phases.finish(
                db, run, "draft_fields", "succeeded",
                detail={
                    "suggestions_created": 0,
                    "a2_status": "skipped",
                    "a2_reason": reason,
                },
            )
            db.commit()
            return state
        counters = drafts_pipeline.run_a2_field_suggestions(db, run)
        _set_stage(db, run, "draft_fields")
        status, error_code = "succeeded", None
        if counters["suggestions_created"] == 0 and counters["fields_failed"] > 0:
            status, error_code = "failed", "a2_all_failed"
        run_phases.finish(
            db, run, "draft_fields", status,
            detail={**counters, "a2_status": "ran"}, error_code=error_code,
        )
        db.commit()
        logger.info(
            "A2 suggestions created=%d failed=%d skipped=%d run=%s",
            counters["suggestions_created"], counters["fields_failed"],
            counters["fields_skipped"], run.run_id,
        )
        return state
    finally:
        db.close()


def node_critic_review(state: RunState) -> RunState:
    """Deterministischer Review-Aggregator (läuft IMMER) + advisory A3-Kritik
    auf geeigneten Cloud-Läufen. A3-Findings werden separat persistiert
    (source="agent") und überschreiben A2-Vorschläge nie. Ein A3-Fehler lässt
    Drafts/Vorschläge intakt und markiert nur die Phase als fehlgeschlagen —
    der Lauf endet «teilweise abgeschlossen», nie komplett leer."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        run_phases.start(db, run, "quality_review")
        review_package.apply_findings(db, run)

        phase_status, error_code = "succeeded", None
        available, reason = critic_review.availability(run)
        if available:
            policy = db.get(RunPolicySnapshot, run.run_id)
            budget_stop = drafts_pipeline.budget_stop_reason(db, run, policy)
            if budget_stop is not None:
                available, reason = False, budget_stop
        if not available:
            controls.record(
                db, workspace_id=run.workspace_id, project_id=run.project_id,
                source_id=None, control_id="CTRL.DATA_POLICY", status="passed",
                detail=f"a3_skipped {reason}",
            )
            a3_detail = {"a3_status": "skipped", "a3_reason": reason,
                         "agent_findings": 0}
        else:
            outcome = critic_review.run_a3_evidence_consistency(db, run)
            if outcome.status == "succeeded":
                review_package.apply_agent_findings(
                    db, run, outcome.findings, profile_id=A3_PROFILE_ID
                )
                a3_detail = {"a3_status": "succeeded",
                             "agent_findings": len(outcome.findings)}
            elif outcome.status in ("skipped", "blocked"):
                a3_detail = {"a3_status": "skipped",
                             "a3_reason": outcome.reason, "agent_findings": 0}
            else:  # failed / timed_out — Partial Success, Lauf geht weiter.
                phase_status = "failed"
                error_code = outcome.reason or "a3_failed"
                a3_detail = {"a3_status": outcome.status,
                             "a3_reason": outcome.reason, "agent_findings": 0}
        _set_stage(db, run, "critic_review")
        run_phases.finish(
            db, run, "quality_review", phase_status,
            detail=a3_detail, error_code=error_code,
        )
        db.commit()
        return state
    finally:
        db.close()


def node_aggregate_review(state: RunState) -> RunState:
    """Aggregate findings, evidence gaps, open issues and assessments into the
    ReviewPackage; compute the review package version + approval scope hash."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        package = review_package.refresh_package(
            db, run, recompute_findings=False)
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="CTRL.OUTPUT_SCHEMA", status="passed",
            detail=f"review_package_version={package.review_package_version}",
        )
        _set_stage(db, run, "aggregate_review")
        db.commit()
        return state
    finally:
        db.close()


def node_human_review(state: RunState) -> RunState:
    """Record that review is available. Deterministic and non-pausing: human
    review, recheck and approval happen on the completed run via the review API.
    The run is never auto-approved here."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="CTRL.APPROVAL_GATE", status="warning",
            detail="phase=human_review; reason=review_available_no_auto_approval",
        )
        _set_stage(db, run, "human_review")
        db.commit()
        return state
    finally:
        db.close()


def node_finalize_run(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        # Reload-and-check before finalize — never complete a cancelled run.
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        _set_stage(db, run, "finalize_run")
        transition_run(run, "completed")  # guards against terminal states
        run.ended_at = _now()
        # Run-Wahrheit: der Projekt-Pointer zeigt immer auf den letzten
        # erfolgreich abgeschlossenen Lauf (nie failed/stopped/cancelled).
        project = db.get(Project, run.project_id)
        if project is not None:
            project.active_run_id = run.run_id
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.operation_state", status="passed",
            detail="finalized",
        )
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="run.completed", target_type="run", target_id=run.run_id,
        )
        db.commit()
        return state
    finally:
        db.close()


_checkpointer: SqliteSaver | None = None
_graph = None


def get_checkpointer() -> SqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        path = Path(get_settings().checkpoint_db_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
        _checkpointer.setup()
    return _checkpointer


def get_graph():
    global _graph
    if _graph is None:
        builder = StateGraph(RunState)
        builder.add_node("initialize", node_initialize)
        builder.add_node("validate_source_snapshot",
                         node_validate_source_snapshot)
        builder.add_node(
            "extract_facts_and_map_evidence",
            node_extract_facts_and_map_evidence,
        )
        builder.add_node("verify_evidence", node_verify_evidence)
        builder.add_node(
            "evaluate_requirements_and_rules",
            node_evaluate_requirements_and_rules,
        )
        builder.add_node("web_research", node_web_research)
        builder.add_node("draft_fields", node_draft_fields)
        builder.add_node("create_template_drafts", node_create_template_drafts)
        builder.add_node("critic_review", node_critic_review)
        builder.add_node("aggregate_review", node_aggregate_review)
        builder.add_node("human_review", node_human_review)
        builder.add_node("finalize_run", node_finalize_run)
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "validate_source_snapshot")
        builder.add_edge(
            "validate_source_snapshot", "extract_facts_and_map_evidence"
        )
        builder.add_edge("extract_facts_and_map_evidence", "verify_evidence")
        builder.add_edge("verify_evidence", "evaluate_requirements_and_rules")
        # Recherche VOR den Drafts (Kandidaten fliessen in den VC-A2-Kontext);
        # Templates VOR der A2-Stufe, damit die advisory Vorschläge eine
        # existierende Basisversion referenzieren.
        builder.add_edge("evaluate_requirements_and_rules", "web_research")
        builder.add_edge("web_research", "create_template_drafts")
        builder.add_edge("create_template_drafts", "draft_fields")
        builder.add_edge("draft_fields", "critic_review")
        builder.add_edge("critic_review", "aggregate_review")
        builder.add_edge("aggregate_review", "human_review")
        builder.add_edge("human_review", "finalize_run")
        builder.add_edge("finalize_run", END)
        _graph = builder.compile(checkpointer=get_checkpointer())
    return _graph
