"""R5.3 — Prompt-Snapshot-Regressionstests.

Verhindert stille Änderungen an den versionierten Prompt-Dateien
(``backend/app/agents/prompts/*_vN.md``). Jede aktive Prompt-Datei ist per
normalisiertem sha256 gepinnt; eine Inhaltsänderung ohne Versions-Bump oder
Snapshot-Update (+ CHANGELOG-Eintrag) macht den Test rot.

Reine Datei-Tests — keine Provider-/Gateway-Calls, keine Loader-Cache-Interaktion.
Der Hash wird zeilenenden-normalisiert (CRLF↔LF), damit Windows-Dev und Linux-CI
denselben Wert sehen.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "app" / "agents" / "prompts"
CHANGELOG = PROMPTS_DIR / "CHANGELOG.md"

# {dateiname: sha256(normalisierter Inhalt)}. Ein rot gewordener Hash wird nur
# zusammen mit einem CHANGELOG.md-Eintrag aktualisiert (Workflow siehe CHANGELOG).
_PROMPT_SNAPSHOTS: dict[str, str] = {
    "a1_evidence_candidate_mapping_v1.md": "cf34fa9f00b30fc9698b9f7d659402d831de71d9c6d1f90467d5f79c76fce761",
    "a1_project_fact_extraction_v1.md": "64235ac962c58af85b45450aa9e420e2b1d92483bd95ba2c8d41044243dc7364",
    "a1_public_competence_research_v1.md": "a0359459e600ceae790cf9056e296f9b1e6436cfda58aecf80175dc672be5cfb",
    "a2_introduction_public_summary_v2.md": "1552c8170804e89b885d26965f3178de49989723270264b5a91135fad9fccadc",
    "a2_organisations_governance_v1.md": "b1962a3eb54210aaebbe7cba9e3957e5f66de3ffd67399808b84e3bd6d78b215",
    "a2_project_setup_workplan_v1.md": "36e51956b2aab8fce9946d3e81e56477ac92e55d889db6f2f4b297dd57928e79",
    "a2_solution_innovation_v3.md": "0b0cb392b7e59b0e0b275925b79d91f157b7957d51a67008554bbde64db75d4d",
    "a2_value_creation_market_logic_v3.md": "d59759421bf6068a6b0d06c9d87eebbb119e8216a9a57db65691e07079ed1442",
    "a3_evidence_consistency_v2.md": "cfa771ce56018f71093357e7128a25ab5318ecfa9dc715f8710f8353cf1266b3",
    "market_comparison_v2.md": "d9f309a310dac77220642273b3ac9ff40219b36602609fd9f643e33bfc028538",
}


def _normalize(text: str) -> str:
    """CRLF/CR → LF, damit der Hash OS-unabhängig ist (Repo-Idiom normalize.py)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def _prompt_files(prompt_dir: Path) -> list[Path]:
    """Versionierte Prompt-Dateien — CHANGELOG.md ist keine Prompt-Datei."""
    return [p for p in sorted(prompt_dir.glob("*.md")) if p.name != "CHANGELOG.md"]


def _frontmatter(text: str, key: str) -> str | None:
    """Frontmatter-Wert per Zeilen-Scan (spiegelt prompt_assets._parse_prompt)."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip()
    return None


def _check(prompt_dir: Path, snapshots: dict[str, str]) -> list[str]:
    """Abweichungen Prompt-Ordner ↔ Snapshots (leer = alles gepinnt)."""
    problems: list[str] = []
    seen: set[str] = set()
    for path in _prompt_files(prompt_dir):
        seen.add(path.name)
        actual = _hash(path.read_text(encoding="utf-8"))
        expected = snapshots.get(path.name)
        if expected is None:
            problems.append(f"{path.name}: neue Prompt-Datei ohne Snapshot-Eintrag")
        elif actual != expected:
            problems.append(f"{path.name}: Inhalt geändert ohne Snapshot-Update")
    for name in snapshots:
        if name not in seen:
            problems.append(f"{name}: Snapshot vorhanden, aber Prompt-Datei fehlt")
    return sorted(problems)


def _copy_prompts(dst: Path) -> None:
    for path in _prompt_files(PROMPTS_DIR):
        (dst / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def test_prompt_snapshots_match():
    """Der reale Prompt-Ordner deckt sich exakt mit den gepinnten Snapshots."""
    assert _prompt_files(PROMPTS_DIR), "keine Prompt-Dateien gefunden — falscher Pfad?"
    assert _check(PROMPTS_DIR, _PROMPT_SNAPSHOTS) == []


def test_silent_change_is_detected(tmp_path):
    """Manipulationstest: geänderter Inhalt ohne Snapshot-Update ⇒ rot."""
    _copy_prompts(tmp_path)
    assert _check(tmp_path, _PROMPT_SNAPSHOTS) == []  # Kopie ist zunächst sauber
    target = tmp_path / "a2_solution_innovation_v3.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nStille Änderung.\n", encoding="utf-8"
    )
    problems = _check(tmp_path, _PROMPT_SNAPSHOTS)
    assert any("a2_solution_innovation_v3.md" in p for p in problems), problems


def test_new_prompt_requires_snapshot(tmp_path):
    """Eine neue Prompt-Datei ohne Snapshot-Eintrag wird gemeldet."""
    _copy_prompts(tmp_path)
    (tmp_path / "zzz_new_field_v1.md").write_text(
        "---\nversion: zzz_new_field_v1\nprofile_id: X.zzz\n---\n\nbody\n",
        encoding="utf-8",
    )
    problems = _check(tmp_path, _PROMPT_SNAPSHOTS)
    assert any("zzz_new_field_v1.md" in p for p in problems), problems


def test_version_slug_matches_filename():
    """``version:`` == Datei-Stem — ein Versions-Bump erzwingt eine neue Datei."""
    offenders = [
        f"{p.name}: version={_frontmatter(p.read_text(encoding='utf-8'), 'version')!r}"
        f" != stem={p.stem!r}"
        for p in _prompt_files(PROMPTS_DIR)
        if _frontmatter(p.read_text(encoding="utf-8"), "version") != p.stem
    ]
    assert offenders == [], offenders


def test_no_duplicate_identity():
    """Kein doppelter profile_id/version-Slug (Guard gegen Loader-last-file-wins)."""
    pids: list[str | None] = []
    versions: list[str | None] = []
    for path in _prompt_files(PROMPTS_DIR):
        text = path.read_text(encoding="utf-8")
        pids.append(_frontmatter(text, "profile_id"))
        versions.append(_frontmatter(text, "version"))
    dup_pids = [k for k, n in Counter(pids).items() if n > 1]
    dup_versions = [k for k, n in Counter(versions).items() if n > 1]
    assert dup_pids == [], f"doppelte profile_id (last-file-wins-Risiko): {dup_pids}"
    assert dup_versions == [], f"doppelter version-Slug: {dup_versions}"


def test_every_prompt_in_changelog():
    """Jeder aktive Prompt-Slug ist im CHANGELOG dokumentiert (Req 4)."""
    changelog = _normalize(CHANGELOG.read_text(encoding="utf-8"))
    missing = [
        version
        for path in _prompt_files(PROMPTS_DIR)
        if (version := _frontmatter(path.read_text(encoding="utf-8"), "version"))
        and version not in changelog
    ]
    assert missing == [], f"Prompt-Version(en) ohne CHANGELOG-Eintrag: {missing}"
