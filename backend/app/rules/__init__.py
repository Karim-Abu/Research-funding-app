"""Deterministic rule engine (Milestone 4).

Executes the 12 official core rules against structured project + partner inputs.
The engine is *purely deterministic*: it never calls an LLM, never uses
``eval``/``exec``, and never mutates a rule. Thresholds, ranges and the
pass/fail mapping are read from the versioned rule registry — not hardcoded.
Missing inputs yield ``needs_input`` (never a guessed pass/fail).
"""
from app.rules.engine import RuleOutcome, evaluate_rule
from app.rules.inputs import RuleInputs

__all__ = ["RuleOutcome", "RuleInputs", "evaluate_rule"]
