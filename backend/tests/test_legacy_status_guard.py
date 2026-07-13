"""R1.4 — Selbsttests fuer scripts/check_legacy_status_paths.py.

Guard schlaegt bei neuen isMock("legacy")-Stellen ausserhalb der Allowlist an,
akzeptiert den dokumentierten Bestand und verteidigt den Paritaetstest.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_legacy_status_paths.py"

spec = importlib.util.spec_from_file_location("check_legacy_status_paths", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _write_parity_spec(root: Path) -> None:
    spec_file = root / "e2e" / "status-parity.spec.ts"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text('test("R1 Parität: ...")', encoding="utf-8")


def test_clean_tree_passes(tmp_path):
    _write_parity_spec(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "clean.ts").write_text("export const a = 1", encoding="utf-8")
    assert mod.main(["--root", str(tmp_path)]) == 0


def test_new_legacy_call_fails(tmp_path):
    _write_parity_spec(tmp_path)
    comp = tmp_path / "components" / "review"
    comp.mkdir(parents=True)
    (comp / "bad.tsx").write_text(
        'if (isMock("legacy")) { return mockData }', encoding="utf-8"
    )
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_allowlisted_file_passes(tmp_path):
    _write_parity_spec(tmp_path)
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.ts").write_text('if (isMock("legacy")) {}', encoding="utf-8")
    assert mod.main(["--root", str(tmp_path)]) == 0


def test_missing_parity_spec_fails(tmp_path):
    (tmp_path / "lib").mkdir()
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_hollowed_parity_spec_fails(tmp_path):
    spec_file = tmp_path / "e2e" / "status-parity.spec.ts"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("// leer", encoding="utf-8")
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_real_repo_is_currently_clean():
    # Integrationstest: der dokumentierte Bestand (R1.1-Inventar) ist gruen.
    assert mod.main(["--root", str(REPO_ROOT)]) == 0
