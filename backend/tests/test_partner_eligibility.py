from app.partner_research.eligibility import match_eligibility, snapshot


def test_exact_name_and_domain_are_verified():
    result = match_eligibility("FHNW", "https://www.fhnw.ch/de/forschung")
    assert result.status == "eligibility_verified"


def test_group_on_listed_parent_domain_is_likely_eligible():
    result = match_eligibility(
        "Institute for Data Science", "https://www.fhnw.ch/en/research/data-science"
    )
    assert result.status == "likely_eligible"


def test_unknown_candidate_needs_human_check_and_snapshot_has_hash():
    result = match_eligibility("Unknown Innovation Lab", "https://unknown-lab.ch")
    assert result.status == "needs_human_check"
    assert len(snapshot()["source_sha256"]) == 64
