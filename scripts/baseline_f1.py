#!/usr/bin/env python
"""R0.3 — Baseline-Messung am Goldfall F1 (QUALIMON) gegen eine LAUFENDE Instanz.

Spielt F1 (docs/evaluation/cases/F1_synthetic_case.md) per API ein und misst
den Ist-Zustand VOR den Reparaturen:

  1. Projekt anlegen (D2 synthetic, deterministic_only, Websearch off)
  2. Budget-Snapshot + 3 synthetische Partner + 1 Textquelle
  3. Standard-Analyse (Fake-Provider) ausfuehren
  4. Die 8 aktiven Feldtexte aus F1 eintragen
  5. Reliability-Pass ausfuehren
  6. Messwerte erheben: Blockerzahlen je Screen-Datenquelle,
     Findings gesamt + je Meldungstyp (Duplikat-Nachweis), Feld-Status

Nichts wird gefixt; das Skript ist reine Messung (R0.3).

    python scripts/baseline_f1.py [--base http://localhost:8000/api/v1]

Ausgabe: JSON auf stdout (fuer docs/evaluation/baseline-report.md).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections import Counter

import httpx

ORIGIN = "http://localhost:3000"
PROFILE = "innosuisse_innovation_project_with_implementation_partner"

# F1: D2 synthetic simulation, fake/local, Websearch off.
F1_CLASSIFICATION = {
    "sensitivity": "confidential",
    "origin": "synthetic",
    "processing_mode": "deterministic_only",
    "web_research_mode": "off",
    "nda_applies": False,
}

F1_TITLE = "QUALIMON — KI-gestützte Qualitätsüberwachung für Produktionslinien"

F1_DESCRIPTION = (
    "Das fiktive Projekt QUALIMON entwickelt eine KI-gestützte Lösung zur "
    "frühzeitigen Erkennung von Qualitätsabweichungen in industriellen "
    "Produktionslinien. Ein Schweizer Umsetzungspartner möchte Maschinendaten, "
    "Qualitätsdaten und Prozessdaten aus Pilotanlagen analysieren, um Ausschuss, "
    "Nacharbeit und ungeplante Stillstände zu reduzieren. Der Forschungspartner "
    "unterstützt bei Datenmodellierung, erklärbarer KI, Validierungsmethodik und "
    "Evaluation. (Synthetischer F1-Goldfall — kein echter Antrag.)"
)

F1_BUDGET = {
    "direct_total_project_costs_excluding_overhead": 420_000,
    "implementation_own_contribution": 150_000,
    "cash_contribution": 12_000,
    "total_requested_funding": 258_000,
    "duration_months": 24,
}

F1_PARTNERS = [
    {
        "name": "Swiss Applied AI Lab",
        "partner_type": "research_partner",
        "project_role": "Datenmodellierung, erklärbare KI, Validierungsmethodik",
        "country": "CH",
        "research_partner_eligibility_status": "eligible",
        "personnel_independence_status": "confirmed",
        "financial_independence_status": "confirmed",
    },
    {
        "name": "Alpine Monitoring Systems AG",
        "partner_type": "implementation_partner",
        "project_role": "Pilotzugang, Domänenwissen, industrielle Validierung",
        "country": "CH",
        "swiss_value_creation": True,
        "personnel_independence_status": "confirmed",
        # F1: finale Verifikation der finanziellen Unabhängigkeit steht aus.
        "financial_independence_status": "needs_input",
    },
    {
        "name": "Helvetic Components Factory",
        "partner_type": "other",
        "project_role": "Pilotanlage für Produktionsdaten",
        "country": "CH",
    },
]

# Die 8 aktiven Feldtexte, wortgetreu aus F1_synthetic_case.md.
F1_FIELDS = {
    "INTRO.APP.NAME": (
        "QUALIMON — KI-gestützte Qualitätsüberwachung für Produktionslinien"
    ),
    "INTRO.APP.NAME_EN": (
        "QUALIMON — AI-based Quality Monitoring for Production Lines"
    ),
    "INTRO.APP.ABSTRACT": (
        "QUALIMON develops an AI-based monitoring module for industrial "
        "production lines. The system aims to detect quality deviations "
        "earlier, reduce scrap and support better maintenance decisions. "
        "[[Angabe ergänzen: konkreter Nutzen und Validierung]]"
    ),
    "INTRO.APP.EXECUTIVE_SUMMARY": (
        "Industrial production companies often detect quality deviations too "
        "late. As a result, defective batches, rework and unplanned downtime "
        "create avoidable costs. QUALIMON addresses this issue by combining "
        "machine signals, quality measurements and process context in an "
        "AI-supported monitoring module.\n\n"
        "The project develops a prototype that detects abnormal production "
        "patterns and explains potential causes to process engineers. The "
        "implementation partner expects a 20 percent reduction in scrap and a "
        "30 percent faster detection of critical deviations. These values are "
        "project targets and still require baseline data, measurement method "
        "and validation during the pilot.\n\n"
        "The research partner contributes expertise in data modelling, "
        "explainable AI, validation design and industrial analytics. The "
        "solution will be tested on synthetic and pilot production data before "
        "integration into the implementation partner's monitoring environment.\n\n"
        "[[Angabe ergänzen: baseline, measurement method, validation moment]]"
    ),
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS": (
        "The project partners declare that they are financially independent. "
        "No ownership relation above the relevant threshold is known at this "
        "stage. A final verification of ownership and financial dependencies "
        "is still required before submission."
    ),
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": (
        "Business targets and business model\n\n"
        "The implementation partner plans to commercialize QUALIMON as an "
        "add-on module for existing production monitoring systems. The target "
        "customers are Swiss industrial SMEs with automated production lines, "
        "recurring quality checks and a need for earlier deviation detection.\n\n"
        "The solution is expected to reduce scrap by 20 percent and increase "
        "the speed of quality deviation detection by 30 percent. Based on "
        "internal assumptions, a medium-sized production site could save up to "
        "CHF 300'000 per year through reduced waste, fewer rework cycles and "
        "better process stability. These assumptions are not yet supported by "
        "external market evidence.\n\n"
        "Customers and market access\n\n"
        "The primary customer group consists of industrial companies in "
        "precision manufacturing, plastics processing and component assembly. "
        "The first pilot customer is expected to validate the prototype in an "
        "operational production setting.\n\n"
        "The go-to-market plan is still incomplete. The project team plans to "
        "use pilot results, customer demonstrations and industry events to "
        "reach first customers after the project.\n\n"
        "Competition and USP\n\n"
        "Existing competitors offer general predictive-maintenance or "
        "machine-monitoring tools. QUALIMON aims to focus specifically on "
        "quality deviations and root-cause explanations for process engineers.\n\n"
        "[[Angabe ergänzen: Marktgrösse, Wettbewerber, Zahlungsbereitschaft, "
        "Go-to-Market, belastbare Quelle]]"
    ),
    "SOL.INNOVATION_SOLUTION.EDITOR": (
        "State of the art\n\n"
        "Current industrial monitoring systems use rule-based thresholds, "
        "statistical process control and predictive-maintenance models. These "
        "approaches can detect anomalies, but they often provide limited "
        "explanation of why a quality deviation occurs and how it relates to "
        "process parameters.\n\n"
        "Recent AI approaches in manufacturing use machine learning for "
        "anomaly detection and process optimization. However, many solutions "
        "require extensive customization and do not provide sufficient "
        "explanation for quality engineers.\n\n"
        "Novelty of the solution\n\n"
        "QUALIMON combines machine signals, quality measurements and process "
        "context in an explainable AI module. The system should identify early "
        "deviation patterns and propose possible causes. The project aims to "
        "move from pure anomaly detection to actionable quality-deviation "
        "support.\n\n"
        "The expected technical goals are:\n"
        "- 20 percent reduction in scrap\n"
        "- 30 percent faster detection of critical deviations\n"
        "- at least 85 percent precision in detecting relevant deviation events\n\n"
        "The baseline, measurement method and validation time point are not "
        "yet fully defined.\n\n"
        "Preliminary work\n\n"
        "The implementation partner has access to production monitoring data "
        "and quality reports from pilot lines. The research partner has "
        "experience with explainable AI and industrial analytics. The exact "
        "data quality, annotation process and legal basis for using the "
        "production data still need to be clarified.\n\n"
        "Partner suitability\n\n"
        "The implementation partner provides pilot access, domain knowledge "
        "and industrial validation. The research partner provides AI "
        "methodology and evaluation expertise. Evidence for partner track "
        "record and infrastructure should still be linked.\n\n"
        "IPR / FTO\n\n"
        "No patent search or Freedom-to-Operate analysis has been completed "
        "yet. The project team assumes that the main innovation will be "
        "protected as software know-how and trade secret, but the ownership of "
        "newly developed models, interfaces and datasets still needs to be "
        "clarified between the partners.\n\n"
        "[[Angabe ergänzen: concrete SOTA comparison, data source details, "
        "training data quality, validation design, IPR/FTO strategy]]"
    ),
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION": (
        "The project includes coordination, reporting, partner alignment and "
        "preparation of review meetings. Management work is planned across the "
        "project duration. The exact distribution between project management, "
        "technical coordination and reporting still needs to be clarified."
    ),
}


def _mut(csrf: str) -> dict:
    return {
        "X-CSRF-Token": csrf,
        "Origin": ORIGIN,
        "Idempotency-Key": uuid.uuid4().hex,
        "Content-Type": "application/json",
    }


def _wait(c: httpx.Client, base: str, op_id: str, tries: int = 120) -> str:
    for _ in range(tries):
        status = c.get(f"{base}/operations/{op_id}").json()["status"]
        if status in ("succeeded", "failed", "cancelled"):
            return status
        time.sleep(0.5)
    return "timeout"


def run(base: str, email: str, password: str) -> dict:
    t0 = time.monotonic()
    steps: list[str] = []
    with httpx.Client(timeout=60.0) as c:
        r = c.post(f"{base}/session", json={"email": email, "password": password})
        r.raise_for_status()
        csrf = r.json()["csrf_token"]
        steps.append("Login")

        pid = c.post(f"{base}/projects", headers=_mut(csrf), json={
            "title": F1_TITLE,
            "description": F1_DESCRIPTION,
            "innovation_field": "ICT / Industrial AI",
            "funding_instrument_profile_id": PROFILE,
            "data_classification": F1_CLASSIFICATION,
        }).json()["project_id"]
        steps.append("Projekt anlegen (Intake)")

        r = c.patch(f"{base}/projects/{pid}", headers=_mut(csrf), json=F1_BUDGET)
        r.raise_for_status()
        steps.append("Budget-Snapshot eintragen")

        for partner in F1_PARTNERS:
            c.post(
                f"{base}/projects/{pid}/partners", headers=_mut(csrf), json=partner
            ).raise_for_status()
            steps.append(f"Partner erfassen: {partner['partner_type']}")

        c.post(f"{base}/projects/{pid}/sources/text", headers=_mut(csrf), json={
            "name": "F1 Projektkontext (synthetisch)",
            "text": F1_DESCRIPTION,
            "data_classification": F1_CLASSIFICATION,
        }).raise_for_status()
        sv = ""
        for _ in range(40):
            rows = c.get(f"{base}/projects/{pid}/sources").json()
            ready = next((s for s in rows if s["status"] == "processed"
                          and s.get("current_source_version_id")), None)
            if ready:
                sv = ready["current_source_version_id"]
                break
            time.sleep(0.5)
        if not sv:
            raise RuntimeError("Quelle wurde nicht verarbeitet")
        steps.append("Quelle hochladen + Verarbeitung abwarten")

        accepted = c.post(f"{base}/projects/{pid}/runs", headers=_mut(csrf), json={
            "settings": {
                "processing_mode": "deterministic_only", "max_cost_chf": 0,
                "max_llm_calls": 0, "max_web_calls": 0,
                "source_version_ids": [sv],
            },
        }).json()
        run_id = accepted["resource_id"]
        if _wait(c, base, accepted["operation_id"]) != "succeeded":
            raise RuntimeError("Analyse-Run nicht erfolgreich")
        steps.append("Standard-Analyse starten + abwarten")

        for field_id, text in F1_FIELDS.items():
            draft = c.get(f"{base}/runs/{run_id}/fields/{field_id}").json()
            r = c.patch(
                f"{base}/runs/{run_id}/fields/{field_id}", headers=_mut(csrf),
                json={
                    "base_version_id": draft["current_version"]["draft_version_id"],
                    "text": text,
                },
            )
            r.raise_for_status()
            steps.append(f"Feldtext eintragen: {field_id}")

        # Zustand VOR dem Recheck festhalten (Stale-Finding-Nachweis).
        review_pre = c.get(f"{base}/runs/{run_id}/review").json()

        recheck = c.post(f"{base}/runs/{run_id}/rechecks", headers=_mut(csrf), json={
            "expected_review_package_version":
                review_pre["review_package_version"],
            "changed_target_refs": [],
        }).json()
        if _wait(c, base, recheck["operation_id"]) != "succeeded":
            raise RuntimeError("Recheck nicht erfolgreich")
        steps.append("Prüfung aktualisieren (Recheck)")

        rel = c.post(f"{base}/runs/{run_id}/reliability", headers=_mut(csrf)).json()
        if _wait(c, base, rel["operation_id"]) != "succeeded":
            raise RuntimeError("Reliability-Pass nicht erfolgreich")
        steps.append("Qualitäts-/Reliability-Prüfung ausführen")

        # ---- Messung (read-only) -------------------------------------------
        projects = c.get(f"{base}/projects").json()["items"]
        own = next(p for p in projects if p["project_id"] == pid)

        def card_status(p: dict) -> str:
            # Frontend-Ableitung lib/projects.ts::toCardStatus (Dashboard).
            ws = p.get("workflow_summary") or {}
            if ws.get("warning_badge") == "run_stopped":
                return "blockiert"
            if ws.get("next_action") == "approve_review":
                return "review_offen"
            return "in_bearbeitung"

        requirements = c.get(f"{base}/runs/{run_id}/requirements").json()
        review = c.get(f"{base}/runs/{run_id}/review").json()
        reliability = c.get(f"{base}/runs/{run_id}/reliability").json()
        fields = c.get(f"{base}/runs/{run_id}/fields").json()

        req_status = Counter(a["status"] for a in requirements)
        req_issue_sev = Counter(
            i["severity"] for a in requirements for i in a.get("open_issues", [])
        )
        finding_msgs = Counter(
            (f["severity"], f["description"]) for f in review["findings"]
            if f["status"] == "open"
        )
        rel_findings = reliability.get("findings", [])
        rel_msgs = Counter(
            (f["severity"], f["description"]) for f in rel_findings
            if f["status"] == "open"
        )
        rel_summary = reliability.get("summary") or {}

        elapsed = round(time.monotonic() - t0, 1)
        return {
            "f1_project_id": pid,
            "run_id": run_id,
            "elapsed_seconds_scripted": elapsed,
            "manual_steps_checklist": steps,
            "manual_step_count": len(steps),
            "screen_sources": {
                "dashboard": {
                    "definition": "Anzahl Projekte mit cardStatus 'blockiert' "
                                  "(lib/dashboard.ts::summarizeProjects; blockiert "
                                  "nur bei warning_badge run_stopped)",
                    "f1_card_status": card_status(own),
                    "workspace_blocked_projects": sum(
                        1 for p in projects if card_status(p) == "blockiert"
                    ),
                    "workspace_project_count": len(projects),
                },
                "anforderungen": {
                    "definition": "RequirementAssessments + deren OpenIssues "
                                  "(GET /runs/{id}/requirements)",
                    "assessment_count": len(requirements),
                    "status_counts": dict(req_status),
                    "open_issue_severity_counts": dict(req_issue_sev),
                },
                "pruefung_review_package_vor_recheck": {
                    "definition": "ReviewPackage direkt nach Feld-Edits, VOR dem "
                                  "Recheck — zeigt veraltete Findings der "
                                  "Template-Stände",
                    "blocker_count": review_pre["blocker_count"],
                    "warning_count": review_pre["warning_count"],
                    "recheck_required": review_pre["recheck_required"],
                },
                "pruefung_review_package": {
                    "definition": "ReviewPackage (GET /runs/{id}/review) — Quelle "
                                  "der Qualitätsprüfung",
                    "blocker_count": review["blocker_count"],
                    "warning_count": review["warning_count"],
                    "approval_status": review["approval_status"],
                    "recheck_required": review["recheck_required"],
                    "open_findings": sum(finding_msgs.values()),
                    "open_issues": len(review["open_issues"]),
                },
                "pruefung_reliability": {
                    "definition": "ReliabilityView (GET /runs/{id}/reliability) — "
                                  "Zuverlässigkeits-Kacheln",
                    "blocker_count": rel_summary.get("blocker_count"),
                    "warning_count": rel_summary.get("warning_count"),
                    "claim_count": rel_summary.get("claim_count"),
                    "unsupported_claims": rel_summary.get("unsupported_claims"),
                    "open_findings": sum(rel_msgs.values()),
                    "stale": reliability.get("reliability_stale"),
                },
                "export": {
                    "definition": "lib/export-view.ts::summarizeExportReadiness — "
                                  "blockerCount = ReviewPackage.blocker_count; "
                                  "fieldsReady = Felder mit status 'reviewed'",
                    "blocker_count": review["blocker_count"],
                    "fields_ready": sum(
                        1 for f in review["fields"] if f["status"] == "reviewed"
                    ),
                    "fields_total": len(review["fields"]),
                },
            },
            "findings_by_message_review": [
                {"count": n, "severity": sev, "description": desc}
                for (sev, desc), n in finding_msgs.most_common()
            ],
            "findings_by_message_reliability": [
                {"count": n, "severity": sev, "description": desc}
                for (sev, desc), n in rel_msgs.most_common()
            ],
            "fields": [
                {
                    "field_id": f["field_id"],
                    "status": f["status"],
                    "character_count": f["character_count"],
                    "character_limit": f.get("character_limit"),
                    "open_issue_count": f.get("open_issue_count", 0),
                    "placeholder_marker_count":
                        f.get("current_version", {}).get("text", "").count("[["),
                }
                for f in fields
            ],
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=os.environ.get(
        "SMOKE_BASE", "http://localhost:8000/api/v1"))
    p.add_argument("--email", default=os.environ.get(
        "E2E_EMAIL", "anna.keller@example.test"))
    p.add_argument("--password", default=os.environ.get(
        "E2E_PASSWORD", "changeme-dev-lead"))
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run(args.base, args.email, args.password)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
