"""Hermetischer Harness-Test der Rollen-Modell-Evaluation (Fake-Adapter durchs
echte Gateway; nie reale Provider — conftest nullt die Keys)."""
from __future__ import annotations

import csv
import json

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.evaluation import role_model_eval as rme
from app.evaluation import role_model_scoring as scoring


@pytest.fixture()
def live_routing_env(monkeypatch):
    """Live-Routing (role_routes) ohne echte Provider: AI_EVAL_MODE=real +
    AGENT_FAKE_PROVIDER=false; Adapter werden hermetisch injiziert."""
    monkeypatch.setenv("AI_EVAL_MODE", "real")
    monkeypatch.setenv("AGENT_FAKE_PROVIDER", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_derived_registry_pins_candidate_without_fallback():
    registry = rme.derived_registry("a2", "openai_gpt_56_terra_candidate")
    role = registry.role_routes["A2_INNOSUISSE_PROPOSAL_WRITER"]
    assert role.primary == "openai_gpt_56_terra_candidate"
    assert role.fallback is None and role.comparison is None
    # Budgets der Original-Route bleiben erhalten (Kostenbremse).
    assert role.max_cost_chf and role.max_cost_chf > 0
    with pytest.raises(Exception):
        rme.derived_registry("a2", "unbekannte_route")


def test_holdout_requires_explicit_optin(db, live_routing_env, tmp_path):
    with pytest.raises(rme.EvalRefusal, match="HOLDOUT"):
        rme.execute_run(
            db, role="a1", candidate_key="anthropic_haiku_45_candidate",
            cases=("H1",), reps=1, fake=True, allow_holdout=False,
            results_dir=tmp_path,
        )


def test_a1_fake_sample_through_real_gateway(db, live_routing_env):
    sample = rme.run_a1_sample(
        db, case_id="F2", candidate_key="anthropic_haiku_45_candidate",
        rep=1, fake=True,
    )
    assert sample["execution"] == "fake_dryrun"
    assert sample["schema_valid"] is True
    assert sample["scores"]["fact_recall"] == 1.0
    assert sample["scores"]["boundary_accuracy"] == 1.0
    assert sample["evidence_ref_violations"] == 0
    # Gateway hat die Kandidaten-Route wirklich ausgeführt (Live-Routing).
    assert sample["usage"]["actual_adapter"] == "anthropic_direct"
    assert sample["usage"]["generation_kind"] == "model_generated"
    assert not any(f["status"] == "fail" for f in sample["fatal"])


def test_a3_fake_sample_baseline_and_flawed_variant(db, live_routing_env):
    sample = rme.run_a3_sample(
        db, case_id="F2", candidate_key="openai_gpt_56_terra_candidate",
        rep=1, fake=True,
    )
    variants = {v["variant"]: v for v in sample["variants"]}
    assert variants["baseline"]["status"] == "succeeded"
    assert variants["baseline"]["scores"]["false_consensus"] is None
    # Der Fake meldet den injizierten Fehler → kein falscher Konsens.
    assert variants["flawed"]["scores"]["false_consensus"] is False
    assert variants["baseline"]["scores"]["finding_recall_weighted"] == 1.0


def test_execute_run_writes_manifest_and_skips_existing(db, live_routing_env, tmp_path):
    first = rme.execute_run(
        db, role="a1", candidate_key="anthropic_haiku_45_candidate",
        cases=("F2",), reps=1, fake=True, allow_holdout=False,
        results_dir=tmp_path,
    )
    assert len(first) == 1
    sample = json.loads(first[0].read_text(encoding="utf-8"))
    manifest = sample["manifest"]
    assert manifest["prompt_sha"] == rme.prompt_fingerprint()
    assert manifest["holdout"] is False
    assert sample["execution"] == "fake_dryrun"
    # Existierende Samples werden übersprungen (Kostenbremse).
    second = rme.execute_run(
        db, role="a1", candidate_key="anthropic_haiku_45_candidate",
        cases=("F2",), reps=1, fake=True, allow_holdout=False,
        results_dir=tmp_path,
    )
    assert second == []


def test_blind_ingest_roundtrip_no_mapping_leak(db, live_routing_env, tmp_path):
    for candidate in ("openai_gpt_56_terra_candidate", "anthropic_sonnet_5_candidate"):
        rme.execute_run(
            db, role="a3", candidate_key=candidate,
            cases=("F2",), reps=1, fake=True, allow_holdout=False,
            results_dir=tmp_path,
        )
    blind_dir = rme.build_blind_pack("a3", results_dir=tmp_path)
    mapping = json.loads((blind_dir / "mapping.json").read_text(encoding="utf-8"))
    assert sorted(mapping["assignment"].values()) == ["Model A", "Model B"]
    # Kein Kandidatenname in den anonymisierten Unterlagen.
    for md in blind_dir.glob("*.md"):
        content = md.read_text(encoding="utf-8")
        for candidate in mapping["assignment"]:
            assert candidate not in content

    sheet = blind_dir / "a3_scoring_sheet.csv"
    rows = list(csv.DictReader(sheet.open("r", encoding="utf-8-sig", newline="")))
    assert rows, "Bogen darf nicht leer sein"
    for i, row in enumerate(rows):
        for crit in scoring.A3_RUBRIC_CRITERIA:
            row[crit] = str(3 + (i % 3))
        row["review_time_min"] = "5"
        row["rework_needed"] = "ja" if i % 2 == 0 else "nein"
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out = rme.ingest_scores("a3", sheet, results_dir=tmp_path)
    human = json.loads(out.read_text(encoding="utf-8"))["per_candidate"]
    assert set(human) == set(mapping["assignment"])
    for bucket in human.values():
        assert bucket["review_time_min_mean"] == 5.0

    summary = rme.aggregate(tmp_path)
    assert summary["status"].startswith("dry_run")
    assert summary["prompt_sha_consistent"] is True
    dumped = json.dumps(summary, ensure_ascii=False)
    # Whitelist: weder Blind-Mapping noch Draft-/Finding-Rohtexte im Summary.
    assert "Model A" not in dumped
    assert "Zielmodell ist ein Abo" not in dumped


def test_ingest_split_dev_holdout_and_aggregate_uses_split(
    db, live_routing_env, tmp_path
):
    """S3: Human-Scores werden je Dev/Holdout getrennt aggregiert — das
    Holdout-Aggregat erhält nie stille Dev-Werte."""
    for candidate in ("openai_gpt_56_terra_candidate", "anthropic_sonnet_5_candidate"):
        for case_id, allow in (("F2", False), ("H1", True)):
            rme.execute_run(
                db, role="a3", candidate_key=candidate,
                cases=(case_id,), reps=1, fake=True, allow_holdout=allow,
                results_dir=tmp_path,
            )
    blind_dir = rme.build_blind_pack("a3", results_dir=tmp_path)
    sheet = blind_dir / "a3_scoring_sheet.csv"
    rows = list(csv.DictReader(sheet.open("r", encoding="utf-8-sig", newline="")))
    assert {row["case_id"] for row in rows} == {"F2", "H1"}
    for row in rows:
        for crit in scoring.A3_RUBRIC_CRITERIA:
            row[crit] = "3"
        # Dev-Zeilen 5 min, Holdout-Zeilen 7 min — der Split muss das trennen.
        row["review_time_min"] = "7" if row["case_id"] == "H1" else "5"
        row["rework_needed"] = "nein"
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out = rme.ingest_scores("a3", sheet, results_dir=tmp_path)
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Flaches per_candidate bleibt erhalten (Rückwärtskompatibilität) …
    for bucket in payload["per_candidate"].values():
        assert bucket["review_time_min_mean"] == 6.0
    # … der Split trennt Dev und Holdout.
    for bucket in payload["per_candidate_split"]["dev"].values():
        assert bucket["review_time_min_mean"] == 5.0
    for bucket in payload["per_candidate_split"]["holdout"].values():
        assert bucket["review_time_min_mean"] == 7.0

    summary = rme.aggregate(tmp_path)
    for agg in summary["roles"]["a3"].values():
        assert agg["dev"]["human"]["review_time_min_mean"] == 5.0
        assert agg["holdout"]["human"]["review_time_min_mean"] == 7.0
    # Whitelist bleibt: keine Blind-Labels im Summary.
    assert "Model A" not in json.dumps(summary, ensure_ascii=False)


def test_aggregate_a2_counts_hard_dq_fields():
    samples = [{
        "case": "F2",
        "fields": [
            {"field_id": "A", "status": "generated", "gates": [],
             "gates_passed": True, "fatal_candidate": False,
             "hard_dq": ["dq_char_limit"], "usage": {}},
            {"field_id": "B", "status": "generated", "gates": [],
             "gates_passed": True, "fatal_candidate": False,
             "hard_dq": [], "usage": {}},
        ],
    }]
    agg = rme._aggregate_a2(samples, None)
    assert agg["hard_dq_fields"] == 1
    assert agg["hard_dq_by_name"] == {"dq_char_limit": 1}


def test_pilot_dry_run_calibrate_run_blind_and_summary(
    db, live_routing_env, tmp_path
):
    """Pilot (korrigierter Harness): Fake-Dry-Run durch alle Phasen —
    Kalibrierungs-Teilraum + Voll-Lauf idempotent, getrennte Blind-Bögen ohne
    Kandidatennamen, ehrliche Reason-/Filter-Aggregation, Status dry_run."""
    for candidate in rme.PILOT_A2_CANDIDATES:
        rme.run_pilot_a2_mini_smoke(
            candidate_key=candidate, fake=True, results_dir=tmp_path
        )
    ok, problems = rme._pilot_smoke_passed(tmp_path)
    assert ok, problems

    passed, report, written = rme.execute_pilot_calibration(
        lambda: db, fake=True, results_dir=tmp_path,
    )
    # Kalibrierung: A2 2×2 + A3 2×2 (F1, rep1, ohne Cross) = 8 Artefakte.
    assert len(written) == 8
    # Dry-Run: Kriterien verlangen Real-Läufe → nie als bestanden werten.
    assert passed is False
    assert (tmp_path / "calibration_report.json").exists()

    written = rme.execute_pilot_run(
        lambda: db, fake=True, allow_holdout=True, results_dir=tmp_path,
    )
    # Voll-Lauf: A2 24 + A3 24 + Cross 2 = 50, minus 8 Kalibrierung = 42.
    assert len(written) == 42

    totals = rme.pilot_totals(tmp_path)
    assert totals["real_llm_calls"] == 0  # Fake zählt nie gegen das Live-Cap.

    blind_dir = rme.build_pilot_blind_pack(results_dir=tmp_path)
    mapping = json.loads((blind_dir / "mapping.json").read_text(encoding="utf-8"))
    assert sorted(mapping["assignment"].values()) == ["Model A", "Model B"]
    for md in blind_dir.glob("*.md"):
        content = md.read_text(encoding="utf-8")
        for candidate in mapping["assignment"]:
            assert candidate not in content
    a2_rows = list(csv.DictReader(
        (blind_dir / "pilot_a2_scoring_sheet.csv").open(
            "r", encoding="utf-8-sig", newline=""
        )
    ))
    assert len(a2_rows) == 24  # 2 Kandidaten × 3 Fälle × 2 Sections × 2 Reps
    assert {row["unit_kind"] for row in a2_rows} == {"a2"}
    assert {row["rep"] for row in a2_rows} == {"1", "2"}
    assert all(crit in a2_rows[0] for crit in rme.PILOT_A2_RUBRIC)
    a3_rows = list(csv.DictReader(
        (blind_dir / "pilot_a3_scoring_sheet.csv").open(
            "r", encoding="utf-8-sig", newline=""
        )
    ))
    assert {row["unit_kind"] for row in a3_rows} == {
        "a3_fair", "a3_workflow_smoke",
    }
    assert sum(1 for r in a3_rows if r["unit_kind"] == "a3_fair") == 24
    assert sum(1 for r in a3_rows if r["unit_kind"] == "a3_workflow_smoke") == 2
    assert all(crit in a3_rows[0] for crit in rme.PILOT_A3_RUBRIC)

    summary = rme.pilot_summary(tmp_path)
    assert summary["status"].startswith("dry_run")
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Model A" not in dumped
    for agg in summary["a2"].values():
        assert agg["valid_outputs"] == 12 and agg["invalid_outputs"] == 0
        assert agg["reject_reason_counts"] == {}
    for agg in summary["a3_fair"].values():
        assert agg["valid_outputs"] == 12
        assert agg["not_evaluable"] == 0
        # Der Fake meldet jede goldmarkierte Schwäche des jeweiligen Drafts.
        assert set(agg["flaw_detection_rates"].values()) == {"6/6"}
        assert agg["filter_stats_sum"]["rejected"] == 0
    for entry in summary["a3_cross"].values():
        assert entry["status"] == "succeeded"
        assert "nie alleinige" in entry["note"]


def test_pilot_a3_all_findings_filtered_is_not_evaluable(
    db, live_routing_env, tmp_path, monkeypatch
):
    """Owner-Abgrenzung: verwirft der Produktionsfilter ALLE Findings, ist das
    Sample not_evaluable (dq_all_findings_filtered) — nie false_consensus.

    Seit der Caller-Bindung kann ein Finding NICHT mehr an Routing-Metadaten
    scheitern; der Filter greift hier über eine unbekannte Requirement-ID.
    """
    import json as _json

    from app.agents.providers import FakeProvider

    def bad_adapter(field_id, section, flaws):
        findings = [{
            "origin_profile_id": "A3.evidence_consistency",
            "severity": "warning", "status": "open",
            "field_id": field_id,
            "target_section": section,
            "requirement_id": "REQ.GIBT.ES.NICHT",
            "description": "Hinweis auf eine unbekannte Anforderung.",
            "suggested_improvement": "-", "recommended_next_action": "-",
        }]
        return FakeProvider(raw_output=_json.dumps({
            "findings": findings,
            "profile_summaries": [{
                "profile_id": "A3.evidence_consistency", "finding_count": 1,
            }],
            "overall_limitations": [],
        }))

    monkeypatch.setattr(rme, "_fake_a3_fixed_adapter", bad_adapter)
    sample = rme.run_pilot_a3_fixed_sample(
        db, case_id="F1", candidate_key="openai_gpt_56_terra_candidate",
        field_id="VC.BUSINESS_TARGETS_MODEL.EDITOR", rep=1, fake=True,
    )
    assert sample["status"] == "not_evaluable"
    assert sample["reject_reason"] == "all_findings_filtered"
    assert sample["dq"] == "dq_all_findings_filtered"
    assert sample["filter_stats"]["received"] == 1
    assert sample["filter_stats"]["accepted"] == 0
    assert sample["filter_stats"]["rejected_reasons"] == {
        "unknown_requirement": 1,
    }
    assert sample["flaw_detection"] is None  # nie als false_consensus werten
    assert sample["flaws_detected"] is None


def test_pilot_a3_routing_metadata_is_caller_bound(
    db, live_routing_env, tmp_path, monkeypatch
):
    """Owner Block 2/4: der Caller bindet field_id/target_section. Ein Finding
    ohne Routing-ID verschwindet NICHT mehr; der Widerspruch wird gezählt."""
    import json as _json

    from app.agents.providers import FakeProvider

    def no_routing_adapter(field_id, section, flaws):
        return FakeProvider(raw_output=_json.dumps({
            "findings": [{
                "origin_profile_id": "A3.evidence_consistency",
                "severity": "warning", "status": "open",
                "field_id": None,            # Modell liefert keine ID …
                "target_section": "4.9",     # … und einen falschen Marker
                "description": "Marktanteil ist nicht belegt.",
                "suggested_improvement": "Belegen oder offen markieren.",
                "recommended_next_action": "Beleg ergänzen.",
            }],
            "profile_summaries": [{
                "profile_id": "A3.evidence_consistency", "finding_count": 1,
            }],
            "overall_limitations": [],
        }))

    monkeypatch.setattr(rme, "_fake_a3_fixed_adapter", no_routing_adapter)
    sample = rme.run_pilot_a3_fixed_sample(
        db, case_id="F1", candidate_key="openai_gpt_56_terra_candidate",
        field_id="VC.BUSINESS_TARGETS_MODEL.EDITOR", rep=1, fake=True,
    )
    assert sample["status"] == "succeeded"
    assert sample["routing_metadata_source"] == "caller_bound"
    stats = sample["filter_stats"]
    assert stats["received"] == 1 and stats["accepted"] == 1
    assert stats["rejected_reasons"] == {}
    assert stats["model_routing_hint_mismatch"] == 1  # nie still übernommen
    finding = sample["raw"]["findings"][0]
    assert finding["field_id"] == "VC.BUSINESS_TARGETS_MODEL.EDITOR"
    assert finding["target_section"] == "3.1"


def test_pilot_run_refuses_without_passed_smoke(db, live_routing_env, tmp_path):
    with pytest.raises(rme.EvalRefusal, match="Phase-1-Smokes"):
        rme.execute_pilot_run(
            lambda: db, fake=False, allow_holdout=True, results_dir=tmp_path
        )


def test_ingest_rejects_unknown_label(db, live_routing_env, tmp_path):
    rme.execute_run(
        db, role="a3", candidate_key="openai_gpt_56_terra_candidate",
        cases=("F2",), reps=1, fake=True, allow_holdout=False,
        results_dir=tmp_path,
    )
    blind_dir = rme.build_blind_pack("a3", results_dir=tmp_path)
    bogus = tmp_path / "bogus.csv"
    with bogus.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rme._A3_SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({"case_id": "F2", "variant": "baseline",
                         "label": "Model Z", "rep": 1})
    with pytest.raises(rme.EvalRefusal, match="Unbekanntes Blind-Label"):
        rme.ingest_scores("a3", bogus, results_dir=tmp_path)
