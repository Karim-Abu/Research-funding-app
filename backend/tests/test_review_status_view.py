"""R1.2 — Tests für den kanonischen ReviewStatusView (GET /runs/{id}/review/status).

Kriterien aus dem Prompt-Pack: Platzhalter-Blocker ⇒ blocker_count 1; stale
korrekt bei veraltetem Scope-Hash (Draft-Edit); leeres Package ⇒ 0-Counts.
Zusätzlich: Parität mit dem bestehenden ReviewPackage (keine parallele Zähllogik).
"""
from __future__ import annotations

from tests.review_helpers import (
    ABSTRACT,
    clean_field,
    get_review,
    run_recheck,
    setup_completed_run,
)


def get_status(client, run_id) -> dict:
    res = client.get(f"/api/v1/runs/{run_id}/review/status")
    assert res.status_code == 200, res.text
    return res.json()


def test_status_view_matches_review_package(client):
    """Parität: Status-View und ReviewPackage liefern identische Kernzahlen."""
    _csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    status = get_status(client, run_id)
    assert status["run_id"] == run_id
    assert status["blocker_count"] == pkg["blocker_count"]
    assert status["warning_count"] == pkg["warning_count"]
    assert status["approval_status"] == pkg["approval_status"]
    assert status["review_package_version"] == pkg["review_package_version"]


def test_status_view_task_counts_match_fix_queue_and_check_status(client):
    """B7/B8 — «Blockierende Aufgaben»/«Unterliegende Evidenzhinweise» sind auf
    Status-View, Fix Queue und Check-Status-View identisch (eine Quelle)."""
    _csrf, _pid, run_id = setup_completed_run(client)
    status = get_status(client, run_id)
    queue = client.get(f"/api/v1/runs/{run_id}/review/fix-queue").json()
    checks = client.get(f"/api/v1/runs/{run_id}/review/check-status").json()
    assert (
        status["blocking_task_count"]
        == queue["blocking_task_count"]
        == checks["blocking_task_count"]
    )
    assert (
        status["evidence_note_count"]
        == queue["evidence_note_count"]
        == checks["evidence_note_count"]
    )
    assert status["blocking_task_count"] == sum(
        1 for g in queue["grouped_findings"] if g["severity"] == "blocker"
    )


def test_placeholder_blocker_counts_once(client):
    """Ein Feld mit Platzhalter erzeugt genau einen Platzhalter-Blocker, der im
    Status-View mitzählt (Vergleich vor/nach dem Auflösen des Platzhalters)."""
    csrf, _pid, run_id = setup_completed_run(client)
    before = get_status(client, run_id)
    assert before["blocker_count"] >= 1  # Template-Drafts enthalten Platzhalter

    # Platzhalter im Abstract auflösen, Recheck ausführen.
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzer sauberer Abstract.")
    res = run_recheck(client, csrf, run_id)
    assert res.status_code == 202, res.text
    after = get_status(client, run_id)
    # Genau der eine Abstract-Platzhalter-Blocker ist weg.
    assert after["blocker_count"] == before["blocker_count"] - 1


def test_stale_true_after_draft_edit(client):
    """Draft-Edit veraltet den Scope-Hash (recheck_required) ⇒ stale=True;
    nach erfolgreichem Recheck wieder False."""
    csrf, _pid, run_id = setup_completed_run(client)
    assert get_status(client, run_id)["stale"] is False

    clean_field(client, csrf, run_id, ABSTRACT, "Neuer Text ohne Platzhalter.")
    assert get_status(client, run_id)["stale"] is True

    res = run_recheck(client, csrf, run_id)
    assert res.status_code == 202, res.text
    assert get_status(client, run_id)["stale"] is False


def test_empty_package_zero_counts(client):
    """Run ohne Findings/Issues: alle Blocker weg ⇒ 0/0 und kein stale.
    (Alle 8 Felder sauber befüllen, Recheck.)"""
    csrf, _pid, run_id = setup_completed_run(client)
    for field in get_review(client, run_id)["fields"]:
        clean_field(
            client, csrf, run_id, field["field_id"], "Sauberer kurzer Text."
        )
    res = run_recheck(client, csrf, run_id)
    assert res.status_code == 202, res.text

    status = get_status(client, run_id)
    assert status["blocker_count"] == 0
    assert status["stale"] is False
    pkg = get_review(client, run_id)
    assert pkg["blocker_count"] == 0
    assert status["warning_count"] == pkg["warning_count"]


def test_per_area_counts_and_human_review(client):
    """per_area_counts gruppiert offene Findings nach Feldbereich; Findings ohne
    Feldbezug laufen unter 'general'. human_review_count zählt seit RUN 2A
    Slice 1 die OFFENEN Human-Review-/Confirmation-Issues (requires_human_review
    + human_confirmation_pending) — nicht pauschal needs_input-Assessments."""
    _csrf, _pid, run_id = setup_completed_run(client)
    status = get_status(client, run_id)
    pkg = get_review(client, run_id)

    open_findings = [f for f in pkg["findings"] if f["status"] == "open"]
    assert sum(status["per_area_counts"].values()) == len(open_findings)
    expected_areas = {
        (f["field_id"] or "").split(".")[0] or "general" for f in open_findings
    }
    assert set(status["per_area_counts"].keys()) == expected_areas

    review_issue_types = {"human_confirmation_pending", "requires_human_review"}
    open_review_issues = [
        issue
        for a in pkg["requirements"]
        for issue in a["open_issues"]
        if issue["status"] == "open" and issue["issue_type"] in review_issue_types
    ]
    assert status["human_review_count"] == len(open_review_issues)
    # Ein erfüllter Hybrid-Check mit offener Bestätigung zählt hier, bleibt
    # aber im Compliance-Status «fulfilled».
    fulfilled_with_review = [
        a for a in pkg["requirements"]
        if a["status"] == "fulfilled"
        and any(i["issue_type"] == "human_confirmation_pending" for i in a["open_issues"])
    ]
    assert fulfilled_with_review, "Setup erzeugt mindestens einen Hybrid-Pass"


def test_status_view_is_read_only(client):
    """Wiederholtes Lesen verändert nichts (Version stabil, Counts stabil)."""
    _csrf, _pid, run_id = setup_completed_run(client)
    first = get_status(client, run_id)
    second = get_status(client, run_id)
    assert first == second
