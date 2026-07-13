"""EVAL.1 — data_mode als abgeleitetes Label (EVAL.0 §2, Owner-Entscheid D1).

NUR deskriptiv für EvaluationRunSummary/Reports — KEIN Enforcement-Pfad,
kein UI-Override, kein Provider-Bypass. Enforcement bleibt vollständig bei
``data_policy`` × ``provider_policy`` × ``policy_matrix``; dieses Label kann
nichts erlauben, was jene blockieren.

Ableitung (EVAL.0 §2, Ableitungstabelle):
- origin=real_project                      ⇒ real_project
- AI_EVAL_MODE=real + origin=synthetic     ⇒ synthetic_eval
- AI_EVAL_MODE=real + origin=anonymized    ⇒ anonymized_eval (vorerst nicht
  produktiv genutzt, Owner-Entscheid D2)
- sonst                                    ⇒ fake_test
"""
from __future__ import annotations

DATA_MODES = ("fake_test", "synthetic_eval", "anonymized_eval", "real_project")


def derive_data_mode(*, ai_eval_mode: str, origin: str | None) -> str:
    if origin == "real_project":
        return "real_project"
    if ai_eval_mode == "real" and origin == "synthetic":
        return "synthetic_eval"
    if ai_eval_mode == "real" and origin == "anonymized":
        return "anonymized_eval"
    return "fake_test"
