"""R1.4 — CI-Guard gegen neue Legacy-Statuspfade.

Zwei Pruefungen:

1. `isMock("legacy")` darf NUR in den dokumentierten Demo-only-Dateien
   vorkommen (Allowlist unten, begruendet im Inventar
   docs/repair/r1-legacy-mock-inventory.md). Jede neue Aufrufstelle in
   aktiven Komponenten/Libs => Exit 1 (CI rot).
2. Der R1.3-Status-Paritaetstest (e2e/status-parity.spec.ts) muss existieren
   und den Paritaets-Testfall enthalten — er ist dauerhaftes Merge-Gate;
   Loeschen/Aushoehlen => Exit 1.

Nur Standardbibliothek; laeuft offline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

NEEDLE = 'isMock("legacy")'
SCAN_DIRS = ("app", "components", "lib")

# Demo-only-Dateien mit begruendetem Bestand (R1.1-Inventar, Tabelle A).
# Neue Eintraege brauchen einen Inventar-Nachtrag mit Begruendung.
ALLOWLIST = {
    "lib/app-mode.ts",  # Definition von isMock selbst
    "lib/api.ts",  # permanente Mock-Pfade, Demo-only markiert (R1.3)
    "components/export/export-screen.tsx",  # Mock-Body des Export-Screens
}

PARITY_SPEC = "e2e/status-parity.spec.ts"
PARITY_MARKER = "R1 Parität"


def scan_legacy_calls(root: Path) -> list[str]:
    violations: list[str] = []
    for rel_dir in SCAN_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for file in sorted(base.rglob("*")):
            if file.suffix not in (".ts", ".tsx") or not file.is_file():
                continue
            rel = file.relative_to(root).as_posix()
            if rel in ALLOWLIST:
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if NEEDLE in line:
                    violations.append(
                        f"{rel}:{lineno}: {NEEDLE} ausserhalb der Allowlist"
                    )
    return violations


def check_parity_spec(root: Path) -> list[str]:
    spec = root / PARITY_SPEC
    if not spec.is_file():
        return [
            f"{PARITY_SPEC}: fehlt — der Status-Paritätstest ist dauerhaftes "
            "Merge-Gate (R1.3/R1.4) und darf nicht entfernt werden."
        ]
    text = spec.read_text(encoding="utf-8", errors="replace")
    if PARITY_MARKER not in text:
        return [
            f"{PARITY_SPEC}: Paritäts-Testfall ('{PARITY_MARKER}') nicht "
            "gefunden — Gate ausgehöhlt."
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repo-Wurzel")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    problems = scan_legacy_calls(root) + check_parity_spec(root)
    for problem in problems:
        print(f"VERSTOSS: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(
        "legacy-status-guard: OK "
        f"({len(ALLOWLIST)} Allowlist-Dateien, Paritätstest vorhanden)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
