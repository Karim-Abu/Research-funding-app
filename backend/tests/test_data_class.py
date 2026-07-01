"""Milestone 9J — data-class derivation, central policy matrix, firewall pure logic.

No DB needed here (D0 generic + D3/UNKNOWN don't build the project lexicon). The
DB-backed D1/D2 firewall + approval flow lives in ``test_privacy_firewall.py``.
"""
from __future__ import annotations

from app.policy.classification import resolve_effective_classification
from app.security.data_class import DataClass, derive_data_class, is_external_blocked
from app.security.policy_matrix import Decision, Tool, decide, web_research_decision
from app.security.search_query_firewall import evaluate_query, raw_query_hash


def _cls(sensitivity, origin="public_source", nda=False):
    return {
        "sensitivity": sensitivity, "origin": origin,
        "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
        "nda_applies": nda,
    }


# --- classification ---------------------------------------------------------

def test_data_class_mapping():
    assert derive_data_class(_cls("public")) == DataClass.D0_PUBLIC
    assert derive_data_class(_cls("internal", "real_project")) == DataClass.D1_INTERNAL
    assert derive_data_class(_cls("confidential", "real_project")) == DataClass.D2_CONFIDENTIAL_IDEA
    assert derive_data_class(_cls("public", nda=True)) == DataClass.D3_NDA_BLOCKED


def test_unknown_fail_closed():
    # Empty / missing classification and unrecognized values are UNKNOWN (deny-by-default).
    assert derive_data_class({}) == DataClass.UNKNOWN
    assert derive_data_class({"sensitivity": "top-secret"}) == DataClass.UNKNOWN
    # public sensitivity but a non-public origin is ambiguous → UNKNOWN, not D0.
    assert derive_data_class(_cls("public", "real_project")) == DataClass.UNKNOWN
    assert is_external_blocked(DataClass.UNKNOWN)
    assert is_external_blocked(DataClass.D3_NDA_BLOCKED)


def test_most_restrictive_wins():
    # A public project with a confidential source resolves to confidential → D2.
    effective, _ = resolve_effective_classification(
        _cls("public"), {"sensitivity": "confidential"}
    )
    assert effective["sensitivity"] == "confidential"
    assert derive_data_class(effective) == DataClass.D2_CONFIDENTIAL_IDEA
    # NDA on either side → D3.
    effective2, _ = resolve_effective_classification(_cls("public"), {"nda_applies": True})
    assert derive_data_class(effective2) == DataClass.D3_NDA_BLOCKED


# --- policy matrix (fail-closed) --------------------------------------------

def test_policy_matrix_fail_closed():
    assert web_research_decision(DataClass.D0_PUBLIC) == Decision.ALLOW
    assert web_research_decision(DataClass.D1_INTERNAL) == Decision.REQUIRE_SANITIZED_APPROVAL
    assert web_research_decision(DataClass.D2_CONFIDENTIAL_IDEA) == Decision.REQUIRE_SANITIZED_APPROVAL
    assert web_research_decision(DataClass.D3_NDA_BLOCKED) == Decision.BLOCKED
    assert web_research_decision(DataClass.UNKNOWN) == Decision.BLOCKED
    # Provider vector store is never allowed, even for D0 (no stateful provider features).
    assert decide(DataClass.D0_PUBLIC, Tool.PROVIDER_VECTOR_STORE) == Decision.BLOCKED
    # D3/UNKNOWN external tools all blocked; only local db/logs.
    assert decide(DataClass.D3_NDA_BLOCKED, Tool.AZURE_LLM_GATEWAY) == Decision.BLOCKED
    assert decide(DataClass.D3_NDA_BLOCKED, Tool.LOCAL_DB) == Decision.ALLOW
    assert decide(DataClass.UNKNOWN, Tool.FIRECRAWL_WEBRESEARCH) == Decision.BLOCKED


# --- firewall: generic (no DB / no project lexicon) -------------------------

def test_firewall_d0_generic_allowed():
    r = evaluate_query(
        None, project_id="p", workspace_id="w", actor_user_id="u",
        raw_query="öffentliche Wettbewerbsanalyse Robotik", data_class=DataClass.D0_PUBLIC,
        intended_tool="firecrawl",
    )
    assert r.decision == "allow"
    assert r.risk_score <= 2
    assert r.detected_sensitive_categories == []


def test_firewall_d0_email_and_budget_flagged():
    r = evaluate_query(
        None, project_id="p", workspace_id="w", actor_user_id="u",
        raw_query="mail me at john.doe@example.com about CHF 500'000 budget",
        data_class=DataClass.D0_PUBLIC, intended_tool="firecrawl",
    )
    assert "email" in r.detected_sensitive_categories
    assert "budget_amount" in r.detected_sensitive_categories
    # sanitized removes the address + figure.
    assert "example.com" not in r.sanitized_query
    assert "500" not in r.sanitized_query


def test_firewall_d3_and_unknown_blocked():
    for dc in (DataClass.D3_NDA_BLOCKED, DataClass.UNKNOWN):
        r = evaluate_query(
            None, project_id="p", workspace_id="w", actor_user_id="u",
            raw_query="anything at all", data_class=dc, intended_tool="firecrawl",
        )
        assert r.decision == "block"


def test_raw_query_hash_is_stable_and_opaque():
    h1 = raw_query_hash("Acme  Robotics")
    h2 = raw_query_hash("acme robotics")  # normalized (casefold + NFKC + ws collapse)
    assert h1 == h2 and len(h1) == 64
    assert "acme" not in h1.lower()
