"""DISCOVERY-RED (Abschnitt-B-Mandat, 2026-07-19): reproduzierbare rote Tests.

Dokumentiert die fehlende Ableitung der Projektdauer aus Start-/Enddatum
(Mandat D2: ``project_duration_months`` ist DERIVED_VALUE bei validen Daten;
01.03.2027–31.08.2028 ⇒ 18 abgedeckte Kalendermonate; Abweichung zum manuellen
Wert ⇒ Konflikt anzeigen, nicht still akzeptieren).

Ist-Zustand: ``duration_months`` ist ein unabhängiger manueller Integer
(``app/contracts/project.py::ProjectPatch``, ``repositories/projects.py``);
``start_date``/``end_date`` sind reine Passthrough-Felder ohne Kalenderlogik.

Nicht löschen, nicht invertieren, nicht durch Aufweichen «fixen».
``xfail(strict=True)``: ein Fix macht die Tests XPASS (Gate rot) und erzwingt
die bewusste Promotion. Das Feld ``duration_conflict`` ist ein VORSCHLAG und
braucht Owner-Freigabe. Siehe docs/IMPLEMENTATION_DISCOVERY.md §5 (Fehler #2).
"""
from __future__ import annotations

import pytest

XFAIL_REASON_DERIVE = (
    "DISCOVERY-RED #2a: Keine Kalendermonats-Ableitung — duration_months bleibt "
    "None trotz valider Start-/Enddaten (Mandat D2: 01.03.2027–31.08.2028 = 18)."
)
XFAIL_REASON_CONFLICT = (
    "DISCOVERY-RED #2b: Abweichung zwischen Datumsspanne (18 Monate) und "
    "manueller Dauer (12) wird heute still akzeptiert — Mandat D2 fordert einen "
    "sichtbaren Konflikt statt Überschreiben/Schweigen."
)


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON_DERIVE)
def test_discovery_red_duration_months_derived_from_dates(client):
    from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project, login, unsafe_headers

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, "Discovery Dauer-Ableitung")

    res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"start_date": "2027-03-01", "end_date": "2028-08-31"},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text

    fetched = client.get(f"/api/v1/projects/{project_id}").json()
    # Mandats-Kalendermonatslogik: März 2027 … August 2028 = 18 Kalendermonate.
    assert fetched["duration_months"] == 18


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON_CONFLICT)
def test_discovery_red_duration_divergence_yields_conflict(client):
    from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project, login, unsafe_headers

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, "Discovery Dauer-Konflikt")

    res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "start_date": "2027-03-01",
            "end_date": "2028-08-31",
            "duration_months": 12,
        },
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text

    fetched = client.get(f"/api/v1/projects/{project_id}").json()
    # Vorgeschlagener Vertrag (genehmigungspflichtig): entweder ein explizites
    # Konfliktsignal ODER die abgeleitete Dauer gewinnt sichtbar — nie stille
    # Übernahme des abweichenden manuellen Werts.
    has_conflict_signal = bool(
        res.json().get("duration_conflict") or fetched.get("duration_conflict")
    )
    assert has_conflict_signal or fetched["duration_months"] == 18
