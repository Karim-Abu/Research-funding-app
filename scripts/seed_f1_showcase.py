#!/usr/bin/env python
"""Seed the isolated F1/QUALIMON showcase through the public API.

This script is demo-only. It does not import backend internals and does not
modify application logic. Expected setup:

  backend DATABASE_URL=sqlite:///./var/f1_showcase.db
  backend AGENT_FAKE_PROVIDER=true
  backend WEB_RESEARCH_ENABLED=false
  backend D2_WEB_RESEARCH_ENABLED=false

Run from the repo root after the backend is listening:

  python scripts/seed_f1_showcase.py --base http://127.0.0.1:8001/api/v1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from baseline_f1 import (
    F1_BUDGET,
    F1_DESCRIPTION,
    F1_FIELDS,
    F1_PARTNERS,
    F1_TITLE,
    PROFILE,
)

DEFAULT_BASE = "http://127.0.0.1:8001/api/v1"
DEFAULT_ORIGIN = "http://localhost:3000"
POLICY_VERSION = "1.1.0"
SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

F1_LOCAL_CLASSIFICATION = {
    "sensitivity": "confidential",
    "origin": "synthetic",
    "processing_mode": "local_only",
    "web_research_mode": "off",
    "nda_applies": False,
}


def _unsafe_headers(csrf: str, origin: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": csrf,
        "Origin": origin,
        "Idempotency-Key": uuid.uuid4().hex,
        "Content-Type": "application/json",
    }


def _require_ok(response: httpx.Response, label: str) -> httpx.Response:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"{label} failed: {response.status_code} {detail}") from exc
    return response


def _wait_operation(
    client: httpx.Client,
    base: str,
    operation_id: str,
    *,
    label: str,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        op = _require_ok(
            client.get(f"{base}/operations/{operation_id}"),
            f"poll {label}",
        ).json()
        if op["status"] in {"succeeded", "failed", "cancelled"}:
            if op["status"] != "succeeded":
                raise RuntimeError(f"{label} ended as {op['status']}: {op.get('error')}")
            return op
        time.sleep(0.5)
    raise RuntimeError(f"{label} timed out after {timeout_seconds:.0f}s")


def _list_sources(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    raise RuntimeError(f"Unexpected sources payload: {payload!r}")


def _wait_source_processed(
    client: httpx.Client,
    base: str,
    project_id: str,
    *,
    timeout_seconds: float = 60.0,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        rows = _list_sources(
            _require_ok(
                client.get(f"{base}/projects/{project_id}/sources"),
                "list sources",
            ).json()
        )
        ready = next(
            (
                row
                for row in rows
                if row.get("status") == "processed"
                and row.get("current_source_version_id")
            ),
            None,
        )
        if ready is not None:
            return str(ready["current_source_version_id"])
        time.sleep(0.5)
    raise RuntimeError("F1 showcase source was not processed in time")


def _ensure_no_existing_f1(client: httpx.Client, base: str) -> None:
    projects = _require_ok(client.get(f"{base}/projects"), "list projects").json()
    items = projects.get("items", []) if isinstance(projects, dict) else []
    matches = [p for p in items if p.get("title") == F1_TITLE]
    if matches:
        raise RuntimeError(
            "A QUALIMON showcase project already exists in this database. "
            "Use a fresh backend/var/f1_showcase.db for a one-project demo."
        )


def _create_project(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
) -> str:
    project = _require_ok(
        client.post(
            f"{base}/projects",
            headers=_unsafe_headers(csrf, origin),
            json={
                "title": F1_TITLE,
                "description": F1_DESCRIPTION,
                "innovation_field": "ICT / Industrial AI",
                "funding_instrument_profile_id": PROFILE,
                "data_classification": F1_LOCAL_CLASSIFICATION,
            },
        ),
        "create F1 showcase project",
    ).json()
    project_id = project["project_id"]

    _require_ok(
        client.patch(
            f"{base}/projects/{project_id}",
            headers=_unsafe_headers(csrf, origin),
            json=F1_BUDGET,
        ),
        "patch F1 budget",
    )
    for partner in F1_PARTNERS:
        _require_ok(
            client.post(
                f"{base}/projects/{project_id}/partners",
                headers=_unsafe_headers(csrf, origin),
                json=partner,
            ),
            f"create partner {partner['partner_type']}",
        )
    return project_id


def _upload_case_source(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    project_id: str,
    case_file: Path,
) -> str:
    text = case_file.read_text(encoding="utf-8")
    _require_ok(
        client.post(
            f"{base}/projects/{project_id}/sources/text",
            headers=_unsafe_headers(csrf, origin),
            json={
                "name": "F1 QUALIMON Synthetic Case.md",
                "text": text,
                "data_classification": F1_LOCAL_CLASSIFICATION,
            },
        ),
        "upload F1 markdown source",
    )
    return _wait_source_processed(client, base, project_id)


def _create_local_confirmation(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    project_id: str,
    source_version_id: str,
) -> str:
    confirmation = _require_ok(
        client.post(
            f"{base}/projects/{project_id}/processing-confirmations",
            headers=_unsafe_headers(csrf, origin),
            json={
                "processing_mode": "local_only",
                "source_version_ids": [source_version_id],
                "accepted_policy_version": POLICY_VERSION,
                "purpose": "Prepare local AI suggestions for the F1 showcase",
                "expires_after_one_run": True,
            },
        ),
        "create local AI processing confirmation",
    ).json()
    return confirmation["confirmation_id"]


def _start_local_run(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    project_id: str,
    source_version_id: str,
    confirmation_id: str,
) -> str:
    accepted = _require_ok(
        client.post(
            f"{base}/projects/{project_id}/runs",
            headers=_unsafe_headers(csrf, origin),
            json={
                "settings": {
                    "processing_mode": "local_only",
                    "max_cost_chf": 0,
                    "max_llm_calls": 2,
                    "max_web_calls": 0,
                    "source_version_ids": [source_version_id],
                    "internal_cloud_confirmation_id": confirmation_id,
                }
            },
        ),
        "start local F1 analysis run",
    ).json()
    _wait_operation(
        client,
        base,
        accepted["operation_id"],
        label="local F1 analysis run",
    )
    return accepted["resource_id"]


def _fill_f1_fields(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    run_id: str,
) -> None:
    for field_id, text in F1_FIELDS.items():
        draft = _require_ok(
            client.get(f"{base}/runs/{run_id}/fields/{field_id}"),
            f"get draft {field_id}",
        ).json()
        base_version = draft["current_version"]["draft_version_id"]
        _require_ok(
            client.patch(
                f"{base}/runs/{run_id}/fields/{field_id}",
                headers=_unsafe_headers(csrf, origin),
                json={"base_version_id": base_version, "text": text},
            ),
            f"write F1 field {field_id}",
        )


def _run_recheck_and_reliability(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    run_id: str,
) -> None:
    review_pre = _require_ok(
        client.get(f"{base}/runs/{run_id}/review"),
        "get review before recheck",
    ).json()
    accepted = _require_ok(
        client.post(
            f"{base}/runs/{run_id}/rechecks",
            headers=_unsafe_headers(csrf, origin),
            json={
                "expected_review_package_version": review_pre["review_package_version"],
                "changed_target_refs": [],
            },
        ),
        "start targeted recheck",
    ).json()
    _wait_operation(client, base, accepted["operation_id"], label="targeted recheck")

    accepted = _require_ok(
        client.post(
            f"{base}/runs/{run_id}/reliability",
            headers=_unsafe_headers(csrf, origin),
        ),
        "start reliability pass",
    ).json()
    _wait_operation(client, base, accepted["operation_id"], label="reliability pass")


def _prepare_redraft(
    client: httpx.Client,
    base: str,
    csrf: str,
    origin: str,
    run_id: str,
    field_id: str,
) -> dict[str, Any]:
    draft = _require_ok(
        client.get(f"{base}/runs/{run_id}/fields/{field_id}"),
        f"get A2 base draft {field_id}",
    ).json()
    base_version = draft["current_version"]["draft_version_id"]
    accepted = _require_ok(
        client.post(
            f"{base}/runs/{run_id}/fields/{field_id}/redrafts",
            headers=_unsafe_headers(csrf, origin),
            json={"base_version_id": base_version},
        ),
        f"prepare A2 redraft {field_id}",
    ).json()
    operation = _wait_operation(
        client,
        base,
        accepted["operation_id"],
        label=f"A2 redraft {field_id}",
    )
    result = operation.get("result") or {}
    return {
        "field_id": field_id,
        "operation_id": operation["operation_id"],
        "suggestion_id": result.get("suggestion_id"),
        "character_count": result.get("character_count"),
        "base_version_id": result.get("base_version_id"),
    }


def _verify(
    client: httpx.Client,
    base: str,
    project_id: str,
    run_id: str,
    redrafts: list[dict[str, Any]],
) -> dict[str, Any]:
    fields = _require_ok(client.get(f"{base}/runs/{run_id}/fields"), "list fields").json()
    review = _require_ok(client.get(f"{base}/runs/{run_id}/review"), "get review").json()
    reliability = _require_ok(
        client.get(f"{base}/runs/{run_id}/reliability"),
        "get reliability",
    ).json()
    requirements = _require_ok(
        client.get(f"{base}/runs/{run_id}/requirements"),
        "get requirements",
    ).json()

    field_map = {row["field_id"]: row for row in fields}
    missing = [field_id for field_id in F1_FIELDS if field_id not in field_map]
    mismatched = [
        field_id
        for field_id, text in F1_FIELDS.items()
        if field_id in field_map and field_map[field_id]["current_version"]["text"] != text
    ]
    if missing or mismatched:
        raise RuntimeError(
            f"F1 field verification failed: missing={missing}, mismatched={mismatched}"
        )
    if not redrafts or len(redrafts) != 2 or any(not r.get("suggestion_id") for r in redrafts):
        raise RuntimeError(f"A2 redraft verification failed: {redrafts}")

    projects = _require_ok(client.get(f"{base}/projects"), "list projects").json()["items"]
    f1_projects = [p for p in projects if p.get("title") == F1_TITLE]
    if len(f1_projects) != 1 or f1_projects[0]["project_id"] != project_id:
        raise RuntimeError("Expected exactly one QUALIMON showcase project.")

    return {
        "project_count": len(projects),
        "field_count": len(fields),
        "requirement_count": len(requirements),
        "review_blocker_count": review.get("blocker_count"),
        "review_warning_count": review.get("warning_count"),
        "approval_status": review.get("approval_status"),
        "recheck_required": review.get("recheck_required"),
        "reliability_summary": reliability.get("summary"),
    }


def run(
    *,
    base: str,
    origin: str,
    email: str,
    password: str,
    case_file: Path,
) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        session = _require_ok(
            client.post(f"{base}/session", json={"email": email, "password": password}),
            "login",
        ).json()
        csrf = session["csrf_token"]

        _ensure_no_existing_f1(client, base)
        project_id = _create_project(client, base, csrf, origin)
        source_version_id = _upload_case_source(
            client, base, csrf, origin, project_id, case_file
        )
        confirmation_id = _create_local_confirmation(
            client, base, csrf, origin, project_id, source_version_id
        )
        run_id = _start_local_run(
            client,
            base,
            csrf,
            origin,
            project_id,
            source_version_id,
            confirmation_id,
        )
        _fill_f1_fields(client, base, csrf, origin, run_id)
        _run_recheck_and_reliability(client, base, csrf, origin, run_id)
        redrafts = [
            _prepare_redraft(client, base, csrf, origin, run_id, SOL_FIELD),
            _prepare_redraft(client, base, csrf, origin, run_id, VC_FIELD),
        ]
        verification = _verify(client, base, project_id, run_id, redrafts)
        return {
            "project_id": project_id,
            "run_id": run_id,
            "source_version_id": source_version_id,
            "processing_confirmation_id": confirmation_id,
            "prepared_redrafts": redrafts,
            "verification": verification,
            "demo_urls": {
                "frontend": "http://127.0.0.1:3001",
                "backend_health": f"{base.rsplit('/api/v1', 1)[0]}/api/v1/health",
            },
            "login": {"email": email, "password": password},
        }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("F1_SHOWCASE_BASE", DEFAULT_BASE))
    parser.add_argument("--origin", default=os.environ.get("F1_SHOWCASE_ORIGIN", DEFAULT_ORIGIN))
    parser.add_argument("--email", default=os.environ.get("E2E_EMAIL", "anna.keller@example.test"))
    parser.add_argument("--password", default=os.environ.get("E2E_PASSWORD", "changeme-dev-lead"))
    parser.add_argument(
        "--case-file",
        type=Path,
        default=repo_root / "docs" / "evaluation" / "cases" / "F1_synthetic_case.md",
    )
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run(
        base=args.base.rstrip("/"),
        origin=args.origin,
        email=args.email,
        password=args.password,
        case_file=args.case_file,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
