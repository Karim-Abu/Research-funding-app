from app.partner_research.eligibility import match_eligibility, snapshot


def test_exact_name_and_domain_are_only_a_reference_match():
    result = match_eligibility("FHNW", "https://www.fhnw.ch/de/forschung")
    assert result.status == "reference_match"


def test_group_on_listed_parent_domain_is_only_a_reference_match():
    result = match_eligibility(
        "Institute for Data Science", "https://www.fhnw.ch/en/research/data-science"
    )
    assert result.status == "reference_match"


def test_unknown_candidate_requires_human_review_and_snapshot_has_hash():
    result = match_eligibility("Unknown Innovation Lab", "https://unknown-lab.ch")
    assert result.status == "human_review_required"
    assert len(snapshot()["source_sha256"]) == 64
