"""R4.2 — Reason-Code-Matrix: interne Block-Reasons → freigegebener Katalog."""
from __future__ import annotations

import pytest

from app.fields.reason_codes import REASON_TEXTS_DE, maybe_reason, to_reason


@pytest.mark.parametrize(
    ("internal", "expected_code"),
    [
        # availability() pre-check
        ("field_not_supported", "field_not_supported"),
        ("processing_mode_deterministic_only", "mode_deterministic_only"),
        ("processing_mode_local_only", "mode_deterministic_only"),
        ("provider_unavailable", "provider_unavailable"),
        ("live_fake_conflict", "live_fake_conflict"),
        ("live_eval_mode_disabled", "live_eval_mode_disabled"),
        ("live_provider_key_missing", "live_provider_key_missing"),
        ("live_model_id_missing", "live_model_id_missing"),
        ("live_price_metadata_missing", "live_price_metadata_missing"),
        ("live_preflight_required", "live_preflight_required"),
        ("live_preflight_expired", "live_preflight_expired"),
        ("live_preflight_failed", "live_preflight_failed"),
        ("live_preflight_stale_model", "live_preflight_stale_model"),
        ("live_actual_model_missing", "live_actual_model_missing"),
        # data_policy.evaluate
        ("nda_applies", "nda_locked"),
        ("processing_mode_not_cloud_assisted", "run_mode_mismatch"),
        ("processing_mode_not_in_profile", "run_mode_mismatch"),
        ("sensitivity_confidential_blocked", "provider_unavailable"),
        ("internal_requires_institutional_approval_and_confirmation", "provider_unavailable"),
        ("sensitivity_not_allowed", "provider_unavailable"),
        ("default_deny", "provider_unavailable"),
        # Executor-Skips
        ("mode_deterministic_only", "mode_deterministic_only"),
        ("mode_local_only", "mode_deterministic_only"),
        # Katalog-Code, reserviert für R5
        ("missing_sources", "missing_sources"),
    ],
)
def test_reason_matrix(internal: str, expected_code: str):
    code, text = to_reason(internal)
    assert code == expected_code
    assert text == REASON_TEXTS_DE[expected_code]
    assert text  # nie leer


def test_unknown_reason_fails_closed_to_provider_unavailable():
    code, text = to_reason("something_entirely_new")
    assert code == "provider_unavailable"
    assert text == REASON_TEXTS_DE["provider_unavailable"]


def test_generation_failures_carry_no_reason_code():
    # Reine Generierungsfehler sind keine Verfügbarkeits-Blockgründe.
    for internal in ("character_limit_exceeded", "no_candidate_for_field",
                     "internal_error", "input_schema"):
        assert maybe_reason(internal) is None


def test_catalog_texts_are_the_approved_microcopy():
    assert REASON_TEXTS_DE == {
        "nda_locked": "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
        "mode_deterministic_only":
            "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.",
        "provider_unavailable": (
            "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider "
            "konfiguriert. Die App führt nur regelbasierte Prüfungen aus."
        ),
        "live_fake_conflict": (
            "Live-KI ist wegen einer widersprüchlichen Konfiguration nicht verfügbar. "
            "Öffnen Sie den Systemstatus, um die Verbindung zu prüfen."
        ),
        "live_eval_mode_disabled": (
            "Live-KI ist deaktiviert. Öffnen Sie den Systemstatus, um die Verbindung "
            "zu prüfen."
        ),
        "live_provider_key_missing": (
            "Live-KI ist nicht verfügbar. Hinterlegen Sie den API-Schlüssel der "
            "konfigurierten Route und öffnen Sie danach den Systemstatus."
        ),
        "live_model_id_missing": (
            "Live-KI ist nicht verfügbar. Hinterlegen Sie die konkrete "
            "AGENT_MODEL_*_ID der Route und öffnen Sie danach den Systemstatus."
        ),
        "live_price_metadata_missing": (
            "Live-KI ist nicht verfügbar. Ergänzen Sie geprüfte Preis-Metadaten "
            "für die konkrete Modell-ID."
        ),
        "live_preflight_required": (
            "Live-KI ist noch nicht freigegeben. Öffnen Sie den Systemstatus."
        ),
        "live_preflight_expired": (
            "Die letzte Verbindungsprüfung ist abgelaufen. Öffnen Sie den Systemstatus."
        ),
        "live_preflight_failed": (
            "Die Verbindungsprüfung ist fehlgeschlagen. Öffnen Sie den Systemstatus."
        ),
        "live_preflight_stale_model": (
            "Die konfigurierte Modell-ID wurde seit der letzten Verbindungsprüfung "
            "geändert. Öffnen Sie den Systemstatus."
        ),
        "live_actual_model_missing": (
            "Der Provider hat im Preflight keine tatsächliche Modell-ID bestätigt. "
            "Prüfen Sie die Route im Live-Systemstatus."
        ),
        "run_mode_mismatch": "Der aktuelle Analysemodus passt nicht zum Feldvorschlag.",
        "missing_sources": "Für einen belastbaren Vorschlag fehlen passende Quellen.",
        "field_not_supported": "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar.",
    }


def test_legacy_generic_sentence_absent_from_backend_texts():
    legacy = "für diese Datenklasse oder Umgebung nicht verfügbar"
    assert all(legacy not in text.lower() for text in REASON_TEXTS_DE.values())
