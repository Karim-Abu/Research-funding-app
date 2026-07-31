"""EVALUATION-ONLY: Requirement -> Regel -> Test Coverage-Join.

NEU ERSTELLT fuer den EVAL2/EVAL3-Lauf (2026-07-25). Aendert KEINE Runtime-Logik,
importiert die App nicht und schreibt nur nach docs/evaluation/generated/.

Was das Skript tut:
  1. liest die Requirement-Registry (76 Requirements),
  2. liest die Rule-Registry und bestimmt, welche Regeln der Loader tatsaechlich
     auswertet (nur `official_core_rules`),
  3. sucht in den Testbaeumen nach Requirement- und Rule-IDs,
  4. schreibt requirement_coverage.json + eine Markdown-Tabelle.

Bewusst KEINE Bewertung der Testqualitaet - nur Vorhandensein einer Referenz.
Ein Treffer heisst "es gibt einen Test, der diese ID nennt", nicht "die
Anforderung ist korrekt geprueft".

Aufruf (aus dem Repo-Root):
    backend/.venv/Scripts/python.exe scripts/evaluation/requirement_coverage.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "final_backend_contracts_v1_1"
REQ_YAML = CONTRACTS / "requirements.yaml"
RULE_YAML = CONTRACTS / "innosuisse_innovation_project_v1_1.yaml"
OUT_DIR = ROOT / "docs" / "evaluation" / "generated"

TEST_TREES = [
    ROOT / "backend" / "tests",
    ROOT / "test",
    ROOT / "e2e",
]
CODE_TREES = [
    ROOT / "backend" / "app",
    ROOT / "lib",
    ROOT / "components",
]


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _collect_text(trees: list[Path]) -> dict[Path, str]:
    """Alle Text-Dateien der Baeume einlesen (einmal, dann in-memory suchen)."""
    out: dict[Path, str] = {}
    suffixes = {".py", ".ts", ".tsx", ".json", ".yaml", ".yml"}
    for tree in trees:
        if not tree.exists():
            continue
        for path in tree.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            try:
                out[path] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return out


def _hits(needles: list[str], corpus: dict[Path, str]) -> list[str]:
    """Repo-relative Pfade, die eine der IDs woertlich nennen."""
    found: list[str] = []
    for path, text in corpus.items():
        if any(n and n in text for n in needles):
            found.append(path.relative_to(ROOT).as_posix())
    return sorted(found)


def main() -> int:
    reqs = _load(REQ_YAML)["requirements"]
    rules_doc = _load(RULE_YAML)

    # Nur diese Regeln wertet backend/app/registry/loader.py aus.
    core_rules = rules_doc.get("official_core_rules", []) or []
    evaluated_rule_ids = {r["rule_id"] for r in core_rules}

    # Die Rule-Engine dispatcht ueber ``condition.type`` (app/rules/engine.py:90),
    # NICHT ueber die rule_id. Eine fehlende ID-Nennung im Code ist deshalb kein
    # Implementierungsmangel. Der belastbare Implementierungstest ist: existiert
    # fuer den condition.type ein Handler in app/rules/handlers.py::HANDLERS?
    handlers_src = (ROOT / "backend" / "app" / "rules" / "handlers.py").read_text(
        encoding="utf-8"
    )
    handler_block = handlers_src.split("HANDLERS = {", 1)[-1]
    known_condition_types = set(re.findall(r'"([a-z0-9_]+)"\s*:', handler_block))
    rule_condition_type = {
        r["rule_id"]: (r.get("condition") or {}).get("type") for r in core_rules
    }
    quality_gate_ids = {
        r["rule_id"] for r in rules_doc.get("portal_quality_gates", []) or []
    }
    cross_field_ids = {
        r["rule_id"] for r in rules_doc.get("cross_field_rules", []) or []
    }

    test_corpus = _collect_text(TEST_TREES)
    code_corpus = _collect_text(CODE_TREES)

    rows = []
    for req in reqs:
        rid = req["requirement_id"]
        linked = list(req.get("linked_rule_ids") or [])
        gates = list(req.get("linked_quality_gate_ids") or [])
        needles = [rid, *linked, *gates]

        test_paths = _hits(needles, test_corpus)
        code_paths = _hits(needles, code_corpus)
        evaluated_rules = sorted(set(linked) & evaluated_rule_ids)
        evaluable = bool(evaluated_rules)

        # Implementiert = Regel wird geladen UND ihr condition.type hat einen
        # Handler. Das ist der echte Nachweis, nicht die ID-Nennung im Code.
        cond_types = [rule_condition_type.get(r) for r in evaluated_rules]
        handled = bool(cond_types) and all(
            ct in known_condition_types for ct in cond_types if ct
        )

        if evaluable and handled and test_paths:
            status = "implemented-and-tested"
        elif evaluable and handled:
            status = "implemented-not-tested"
        elif evaluable:
            status = "rule-loaded-no-handler"
        else:
            status = "contract-only"

        rows.append(
            {
                "requirement_id": rid,
                "title": req.get("title", ""),
                "category": req.get("category", ""),
                "type": req.get("type", ""),
                "assessment_basis": req.get("assessment_basis", ""),
                "severity": req.get("severity", ""),
                "status_field": req.get("status", ""),
                "user_facing": req.get("user_facing"),
                "linked_rule_ids": linked,
                "linked_quality_gate_ids": gates,
                "affected_field_ids": list(req.get("affected_field_ids") or []),
                "rule_is_evaluated_by_loader": evaluable,
                "condition_types": [ct for ct in cond_types if ct],
                "condition_handler_exists": handled,
                "code_paths": code_paths[:6],
                "code_path_count": len(code_paths),
                "test_paths": test_paths[:6],
                "test_path_count": len(test_paths),
                "coverage_status": status,
            }
        )

    summary = {
        "generated_from": "scripts/evaluation/requirement_coverage.py",
        "requirement_count": len(rows),
        "severity_distribution": dict(Counter(r["severity"] for r in rows)),
        "type_distribution": dict(Counter(r["type"] for r in rows)),
        "status_field_distribution": dict(Counter(r["status_field"] for r in rows)),
        "coverage_status_distribution": dict(
            Counter(r["coverage_status"] for r in rows)
        ),
        "official_core_rules_evaluated": len(evaluated_rule_ids),
        "portal_quality_gates_defined": len(quality_gate_ids),
        "cross_field_rules_defined": len(cross_field_ids),
        "evaluable_requirements": sum(
            1 for r in rows if r["rule_is_evaluated_by_loader"]
        ),
        "requirements_with_test_reference": sum(
            1 for r in rows if r["test_path_count"] > 0
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "requirement_coverage.json").write_text(
        json.dumps({"summary": summary, "requirements": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(rows, summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _write_markdown(rows: list[dict], summary: dict) -> None:
    """Tabelle direkt aus den Daten erzeugen - keine Abschrift von Hand."""
    ev = [r for r in rows if r["rule_is_evaluated_by_loader"]]
    co = [r for r in rows if not r["rule_is_evaluated_by_loader"]]
    n_all, n_ev = len(rows), len(ev)
    impl = sum(1 for r in rows if r["coverage_status"].startswith("implemented"))
    tested = sum(1 for r in rows if r["coverage_status"] == "implemented-and-tested")

    def pct(a: int, b: int) -> str:
        return f"{a}/{b} = {100.0 * a / b:.1f} %" if b else "n/a"

    def row_line(r: dict) -> str:
        tests = ", ".join(f"`{p}`" for p in r["test_paths"][:3]) or "—"
        if r["test_path_count"] > 3:
            tests += f" (+{r['test_path_count'] - 3})"
        rules = ", ".join(f"`{x}`" for x in r["linked_rule_ids"]) or "—"
        return (
            f"| `{r['requirement_id']}` | {r['title']} | {r['severity']} | "
            f"{rules} | {tests} | {r['coverage_status']} |"
        )

    head = (
        "| Requirement ID | Titel | Priorität | Verknüpfte Regel | "
        "Testreferenz | Coverage-Status |\n|---|---|---|---|---|---|"
    )
    lines = [
        "---",
        'title: "EVAL3 — Requirement Coverage"',
        "date: 2026-07-25",
        "commit: 8416914",
        "status: generated",
        "tags: [eval3, coverage, requirements]",
        "---",
        "",
        "# EVAL3 — Requirement Coverage",
        "",
        "> Erzeugt von `scripts/evaluation/requirement_coverage.py` "
        "(evaluation-only, neu für diesen Lauf). Rohdaten: "
        "`requirement_coverage.json`. Siehe [[EVAL3_TECHNICAL_VERIFICATION]] "
        "und [[EVALUATION_BASELINE]].",
        "",
        "## Kennzahlen",
        "",
        f"- Requirements gesamt: **{n_all}** (alle `status: active`)",
        f"- Severity: blocker **{summary['severity_distribution'].get('blocker', 0)}**, "
        f"warning **{summary['severity_distribution'].get('warning', 0)}**, "
        f"info **{summary['severity_distribution'].get('info', 0)}**",
        f"- Vom Loader ausgewertet (`official_core_rules`): **{n_ev}**",
        f"- Nur im Contract (`QG.*` nicht implementiert): **{len(co)}**",
        "",
        "| Kennzahl | gegen alle Requirements | gegen die auswertbaren |",
        "|---|---|---|",
        f"| Implementation Coverage | {pct(impl, n_all)} | {pct(impl, n_ev)} |",
        f"| Test Coverage | {pct(tested, n_all)} | {pct(tested, n_ev)} |",
        "",
        "**Nenner ausgewiesen, nichts stillschweigend entfernt.** «Test Coverage» "
        "heisst hier: mindestens eine Testdatei nennt die Requirement- oder "
        "Regel-ID wörtlich. Das belegt *Vorhandensein*, nicht fachliche "
        "Vollständigkeit der Prüfung.",
        "",
        f"## A. Auswertbare Requirements ({n_ev})",
        "",
        "Regel wird von `app/registry/loader.py` geladen und über "
        "`condition.type` in `app/rules/handlers.py::HANDLERS` dispatcht "
        "(`app/rules/engine.py:90`). Die Regel-ID steht bewusst **nicht** im "
        "Code — die Engine ist datengetrieben.",
        "",
        head,
    ]
    lines += [row_line(r) for r in ev]
    lines += [
        "",
        f"## B. Contract-only Requirements ({len(co)})",
        "",
        "Diese verweisen auf die 64 `QG.*`-Portal-Quality-Gates. `loader.py` "
        "parst ausschliesslich `official_core_rules`; `QG.` und `XF.` kommen im "
        "Code nicht vor. Sie sind **spezifiziert, aber nicht implementiert** — "
        "und werden hier namentlich geführt statt aus dem Nenner entfernt.",
        "",
        head,
    ]
    lines += [row_line(r) for r in co]
    lines.append("")
    (OUT_DIR / "EVAL3_REQUIREMENT_COVERAGE.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
