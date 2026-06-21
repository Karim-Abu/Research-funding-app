"""Pytest fixtures: isolated SQLite DB, seeded workspaces/users, TestClient.

The database URL is set to a temp file *before* importing the app so the app's
engine binds to the test database.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Configure environment before importing any app module.
_TMP_DB = os.path.join(tempfile.gettempdir(), "rf_test_app.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["COOKIE_SECURE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

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
