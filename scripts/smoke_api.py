#!/usr/bin/env python
"""Milestone 10 — API smoke test (against a RUNNING server, fake providers only).

Exercises the core pipeline end to end via HTTP: login → capabilities → project → source →
run → operation polling → requirements → evidence → review → reliability pass → export
create + download, plus (when the capability is on) public web research + market comparison
with the fake provider. No real provider/key required.

    python scripts/smoke_api.py [--base http://localhost:8000/api/v1] [--email ...] [--password ...]

Exit code 0 = all steps passed; 1 = a step failed (prints a summary).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

import httpx

ORIGIN = "http://localhost:3000"
PROFILE = "innosuisse_innovation_project_with_implementation_partner"
PUBLIC = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}
_results: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok, detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


def _mut(csrf: str) -> dict:
    return {"X-CSRF-Token": csrf, "Origin": ORIGIN, "Idempotency-Key": uuid.uuid4().hex,
            "Content-Type": "application/json"}


def _wait(c: httpx.Client, base: str, op_id: str, tries: int = 90) -> str:
    for _ in range(tries):
        status = c.get(f"{base}/operations/{op_id}").json()["status"]
        if status in ("succeeded", "failed", "cancelled"):
            return status
        time.sleep(0.5)
    return "timeout"


def run(base: str, email: str, password: str) -> int:
    with httpx.Client(timeout=60.0) as c:
        r = c.post(f"{base}/session", json={"email": email, "password": password})
        if not _check("login", r.status_code == 200, r.text[:200]):
            return _summary()
        csrf = r.json()["csrf_token"]

        caps = c.get(f"{base}/capabilities").json()
        _check("capabilities", "features" in caps)
        features = caps.get("features", {})

        pid = c.post(f"{base}/projects", headers=_mut(csrf), json={
            "title": "M10 API Smoke", "description": "smoke.",
            "funding_instrument_profile_id": PROFILE, "data_classification": PUBLIC,
        }).json()["project_id"]
        _check("create project", bool(pid))

        c.post(f"{base}/projects/{pid}/sources/text", headers=_mut(csrf), json={
            "name": "Notiz", "text": "Synthetischer öffentlicher Projektinhalt.",
            "data_classification": PUBLIC,
        })
        sv = ""
        for _ in range(40):
            rows = c.get(f"{base}/projects/{pid}/sources").json()
            ready = next((s for s in rows if s["status"] == "processed"
                          and s.get("current_source_version_id")), None)
            if ready:
                sv = ready["current_source_version_id"]
                break
            time.sleep(0.5)
        if not _check("source processed", bool(sv)):
            return _summary()

        accepted = c.post(f"{base}/projects/{pid}/runs", headers=_mut(csrf), json={
            "settings": {"processing_mode": "deterministic_only", "max_cost_chf": 0,
                         "max_llm_calls": 0, "max_web_calls": 0, "source_version_ids": [sv]},
        }).json()
        run_id = accepted["resource_id"]
        _check("run completes", _wait(c, base, accepted["operation_id"]) == "succeeded")

        _check("requirements", c.get(f"{base}/runs/{run_id}/requirements").status_code == 200)
        _check("evidence", c.get(f"{base}/runs/{run_id}/evidence").status_code == 200)
        _check("review package", c.get(f"{base}/runs/{run_id}/review").status_code == 200)

        rel = c.post(f"{base}/runs/{run_id}/reliability", headers=_mut(csrf)).json()
        _check("reliability pass", _wait(c, base, rel["operation_id"]) == "succeeded")
        view = c.get(f"{base}/runs/{run_id}/reliability").json()
        _check("reliability summary", view.get("available") is True)

        for kind in ("technical_evidence", "docx", "markdown"):
            acc = c.post(f"{base}/runs/{run_id}/exports", headers=_mut(csrf),
                         json={"type": kind, "force_draft": False}).json()
            if not _check(f"export {kind}", _wait(c, base, acc["operation_id"]) == "succeeded"):
                continue
            art = c.get(f"{base}/exports/{acc['resource_id']}").json()
            body = c.get(f"{base}/exports/{art['export_id']}/download").content
            _check(f"download {kind}", len(body) > 0)

        if features.get("web_research"):
            acc = c.post(f"{base}/projects/{pid}/research-tasks", headers=_mut(csrf), json={
                "purpose": "partner_role_suggestion", "subject_type": "topic",
                "query_preview": "öffentliche Wettbewerbsanalyse", "max_results": 2,
                "user_confirms_public_professional_purpose": True,
            })
            _check("web research (fake)", acc.status_code == 202
                   and _wait(c, base, acc.json()["operation_id"]) == "succeeded")
        if features.get("market_comparison"):
            acc = c.post(f"{base}/projects/{pid}/market-comparisons", headers=_mut(csrf))
            # Without imported public sources it may 422; the surface must not 5xx.
            _check("market comparison (fake)", acc.status_code < 500)
    return _summary()


def _summary() -> int:
    failed = [n for n, ok, _ in _results if not ok]
    print(f"\nAPI smoke: {len(_results) - len(failed)}/{len(_results)} passed"
          + (f" — FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=os.environ.get("SMOKE_BASE", "http://localhost:8000/api/v1"))
    p.add_argument("--email", default=os.environ.get("E2E_EMAIL", "anna.keller@example.test"))
    p.add_argument("--password", default=os.environ.get("E2E_PASSWORD", "changeme-dev-lead"))
    args = p.parse_args()
    try:
        return run(args.base, args.email, args.password)
    except httpx.HTTPError as exc:
        print(f"API smoke: transport error — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
