"""Pytest fixtures: isolated SQLite DB, seeded workspaces/users, TestClient.

The database URL is set to a temp file *before* importing the app so the app's
engine binds to the test database.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator

import pytest

# Configure environment before importing any app module.
_TMP_DB = os.path.join(tempfile.gettempdir(), "rf_test_app.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
_TMP_STORAGE = os.path.join(tempfile.gettempdir(), "rf_test_sources")
if os.path.isdir(_TMP_STORAGE):
    shutil.rmtree(_TMP_STORAGE, ignore_errors=True)
_TMP_CHECKPOINTS = os.path.join(tempfile.gettempdir(), "rf_test_checkpoints.db")
if os.path.exists(_TMP_CHECKPOINTS):
    os.remove(_TMP_CHECKPOINTS)
_TMP_EXPORTS = os.path.join(tempfile.gettempdir(), "rf_test_exports")
if os.path.isdir(_TMP_EXPORTS):
    shutil.rmtree(_TMP_EXPORTS, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SOURCE_STORAGE_DIR"] = _TMP_STORAGE
os.environ["EXPORT_STORAGE_DIR"] = _TMP_EXPORTS
os.environ["MAX_UPLOAD_BYTES"] = "1048576"
os.environ["CHECKPOINT_DB_PATH"] = _TMP_CHECKPOINTS
# Die Pflicht-Suite ist für die Fake-/CI-Umgebung spezifiziert
# (docs/evaluation/Provider_Mode_Matrix.md). Seit der Live-Aktivierung
# (2026-07-23) kann backend/.env AI_EVAL_MODE=real setzen — Prozess-Env schlägt
# .env, darum hier neutralisieren. Der opt-in Real-Provider-Smoke
# (RUN_REAL_PROVIDER_SMOKE=true) bleibt unberührt und darf real bleiben.
if os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").casefold() != "true":
    os.environ.setdefault("AI_EVAL_MODE", "off")

from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import FundingProfile, User, Workspace  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

ORIGIN = "http://localhost:3000"
DEMO_WS = "ws-demo"
TEST_WS = "ws-test"
ANNA_EMAIL = "anna.keller@example.test"
ANNA_PASSWORD = "lead-secret"
TOBIAS_EMAIL = "tobias.frei@example.test"
TOBIAS_PASSWORD = "member-secret"
OUTSIDER_EMAIL = "outsider@example.test"
OUTSIDER_PASSWORD = "outsider-secret"


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        db.add_all(
            [
                Workspace(id=DEMO_WS, name="Demo Workspace"),
                Workspace(id=TEST_WS, name="Test Workspace"),
                FundingProfile(
                    id="innosuisse_innovation_project_with_implementation_partner",
                    title="Innosuisse Innovation Project",
                ),
            ]
        )
        db.add_all(
            [
                User(
                    id="user-anna", workspace_id=DEMO_WS, name="Anna Keller",
                    email=ANNA_EMAIL, password_hash=hash_password(ANNA_PASSWORD),
                    role="lead_admin", display_label="Anna Keller",
                ),
                User(
                    id="user-tobias", workspace_id=DEMO_WS, name="Tobias Frei",
                    email=TOBIAS_EMAIL, password_hash=hash_password(TOBIAS_PASSWORD),
                    role="member", display_label="Tobias Frei",
                ),
                # Separate test-only workspace + user for isolation tests.
                User(
                    id="user-outsider", workspace_id=TEST_WS, name="Test Outsider",
                    email=OUTSIDER_EMAIL, password_hash=hash_password(OUTSIDER_PASSWORD),
                    role="member", display_label="Test Outsider",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(engine)


# RUN 2A Slice 0 (Test-Hermetik): Die mandatorische Suite darf sich nie auf
# eine lokale ``backend/.env`` verlassen — weder Keys noch Modell-IDs,
# Preistabellen oder Live-/Fake-Flags. Diese Defaults entsprechen exakt den
# Settings-Felddefaults (= CI-Zustand ohne .env). Tests, die abweichende Werte
# brauchen, setzen sie selbst via ``monkeypatch`` (siehe z. B. ``web_enabled``).
HERMETIC_PROVIDER_DEFAULTS: dict[str, object] = {
    "openai_api_key": None,
    "anthropic_api_key": None,
    "firecrawl_api_key": None,
    "firecrawl_privacy_mode": None,
    "agent_fake_provider": False,
    "ai_eval_mode": "off",
    "agent_institutional_route_approved": False,
    "agent_quality_ceiling_enabled": False,
    "agent_model_gpt_56_luna_id": None,
    "agent_model_gpt_56_terra_id": None,
    "agent_model_gpt_56_sol_id": None,
    "agent_model_claude_haiku_45_id": None,
    "agent_model_claude_sonnet_5_id": None,
    "agent_model_claude_fable_5_id": None,
    "agent_model_pricing_chf_per_million": {},
    "web_research_enabled": False,
    "web_research_fake_provider": False,
    "d2_web_research_enabled": False,
    "demo_data_enabled": False,
}


def apply_hermetic_provider_defaults(settings) -> dict[str, object]:
    """Normalisiert das Settings-Singleton auf die hermetischen Defaults und
    gibt die vorherigen Werte (für Restore) zurück."""
    saved = {name: getattr(settings, name) for name in HERMETIC_PROVIDER_DEFAULTS}
    for name, value in HERMETIC_PROVIDER_DEFAULTS.items():
        setattr(settings, name, {} if value == {} else value)
    return saved


@pytest.fixture(autouse=True)
def _no_real_provider_keys() -> Iterator[None]:
    """R5.5b-Guard + RUN-2A-Hermetik: mandatorische Tests erreichen NIE echte
    Provider und sehen NIE lokale ``.env``-Konfiguration.

    Liegen echte Keys in ``backend/.env``, macht ``default_provider_resolver``
    die realen Adapter ``available()`` — Module mit eigenem
    ``_PROVIDER_RESOLVER``-Default (z. B. evidence_mapping im A1-Graph-Node)
    würden dann still echte, bezahlte Calls aus der normalen Suite feuern
    (vor R5.5b unsichtbar, weil reale Antworten schema-invalid blieben).
    Zusätzlich (RUN 2A Slice 0): auch Modell-IDs, Preistabelle und
    Live-/Fake-Flags werden pro Test auf die Felddefaults gesetzt, damit die
    Suite auf jeder Maschine identisch zu CI läuft (Regressionsbeweis:
    ``tests/test_env_hermetic.py``). Tests, die Keys/Flags brauchen, setzen
    Dummies selbst via ``monkeypatch``; die bewusst env-gated Real-Smokes
    (``RUN_REAL_PROVIDER_SMOKE=true``, nie CI) behalten die echte Umgebung.

    Bewusst **ohne** ``monkeypatch``: würde diese autouse-Fixture ``monkeypatch``
    anfordern, würde dessen Fixture vor ``client`` aufgebaut und damit (LIFO)
    erst nach dem ``TestClient``-Shutdown zurückgesetzt. Tests, die per
    ``monkeypatch`` ``socket.socket`` blockieren (test_export_security), ließen
    den TestClient dann bei blockiertem Socket herunterfahren → Deadlock. Das
    manuelle Save/Restore hält die monkeypatch-Teardown-Reihenfolge unverändert.
    """
    if os.environ.get("RUN_REAL_PROVIDER_SMOKE") == "true":
        yield
        return
    settings = get_settings()
    saved = apply_hermetic_provider_defaults(settings)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(settings, name, value)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str) -> str:
    """Log in (cookie stored on the client) and return the CSRF token."""
    res = client.post("/api/v1/session", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["csrf_token"]


def unsafe_headers(csrf: str, origin: str = ORIGIN) -> dict[str, str]:
    return {"X-CSRF-Token": csrf, "Origin": origin}


VALID_CLASSIFICATION = {
    "sensitivity": "public",
    "origin": "synthetic",
    "processing_mode": "cloud_assisted",
    "web_research_mode": "off",
    "nda_applies": False,
}


def project_payload(title: str = "Test Project") -> dict:
    return {
        "title": title,
        "description": "A test innovation project.",
        "funding_instrument_profile_id": (
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        "data_classification": VALID_CLASSIFICATION,
    }


def create_project(client, csrf: str, title: str = "Sources Project") -> str:
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    res = client.post(
        "/api/v1/projects", json=project_payload(title), headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["project_id"]
