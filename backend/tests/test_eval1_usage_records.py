"""EVAL.1 — UsageRecord-Kostensemantik an den Schreibstellen.

Fake-Provider only, keine Netzwerk-Calls. Deckt: genau ein Record pro
erfolgreichem Gateway-Call, cost_status/price_version-Logik, Seed-Row.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import cost_guard
from app.agents.gateway import ModelResponse, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.db.models import AgentInvocation, UsageRecord
from app.db.session import SessionLocal
from tests.agent_helpers import base_request, fake_resolver, make_run


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_fake_gateway_call_writes_exactly_one_record_with_status(db):
    run_id = make_run(db)
    fake = FakeProvider(usage=ProviderUsage(input_tokens=11, output_tokens=22))
    resp = invoke(db, base_request(run_id=run_id), provider_resolver=fake_resolver(fake))
    assert isinstance(resp, ModelResponse)

    records = db.scalars(
        select(UsageRecord).where(UsageRecord.run_id == run_id)
    ).all()
    assert len(records) == 1, "genau ein UsageRecord pro erfolgreichem Fake-Call"
    rec = records[0]
    assert rec.input_tokens == 11 and rec.output_tokens == 22
    # Route sagt anthropic_direct (Contract), bedient hat der Fake-Adapter:
    # kein externer Call ⇒ not_applicable, price_version bleibt None.
    assert rec.provider == "anthropic_direct"
    assert rec.cost_status == "not_applicable"
    assert rec.price_version is None
    assert rec.cost_chf == 0.0

    inv = db.get(AgentInvocation, resp.invocation_id)
    assert inv.usage_record_id == rec.usage_record_id


def test_real_provider_without_price_is_unknown_price(db):
    # Direkter record_usage-Aufruf ohne adapter_name (z. B. künftiger echter
    # Call): kein Tabelleneintrag ⇒ unknown_price, cost_chf bleibt 0.0 und
    # darf nie als "0 CHF" gelesen werden.
    run_id = make_run(db)
    rec = cost_guard.record_usage(
        db, run_id=run_id, workspace_id="ws-demo",
        # Id bewusst ausserhalb des USD-Katalogs (siehe test_eval1_pricing).
        provider="anthropic_direct", model_id="model-without-catalogue-entry",
        usage=ProviderUsage(input_tokens=100, output_tokens=50),
    )
    assert rec.cost_status == "unknown_price"
    assert rec.price_version is None
    assert rec.cost_chf == 0.0


def test_run_seed_usage_record_is_not_applicable(client):
    # Der Run-Erstellungs-Seed-Row (runs/service.py) repräsentiert keinen
    # externen Call und muss explizit not_applicable sein.
    import uuid

    from tests.conftest import (
        ANNA_EMAIL,
        ANNA_PASSWORD,
        VALID_CLASSIFICATION,
        create_project,
        login,
        unsafe_headers,
    )

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = create_project(client, csrf, title="EVAL1 Seed Row Projekt")
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    src = client.post(
        f"/api/v1/projects/{pid}/sources/text",
        json={
            "name": "Src",
            "text": "Run source content.",
            "data_classification": VALID_CLASSIFICATION,
        },
        headers=headers,
    )
    assert src.status_code == 201, src.text
    headers["Idempotency-Key"] = uuid.uuid4().hex
    run = client.post(
        f"/api/v1/projects/{pid}/runs",
        json={
            "settings": {
                "processing_mode": "deterministic_only",
                "max_cost_chf": 0,
                "max_llm_calls": 0,
                "max_web_calls": 0,
            }
        },
        headers=headers,
    )
    assert run.status_code == 202, run.text
    run_id = run.json()["resource_id"]

    with SessionLocal() as db:
        seed = db.scalars(
            select(UsageRecord).where(UsageRecord.run_id == run_id)
        ).all()
        assert len(seed) >= 1
        assert all(r.cost_status == "not_applicable" for r in seed)
        assert all(r.price_version is None for r in seed)
        assert all(r.input_tokens == 0 and r.output_tokens == 0 for r in seed)
