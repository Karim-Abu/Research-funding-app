"""Partner CRUD: auth/CSRF, idempotency, workspace isolation, scoping."""
from __future__ import annotations

import uuid

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    ORIGIN,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    create_project,
    login,
    unsafe_headers,
)


def _mut(csrf, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


def _partner_body(name="ETH Zürich", partner_type="research_partner", **kw):
    return {"name": name, "partner_type": partner_type, **kw}


def _create_partner(client, project_id, csrf, body=None, key=None):
    return client.post(
        f"/api/v1/projects/{project_id}/partners",
        json=body or _partner_body(), headers=_mut(csrf, key),
    )


def test_create_list_update_delete_partner(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)

    res = _create_partner(
        client, project_id, csrf,
        _partner_body(country="CH", research_partner_eligibility_status="eligible"),
    )
    assert res.status_code == 201, res.text
    partner = res.json()
    assert partner["partner_id"] and partner["project_id"] == project_id
    assert partner["research_partner_eligibility_status"] == "eligible"

    listed = client.get(f"/api/v1/projects/{project_id}/partners")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    upd = client.patch(
        f"/api/v1/partners/{partner['partner_id']}",
        json=_partner_body(name="EPFL", partner_type="research_partner", country="CH"),
        headers=unsafe_headers(csrf),
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["name"] == "EPFL"

    deleted = client.delete(
        f"/api/v1/partners/{partner['partner_id']}", headers=unsafe_headers(csrf)
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}/partners").json() == []


def test_partner_form_fields_roundtrip(client):
    """Slice 1: project_role + independence statuses persist through the API.
    Ein explizites «needs_input» braucht seit der Konsistenzregel einen
    Kommentar; Kompetenz (contribution) und Kommentar runden mit."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    res = _create_partner(
        client, project_id, csrf,
        _partner_body(
            name="Industrie AG",
            partner_type="implementation_partner",
            project_role="Entwicklung des Prototyps",
            contribution="Langjährige Erfahrung mit Prototypenbau.",
            personnel_independence_status="confirmed",
            financial_independence_status="needs_input",
            review_comment="Beteiligungsverhältnisse werden noch geklärt.",
        ),
    )
    assert res.status_code == 201, res.text
    partner = res.json()
    assert partner["project_role"] == "Entwicklung des Prototyps"
    assert partner["contribution"] == "Langjährige Erfahrung mit Prototypenbau."
    assert partner["personnel_independence_status"] == "confirmed"
    assert partner["financial_independence_status"] == "needs_input"
    assert partner["review_comment"] == (
        "Beteiligungsverhältnisse werden noch geklärt."
    )

    listed = client.get(f"/api/v1/projects/{project_id}/partners").json()
    assert listed[0]["project_role"] == "Entwicklung des Prototyps"
    assert listed[0]["personnel_independence_status"] == "confirmed"
    assert listed[0]["financial_independence_status"] == "needs_input"
    assert listed[0]["review_comment"]


def test_unclear_status_requires_comment(client):
    """Konsistenzregel: explizit unklar/nicht bestätigt ohne Kommentar → 422;
    None (nicht erfasst) bleibt gültig — kein erfundenes Urteil."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)

    triggering = [
        {"personnel_independence_status": "needs_input"},
        {"financial_independence_status": "exception"},
        {"research_partner_eligibility_status": "needs_verification"},
        {"research_partner_eligibility_status": "not_eligible"},
        {"partner_type": "implementation_partner", "swiss_value_creation": False},
    ]
    for fields in triggering:
        res = _create_partner(client, project_id, csrf, _partner_body(**fields))
        assert res.status_code == 422, (fields, res.text)
        assert res.json()["code"] == "partner_comment_required"
        # Mit Kommentar ist derselbe Datensatz gültig.
        ok = _create_partner(
            client, project_id, csrf,
            _partner_body(
                name=f"Partner {list(fields)[0]}",
                review_comment="Kurze Begründung für die Einstufung.",
                **fields,
            ),
        )
        assert ok.status_code == 201, (fields, ok.text)

    # Whitespace zählt nicht als Begründung.
    res = _create_partner(
        client, project_id, csrf,
        _partner_body(
            personnel_independence_status="needs_input", review_comment="   "
        ),
    )
    assert res.status_code == 422

    # Regression (Owner-Entscheid): name-only bleibt via API gültig.
    assert _create_partner(client, project_id, csrf).status_code == 201


def test_update_enforces_comment_consistency(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    partner_id = _create_partner(client, project_id, csrf).json()["partner_id"]

    res = client.patch(
        f"/api/v1/partners/{partner_id}",
        json=_partner_body(financial_independence_status="needs_input"),
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 422
    assert res.json()["code"] == "partner_comment_required"

    ok = client.patch(
        f"/api/v1/partners/{partner_id}",
        json=_partner_body(
            financial_independence_status="needs_input",
            review_comment="Klärung der Finanzierung läuft.",
        ),
        headers=unsafe_headers(csrf),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["review_comment"] == "Klärung der Finanzierung läuft."


def test_create_partner_requires_session(client):
    # No login → 401.
    res = client.post(
        "/api/v1/projects/p/partners", json=_partner_body(),
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert res.status_code == 401


def test_create_partner_requires_csrf(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    # Missing CSRF/Origin headers → 403.
    res = client.post(
        f"/api/v1/projects/{project_id}/partners", json=_partner_body(),
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert res.status_code == 403


def test_create_partner_rejects_invalid_enum(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    res = _create_partner(
        client, project_id, csrf, _partner_body(partner_type="vendor")
    )
    assert res.status_code == 422


def test_create_partner_idempotent_replay(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    key = uuid.uuid4().hex
    first = _create_partner(client, project_id, csrf, key=key)
    second = _create_partner(client, project_id, csrf, key=key)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["partner_id"] == second.json()["partner_id"]
    assert len(client.get(f"/api/v1/projects/{project_id}/partners").json()) == 1


def test_partner_workspace_isolation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    partner_id = _create_partner(client, project_id, csrf).json()["partner_id"]

    other = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    # Foreign project → 404 on list; foreign partner → 404 on update/delete.
    assert client.get(f"/api/v1/projects/{project_id}/partners").status_code == 404
    assert client.patch(
        f"/api/v1/partners/{partner_id}", json=_partner_body(),
        headers=unsafe_headers(other),
    ).status_code == 404
    assert client.delete(
        f"/api/v1/partners/{partner_id}", headers=unsafe_headers(other)
    ).status_code == 404
