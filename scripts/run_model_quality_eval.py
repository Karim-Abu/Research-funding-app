#!/usr/bin/env python
"""Opt-in Live-Model-Evaluation (Ebene C) — Modellqualität OpenAI vs. Anthropic.

Zwei Phasen, beide über die PRODUKTIVEN Pfade (Harness-Vertrag E.8 — keine
parallele Evaluationslogik):

1. Generierung (nur mit vollem Opt-in): je Provider ein R5.9-REAL-Lauf
   (``scripts/run_integrated_draft_real.py`` — gateway.invoke, Produktiv-
   Profile, Prompt-Assets, echte Adapter, synthetischer F1/D0-Fall).
   Guards dort: ``CI`` ungesetzt, ``RUN_REAL_PROVIDER_SMOKE=true``,
   ``AI_EVAL_MODE=real``, Key vorhanden. Provider-Ausfall macht diesen
   Aufruf NIE rot — er wird als ``not_run`` berichtet.
2. Auswertung (immer): deterministische Qualitätsmetriken über die
   vorhandenen Ergebnisartefakte (``app.evaluation.model_quality``).

Artefakte: Rohoutputs nur gitignoriert unter ``backend/var/evaluation/
r5_9_real/``; Whitelist-Summary unter ``backend/var/evaluation/
model_quality_summary.{md,json}`` (Status, Zählwerte, Modell-IDs — keine
Rohtexte). Exit-Code immer 0; die Wahrheit steht im Report
(durchgeführt/not_run je Provider).

Aufruf (PowerShell, Keys in backend/.env):
    $env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
    backend\\.venv\\Scripts\\python.exe scripts\\run_model_quality_eval.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
_RESULTS_DIR = _BACKEND / "var" / "evaluation" / "r5_9_real"
_OUT_DIR = _BACKEND / "var" / "evaluation"
_RUNNER = _ROOT / "scripts" / "run_integrated_draft_real.py"

sys.path.insert(0, str(_BACKEND))

from app.evaluation.model_quality import (  # noqa: E402
    PROVIDERS,
    evaluate_results_dir,
    render_quality_report,
    summarize_status,
)


def _opted_in() -> bool:
    return (
        os.environ.get("CI") is None
        and os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").lower() == "true"
        and os.environ.get("AI_EVAL_MODE", "").lower() == "real"
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if _opted_in():
        for provider in PROVIDERS:
            if (_RESULTS_DIR / f"{provider}.json").exists():
                print(f"{provider}: vorhandenes Ergebnis wird ausgewertet.")
                continue
            print(f"{provider}: starte R5.9-REAL-Lauf (produktiver Pfad) …")
            outcome = subprocess.run(
                [sys.executable, str(_RUNNER), "--provider", provider],
                cwd=_ROOT, check=False,
            )
            if outcome.returncode != 0:
                # Ausfall wird berichtet, nie verschwiegen — und macht den
                # Evaluationsaufruf nicht rot.
                print(f"{provider}: Lauf nicht durchgeführt (Guard/Ausfall).")
    else:
        print(
            "Hinweis: Kein Opt-in (RUN_REAL_PROVIDER_SMOKE/AI_EVAL_MODE) — es "
            "werden keine Provider-Läufe gestartet; vorhandene Ergebnisse "
            "werden ausgewertet, fehlende als not_run berichtet."
        )

    per_provider, reasons = evaluate_results_dir(_RESULTS_DIR)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = render_quality_report(
        per_provider, generated_at=generated_at, not_run_reasons=reasons
    )
    print(report)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "model_quality_summary.md").write_text(report, encoding="utf-8")
    (_OUT_DIR / "model_quality_summary.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "status": summarize_status(per_provider),
                "providers": {
                    provider: (rows if rows is not None else {"not_run": reasons[provider]})
                    for provider, rows in per_provider.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Status: {summarize_status(per_provider)}")
    print(f"Bericht: {_OUT_DIR / 'model_quality_summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
