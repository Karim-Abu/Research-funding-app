from __future__ import annotations

from app.evaluation.harness import run_r0_harness_smoke


def test_r0_evaluation_harness_smoke_runs_without_external_provider():
    result = run_r0_harness_smoke()

    assert result["ok"] is True
    assert result["provider_mode"] == "fake/local"
    assert result["external_provider_calls"] == 0
    assert "metrics" in result
