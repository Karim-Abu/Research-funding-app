"""Shared setup for Milestone 8 export tests."""
from __future__ import annotations

from tests.review_helpers import (  # noqa: F401 (re-exported)
    approve,
    clean_field,
    get_review,
    mut,
    run_recheck,
    setup_completed_run,
)

# The 8 supported deterministic-draft fields in canonical registry order.
SUPPORTED_FIELDS = [
    "INTRO.APP.NAME",
    "INTRO.APP.NAME_EN",
    "INTRO.APP.ABSTRACT",
    "INTRO.APP.EXECUTIVE_SUMMARY",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR",
    "SOL.INNOVATION_SOLUTION.EDITOR",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
]

CLEAN_TEXT = "Inhalt fachlich ergänzt (üöä)."


def fill_all_fields(client, csrf, run_id) -> None:
    for field_id in SUPPORTED_FIELDS:
        clean_field(client, csrf, run_id, field_id, CLEAN_TEXT)


def setup_approved_run(client):
    """A completed run with all supported fields placeholder-free + a valid
    run-scope ReviewApproval (→ non-draft export)."""
    csrf, _pid, run_id = setup_completed_run(client, with_research_partner=True)
    fill_all_fields(client, csrf, run_id)
    assert run_recheck(client, csrf, run_id).status_code == 202
    res = approve(client, csrf, run_id, scope="run", scope_id=run_id)
    assert res.status_code == 201, res.text
    return csrf, run_id


def create_export(client, csrf, run_id, export_type, *, force_draft=False):
    return client.post(
        f"/api/v1/runs/{run_id}/exports",
        json={"type": export_type, "force_draft": force_draft},
        headers=mut(csrf),
    )


def get_export(client, export_id):
    return client.get(f"/api/v1/exports/{export_id}")


def download(client, export_id):
    return client.get(f"/api/v1/exports/{export_id}/download")


def make_export(client, csrf, run_id, export_type, *, force_draft=False):
    """Create an export and return the available ExportArtifact JSON.

    TestClient runs the background task synchronously, so the export is available
    immediately after createExport returns.
    """
    accepted = create_export(
        client, csrf, run_id, export_type, force_draft=force_draft
    )
    assert accepted.status_code == 202, accepted.text
    export_id = accepted.json()["resource_id"]
    artifact = get_export(client, export_id).json()
    return artifact
