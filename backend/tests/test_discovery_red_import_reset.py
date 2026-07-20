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

import pytest

XFAIL_REASON_RESET = (
    "DISCOVERY-RED #1a: Reset-Endpoint existiert nicht — Import-Entscheidungen "
    "sind heute endgültig (Mandat D1 fordert Zurücksetzen auf pending)."
)
XFAIL_REASON_REDECIDE = (
    "DISCOVERY-RED #1b: Re-Decide nach Entscheid liefert heute 409 "
    "import_already_decided (gepinnt in test_import_api.py); Mandat D1 fordert "
    "eine revidierbare Entscheidung."
)


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON_RESET)
def test_discovery_red_decided_candidate_can_be_reset_to_pending(client):
    from tests.review_helpers import ABSTRACT, mut
    from tests.test_import_api import _decide, _setup_without_run

    csrf, _project_id, by_field = _setup_without_run(client)
    cid = by_field[ABSTRACT]["import_candidate_id"]
    assert _decide(client, csrf, cid, decision="ignored").status_code == 200

    # Vorgeschlagener Vertrag (genehmigungspflichtig): Entscheidung zurücksetzen.
    res = client.post(f"/api/v1/imports/{cid}/reset", headers=mut(csrf))
    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "pending"


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON_REDECIDE)
def test_discovery_red_redecide_after_decision_is_possible(client):
    from tests.review_helpers import ABSTRACT
    from tests.test_import_api import _decide, _setup_without_run

    csrf, _project_id, by_field = _setup_without_run(client)
    cid = by_field[ABSTRACT]["import_candidate_id"]
    assert _decide(client, csrf, cid, decision="ignored").status_code == 200

    res = _decide(client, csrf, cid, decision="saved_as_source")
    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "saved_as_source"
