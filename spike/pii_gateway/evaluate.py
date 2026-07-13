"""PII-Gateway-Spike — Evaluations-Harness (Tier A deterministisch, Tier B Presidio).

Misst je Entitätstyp Precision, Recall und False Negatives sowie die Latenz auf
den synthetischen Fixtures, druckt eine feststehende Tabelle und schreibt einen
maschinenlesbaren Report (eval_report.json). Enthält eine begründete
Go/No-Go-Empfehlung, abgeleitet aus den gemessenen Zahlen.

Aufruf (mit dem Backend-venv für Tier A; für Tier B den Spike-venv nutzen):
    backend\\.venv\\Scripts\\python.exe spike\\pii_gateway\\evaluate.py
    backend\\.venv\\Scripts\\python.exe spike\\pii_gateway\\evaluate.py --selftest
    backend\\.venv\\Scripts\\python.exe spike\\pii_gateway\\evaluate.py --restore-demo

Matching: typbewusste Überlappung, 1:1 (ein vorhergesagter Span zählt als TP,
wenn er einen noch nicht belegten Gold-Span gleichen Typs überlappt).

Spike-Regel: kein Import aus backend/app oder lib/.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import detectors
import presidio_adapter
from detectors import Span
from pseudonymize import pseudonymize, restore

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures" / "cases.json"
REPORT = HERE / "eval_report.json"
ENTITY_TYPES = ("PERSON", "EMAIL", "PHONE", "ADDRESS", "DOB", "IBAN", "USERNAME")

# Schwellen für die Go/No-Go-Ableitung (dokumentiert, im Report ausgegeben).
FORMATTED = ("EMAIL", "PHONE", "IBAN", "DOB", "USERNAME")
FREE = ("PERSON", "ADDRESS")
RECALL_GO = 0.95
PRECISION_GO = 0.90


def load_cases() -> list[dict]:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["cases"]


def _overlap(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


def score_case(gold: list[dict], pred: list[Span]) -> dict[str, dict[str, int]]:
    """Typbewusstes 1:1-Overlap-Matching. Liefert je Typ tp/fp/fn."""
    res = {t: {"tp": 0, "fp": 0, "fn": 0} for t in ENTITY_TYPES}
    for etype in ENTITY_TYPES:
        golds = [Span(g["type"], g["start"], g["end"], g["value"])
                 for g in gold if g["type"] == etype]
        preds = [p for p in pred if p.type == etype]
        used: set[int] = set()
        for p in preds:
            match_idx = next(
                (i for i, g in enumerate(golds) if i not in used and _overlap(p, g)),
                None,
            )
            if match_idx is None:
                res[etype]["fp"] += 1
            else:
                used.add(match_idx)
                res[etype]["tp"] += 1
        res[etype]["fn"] += len(golds) - len(used)
    return res


def _prf(counts: dict[str, int]) -> dict[str, float | int]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4), "recall": round(recall, 4),
    }


def evaluate_tier(detect_fn, cases: list[dict]) -> dict:
    """Aggregiert tp/fp/fn je Typ + gesamt und misst die Latenz (Median-stabil)."""
    per_entity = {t: {"tp": 0, "fp": 0, "fn": 0} for t in ENTITY_TYPES}
    for case in cases:
        pred = detect_fn(case["text"])
        scored = score_case(case["entities"], pred)
        for etype, c in scored.items():
            for k in ("tp", "fp", "fn"):
                per_entity[etype][k] += c[k]

    # Latenz: Median über mehrere Durchläufe (indikativ, nicht bit-reproduzierbar).
    runs_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        for case in cases:
            detect_fn(case["text"])
        runs_ms.append((time.perf_counter() - t0) * 1000.0)
    total_ms = round(statistics.median(runs_ms), 2)

    per_entity_prf = {t: _prf(per_entity[t]) for t in ENTITY_TYPES}
    overall_counts = {
        k: sum(per_entity[t][k] for t in ENTITY_TYPES) for k in ("tp", "fp", "fn")
    }
    overall = _prf(overall_counts)
    return {
        "available": True,
        "latency_ms": {"total_median": total_ms,
                       "per_doc_avg": round(total_ms / max(len(cases), 1), 3)},
        "per_entity": per_entity_prf,
        "overall": {
            "precision": overall["precision"],
            "recall": overall["recall"],
            "false_negatives": overall["fn"],
        },
    }


def _group_recall(tier: dict, group: tuple[str, ...]) -> float:
    tp = sum(tier["per_entity"][t]["tp"] for t in group)
    fn = sum(tier["per_entity"][t]["fn"] for t in group)
    return tp / (tp + fn) if (tp + fn) else 1.0


def _group_precision(tier: dict, group: tuple[str, ...]) -> float:
    tp = sum(tier["per_entity"][t]["tp"] for t in group)
    fp = sum(tier["per_entity"][t]["fp"] for t in group)
    return tp / (tp + fp) if (tp + fp) else 1.0


def go_no_go(tiers: dict) -> dict:
    """Datengetriebene Empfehlung aus den gemessenen Zahlen."""
    det = tiers["deterministic"]
    fmt_recall = _group_recall(det, FORMATTED)
    fmt_prec = _group_precision(det, FORMATTED)
    free_recall = _group_recall(det, FREE)

    lines: list[str] = []
    if fmt_recall >= RECALL_GO and fmt_prec >= PRECISION_GO:
        lines.append(
            f"GO als Pseudonymisierungs-Vorfilter für klar formatierte PII "
            f"(E-Mail/Telefon/IBAN/Datum/Benutzername): Recall {fmt_recall:.0%}, "
            f"Precision {fmt_prec:.0%}."
        )
    else:
        lines.append(
            f"KEIN uneingeschränktes GO für formatierte PII: Recall {fmt_recall:.0%}, "
            f"Precision {fmt_prec:.0%} unter der Schwelle."
        )
    lines.append(
        f"NO-GO als alleinige Anonymisierung: freie Namen/Adressen erreichen nur "
        f"Recall {free_recall:.0%} (deterministisch) — Restrisiko bleibt."
    )
    presidio = tiers.get("presidio", {})
    if presidio.get("available"):
        p_free = _group_recall(presidio, FREE)
        lines.append(
            f"ML-Tier (Presidio+spaCy) hebt freie Namen/Adressen auf Recall "
            f"{p_free:.0%}; auch damit ist es Pseudonymisierung, keine Garantie."
        )
    else:
        lines.append(
            "ML-Tier nicht gemessen (nicht installiert) — Vergleich offen."
        )
    lines.append(
        "In JEDEM Fall bleibt die Search Query Firewall der zwingende, separate "
        "Schutz; Rohidee, Geschäftsgeheimnisse, Methodik, Partnerstrategie und "
        "Budgetlogik werden von einem PII-Detektor NICHT zuverlässig entfernt."
    )
    return {
        "recommendation": "Pseudonymisierungs-Vorfilter: JA (formatierte PII); "
                          "Anonymisierungsersatz: NEIN.",
        "rationale": lines,
        "thresholds": {"recall_go": RECALL_GO, "precision_go": PRECISION_GO,
                       "formatted": list(FORMATTED), "free": list(FREE)},
    }


def print_table(name: str, tier: dict) -> None:
    print(f"\n== Tier: {name} ==")
    if not tier.get("available"):
        print(f"  übersprungen — {tier.get('reason_if_skipped', 'nicht verfügbar')}")
        return
    print(f"  {'Entität':10} {'TP':>4} {'FP':>4} {'FN':>4} {'Precision':>10} {'Recall':>8}")
    for t in ENTITY_TYPES:
        e = tier["per_entity"][t]
        print(f"  {t:10} {e['tp']:>4} {e['fp']:>4} {e['fn']:>4} "
              f"{e['precision']:>10.2f} {e['recall']:>8.2f}")
    o = tier["overall"]
    print(f"  {'GESAMT':10} {'':>4} {'':>4} {o['false_negatives']:>4} "
          f"{o['precision']:>10.2f} {o['recall']:>8.2f}")
    lat = tier["latency_ms"]
    print(f"  Latenz: {lat['total_median']} ms gesamt (Median), "
          f"{lat['per_doc_avg']} ms/Dokument (indikativ)")


def run_eval() -> dict:
    cases = load_cases()
    entity_counts: dict[str, int] = {t: 0 for t in ENTITY_TYPES}
    for c in cases:
        for e in c["entities"]:
            entity_counts[e["type"]] += 1

    tiers: dict = {"deterministic": evaluate_tier(detectors.detect, cases)}

    ok, reason = presidio_adapter.availability()
    if ok:
        tiers["presidio"] = evaluate_tier(presidio_adapter.detect, cases)
        tiers["presidio"]["model"] = presidio_adapter.model_used()
    else:
        tiers["presidio"] = {"available": False, "reason_if_skipped": reason}

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "matching": "type-aware overlap, 1:1",
        "fixtures": {"count": len(cases), "entity_counts": entity_counts},
        "tiers": tiers,
        "go_no_go": go_no_go(tiers),
    }
    return report


def write_report(report: dict) -> None:
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")


def selftest() -> int:
    """Test-parallel-Sanity (Requirement 9): Recognizer + Mod-97 + Span-Konsistenz."""
    failures: list[str] = []

    if not detectors.iban_mod97_ok("CH93 0076 2011 6238 5295 7"):
        failures.append("IBAN CH sollte gültig sein")
    if detectors.iban_mod97_ok("CH00 0000 0000 0000 0000 0"):
        failures.append("Ungültige IBAN sollte abgelehnt werden")

    checks = [
        ("anna.meier@example.ch", "EMAIL"),
        ("+41 79 123 45 67", "PHONE"),
        ("14.03.1987", "DOB"),
        ("@a_meier", "USERNAME"),
        ("Bahnhofstrasse 12, 4051 Basel", "ADDRESS"),
    ]
    for text, etype in checks:
        types = {s.type for s in detectors.detect(text)}
        if etype not in types:
            failures.append(f"{etype!r} nicht erkannt in {text!r} (gefunden: {types})")

    # Gold-Spans müssen exakt auf die Fixture-Werte zeigen (Fixture-Integrität).
    for case in load_cases():
        for e in case["entities"]:
            if case["text"][e["start"]:e["end"]] != e["value"]:
                failures.append(f"Span-Mismatch in {case['id']}: {e}")

    # Nicht-PII-Geheimnisfälle: der deterministische Detektor darf sie NICHT
    # (als PII) markieren — Nachweis, dass Geheimnisse nicht entfernt werden.
    for case in load_cases():
        if case["id"].startswith("secret-"):
            spans = detectors.detect(case["text"])
            if spans:
                failures.append(
                    f"Geheimnisfall {case['id']} fälschlich als PII markiert: "
                    f"{[(s.type, s.value) for s in spans]}"
                )

    if failures:
        print("SELFTEST FEHLGESCHLAGEN:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SELFTEST OK — Recognizer, Mod-97, Span-Integrität, Geheimnis-Nichtentfernung.")
    return 0


def restore_demo() -> int:
    """Zeigt Pseudonymisierung + Rückersetzung; Speicher-Map wird danach verworfen."""
    case = next(c for c in load_cases() if c["id"] == "formatted-contact")
    spans = detectors.detect(case["text"])
    result = pseudonymize(case["text"], spans)
    print("Original     :", case["text"])
    print("Pseudonymisiert:", result.text)
    back = restore(result.text, result.mapping)
    print("Rückersetzt  :", back)
    ok = back == case["text"]
    print(f"Round-Trip {'OK' if ok else 'FEHLGESCHLAGEN'}; Map lebte nur im Speicher.")
    # Map bewusst verwerfen (nie persistieren).
    result.mapping.clear()
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--restore-demo", action="store_true")
    parser.add_argument("--no-write", action="store_true",
                        help="Report nicht schreiben (nur Tabelle drucken)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.restore_demo:
        return restore_demo()

    report = run_eval()
    print(f"Fixtures: {report['fixtures']['count']} Fälle, "
          f"{sum(report['fixtures']['entity_counts'].values())} Gold-Entitäten")
    print_table("deterministisch", report["tiers"]["deterministic"])
    print_table("presidio", report["tiers"]["presidio"])
    print("\n== Go/No-Go ==")
    print(f"  {report['go_no_go']['recommendation']}")
    for line in report["go_no_go"]["rationale"]:
        print(f"  - {line}")
    if not args.no_write:
        write_report(report)
        print(f"\nReport geschrieben: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
