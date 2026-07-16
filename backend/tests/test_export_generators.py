"""Working-copy / technical-evidence v2 generator tests."""
from __future__ import annotations

import copy
import io
import json
import uuid

import docx

from app.db.models import AgentInvocation, AnalysisRun, ExportArtifact, UsageRecord
from app.db.session import SessionLocal
from app.exports.generators import GENERATORS
from app.exports.snapshot import _technical_trace
from tests.export_helpers import download, make_export, setup_approved_run
from tests.review_helpers import setup_completed_run


def _snapshot(export_id: str) -> dict:
    db = SessionLocal()
    try:
        return copy.deepcopy(db.get(ExportArtifact, export_id).export_snapshot_json)
    finally:
        db.close()


def _paragraphs(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    table_text = "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    return "\n".join(p.text for p in document.paragraphs) + "\n" + table_text


def test_working_doc_is_snapshot_based_and_has_no_technical_ids(client):
    csrf, _project_id, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    snapshot = _snapshot(artifact["export_id"])
    snapshot["structured"]["budget"]["values"] = [
        {"label": "Direkte Projektkosten (ohne Overhead)", "value": 120000, "provenance": "Import bestätigt: Antrag.pdf", "copy_target": "budget:direct_total_project_costs_excluding_overhead"}
    ]
    data = GENERATORS["docx"](snapshot, "technical-hash-that-must-not-appear")
    text = _paragraphs(data)
    assert "ENTWURF – Arbeitskopie – Nicht zur Einreichung" in text
    assert "Partner" in text and "Budgetübersicht" in text
    assert "CHF 120’000.00" in text
    assert "Antragssprache: noch in Innolink festlegen" in text
    assert run_id not in text
    assert "INTRO.APP.ABSTRACT" not in text
    assert "technical-hash-that-must-not-appear" not in text


def test_approved_docx_is_still_never_submission_ready(client):
    csrf, run_id = setup_approved_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    text = _paragraphs(download(client, artifact["export_id"]).content)
    assert "Arbeitskopie" in text
    assert "einreichbereit" not in text.lower()
    assert "keine Einreichfreigabe" in text


def test_markdown_has_human_sections_and_full_field_text_without_ids(client):
    csrf, _project_id, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    snapshot = _snapshot(artifact["export_id"])
    a = GENERATORS["markdown"](snapshot, "ignored")
    assert a == GENERATORS["markdown"](snapshot, "other-ignored")
    text = a.decode("utf-8")
    assert "## Partner" in text
    assert "## Budgetübersicht" in text
    assert "## Narrative Innolink-Felder" in text
    assert "## Offene Aufgaben" in text
    assert "## Quellenverzeichnis" in text
    assert "## Noch manuell in Innolink zu erfassen" in text
    assert run_id not in text
    assert "INTRO.APP.ABSTRACT" not in text


def test_optional_explanations_and_composites_are_honestly_rendered(client):
    csrf, _project_id, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    snapshot = _snapshot(artifact["export_id"])
    financial_rule = next(r for r in snapshot["rule_results"] if r["rule_id"] == "INNO.PARTNER.INDEPENDENCE.FINANCIAL_20")
    financial_rule["outcome_label"] = "below_threshold_and_confirmed"
    snapshot["structured"]["project"]["structured_answers"] = {"management_hours": {"management_hours": 0, "total_project_hours": 50}}
    financial = next(f for f in snapshot["fields"] if f["field_id"] == "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS")
    management = next(f for f in snapshot["fields"] if f["field_id"] == "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION")
    financial["text"] = "[[Angabe ergänzen: Finanzkommentar]]"
    management["text"] = "[[Angabe ergänzen: Management]]"
    composite = next(f for f in snapshot["fields"] if f["field_id"] == "VC.BUSINESS_TARGETS_MODEL.EDITOR")
    composite["text"] = "3.1 Markt\nText A\n3.2 Zielgruppen\nText B\n3.3 Modell\nText C"
    from app.exports.generators.common import field_working_text
    assert field_working_text(snapshot, financial)[0] == "Nicht erforderlich gemäss bestätigten Eingaben."
    assert field_working_text(snapshot, management)[0] == "Nicht erforderlich gemäss bestätigten Eingaben."
    text = _paragraphs(GENERATORS["docx"](snapshot, "x"))
    assert text.count("Nicht erforderlich gemäss bestätigten Eingaben.") >= 1
    assert "3.1" in text and "3.2" in text and "3.3" in text
    assert text.index("3.1") < text.index("3.2") < text.index("3.3")


def test_technical_evidence_v2_has_ids_and_hashes_but_no_raw_text(client):
    csrf, _project_id, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "technical_evidence")
    payload = json.loads(download(client, artifact["export_id"]).content)
    assert payload["schema"] == "technical-evidence-2"
    assert payload["export"]["run_id"] == run_id
    assert "project_title" not in payload["export"]
    assert all("text" not in item for item in payload["fields"])
    assert all("quote" not in item for item in payload["evidence_anchors"])
    assert "technical_trace" in payload
    snap = _snapshot(artifact["export_id"])
    assert GENERATORS["technical_evidence"](snap, payload["snapshot_hash"]) == download(client, artifact["export_id"]).content


def test_technical_trace_exposes_metering_only_for_real_model_calls(client):
    csrf, _project_id, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        usage_id = str(uuid.uuid4())
        db.add(UsageRecord(
            usage_record_id=usage_id, run_id=run_id, workspace_id=run.workspace_id,
            provider="openai", model="gpt-test", input_tokens=12, output_tokens=7,
            cost_chf=0.03, cost_status="priced", price_version="test-price-v1",
        ))
        common = {
            "run_id": run_id, "workspace_id": run.workspace_id, "project_id": run.project_id,
            "agent_id": "a2", "profile_id": "profile", "model_route": "route",
            "input_schema_id": "in-v1", "output_schema_id": "out-v1", "status": "succeeded",
        }
        db.add(AgentInvocation(
            invocation_id="fake-invocation", provider="fake-provider", model_id="fake-model",
            context_meta={"generation_kind": "rule_template", "model_call_attempted": False}, **common,
        ))
        db.add(AgentInvocation(
            invocation_id="real-invocation", provider="openai", model_id="gpt-test",
            usage_record_id=usage_id,
            context_meta={"generation_kind": "model_generated", "model_call_attempted": True}, **common,
        ))
        db.commit()
        trace = _technical_trace(db, run)
    finally:
        db.close()
    fake = next(item for item in trace["agent_invocations"] if item["invocation_id"] == "fake-invocation")
    real = next(item for item in trace["agent_invocations"] if item["invocation_id"] == "real-invocation")
    assert fake["call_kind"] == "fake_or_stubbed_call"
    assert "provider" not in fake and "model_id" not in fake
    assert fake["metering"]["status"] == "not_applicable_no_real_model_call"
    assert real["call_kind"] == "real_model_call"
    assert real["provider"] == "openai"
    assert real["metering"]["input_tokens"] == 12
