"""R0.4 — Testdaten-CI-Marker-Check.

Durchsucht die Fixture-Verzeichnisse nach sensiblen Markern aus
docs/evaluation/testdata-policy.md (Abschnitt "Sensible Marker").
Treffer ausserhalb der Allowlist => Exit 1 (CI rot).
Leerer Markerkatalog => Exit 0 (gruen).
Fehlende/kaputte Policy-Bloecke => Exit 2 (fail-closed).

Nur Standardbibliothek; laeuft offline und ohne Provider.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

POLICY_DEFAULT = "docs/evaluation/testdata-policy.md"
SCAN_DIRS_DEFAULT = (
    "spike/fixtures",
    "backend/tests/reliability_fixtures",
    "docs/evaluation/cases",
)
MARKER_BLOCK = ("<!-- marker-katalog:start -->", "<!-- marker-katalog:end -->")
ALLOW_BLOCK = ("<!-- marker-allowlist:start -->", "<!-- marker-allowlist:end -->")


class PolicyError(Exception):
    """Policy-Datei fehlt oder ein Pflichtblock ist nicht auffindbar."""


def _extract_block(text: str, begin: str, end: str) -> list[str]:
    try:
        start = text.index(begin) + len(begin)
        stop = text.index(end, start)
    except ValueError as exc:
        raise PolicyError(f"Block {begin!r}..{end!r} nicht gefunden") from exc
    lines: list[str] = []
    for raw in text[start:stop].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        lines.append(line)
    return lines


def parse_policy(text: str) -> tuple[list[str], dict[str, str], list[str]]:
    """Liefert (marker, allowlist{pfad: begruendung}, fehlerliste)."""
    markers = _extract_block(text, *MARKER_BLOCK)
    errors: list[str] = []
    allowlist: dict[str, str] = {}
    for entry in _extract_block(text, *ALLOW_BLOCK):
        path, sep, reason = entry.partition("::")
        path, reason = path.strip(), reason.strip()
        if not sep or not reason or not path:
            errors.append(
                f"Allowlist-Eintrag ohne Begruendung (Format 'pfad :: Grund'): {entry!r}"
            )
            continue
        allowlist[Path(path).as_posix()] = reason
    return markers, allowlist, errors


def scan(
    root: Path,
    scan_dirs: tuple[str, ...],
    markers: list[str],
    allowlist: dict[str, str],
) -> list[str]:
    """Liefert Trefferliste 'datei: marker'. Case-insensitive Byte-Suche."""
    hits: list[str] = []
    needles = [m.lower().encode("utf-8") for m in markers]
    if not needles:
        return hits
    for rel_dir in scan_dirs:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for file in sorted(p for p in base.rglob("*") if p.is_file()):
            rel = file.relative_to(root).as_posix()
            if rel in allowlist:
                continue
            data = file.read_bytes().lower()
            for marker, needle in zip(markers, needles):
                if needle in data:
                    hits.append(f"{rel}: enthaelt Marker {marker!r}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repo-Wurzel")
    parser.add_argument("--policy", default=POLICY_DEFAULT)
    parser.add_argument(
        "--scan-dir",
        action="append",
        dest="scan_dirs",
        help="Zu durchsuchendes Verzeichnis (mehrfach; Default: Fixture-Ordner)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    policy_file = root / args.policy
    if not policy_file.is_file():
        print(f"FEHLER: Policy-Datei fehlt: {policy_file}", file=sys.stderr)
        return 2
    try:
        markers, allowlist, errors = parse_policy(
            policy_file.read_text(encoding="utf-8")
        )
    except PolicyError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2

    for problem in errors:
        print(f"FEHLER: {problem}", file=sys.stderr)
    if errors:
        return 1

    scan_dirs = tuple(args.scan_dirs) if args.scan_dirs else SCAN_DIRS_DEFAULT
    hits = scan(root, scan_dirs, markers, allowlist)
    for hit in hits:
        print(f"TREFFER: {hit}", file=sys.stderr)
    if hits:
        return 1

    print(
        f"testdata-marker-check: OK ({len(markers)} Marker, "
        f"{len(allowlist)} Allowlist-Eintraege, Verzeichnisse: {', '.join(scan_dirs)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
