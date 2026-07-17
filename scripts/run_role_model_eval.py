#!/usr/bin/env python
"""Opt-in Rollen-Modell-Evaluation (A1/A2/A3) — Kandidatenvergleich je Agentenrolle.

Vier Unterbefehle (Details: ``backend/app/evaluation/role_model_eval.py``):

  run     Kandidaten-Läufe ausführen (Dev-Set F1,F2; Holdout H1 nur mit
          --allow-holdout). Wiederholungen via --reps (Default 2). Vorhandene
          Sample-Dateien werden übersprungen (Kostenbremse — Re-Run erfordert
          Löschen der Datei).
  blind   Anonymisierte Bewertungsunterlagen (Model A/B/C/…, randomisiert)
          plus CSV-Bogen erzeugen (Rollen a2/a3). mapping.json bleibt lokal.
  ingest  Ausgefüllten Blindbogen einlesen (menschliche Rubrik — nie KI;
          seit dem Dev/Holdout-Split zusätzlich `per_candidate_split`).
  report  Whitelist-Summary (summary.{json,md}) neu aggregieren.
  pilot   Begrenzter Live-Pilot (Owner-Auftrag 2026-07-16): Phase `smoke`
          (Route-Preflight + 1 strukturierter Call je Kandidatenroute, danach
          STOPP + Bericht), `run` (A2 VC+SOL für F1/H1 je Kandidat + Cross-
          Critic des jeweils anderen Modells), `blind`/`ingest` (10-Kriterien-
          Owner-Rubrik), `report`. Harte Limits: max 24 echte Calls, max
          CHF 12; eigenes Verzeichnis `role_model_eval_pilot/`.

Guards für reale Läufe (wie EVAL.2/R5.9-REAL): ``CI`` ungesetzt,
``RUN_REAL_PROVIDER_SMOKE=true``, ``AI_EVAL_MODE=real``, API-Key in
``backend/.env``; ``evaluation_only``-Routen zusätzlich
``AGENT_QUALITY_CEILING_ENABLED=true``. Kandidaten-Modell-IDs kommen aus den
``AGENT_MODEL_*_ID``-Settings; ohne verifizierte Preise in
``AGENT_MODEL_PRICING_CHF_PER_MILLION`` blockiert das Gateway die Route
(``price_unknown_for_cost_guard``) — kein stiller Gratis-Lauf.

``--fake``: kostenloser Dry-Run (injizierte Fake-Adapter durch das echte
Gateway, Live-Routing, Gates, Blindung, Ingest, Aggregation) — Samples sind
als ``fake_dryrun`` markiert und werden nie als Live-Evaluation berichtet.

Rohoutputs nur im gitignorierten ``backend/var/evaluation/role_model_eval/``.
Exit 2 bei Guard-Verweigerung, sonst 0.

Aufruf (PowerShell, Keys/Preise in backend/.env):
    $env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
    backend\\.venv\\Scripts\\python.exe scripts\\run_role_model_eval.py run --role a2
    backend\\.venv\\Scripts\\python.exe scripts\\run_role_model_eval.py blind --role a2
    backend\\.venv\\Scripts\\python.exe scripts\\run_role_model_eval.py ingest --role a2 \
        --scores backend/var/evaluation/role_model_eval/blind/a2/a2_scoring_sheet.csv
    backend\\.venv\\Scripts\\python.exe scripts\\run_role_model_eval.py report
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Kandidaten-Läufe ausführen")
    run.add_argument("--role", required=True, choices=("a1", "a2", "a3"))
    run.add_argument(
        "--candidate", action="append", dest="candidates",
        help="Kandidaten-Route (mehrfach; Default: Auftrag-Kandidaten der Rolle)",
    )
    run.add_argument("--cases", default="F1,F2")
    run.add_argument("--reps", type=int, default=2)
    run.add_argument("--fake", action="store_true",
                     help="Kostenloser Dry-Run mit injizierten Fake-Adaptern")
    run.add_argument("--allow-holdout", action="store_true",
                     help="Holdout-Fall H1 zulassen (nie für Prompt-Tuning)")
    run.add_argument("--results-dir", default=None)

    blind = sub.add_parser("blind", help="Blind-Pack + CSV-Bogen erzeugen")
    blind.add_argument("--role", required=True, choices=("a2", "a3"))
    blind.add_argument("--results-dir", default=None)

    ingest = sub.add_parser("ingest", help="Ausgefüllten Blindbogen einlesen")
    ingest.add_argument("--role", required=True, choices=("a2", "a3"))
    ingest.add_argument("--scores", required=True)
    ingest.add_argument("--results-dir", default=None)

    report = sub.add_parser("report", help="Summary neu aggregieren")
    report.add_argument("--results-dir", default=None)

    # Live-Pilot (Owner-Auftrag 2026-07-16): begrenzter A2/A3-Vergleich
    # (max 24 echte Calls, max CHF 12) VOR dem grossen Benchmark.
    pilot = sub.add_parser(
        "pilot",
        help="Begrenzter Live-Pilot: smoke → STOPP/Bericht → run → blind → "
             "ingest → report (eigenes Verzeichnis role_model_eval_pilot)",
    )
    pilot.add_argument(
        "--phase", required=True,
        choices=("smoke", "so_smoke", "rescore", "calibrate", "run", "blind",
                 "ingest", "report"),
    )
    pilot.add_argument("--fake", action="store_true",
                       help="Kostenloser Dry-Run mit injizierten Fake-Adaptern")
    pilot.add_argument("--allow-holdout", action="store_true",
                       help="Holdout-Fall H1 im Pilot zulassen")
    pilot.add_argument("--scores", default=None,
                       help="Ausgefüllter Pilot-Blindbogen (Phase ingest)")
    pilot.add_argument("--role", default=None, choices=("a2", "a3"),
                       help="Rolle des Pilot-Blindbogens (Phase ingest)")
    pilot.add_argument("--results-dir", default=None)

    return parser.parse_args(argv)


def _run_pilot(args, rme, results_dir: Path) -> int:
    """Pilot-Phasen: smoke (STOPP+Bericht) · calibrate (bei PASS automatisch
    Voll-Lauf + neuer Blind-Pack, dann STOPP) · run · blind · ingest · report."""
    if args.phase in ("smoke", "so_smoke", "rescore", "calibrate", "run"):
        from app.db.base import Base
        from app.db.session import SessionLocal, engine

        Base.metadata.create_all(engine)
        try:
            if args.phase == "smoke":
                # Owner-Entscheid 2026-07-16 (Option b): BEIDE Kandidaten
                # laufen über den A2-Mini-Smoke (Anthropic mit forced tool
                # use, ohne effort-Feld; 529-Retry-Policy im Runner).
                written = []
                for candidate in rme.PILOT_A2_CANDIDATES:
                    written.append(rme.run_pilot_a2_mini_smoke(
                        candidate_key=candidate,
                        fake=args.fake, results_dir=results_dir,
                    ))
                print(f"pilot smoke: {len(written)} Smoke-Sample(s) aktuell.")
                print(
                    "STOPP nach Phase 1 (Owner-Auftrag): Zwischenbericht via "
                    "`pilot --phase report` prüfen, dann erst `--phase run`."
                )
            elif args.phase == "so_smoke":
                # Owner Block 1/6: je 1 kleiner Anthropic-Structured-Output-
                # Smoke für A2 und A3 — Vorbedingung der Kalibrierung.
                written = rme.execute_structured_output_smokes(
                    fake=args.fake, results_dir=results_dir,
                )
                passed, report = rme.structured_output_smokes_passed(results_dir)
                print(f"pilot so_smoke: {len(written)} Artefakt(e).")
                for slug, detail in report["smokes"].items():
                    print(f"  {slug}: {detail}")
                if args.fake:
                    # Ein Fake-Lauf ist NIE eine bestandene Live-Smoke-Evidenz.
                    print("Dry-Run — keine Smoke-Aussage (Vertrag nur geprobt).")
                    rme.write_pilot_summary(results_dir)
                    return 0
                if not passed:
                    print(
                        "STRUCTURED-OUTPUT-SMOKE NICHT BESTANDEN — STOPP "
                        "(keine Rückkehr zu forced tool use ohne Freigabe): "
                        + "; ".join(report["problems"]),
                        file=sys.stderr,
                    )
                    rme.write_pilot_summary(results_dir)
                    return 2
                print("Beide Structured-Output-Smokes bestanden.")
            elif args.phase == "rescore":
                # Owner Block 6: Scoringkorrekturen NIE mit neuen Calls
                # erkaufen — gespeicherte Outputs offline neu bewerten.
                summary = rme.rescore_pilot_samples(SessionLocal)
                print(
                    f"pilot rescore: {len(summary['rescored'])} Sample(s) neu "
                    f"bewertet, {len(summary['unchanged'])} unverändert, "
                    f"{len(summary['skipped'])} übersprungen (0 Provider-Calls)."
                )
                for row in summary["rescored"]:
                    print(f"  {row['candidate']} {row.get('section')}: {row['after']}")
                passed, report = rme.calibration_check(results_dir)
                print(f"Kalibrierung (technisch): {report['criteria']}")
                if report.get("content_findings"):
                    print("Inhaltliche Befunde (Modellbefunde, kein Blocker):")
                    for key, codes in report["content_findings"].items():
                        print(f"  {key}: {codes}")
                if not passed:
                    print(
                        "TECHNISCHE KALIBRIERUNG NICHT BESTANDEN — STOPP.",
                        file=sys.stderr,
                    )
                    rme.write_pilot_summary(results_dir)
                    return 2
                print("Technische Kalibrierung BESTANDEN.")
            elif args.phase == "calibrate":
                passed, report, written = rme.execute_pilot_calibration(
                    SessionLocal, fake=args.fake, results_dir=results_dir,
                )
                print(
                    f"pilot calibrate: {len(written)} neue Sample(s); "
                    f"Kriterien: {report['criteria']}"
                )
                if not passed or args.fake:
                    rme.write_pilot_summary(results_dir)
                    if args.fake:
                        print("Dry-Run — keine Kalibrierungsaussage.")
                        return 0
                    print(
                        "KALIBRIERUNG NICHT BESTANDEN — STOPP (nur "
                        "technischer Bericht; kein Blind-Pack)."
                    )
                    return 2
                # Owner Block 8: bei PASS ohne Rückfrage den Voll-Lauf fahren.
                print("Kalibrierung BESTANDEN — Voll-Lauf startet.")
                written = rme.execute_pilot_run(
                    SessionLocal, fake=args.fake, allow_holdout=True,
                    results_dir=results_dir,
                )
                print(f"pilot run (voll): {len(written)} neue Sample(s).")
                blind_dir = rme.build_pilot_blind_pack(results_dir=results_dir)
                print(f"Neuer Blind-Pack: {blind_dir}")
                print(
                    "ZWINGENDER STOPP: Owner scort die Bögen; keine "
                    "Auto-Scores, keine Modellwahl, keine Registry-Änderung."
                )
            else:
                written = rme.execute_pilot_run(
                    SessionLocal, fake=args.fake,
                    allow_holdout=args.allow_holdout, results_dir=results_dir,
                )
                print(f"pilot run: {len(written)} neue Sample(s).")
        except rme.EvalRefusal as exc:
            print(f"pilot {args.phase}: verweigert — {exc}", file=sys.stderr)
            rme.write_pilot_summary(results_dir)
            return 2
        except Exception as exc:  # Ausfall berichten, nie verschweigen
            print(f"pilot {args.phase}: fehlgeschlagen — {exc}", file=sys.stderr)
            rme.write_pilot_summary(results_dir)
            return 2
        json_path, md_path = rme.write_pilot_summary(results_dir)
        print(f"Pilot-Summary aktualisiert: {md_path}")
        return 0

    if args.phase == "blind":
        try:
            blind_dir = rme.build_pilot_blind_pack(results_dir=results_dir)
        except rme.EvalRefusal as exc:
            print(f"pilot blind: {exc}", file=sys.stderr)
            return 2
        print(
            f"Pilot-Blind-Pack erzeugt: {blind_dir}\n"
            "Bewertung: pilot_scoring_sheet.csv ausfüllen (1–5 je Kriterium, "
            "leere Zellen erlaubt, review_time_min, rework_needed), dann "
            "`pilot --phase ingest --scores <csv>`. mapping.json NICHT öffnen, "
            "solange blind bewertet wird."
        )
        return 0

    if args.phase == "ingest":
        if not args.scores or not args.role:
            print("pilot ingest: --role a2|a3 und --scores <csv> nötig.",
                  file=sys.stderr)
            return 2
        try:
            out_path = rme.ingest_pilot_scores(
                args.role, Path(args.scores), results_dir=results_dir
            )
        except rme.EvalRefusal as exc:
            print(f"pilot ingest: {exc}", file=sys.stderr)
            return 2
        json_path, md_path = rme.write_pilot_summary(results_dir)
        print(f"Pilot-Human-Scores übernommen: {out_path}")
        print(f"Pilot-Summary aktualisiert: {md_path}")
        return 0

    # report
    json_path, md_path = rme.write_pilot_summary(results_dir)
    print(f"Pilot-Summary aktualisiert: {json_path} / {md_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)

    # JEDE call-ausführende Phase braucht die frische Temp-DB (ein fehlender
    # Eintrag liess einen Lauf gegen die Entwickler-DB laufen).
    needs_db = args.command == "run" or (
        args.command == "pilot"
        and args.phase in ("smoke", "so_smoke", "rescore", "calibrate", "run")
    )
    if needs_db:
        # Frische Temp-SQLite je Prozess (nie unter OneDrive — Locking) und
        # Live-Routing-Env VOR den App-Imports setzen.
        db_path = Path(tempfile.gettempdir()) / f"role_model_eval_{uuid.uuid4().hex[:8]}.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ.setdefault("APP_ENV", "development")
        if args.fake:
            # Dry-Run erzwingt denselben Live-Routing-Pfad (role_routes) —
            # ohne Keys, ohne Kosten; Samples sind als fake_dryrun markiert.
            os.environ["AI_EVAL_MODE"] = "real"
            os.environ["AGENT_FAKE_PROVIDER"] = "false"

    from app.evaluation import role_model_eval as rme  # noqa: E402

    results_dir = (
        Path(getattr(args, "results_dir", None))
        if getattr(args, "results_dir", None)
        else (
            rme.default_pilot_results_dir()
            if args.command == "pilot"
            else rme.default_results_dir()
        )
    )

    if args.command == "pilot":
        return _run_pilot(args, rme, results_dir)

    if args.command == "run":
        from app.db.base import Base
        from app.db.session import SessionLocal, engine

        Base.metadata.create_all(engine)
        candidates = tuple(
            args.candidates or rme.DEFAULT_CANDIDATES[args.role]
        )
        cases = tuple(c.strip() for c in args.cases.split(",") if c.strip())
        exit_code = 0
        for candidate in candidates:
            db = SessionLocal()
            try:
                written = rme.execute_run(
                    db, role=args.role, candidate_key=candidate, cases=cases,
                    reps=args.reps, fake=args.fake,
                    allow_holdout=args.allow_holdout, results_dir=results_dir,
                )
            except rme.EvalRefusal as exc:
                print(f"{candidate}: verweigert — {exc}", file=sys.stderr)
                exit_code = 2
                continue
            except Exception as exc:  # Ausfall berichten, nie verschweigen
                print(f"{candidate}: Lauf fehlgeschlagen — {exc}", file=sys.stderr)
                exit_code = 2
                continue
            finally:
                db.close()
            print(f"{candidate}: {len(written)} neue Sample(s) geschrieben.")
        json_path, md_path = rme.write_summary(results_dir)
        print(f"Summary aktualisiert: {md_path}")
        return exit_code

    if args.command == "blind":
        try:
            blind_dir = rme.build_blind_pack(args.role, results_dir=results_dir)
        except rme.EvalRefusal as exc:
            print(f"blind: {exc}", file=sys.stderr)
            return 2
        print(
            f"Blind-Pack erzeugt: {blind_dir}\n"
            "Bewertung: CSV-Bogen ausfüllen (1–5 je Kriterium, review_time_min, "
            "rework_needed), dann `ingest`. mapping.json NICHT öffnen, solange "
            "blind bewertet wird."
        )
        return 0

    if args.command == "ingest":
        try:
            out_path = rme.ingest_scores(
                args.role, Path(args.scores), results_dir=results_dir
            )
        except rme.EvalRefusal as exc:
            print(f"ingest: {exc}", file=sys.stderr)
            return 2
        json_path, md_path = rme.write_summary(results_dir)
        print(f"Human-Scores übernommen: {out_path}\nSummary aktualisiert: {md_path}")
        return 0

    # report
    json_path, md_path = rme.write_summary(results_dir)
    print(f"Summary aktualisiert: {json_path} / {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
