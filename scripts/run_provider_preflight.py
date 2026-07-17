#!/usr/bin/env python
"""Opt-in Provider-Preflight (Ebene E) — Live-Readiness ohne Antragsinhalt.

Prüft je Provider (OpenAI, Anthropic, Firecrawl) mit einem konstanten
synthetischen Ping: Key vorhanden → API erreichbar → konfiguriertes Modell
verfügbar (Registry-Route vs. Provider-Echo) → strukturierte Ausgabe
unterstützt → Rate-Limit-/Quota-Fehler verständlich. Es werden DIESELBEN
produktiven Adapter benutzt wie in der App (keine parallele Logik).

Opt-in-Guards (ohne sie werden Konfigurationschecks lokal ausgeführt und
externe Live-Checks ehrlich als ``not_run`` berichtet — Exit-Code bleibt 0,
nie CI-rot):

* ``CI`` darf nicht gesetzt sein,
* ``RUN_REAL_PROVIDER_SMOKE=true`` (expliziter manueller Opt-in).

Dieser Preflight ist bewusst NICHT Teil von ``verify_all`` (dessen Kontrakt
ist «nur Fake-Provider»). Aufruf:

    # PowerShell (mit Keys in backend/.env):
    $env:RUN_REAL_PROVIDER_SMOKE = "true"
    backend\\.venv\\Scripts\\python.exe scripts\\run_provider_preflight.py

Bericht: stdout + ``backend/var/evaluation/provider_preflight.{md,json}``.
Keine API-Keys, keine Prompts, keine Rohantworten im Report.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
_OUT_DIR = _BACKEND / "var" / "evaluation"

os.chdir(_BACKEND)  # pydantic-settings lädt backend/.env, nie eine Root-Datei.
sys.path.insert(0, str(_BACKEND))

from app.evaluation.preflight import (  # noqa: E402
    render_report,
    run_configured_preflight,
    to_json,
)


def main() -> int:
    execute_live = (
        os.environ.get("CI") is None
        and os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").lower() == "true"
    )
    if not execute_live:
        print(
            "Hinweis: Kein Opt-in (RUN_REAL_PROVIDER_SMOKE=true fehlt oder CI "
            "gesetzt) — es werden keine Live-Aufrufe gemacht; lokale "
            "Konfigurationschecks laufen weiter."
        )
    results = run_configured_preflight(execute_live=execute_live)
    report = render_report(results)
    print(report)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "provider_preflight.md").write_text(report, encoding="utf-8")
    (_OUT_DIR / "provider_preflight.json").write_text(
        to_json(results), encoding="utf-8"
    )
    print(f"Bericht: {_OUT_DIR / 'provider_preflight.md'}")
    # Ausfälle machen den Preflight-Aufruf nie rot — der Report trägt die
    # Wahrheit (pass/fail/not_run je Check).
    return 0


if __name__ == "__main__":
    sys.exit(main())
