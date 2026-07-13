"""R2.1 — Fingerprint-Modul (tests first).

Zwei getrennte Konzepte:
- ``compute_finding_fingerprint``: stabile technische Identität EINES Findings
  (enthält den normalisierten claim_core) — Idempotenz/Dedupe auf Row-Ebene.
- ``compute_display_group_key``: UI-Gruppierung gleichartiger Meldungen —
  enthält NIE den claim_core (kein Roh-Claim-Text in Gruppenschlüsseln).
"""
from app.review.fingerprint import (
    compute_display_group_key,
    compute_finding_fingerprint,
)


class TestFindingFingerprint:
    def test_same_input_same_hash(self) -> None:
        a = compute_finding_fingerprint(
            "reliability:quantified", "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            claim_core="Der Markt wächst um 40 Prozent pro Jahr.",
        )
        b = compute_finding_fingerprint(
            "reliability:quantified", "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            claim_core="Der Markt wächst um 40 Prozent pro Jahr.",
        )
        assert a == b

    def test_stable_sha256_hex(self) -> None:
        fp = compute_finding_fingerprint("draft_placeholder", "INTRO.APP.ABSTRACT")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_claim_other_number_same_hash(self) -> None:
        a = compute_finding_fingerprint(
            "reliability:quantified", "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            claim_core="Der Markt wächst um 40 Prozent pro Jahr.",
        )
        b = compute_finding_fingerprint(
            "reliability:quantified", "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            claim_core="Der Markt wächst um 55.5 Prozent pro Jahr.",
        )
        assert a == b

    def test_whitespace_and_case_normalized(self) -> None:
        a = compute_finding_fingerprint(
            "draft_placeholder", "INTRO.APP.ABSTRACT",
            claim_core="  Ein   Claim\nmit Umbruch ",
        )
        b = compute_finding_fingerprint(
            "draft_placeholder", "INTRO.APP.ABSTRACT",
            claim_core="ein claim mit umbruch",
        )
        assert a == b

    def test_other_field_other_hash(self) -> None:
        a = compute_finding_fingerprint("draft_placeholder", "INTRO.APP.ABSTRACT")
        b = compute_finding_fingerprint(
            "draft_placeholder", "SOL.INNOVATION_SOLUTION.EDITOR"
        )
        assert a != b

    def test_none_claim_equals_empty(self) -> None:
        a = compute_finding_fingerprint("draft_empty", "INTRO.APP.NAME", claim_core=None)
        b = compute_finding_fingerprint("draft_empty", "INTRO.APP.NAME", claim_core="")
        assert a == b

    def test_source_id_changes_hash_when_set(self) -> None:
        base = compute_finding_fingerprint("reliability:weak", "INTRO.APP.ABSTRACT")
        with_source = compute_finding_fingerprint(
            "reliability:weak", "INTRO.APP.ABSTRACT", source_id="src-1"
        )
        other_source = compute_finding_fingerprint(
            "reliability:weak", "INTRO.APP.ABSTRACT", source_id="src-2"
        )
        assert base != with_source
        assert with_source != other_source


class TestDisplayGroupKey:
    def test_different_claims_same_family_same_key(self) -> None:
        # Vier Findings "Quantifizierte Aussage ohne passenden Zahlenbeleg" mit
        # unterschiedlichen Claims => EINE UI-Gruppe.
        a = compute_display_group_key("evidence_risk", "reliability:quantified")
        b = compute_display_group_key("evidence_risk", "reliability:quantified")
        assert a == b

    def test_other_severity_class_other_key(self) -> None:
        a = compute_display_group_key("evidence_risk", "reliability:quantified")
        b = compute_display_group_key("export_blocker", "reliability:quantified")
        assert a != b

    def test_other_family_other_key(self) -> None:
        a = compute_display_group_key("evidence_risk", "reliability:quantified")
        b = compute_display_group_key("evidence_risk", "reliability:market")
        assert a != b

    def test_field_group_optional(self) -> None:
        without = compute_display_group_key("export_blocker", "draft_placeholder")
        with_group = compute_display_group_key(
            "export_blocker", "draft_placeholder", field_group="INTRO"
        )
        assert without != with_group
        assert compute_display_group_key(
            "export_blocker", "draft_placeholder", field_group="INTRO"
        ) == with_group

    def test_key_never_contains_claim_text(self) -> None:
        # Der Key wird ohne claim_core gebildet; Signatur nimmt keinen Claim an.
        key = compute_display_group_key("evidence_risk", "reliability:quantified")
        assert "PROJECT_SECRET_MARKER_123" not in key
        # Lesbar und stabil aufgebaut (severity_class|familie[|field_group]).
        assert key == "evidence_risk|reliability:quantified"

    def test_key_normalizes_case_and_whitespace(self) -> None:
        a = compute_display_group_key("Export_Blocker", " draft_placeholder ")
        b = compute_display_group_key("export_blocker", "draft_placeholder")
        assert a == b
