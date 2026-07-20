"""RUN 2A Slice 0 — Hermetik-Regressionstests.

Beweist, dass lokale Provider-Konfiguration (``backend/.env``: Keys,
Modell-IDs, Preistabelle, Live-/Fake-Flags) die Default-Annahmen der
mandatorischen Suite nie verändert. Root Cause der Baseline-Fehlschläge vom
2026-07-19: die Live-Slice-``.env`` (Preistabelle, Modell-IDs) leckte in
``test_run_real_all_a2_fields_metered`` (``priced`` statt ``unknown_price``).
"""
from __future__ import annotations

from app.config.settings import get_settings
from tests.conftest import (
    HERMETIC_PROVIDER_DEFAULTS,
    apply_hermetic_provider_defaults,
)


def test_suite_sees_hermetic_provider_defaults():
    """Im Test gelten IMMER die Felddefaults — egal was backend/.env setzt."""
    settings = get_settings()
    for name, expected in HERMETIC_PROVIDER_DEFAULTS.items():
        assert getattr(settings, name) == expected, (
            f"{name} ist nicht hermetisch: lokale Umgebung leckt in die Suite"
        )


def test_leaked_pricing_and_model_ids_are_normalized():
    """Simulierter .env-Leak: Preise/Modell-IDs/Fake-Flag gesetzt → die
    Normalisierung stellt die Default-Testannahmen wieder her."""
    settings = get_settings()
    settings.agent_model_pricing_chf_per_million = {
        "gpt-5.6-terra": {"input_chf_per_million": 2.0, "output_chf_per_million": 12.0}
    }
    settings.agent_model_gpt_56_terra_id = "gpt-5.6-terra"
    settings.agent_model_claude_sonnet_5_id = "claude-sonnet-5"
    settings.agent_fake_provider = True
    settings.web_research_enabled = True

    leaked = apply_hermetic_provider_defaults(settings)

    assert leaked["agent_model_gpt_56_terra_id"] == "gpt-5.6-terra"
    assert settings.agent_model_pricing_chf_per_million == {}
    assert settings.agent_model_gpt_56_terra_id is None
    assert settings.agent_model_claude_sonnet_5_id is None
    assert settings.agent_fake_provider is False
    assert settings.web_research_enabled is False
    # Kein Restore nötig: die autouse-Fixture stellt nach dem Test den
    # ursprünglichen (lokalen) Zustand wieder her.
