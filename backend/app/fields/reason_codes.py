"""R4.2 — maschinenlesbare KI-Verfügbarkeits-Reason-Codes.

Mappt die internen Block-Reasons (``field_drafting.availability`` /
``data_policy.evaluate`` / Executor-Skips) auf den freigegebenen Katalog
(docs/repair/message-catalog.md §R4.2, Owner-Microcopy). Der API-``code`` bleibt
``ai_unavailable``; ``reason_code`` + ``reason_text_de`` kommen zusätzlich mit.

Fail-closed: ein unbekannter interner Reason wird als ``provider_unavailable``
gemeldet (kein freigegebener Provider-Pfad) — nie wieder ein generischer Satz
ohne Code.
"""
from __future__ import annotations

# Owner-approved Microcopy (Prompt-Pack R4.2, wörtlich).
REASON_TEXTS_DE: dict[str, str] = {
    "nda_locked": "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
    "mode_deterministic_only":
        "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.",
    "provider_unavailable": (
        "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider "
        "konfiguriert. Die App führt nur regelbasierte Prüfungen aus."
    ),
    "live_fake_conflict": (
        "Live-KI ist wegen einer widersprüchlichen Konfiguration nicht verfügbar. "
        "Setzen Sie AGENT_FAKE_PROVIDER=false und führen Sie den Preflight erneut aus."
    ),
    "live_eval_mode_disabled": (
        "Live-KI ist deaktiviert. Setzen Sie AI_EVAL_MODE=real und führen Sie "
        "den synthetischen Preflight erneut aus."
    ),
    "live_provider_key_missing": (
        "Live-KI ist nicht verfügbar. Hinterlegen Sie den API-Schlüssel der "
        "konfigurierten Route und führen Sie den Preflight erneut aus."
    ),
    "live_model_id_missing": (
        "Live-KI ist nicht verfügbar. Hinterlegen Sie die konkrete "
        "AGENT_MODEL_*_ID der Route und führen Sie den Preflight erneut aus."
    ),
    "live_price_metadata_missing": (
        "Live-KI ist nicht verfügbar. Ergänzen Sie geprüfte Preis-Metadaten "
        "für die konkrete Modell-ID."
    ),
    "live_preflight_required": (
        "Live-KI ist noch nicht freigegeben. Starten Sie im Live-Systemstatus "
        "den synthetischen Preflight."
    ),
    "live_preflight_expired": (
        "Der Live-Preflight ist abgelaufen. Führen Sie ihn im Live-Systemstatus "
        "erneut aus."
    ),
    "live_preflight_failed": (
        "Der Live-Preflight ist fehlgeschlagen. Prüfen Sie den konkreten "
        "Routenfehler im Live-Systemstatus und wiederholen Sie den Test."
    ),
    "live_preflight_stale_model": (
        "Die konfigurierte Modell-ID wurde seit dem Preflight geändert. "
        "Führen Sie den synthetischen Preflight erneut aus."
    ),
    "live_actual_model_missing": (
        "Der Provider hat im Preflight keine tatsächliche Modell-ID bestätigt. "
        "Prüfen Sie die Route im Live-Systemstatus."
    ),
    "run_mode_mismatch": "Der aktuelle Analysemodus passt nicht zum Feldvorschlag.",
    "missing_sources": "Für einen belastbaren Vorschlag fehlen passende Quellen.",
    "field_not_supported": "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar.",
}

_FALLBACK_CODE = "provider_unavailable"

# Interner Reason → Katalog-Code. Die internen Bezeichner bleiben unverändert
# (Audit-Details nutzen sie weiter); hier wird nur die Nutzersicht abgeleitet.
_INTERNAL_TO_CODE: dict[str, str] = {
    # availability() pre-check --------------------------------------------
    "field_not_supported": "field_not_supported",
    "processing_mode_deterministic_only": "mode_deterministic_only",
    "processing_mode_local_only": "mode_deterministic_only",
    "provider_unavailable": "provider_unavailable",
    "local_ai_provider_unavailable": "provider_unavailable",
    "live_fake_conflict": "live_fake_conflict",
    "live_eval_mode_disabled": "live_eval_mode_disabled",
    "live_provider_key_missing": "live_provider_key_missing",
    "live_model_id_missing": "live_model_id_missing",
    "live_price_metadata_missing": "live_price_metadata_missing",
    "live_preflight_required": "live_preflight_required",
    "live_preflight_expired": "live_preflight_expired",
    "live_preflight_failed": "live_preflight_failed",
    "live_preflight_stale_model": "live_preflight_stale_model",
    "live_actual_model_missing": "live_actual_model_missing",
    "real_eval_confirmation_required": "run_mode_mismatch",
    # data_policy.evaluate -------------------------------------------------
    "nda_applies": "nda_locked",
    "processing_mode_not_cloud_assisted": "run_mode_mismatch",
    "processing_mode_not_in_profile": "run_mode_mismatch",
    # Kein freigegebener Provider-Pfad für diese Datenklasse (Beta-Policy /
    # ProviderPolicy R4.3): aus Nutzersicht fehlt ein freigegebener Provider.
    "sensitivity_confidential_blocked": "provider_unavailable",
    "internal_requires_institutional_approval_and_confirmation": "provider_unavailable",
    "sensitivity_not_allowed": "provider_unavailable",
    "default_deny": "provider_unavailable",
    # Executor-Skips (run_a2_field_drafting) -------------------------------
    "mode_deterministic_only": "mode_deterministic_only",
    "mode_local_only": "mode_deterministic_only",
    # R4.3 — lokaler KI-Pfad: ohne Opt-in bleibt der Lauf regelbasiert; der
    # Ausweg ist derselbe (Verarbeitungsmodus ändern = Opt-in beim Start).
    "internal_local_requires_confirmation": "mode_deterministic_only",
    "confidential_local_requires_confirmation": "mode_deterministic_only",
    "provider_blocked_for_data_class": "provider_unavailable",
    "provider_unknown_adapter": "provider_unavailable",
    # Reserviert: aktuell blockiert kein Ist-Pfad wegen fehlender Quellen;
    # der Code ist Teil des freigegebenen Katalogs (Emission folgt mit R5).
    "missing_sources": "missing_sources",
}


def maybe_reason(internal_reason: str) -> tuple[str, str] | None:
    """(reason_code, reason_text_de) wenn der interne Reason ein
    Verfügbarkeits-Blockgrund ist, sonst None (z. B. Generierungsfehler)."""
    code = _INTERNAL_TO_CODE.get(internal_reason)
    if code is None:
        return None
    return code, REASON_TEXTS_DE[code]


def to_reason(internal_reason: str) -> tuple[str, str]:
    """Wie ``maybe_reason``, aber fail-closed: unbekannte Reasons melden
    ``provider_unavailable`` statt eines codelosen Generiktexts."""
    return maybe_reason(internal_reason) or (
        _FALLBACK_CODE,
        REASON_TEXTS_DE[_FALLBACK_CODE],
    )
