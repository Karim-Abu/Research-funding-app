#!/usr/bin/env python
"""Opt-in Verfügbarkeits-Smoke für OpenAI, Anthropic und Firecrawl.

Prüft — pro Provider mit genau EINEM realen Call — ob die Provider erreichbar
sind, und berichtet das Ergebnis KLAR, ohne bei einem Ausfall selbst rot zu
werden (Exit-Code immer 0). Dieser Wrapper ruft ``run_real_provider_smoke.py``
je Provider auf; alle Sicherheits-Guards liegen dort und bleiben aktiv:

* ``CI`` darf nicht gesetzt sein,
* ``RUN_REAL_PROVIDER_SMOKE=true`` (expliziter manueller Opt-in),
* ``AI_EVAL_MODE=real`` (Owner-Freigabe),
* ausschliesslich synthetische/öffentliche D0-Daten, max. 1 Call pro Provider.

Ohne diese Opt-in-Umgebung (Normalfall, auch im ``verify_all``-Gate) verweigert
jeder Provider-Lauf sauber und wird als ``übersprungen`` berichtet — nie als
Fehler. Dieser Wrapper ist bewusst NICHT Teil von ``verify_all`` (dessen
Kontrakt ist «nur Fake-Provider»); er wird separat und manuell ausgeführt:

    # PowerShell (mit Keys in backend/.env):
    $env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
    backend\\.venv\\Scripts\\python.exe scripts\\run_provider_availability_smoke.py

Bericht: stdout-Tabelle + ``backend/var/evaluation/provider_availability_summary.{md,json}``.
Es werden keine API-Keys, Rohprompts oder Rohantworten berichtet.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROVIDERS = ("openai", "anthropic", "firecrawl")
PROVIDER_LABELS = {"openai": "OpenAI", "anthropic": "Anthropic", "firecrawl": "Firecrawl"}

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / "scripts" / "run_real_provider_smoke.py"
_OUT_DIR = _ROOT / "backend" / "var" / "evaluation"

# Ergebnis-Kategorien.
AVAILABLE = "verfügbar"
SKIPPED = "übersprungen"
OUTAGE = "Ausfall"


def _classify(returncode: int, stderr: str) -> tuple[str, str]:
    """Ordnet den Subprozess-Ausgang einer Kategorie + Klartext-Grund zu."""
    text = stderr.strip()
    last_line = text.splitlines()[-1] if text else ""
    if returncode == 0:
        return AVAILABLE, "Ein realer Call ist erfolgreich durchgelaufen."
    if "verweigert" in text:
        # Guard-Refusal (kein Opt-in / kein Key / CI) — bewusst kein Fehler.
        if "provider_unavailable" in text or "kein API-Key" in text:
            return SKIPPED, "Kein API-Key konfiguriert (backend/.env)."
        if "RUN_REAL_PROVIDER_SMOKE" in text:
            return SKIPPED, "Opt-in fehlt (RUN_REAL_PROVIDER_SMOKE=true)."
        if "AI_EVAL_MODE" in text:
            return SKIPPED, "AI_EVAL_MODE=real fehlt (Owner-Freigabe)."
        if "ci_environment" in text:
            return SKIPPED, "In CI-Umgebung deaktiviert."
        return SKIPPED, last_line or "Manual-Mode-Guard nicht erfüllt."
    if "bereits ausgeführt" in text:
        return SKIPPED, "Bereits ausgeführt (frisches Ergebnisverzeichnis nötig)."
    # Kein Guard-Refusal, aber Fehler ⇒ echter Provider-/Transportausfall.
    return OUTAGE, last_line or f"Unerwarteter Fehler (Exit {returncode})."


def _run_one(provider: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"provavail_{provider}_") as tmp:
        results_dir = Path(tmp) / "results"
        out_file = Path(tmp) / "report.md"
        proc = subprocess.run(
            [
                sys.executable,
                str(_RUNNER),
                "--case", "F1",
                "--provider", provider,
                "--results-dir", str(results_dir),
                "--out", str(out_file),
            ],
            capture_output=True,
            text=True,
        )
    status, detail = _classify(proc.returncode, proc.stderr)
    return {
        "provider": provider,
        "status": status,
        "detail": detail,
        "exit_code": proc.returncode,
    }


def _render_markdown(generated_at: str, results: list[dict]) -> str:
    lines = [
        "# Provider-Verfügbarkeit — Opt-in Smoke",
        "",
        f"*Generiert:* {generated_at}",
        "",
        "Prüft die reale Erreichbarkeit von OpenAI, Anthropic und Firecrawl mit je",
        "einem synthetischen/öffentlichen Call. Ein Provider-Ausfall macht dieses",
        "Skript NICHT rot (Exit-Code 0), wird aber klar berichtet. Ohne den",
        "manuellen Opt-in (`RUN_REAL_PROVIDER_SMOKE=true`, `AI_EVAL_MODE=real`,",
        "Keys in `backend/.env`) erscheinen alle Provider als *übersprungen*.",
        "",
        "| Provider | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {PROVIDER_LABELS[r['provider']]} | {r['status']} | {r['detail']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not _RUNNER.exists():
        print(f"provider-availability: Runner fehlt: {_RUNNER}", file=sys.stderr)
        # Selbst hier nicht rot werden — nur ehrlich berichten.
        return 0

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = [_run_one(p) for p in PROVIDERS]

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "provider_availability_summary.json").write_text(
        json.dumps(
            {"generated_at": generated_at, "providers": results},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (_OUT_DIR / "provider_availability_summary.md").write_text(
        _render_markdown(generated_at, results), encoding="utf-8"
    )

    print("== Provider-Verfügbarkeit (Opt-in Smoke) ==")
    for r in results:
        print(f"  {PROVIDER_LABELS[r['provider']]:<10} {r['status']:<12} {r['detail']}")
    outages = [r for r in results if r["status"] == OUTAGE]
    if outages:
        print(
            "Hinweis: mindestens ein Provider ist ausgefallen — klar berichtet, "
            "das Gate bleibt grün (Fake-/manueller Fallback verfügbar)."
        )
    print(f"Bericht: {_OUT_DIR / 'provider_availability_summary.md'}")
    # Ausfälle machen dieses Skript bewusst NICHT rot.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
