"""RUN 4B — additive Versionsliste je Portalfeld (read-only, keine Migration).

Deckt ab: Reihenfolge neueste-zuerst + is_current, keine Volltexte im
Listen-JSON, Workspace-/Feld-Scoping und die client-orchestrierte
Restore-Semantik über den bestehenden updateField-PATCH (neue user-Version;
Altzeilen unverändert; No-op bei identischem Text).
"""
from __future__ import annotations

import uuid

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)

SOURCE_TEXT = (
    "Industrie AG ist als Umsetzungspartner in der Schweiz wertschöpfend tätig. "
    "ETH ist als beitragsberechtigter Schweizer Forschungspartner eingebunden."
)
ABSTRACT = "INTRO.APP.ABSTRACT"


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _setup_run(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    source = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Quelle",
            "text": SOURCE_TEXT,
            "data_classification": VALID_CLASSIFICATION,
        },
        headers=_mut(csrf),
    ).json()
    selected = client.put(
        f"/api/v1/projects/{project_id}/primary-application",
        json={
            "source_id": source["source_id"],
            "expected_primary_source_id": None,
        },
        headers=_mut(csrf),
    )
    assert selected.status_code == 200, selected.text
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "deterministic_only",
                "max_cost_chf": 0,
                "max_llm_calls": 0,
                "max_web_calls": 0,
            }
        },
        headers=_mut(csrf),
    ).json()
    assert client.get(f"/api/v1/runs/{run['resource_id']}").json()["status"] == "completed"
    return csrf, project_id, run["resource_id"]


def _edit(client, csrf, run_id, text):
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    base = draft["current_version"]["draft_version_id"]
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}",
        json={"base_version_id": base, "text": text},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_version_list_newest_first_with_metadata_only(client):
    csrf, _pid, run_id = _setup_run(client)
    _edit(client, csrf, run_id, "Kurzfassung über die Förderfähigkeit.")

    res = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/versions")
    assert res.status_code == 200, res.text
    versions = res.json()["versions"]
    assert len(versions) == 2
    # Neueste zuerst; genau der Kopf ist aktuell.
    assert [v["is_current"] for v in versions] == [True, False]
    assert versions[0]["created_by"] == "user"
    assert versions[1]["created_by"] == "template"
    assert versions[1]["generation_kind"] == "rule_template"
    # Payload-Ehrlichkeit: Metadaten-Liste ohne Volltexte.
    for version in versions:
        assert "text" not in version
        assert version["character_count"] >= 0
        assert version["created_at"]


def test_version_list_scoping(client):
    _csrf, _pid, run_id = _setup_run(client)
    # Nicht unterstütztes Feld → 404 (gleiches Scoping wie getField).
    assert (
        client.get(
            f"/api/v1/runs/{run_id}/fields/PS.WORK_PACKAGE.DESCRIPTION/versions"
        ).status_code
        == 404
    )
    # Fremder Workspace → 404 (Run nicht sichtbar).
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert (
        client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/versions").status_code
        == 404
    )


def test_restore_via_existing_patch_creates_user_version_and_keeps_history(client):
    csrf, _pid, run_id = _setup_run(client)
    original = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    original_version = original["current_version"]
    _edit(client, csrf, run_id, "Neuer Zwischenstand des Abstracts.")

    # Restore = Einzelversion lesen (bestehender GET) + regulärer PATCH.
    old = client.get(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/versions/"
        f"{original_version['draft_version_id']}"
    )
    assert old.status_code == 200, old.text
    restored = _edit(client, csrf, run_id, old.json()["text"])
    assert restored["current_version"]["created_by"] == "user"
    assert restored["current_version"]["text"] == original_version["text"]

    versions = client.get(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/versions"
    ).json()["versions"]
    # Drei Versionen: Restore ist eine NEUE Version, Altzeilen bleiben erhalten.
    assert len(versions) == 3
    assert versions[0]["is_current"] is True
    assert original_version["draft_version_id"] in [
        v["draft_version_id"] for v in versions
    ]

    # No-op: identischer Text erzeugt keine redundante vierte Version.
    _edit(client, csrf, run_id, original_version["text"])
    versions_after = client.get(
        f"/api/v1/runs/{run_id}/fields/{ABSTRACT}/versions"
    ).json()["versions"]
    assert len(versions_after) == 3
