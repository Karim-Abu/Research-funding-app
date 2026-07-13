"""R0.4 — Selbsttests fuer scripts/check_testdata_markers.py.

Leerer Markerkatalog => gruen; Testtreffer => rot; Allowlist nur mit
Begruendung; kaputte/fehlende Policy => fail-closed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_testdata_markers.py"

spec = importlib.util.spec_from_file_location("check_testdata_markers", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _write_policy(root: Path, markers: str = "", allow: str = "") -> None:
    policy = root / "docs" / "evaluation" / "testdata-policy.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        "# Testdata Policy (Testkopie)\n\n"
        f"<!-- marker-katalog:start -->\n{markers}\n<!-- marker-katalog:end -->\n"
        f"<!-- marker-allowlist:start -->\n{allow}\n<!-- marker-allowlist:end -->\n",
        encoding="utf-8",
    )


def _write_fixture(root: Path, name: str, content: str) -> None:
    fixture = root / "spike" / "fixtures" / name
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(content, encoding="utf-8")


def test_empty_catalog_is_green(tmp_path):
    _write_policy(tmp_path)
    _write_fixture(tmp_path, "sample.txt", "Irgendein synthetischer Inhalt")
    assert mod.main(["--root", str(tmp_path)]) == 0


def test_marker_hit_fails(tmp_path):
    _write_policy(tmp_path, markers="GeheimPartner AG")
    _write_fixture(tmp_path, "sample.txt", "Vertrag mit geheimpartner ag, Basel")
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_allowlisted_file_with_reason_passes(tmp_path):
    _write_policy(
        tmp_path,
        markers="GeheimPartner AG",
        allow="spike/fixtures/sample.txt :: dokumentiertes Negativ-Testfixture",
    )
    _write_fixture(tmp_path, "sample.txt", "GeheimPartner AG")
    assert mod.main(["--root", str(tmp_path)]) == 0


def test_allowlist_entry_without_reason_fails(tmp_path):
    _write_policy(
        tmp_path,
        markers="GeheimPartner AG",
        allow="spike/fixtures/sample.txt",
    )
    _write_fixture(tmp_path, "sample.txt", "harmlos")
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_missing_policy_fails_closed(tmp_path):
    assert mod.main(["--root", str(tmp_path)]) == 2


def test_missing_marker_block_fails_closed(tmp_path):
    policy = tmp_path / "docs" / "evaluation" / "testdata-policy.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text("# Policy ohne Markerblock\n", encoding="utf-8")
    assert mod.main(["--root", str(tmp_path)]) == 2


def test_real_repo_policy_is_currently_green():
    # Integrationstest gegen die echte Policy: Katalog ist initial leer.
    assert mod.main(["--root", str(REPO_ROOT)]) == 0
