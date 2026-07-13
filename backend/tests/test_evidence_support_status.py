"""R6 — Evidence-Statusleiter: Kombinationsmatrix (Akzeptanzkriterium).

Kernaussage: Coverage ≠ Correctness. ``exact_verified`` ohne Reliability-
Urteil ist NUR ``location_found`` — nie eine ``supports_*``-Stufe. Unbekannte
Eingaben fallen fail-closed auf ``human_review_required``.
"""
import pytest

from app.review.evidence_status import (
    SUPPORT_STATUSES,
    aggregate_field_support_status,
    derive_anchor_support_status,
    most_cautious,
    support_status_for_anchor,
)


class TestAnchorMatrix:
    # (verification_status, lineage_status, sufficiency_status) → erwartete Stufe
    MATRIX = [
        # Fundstellen-Abgleich allein: Coverage, nie Stützung.
        ("exact_verified", None, None, "location_found"),
        ("human_verified", None, None, "location_found"),
        ("unverified", None, None, "human_review_required"),
        ("rejected", None, None, "conflict_or_uncertain"),
        # Reliability-Urteile heben/senken die Stufe.
        ("exact_verified", "direct_evidence", "supports_claim", "supports_strongly"),
        ("exact_verified", "indirect_evidence", "supports_claim", "supports_partially"),
        ("exact_verified", "indirect_evidence", "weakly_supports_claim", "supports_partially"),
        ("exact_verified", "weak_evidence", "insufficient_evidence", "supports_partially"),
        ("exact_verified", "conflicting_evidence", "supports_claim", "conflict_or_uncertain"),
        ("exact_verified", "direct_evidence", "does_not_support_claim", "conflict_or_uncertain"),
        ("exact_verified", "needs_human_review", "supports_claim", "human_review_required"),
        ("exact_verified", "direct_evidence", "needs_human_review", "human_review_required"),
        ("exact_verified", "no_evidence", "insufficient_evidence", "location_found"),
        ("human_verified", "direct_evidence", "supports_claim", "supports_strongly"),
        # Verwerfung/Nichtverifikation dominiert jedes Reliability-Urteil.
        ("rejected", "direct_evidence", "supports_claim", "conflict_or_uncertain"),
        ("unverified", "direct_evidence", "supports_claim", "human_review_required"),
        # Fail-closed bei unbekannten Werten.
        ("garbage", None, None, "human_review_required"),
        ("exact_verified", "garbage", "garbage", "human_review_required"),
    ]

    @pytest.mark.parametrize("verification,lineage,sufficiency,expected", MATRIX)
    def test_matrix(self, verification, lineage, sufficiency, expected) -> None:
        assert (
            derive_anchor_support_status(verification, lineage, sufficiency)
            == expected
        )

    def test_all_seven_levels_reachable(self) -> None:
        reached = {expected for *_, expected in self.MATRIX}
        reached.add(aggregate_field_support_status("required", []))
        reached.add(aggregate_field_support_status("not_required", []))
        assert reached == set(SUPPORT_STATUSES)

    def test_location_found_is_never_a_supports_level(self) -> None:
        # Wording-Schutz: der reine Fundstellen-Abgleich darf nie als
        # fachliche Stützung erscheinen.
        for verification in ("exact_verified", "human_verified"):
            status = derive_anchor_support_status(verification)
            assert not status.startswith("supports_")
            assert status == "location_found"


class TestAggregation:
    def test_field_without_links_required(self) -> None:
        assert aggregate_field_support_status("required", []) == "evidence_missing"
        assert aggregate_field_support_status("conditional", []) == "evidence_missing"

    def test_field_without_links_not_required(self) -> None:
        assert aggregate_field_support_status("not_required", []) == "not_required"
        assert aggregate_field_support_status("", []) == "not_required"

    def test_voluntary_evidence_on_not_required_field_shows_aggregate(self) -> None:
        assert (
            aggregate_field_support_status("not_required", ["location_found"])
            == "location_found"
        )

    def test_most_cautious_wins(self) -> None:
        assert (
            most_cautious(["supports_strongly", "conflict_or_uncertain"])
            == "conflict_or_uncertain"
        )
        assert (
            most_cautious(["supports_strongly", "location_found"])
            == "location_found"
        )
        assert (
            most_cautious(["supports_partially", "supports_strongly"])
            == "supports_partially"
        )

    def test_most_cautious_unknown_value_fails_closed(self) -> None:
        assert most_cautious(["supports_strongly", "???"]) == "human_review_required"

    def test_anchor_over_multiple_claims_takes_most_cautious(self) -> None:
        judgments = [
            ("direct_evidence", "supports_claim"),
            ("conflicting_evidence", "supports_claim"),
        ]
        assert (
            support_status_for_anchor("exact_verified", judgments)
            == "conflict_or_uncertain"
        )

    def test_anchor_without_judgments_is_location_found(self) -> None:
        assert support_status_for_anchor("exact_verified", None) == "location_found"
        assert support_status_for_anchor("exact_verified", []) == "location_found"
