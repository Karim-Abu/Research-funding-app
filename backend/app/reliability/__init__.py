"""MAS reliability & value assurance (Milestone 9K).

A deterministic, beta-internal reliability layer over the current DraftVersions of a
completed run: claim extraction → lineage → evidence-sufficiency → unsupported-claim gate
+ false-consensus + semantic-drift guards → a per-run RunQualitySummary. No provider call;
A3 is read only as an already-persisted advisory signal. No finalized contract is modified.
"""
from __future__ import annotations

# The reliability profile used on reused ReviewFinding rows (source="agent") so the gate,
# Review Center, export and approval logic can recognise M9K findings without a new source
# enum value or migration (binding correction 1).
RELIABILITY_PROFILE_ID = "M9K.reliability_assurance"
SUMMARY_VERSION = "run-quality-1"
EXTRACTION_VERSION = "reliability-extract-1"
GLOSSARY_VERSION = "reliability-glossary-1"
