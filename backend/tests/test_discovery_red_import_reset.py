"""DISCOVERY-RED (Abschnitt-B-Mandat, 2026-07-19): reproduzierbare rote Tests.

Dokumentiert die fehlende Umkehrbarkeit von Import-Entscheidungen (Mandat D1:
«Entscheidung vollständig rückgängig machen»). Der Ist-Zustand ist bewusstes
Design und durch ``tests/test_import_api.py::test_already_decided_cannot_be_redecided``
gepinnt (409 ``import_already_decided``); dieser Gegen-Test bleibt unangetastet.

Nicht löschen, nicht invertieren, nicht durch Aufweichen «fixen». Die Tests sind
``xfail(strict=True)``: sobald Phase 1 die Umkehrbarkeit implementiert, werden
sie XPASS (Gate rot) und müssen bewusst zu normalen Tests promoted werden —
gleichzeitig braucht der gepinnte Gegen-Test eine freigegebene Anpassung.

Die Routenform ``POST /api/v1/imports/{id}/reset`` ist ein VORSCHLAG und braucht
Owner-Freigabe (CLAUDEX §2: keine API-Vertragsänderung ohne Freigabe).
Siehe docs/IMPLEMENTATION_DISCOVERY.md §5 (Fehler #1).
"""
from __future__ import annotations

from tests.review_helpers import mut

def _scope(candidate):
    return {
        "project_id": candidate["project_id"],
        "source_id": candidate["source_id"],
        "expected_revision_id": candidate["current_revision_id"],
    }


def test_discovery_red_decided_candidate_can_restore_pdf_value(client):
    from tests.review_helpers import ABSTRACT, mut
    from tests.test_import_api import _decide, _setup_without_run

    csrf, project_id, by_field = _setup_without_run(client)
    candidate = by_field[ABSTRACT]
    candidate["project_id"] = project_id
    cid = candidate["import_candidate_id"]
    assert _decide(client, csrf, cid, decision="ignored").status_code == 200

    current = client.get(f"/api/v1/projects/{project_id}/imports").json()
    candidate = next(item for item in current if item["import_candidate_id"] == cid)
    candidate["project_id"] = project_id
    res = client.post(
        f"/api/v1/imports/{cid}/reset",
        json=_scope(candidate),
        headers=mut(csrf),
    )
    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "accepted"
    assert res.json()["acceptance_state"] == "accepted_original"


def test_discovery_red_redecide_after_decision_is_possible(client):
    from tests.review_helpers import ABSTRACT
    from tests.test_import_api import _decide, _setup_without_run

    csrf, project_id, by_field = _setup_without_run(client)
    candidate = by_field[ABSTRACT]
    cid = candidate["import_candidate_id"]
    decided = _decide(client, csrf, cid, decision="ignored")
    assert decided.status_code == 200

    res = client.patch(
        f"/api/v1/imports/{cid}/decision",
        json={
            "decision": "saved_as_source",
            "project_id": project_id,
            "source_id": candidate["source_id"],
            "expected_revision_id": decided.json()["current_revision_id"],
        },
        headers=mut(csrf),
    )
    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "saved_as_source"
