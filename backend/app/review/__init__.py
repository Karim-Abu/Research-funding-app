"""Deterministic review layer (Milestone 7).

Aggregates M4-M6 artifacts into deterministic ReviewFindings + a ReviewPackage,
computes the approval scope hash, gates approvals, and runs targeted rechecks.
NO semantic judgement, NO A3/LLM/provider/network calls.
"""
from __future__ import annotations

REVIEW_PROFILE_VERSION = "deterministic-review-1"
