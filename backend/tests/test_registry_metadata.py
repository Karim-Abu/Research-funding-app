"""R2.7 — Loader-Validierung der Regel-Metadaten.

Die INHALTE (source_ref/source_version/last_checked/validity_status) liefert
der Owner in den Contract-YAMLs; der Loader validiert nur das Format:
leere/fehlende Felder sind toleriert (None), kaputtes Format ⇒ RegistryError
(fail-closed). Contract-WERTE werden hier nicht angefasst — die Tests bauen
synthetische Registry-Rohdaten.
"""
from __future__ import annotations

import pytest

from app.registry.loader import (
    EXPECTED_RULE_REGISTRY_ID,
    RegistryError,
    _parse_rules,
    load_registry,
)


def _raw(rule_overrides: dict | None = None) -> dict:
    rule = {
        "rule_id": "TEST.RULE.ONE",
        "title": "Testregel",
        "condition": {"type": "exists", "entity": "research_partner"},
        "result_mapping": {"true": "passed", "false": "failed"},
    }
    rule.update(rule_overrides or {})
    return {
        "registry_id": EXPECTED_RULE_REGISTRY_ID,
        "official_core_rules": [rule],
    }


class TestValidMetadata:
    def test_all_four_fields_parsed(self) -> None:
        rules = _parse_rules(
            _raw(
                {
                    "source_ref": "Innosuisse Förderreglement, Art. 3",
                    "source_version": "2026-01",
                    "last_checked": "2026-07-01",
                    "validity_status": "valid",
                }
            )
        )
        rule = rules["TEST.RULE.ONE"]
        assert rule.source_ref == "Innosuisse Förderreglement, Art. 3"
        assert rule.source_version == "2026-01"
        assert rule.last_checked == "2026-07-01"
        assert rule.validity_status == "valid"

    def test_values_are_stripped(self) -> None:
        rules = _parse_rules(_raw({"last_checked": " 2026-07-01 "}))
        assert rules["TEST.RULE.ONE"].last_checked == "2026-07-01"


class TestMissingMetadataTolerated:
    def test_absent_fields_are_none(self) -> None:
        rule = _parse_rules(_raw())["TEST.RULE.ONE"]
        assert rule.source_ref is None
        assert rule.source_version is None
        assert rule.last_checked is None
        assert rule.validity_status is None

    def test_empty_string_is_none(self) -> None:
        rule = _parse_rules(_raw({"source_ref": ""}))["TEST.RULE.ONE"]
        assert rule.source_ref is None

    def test_real_registry_loads_with_unmaintained_metadata(self) -> None:
        # Die echten Contract-YAMLs sind noch ohne Metadaten — Laden bleibt grün.
        registry = load_registry()
        assert len(registry.rules) == 12


class TestBrokenFormatFailsClosed:
    def test_non_iso_last_checked_raises(self) -> None:
        with pytest.raises(RegistryError, match="last_checked"):
            _parse_rules(_raw({"last_checked": "07.05.2026"}))

    def test_non_string_source_ref_raises(self) -> None:
        with pytest.raises(RegistryError, match="source_ref"):
            _parse_rules(_raw({"source_ref": 123}))

    def test_whitespace_only_validity_status_raises(self) -> None:
        with pytest.raises(RegistryError, match="validity_status"):
            _parse_rules(_raw({"validity_status": "   "}))
