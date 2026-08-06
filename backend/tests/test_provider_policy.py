"""R4.3 — ProviderPolicy: Matrix provider × data_class (× origin/eval) + lokaler
Opt-in-Pfad in der Data Policy. Keys dürfen NIE eine blockierte Klasse öffnen."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import data_policy
from app.config.provider_policy import (
    BLOCKED_REASON,
    ProviderKind,
    decide,
    decide_for_adapter,
    kind_of_adapter,
)
from app.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cls(sensitivity="public", origin="synthetic", nda=False):
    return {
        "sensitivity": sensitivity, "origin": origin,
        "processing_mode": "cloud_assisted", "web_research_mode": "off",
        "nda_applies": nda,
    }


D0 = _cls("public", "synthetic")
D1_REAL = _cls("internal", "real_project")
D2_REAL = _cls("confidential", "real_project")
D2_SYNTH = _cls("confidential", "synthetic")
D2_ANON = _cls("confidential", "anonymized")
D3 = _cls("public", "synthetic", nda=True)
UNKNOWN = {"sensitivity": "top-secret"}

# Settings MIT gesetzten Keys — die Matrix darf sich davon nie beeinflussen lassen.
KEYED = Settings(anthropic_api_key="sk-test-not-real",
                 openai_api_key="sk-test-not-real", ai_eval_mode="off")
EVAL = Settings(anthropic_api_key="sk-test-not-real",
                openai_api_key="sk-test-not-real", ai_eval_mode="real")


# --- Matrix provider × data_class -------------------------------------------

@pytest.mark.parametrize("kind,classification,allowed", [
    # fake/local: D0–D2 erlaubt; D3/UNKNOWN blockiert (GO-Auflage 2).
    (ProviderKind.FAKE_LOCAL, D0, True),
    (ProviderKind.FAKE_LOCAL, D1_REAL, True),
    (ProviderKind.FAKE_LOCAL, D2_REAL, True),
    (ProviderKind.FAKE_LOCAL, D3, False),
    (ProviderKind.FAKE_LOCAL, UNKNOWN, False),
    # direct OpenAI/Anthropic: nur D0; echte D1/D2 blockiert TROTZ Keys.
    (ProviderKind.DIRECT_OPENAI, D0, True),
    (ProviderKind.DIRECT_ANTHROPIC, D0, True),
    (ProviderKind.DIRECT_OPENAI, D1_REAL, False),
    (ProviderKind.DIRECT_ANTHROPIC, D1_REAL, False),
    (ProviderKind.DIRECT_OPENAI, D2_REAL, False),
    (ProviderKind.DIRECT_ANTHROPIC, D2_REAL, False),
    (ProviderKind.DIRECT_OPENAI, D3, False),
    (ProviderKind.DIRECT_ANTHROPIC, UNKNOWN, False),
    # azure: Zielpfad, nicht aktiv — überall blockiert.
    (ProviderKind.AZURE, D0, False),
    (ProviderKind.AZURE, D1_REAL, False),
    (ProviderKind.AZURE, D2_REAL, False),
    (ProviderKind.AZURE, D3, False),
])
def test_matrix(kind, classification, allowed):
    decision = decide(kind, classification, KEYED)
    assert decision.allowed is allowed
    if not allowed:
        assert decision.reason == BLOCKED_REASON
        assert decision.required_basis  # jede Sperre nennt ihre Basis


def test_direct_d2_blocked_even_with_keys():
    """Kernanforderung R4.3: direct + D2 + API-Key gesetzt ⇒ blockiert."""
    for kind in (ProviderKind.DIRECT_OPENAI, ProviderKind.DIRECT_ANTHROPIC):
        assert decide(kind, D2_REAL, KEYED).allowed is False
        assert decide(kind, D1_REAL, KEYED).allowed is False


def test_eval_mode_gates_synthetic_evaluation_only():
    """§3.1: F1 synthetic (D2 + synthetic/anonymized) nur mit AI_EVAL_MODE=real."""
    for classification in (D2_SYNTH, D2_ANON):
        assert decide(ProviderKind.DIRECT_OPENAI, classification, KEYED).allowed is False
        assert decide(ProviderKind.DIRECT_OPENAI, classification, EVAL).allowed is True
    # Echte D2-Daten bleiben auch im Eval-Modus blockiert.
    assert decide(ProviderKind.DIRECT_OPENAI, D2_REAL, EVAL).allowed is False
    # D3/Unknown bleiben in jedem Modus blockiert.
    assert decide(ProviderKind.DIRECT_OPENAI, D3, EVAL).allowed is False
    assert decide(ProviderKind.FAKE_LOCAL, UNKNOWN, EVAL).allowed is False


def test_unknown_adapter_fails_closed():
    assert kind_of_adapter(SimpleNamespace(name="mystery")) is None
    assert kind_of_adapter(object()) is None
    decision = decide_for_adapter(object(), D0, KEYED)
    assert decision.allowed is False
    assert decision.reason == "provider_unknown_adapter"


def test_adapter_name_mapping():
    assert kind_of_adapter(SimpleNamespace(name="fake")) == ProviderKind.FAKE_LOCAL
    assert kind_of_adapter(SimpleNamespace(name="openai_direct")) == ProviderKind.DIRECT_OPENAI
    assert kind_of_adapter(SimpleNamespace(name="anthropic_direct")) == ProviderKind.DIRECT_ANTHROPIC


# --- data_policy: lokaler Opt-in-Pfad (Owner-Entscheid 2026-07-08) -----------

_PROFILE = SimpleNamespace()  # der lokale Zweig konsultiert das Profil nicht


def _local(classification, *, confirmed):
    return data_policy.evaluate(
        profile=_PROFILE, classification=classification,
        processing_mode="local_only", settings=KEYED,
        run_confirmation=confirmed, local_provider=True,
    )


def test_local_path_requires_confirmation_for_d1_d2():
    for classification in (D1_REAL, D2_REAL):
        allowed = _local(classification, confirmed=True)
        assert allowed.outcome == "allowed_with_confirmation"
        blocked = _local(classification, confirmed=False)
        assert blocked.blocked
        assert blocked.reason.endswith("_local_requires_confirmation")


def test_local_path_blocks_d3_and_unknown_even_confirmed():
    assert _local(D3, confirmed=True).blocked
    assert _local(D3, confirmed=True).reason == "nda_applies"
    assert _local(UNKNOWN, confirmed=True).blocked


def test_local_path_without_local_provider_stays_blocked():
    # Externe Adapter dürfen local_only nie bedienen (bestehende Semantik).
    decision = data_policy.evaluate(
        profile=_PROFILE, classification=D2_REAL, processing_mode="local_only",
        settings=KEYED, run_confirmation=True, local_provider=False,
    )
    assert decision.blocked
    assert decision.reason == "processing_mode_local_only"


# --- Kein NEXT_PUBLIC-Provider-Secret ----------------------------------------

def test_no_next_public_provider_secret():
    """R4.3: Provider-Keys dürfen nie als NEXT_PUBLIC_* (Browser-exponiert)
    auftauchen — weder in .env-Vorlagen noch im Frontend-Code."""
    pattern = re.compile(r"NEXT_PUBLIC_\w*(KEY|SECRET|TOKEN|PROVIDER|ANTHROPIC|OPENAI)",
                         re.IGNORECASE)
    offenders: list[str] = []
    candidates = [
        REPO_ROOT / ".env.example",
        REPO_ROOT / "backend" / ".env.example",
        REPO_ROOT / "backend" / ".env.demo.example",
    ]
    for scan_dir in (REPO_ROOT / "lib", REPO_ROOT / "app", REPO_ROOT / "components"):
        if scan_dir.exists():
            candidates.extend(scan_dir.rglob("*.ts"))
            candidates.extend(scan_dir.rglob("*.tsx"))
    for path in candidates:
        if path.exists() and pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
