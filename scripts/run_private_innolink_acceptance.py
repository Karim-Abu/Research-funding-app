#!/usr/bin/env python
"""Private manuelle Akzeptanz — lokaler SEDATE-Fall (nie in CI, nie im Repo).

Prüft das GITIGNORIERTE echte Innolink-PDF (``private_inputs/``) gegen die
erwarteten strukturierten Werte — mit exakt derselben produktiven Pipeline
(``app.imports.mapping.map_document`` + Rule-Engine), ohne Datenbank und ohne
Server. Die Ausgabe enthält AUSSCHLIESSLICH Feldnamen, Zählwerte, Quoten und
Pass/Fail — niemals Antragstexte, Titel, Partnernamen oder andere PII.

Erwartete Werte (SEDATE-Profil, überschreibbar per CLI):
* Titel erkannt; Executive Summary leer;
* 3 Partner (1 Forschungs- + 2 Umsetzungspartner);
* 18 Monate Laufzeit;
* Umsetzungsbeitragsquote (Eigenleistung + Barbeitrag, wie im
  Budget-Precheck) 52.5 % ± 0.5, Barbeitragsquote ~6.5 % ± 0.5;
* Alt→Neu-Migration (IPR → 4.5.x, alt-4.5 → 4.6) vorhanden;
* kein falscher Pflichtblocker (leerer Independence-Kommentar bei bestätigten
  Antworten und 0 % Management dürfen keinen Blocker auslösen).

Aufruf:
    backend\\.venv\\Scripts\\python.exe scripts\\run_private_innolink_acceptance.py
    (optional: --pdf <Pfad>)

Exit-Code 0 = alle Checks PASS, 1 = mindestens ein FAIL.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

DEFAULT_PDF = (
    _ROOT / "private_inputs" / "not_commited"
    / "102.320 IP-ICT Innolink Application.pdf"
)


def main() -> int:
    # Windows-Konsole (cp1252) verträgt die Statuszeichen nicht — UTF-8 erzwingen.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--expected-duration", type=int, default=18)
    parser.add_argument("--expected-research-partners", type=int, default=1)
    parser.add_argument("--expected-implementation-partners", type=int, default=2)
    parser.add_argument("--expected-implementation-share", type=float, default=52.5)
    parser.add_argument("--expected-cash-share", type=float, default=6.5)
    parser.add_argument("--share-tolerance", type=float, default=0.5)
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"FEHLER: PDF nicht gefunden: {args.pdf}")
        print("Hinweis: private_inputs/ ist gitignored — Datei lokal ablegen.")
        return 1

    from app.imports.mapping import (
        LEGACY_SCHEMA_MIGRATION_VERSION,
        map_document,
    )
    from app.registry import get_registry
    from app.rules.engine import evaluate_rule
    from app.rules.inputs import inputs_from_snapshot

    result = map_document("pdf", args.pdf.read_bytes())
    fields = {f.field_id: f for f in result.fields}
    by_target = {c.target_key: c for c in result.structured_candidates}

    checks: list[tuple[str, str, str, bool]] = []

    def check(name: str, expected: str, observed: str, passed: bool) -> None:
        checks.append((name, expected, observed, passed))

    # 1. Titel erkannt (nur ja/nein — nie der Titeltext).
    title = fields.get("INTRO.APP.NAME")
    check(
        "Titel erkannt (INTRO.APP.NAME)", "ja",
        "ja" if title is not None and title.extracted_text.strip() else "nein",
        title is not None and bool(title.extracted_text.strip()),
    )

    # 2. Executive Summary leer.
    summary = fields.get("INTRO.APP.EXECUTIVE_SUMMARY")
    summary_status = summary.mapping_status if summary else "nicht gefunden"
    check(
        "Executive Summary (INTRO.APP.EXECUTIVE_SUMMARY)", "empty",
        summary_status, summary_status == "empty",
    )

    # 3. Partneranzahl nach Typ.
    partners = [
        c for c in result.structured_candidates if c.candidate_kind == "partner"
    ]
    research = [
        c for c in partners
        if c.payload_json.get("partner_type") == "research_partner"
    ]
    implementation = [
        c for c in partners
        if c.payload_json.get("partner_type") == "implementation_partner"
    ]
    expected_total = (
        args.expected_research_partners + args.expected_implementation_partners
    )
    check(
        "Partner gesamt", str(expected_total), str(len(partners)),
        len(partners) == expected_total,
    )
    check(
        "Forschungspartner", str(args.expected_research_partners),
        str(len(research)), len(research) == args.expected_research_partners,
    )
    check(
        "Umsetzungspartner", str(args.expected_implementation_partners),
        str(len(implementation)),
        len(implementation) == args.expected_implementation_partners,
    )

    # 4. Projektdauer.
    duration_candidate = by_target.get("project.duration_months")
    duration = (
        duration_candidate.payload_json.get("duration_months")
        if duration_candidate else None
    )
    check(
        "Projektdauer (Monate)", str(args.expected_duration), str(duration),
        duration == args.expected_duration,
    )

    # 5. Budgetquoten — dieselbe _share-Semantik wie der Budget-Precheck.
    def amount(target_key: str) -> float | None:
        candidate = by_target.get(target_key)
        if candidate is None:
            return None
        value = candidate.payload_json.get(target_key.removeprefix("project."))
        return float(value) if isinstance(value, (int, float)) else None

    direct = amount("project.direct_total_project_costs_excluding_overhead")
    own = amount("project.implementation_own_contribution")
    cash = amount("project.cash_contribution")

    def share(numerator: float | None) -> float | None:
        if numerator is None or not direct:
            return None
        return round(numerator / direct * 100, 2)

    # Umsetzungsbeitrag = Eigenleistung + Barbeitrag (Identität wie im
    # Budget-Precheck: implementation_share_percent).
    implementation = own + cash if own is not None and cash is not None else None
    implementation_share, cash_share = share(implementation), share(cash)

    def within(observed: float | None, expected: float) -> bool:
        return observed is not None and abs(observed - expected) <= args.share_tolerance

    check(
        "Umsetzungsbeitragsquote (own+cash, %)",
        f"{args.expected_implementation_share} ± {args.share_tolerance}",
        str(implementation_share),
        within(implementation_share, args.expected_implementation_share),
    )
    check(
        "Barbeitragsquote (%)",
        f"~{args.expected_cash_share} ± {args.share_tolerance}",
        str(cash_share), within(cash_share, args.expected_cash_share),
    )

    # 6. Alt→Neu-Migration (IPR → 4.5.x, alt-4.5 → 4.6).
    migrated_targets = {
        "/".join(section.target_sections)
        for f in result.fields
        for section in f.sections
        if section.migration_version == LEGACY_SCHEMA_MIGRATION_VERSION
    }
    has_ipr = any(target.startswith("4.5") for target in migrated_targets)
    has_46 = "4.6" in migrated_targets
    check(
        "Alt→Neu-Migration (IPR → 4.5.x)", "vorhanden",
        f"{sorted(migrated_targets)}" if migrated_targets else "keine",
        has_ipr,
    )
    check(
        "Alt→Neu-Migration (alt-4.5 → 4.6)", "vorhanden",
        "ja" if has_46 else "nein", has_46,
    )

    # 7. Kein falscher Pflichtblocker — Rule-Engine über den simuliert
    # akzeptierten strukturierten Werten (wie nach HITL-Übernahme).
    project_dict: dict = {}
    for candidate in result.structured_candidates:
        if candidate.candidate_kind in ("project_metadata", "budget"):
            for key, value in candidate.payload_json.items():
                if key != "raw_value":
                    project_dict[key] = value
    answers: dict = {}
    scientific = by_target.get("answer.scientific_integrity")
    if scientific is not None:
        answers["scientific_integrity"] = dict(scientific.payload_json)
    management = by_target.get("answer.management_hours")
    if management is not None:
        answers["management_hours"] = dict(management.payload_json)
    project_dict["structured_answers"] = answers
    partner_dicts = [dict(candidate.payload_json) for candidate in partners]

    registry = get_registry()
    inputs = inputs_from_snapshot(
        profile_id=None, partner_dicts=partner_dicts, project_dict=project_dict
    )
    blocker_failures = []
    for rule in registry.rules.values():
        outcome = evaluate_rule(
            rule, inputs, rule_version=registry.rule_registry_version
        )
        if outcome.severity == "blocker" and outcome.status == "failed":
            blocker_failures.append(rule.rule_id)
    check(
        "Pflichtblocker aus Regelkern", "0",
        f"{len(blocker_failures)}"
        + (f" ({', '.join(sorted(blocker_failures))})" if blocker_failures else ""),
        not blocker_failures,
    )
    management_hours = (management.payload_json.get("management_hours")
                        if management is not None else None)
    check(
        "Management-Stunden erkannt (0 erlaubt, kein Blocker)",
        "erkannt", "erkannt" if management is not None else "nicht erkannt",
        management is not None,
    )
    print(
        f"Hinweis: Management-Stunden = {management_hours}; "
        f"needs_input-Ergebnisse sind ehrliche offene Punkte, keine Blocker."
    )

    # --- Bericht (nur Feldnamen, Zählwerte, Pass/Fail) -----------------------
    width = max(len(name) for name, *_ in checks)
    print()
    print(f"{'Check':{width}} | Erwartet | Beobachtet | Ergebnis")
    print("-" * (width + 40))
    failures = 0
    for name, expected, observed, passed in checks:
        status = "PASS" if passed else "FAIL"
        failures += 0 if passed else 1
        print(f"{name:{width}} | {expected} | {observed} | {status}")
    print()
    print(
        f"Gesamt: {len(checks) - failures}/{len(checks)} PASS"
        + (f" — {failures} FAIL" if failures else "")
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
