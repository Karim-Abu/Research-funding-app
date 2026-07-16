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
