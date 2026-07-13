"""R6 — Copy-Readiness: Zustandsmatrix (pure) + End-to-End über die Fields-API.

Präzedenz: blocker → placeholders_open → not_reviewed → draft → copy_ready.
``copy_ready`` bedeutet "bereit zum Kopieren", nie "einreichbereit".

NOTE: Dateiname sortiert bewusst NACH test_demo_seed.py (gleiche Falle wie
test_field_copy_events.py — frühere Projekte brechen den Seed-Isolationstest).
"""
from __future__ import annotations

import pytest

from app.review.copy_readiness import (
    COPY_READINESS_VALUES,
    derive_copy_readiness,
)
from tests.review_helpers import (
    ABSTRACT,
    approve,
    clean_field,
    run_recheck,
    setup_completed_run,
)

CLEAN_TEXT = "Ein vollständig ausgearbeiteter Abstract ohne offene Angaben."


class TestMatrix:
    BASE = dict(
        text_is_empty=False,
        text_has_placeholder=False,
        text_over_limit=False,
        has_blocker_finding=False,
        recheck_required=False,
        approved_current=False,
    )

    # (Overrides, erwartete Stufe) — Präzedenz vollständig abgedeckt.
    MATRIX = [
        ({"text_over_limit": True}, "blocker"),
        ({"text_is_empty": True}, "blocker"),
        ({"has_blocker_finding": True}, "blocker"),
        # Blocker dominiert alles, auch eine (veraltete) Freigabe.
        ({"has_blocker_finding": True, "approved_current": True}, "blocker"),
        ({"text_has_placeholder": True}, "placeholders_open"),
        ({"text_has_placeholder": True, "recheck_required": True}, "placeholders_open"),
        ({"recheck_required": True}, "not_reviewed"),
        # Prüfung nicht aktuell schlägt eine formal noch gültige Freigabe.
        ({"recheck_required": True, "approved_current": True}, "not_reviewed"),
        ({}, "draft"),
        ({"approved_current": True}, "copy_ready"),
    ]

    @pytest.mark.parametrize("overrides,expected", MATRIX)
    def test_matrix(self, overrides, expected) -> None:
        assert derive_copy_readiness(**{**self.BASE, **overrides}) == expected

    def test_all_states_reachable(self) -> None:
        reached = {
            derive_copy_readiness(**{**self.BASE, **overrides})
            for overrides, _ in self.MATRIX
        }
        assert reached == set(COPY_READINESS_VALUES)


def _field(client, run_id, field_id) -> dict:
    res = client.get(f"/api/v1/runs/{run_id}/fields/{field_id}")
    assert res.status_code == 200, res.text
    return res.json()


def test_copy_readiness_lifecycle_over_api(client):
    """Template (Platzhalter) → bereinigt (Prüfung veraltet) → recheck
    (Arbeitskopie) → Feld-Freigabe (bereit zum Kopieren)."""
    csrf, _, run_id = setup_completed_run(client, title="Copy Readiness Flow")

    # Frischer Template-Draft enthält Platzhalter → placeholders_open.
    assert _field(client, run_id, ABSTRACT)["copy_readiness"] == "placeholders_open"

    # Bereinigter Text, aber Prüfung dadurch veraltet → not_reviewed.
    clean_field(client, csrf, run_id, ABSTRACT, CLEAN_TEXT)
    assert _field(client, run_id, ABSTRACT)["copy_readiness"] == "not_reviewed"

    # Erneute Prüfung macht den Stand aktuell, Freigabe fehlt → draft.
    res = run_recheck(client, csrf, run_id)
    assert res.status_code in (200, 202), res.text
    assert _field(client, run_id, ABSTRACT)["copy_readiness"] == "draft"

    # Menschliche Feld-Freigabe → copy_ready.
    res = approve(client, csrf, run_id, scope="field", scope_id=ABSTRACT)
    assert res.status_code == 201, res.text
    assert _field(client, run_id, ABSTRACT)["copy_readiness"] == "copy_ready"

    # listFields liefert dieselbe Ableitung (Paritätscheck Liste vs. Detail).
    listed = {
        f["field_id"]: f["copy_readiness"]
        for f in client.get(f"/api/v1/runs/{run_id}/fields").json()
    }
    assert listed[ABSTRACT] == "copy_ready"
    assert set(listed.values()) <= set(COPY_READINESS_VALUES)
