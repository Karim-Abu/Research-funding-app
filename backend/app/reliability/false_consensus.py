"""False-consensus guard (Milestone 9K, STEP 6).

Detects the dangerous case where A2 generated a claim, A3 did not flag the field, yet the
M9K sufficiency check finds no/insufficient evidence. A3 silence is not evidence of
correctness, and A3 agreement never overrides a missing/insufficient anchor.
"""
from __future__ import annotations

from app.reliability import sufficiency as suff
from app.reliability.extract import ExtractedClaim
from app.reliability.gate import ReliabilityFindingSpec, _claim_spec
from app.reliability.lineage import LineageResult

_WEAK_OR_NONE = {suff.INSUFFICIENT, suff.DOES_NOT, suff.NEEDS_REVIEW}


def false_consensus_specs(
    claim: ExtractedClaim, lineage: LineageResult
) -> list[ReliabilityFindingSpec]:
    if not claim.requires_evidence:
        return []
    # Only A2-authored claims can produce a false A2↔A3 consensus.
    if not lineage.agent_authored:
        return []
    # If A3 flagged the field, there is no *silent* consensus.
    if lineage.a3_flagged_field:
        return []
    if lineage.supported:
        return []
    if lineage.lineage_status == "no_evidence" or lineage.sufficiency_status in _WEAK_OR_NONE:
        severity = "blocker" if claim.strength == "strong" else "warning"
        return [_claim_spec(
            f"reliability:false_consensus:{claim.claim_id}", severity,
            "Falsches Konsensrisiko: A2 hat diese Aussage erzeugt, A3 hat das Feld nicht "
            "beanstandet, doch die Beleg-Suffizienzprüfung findet keinen ausreichenden "
            "Beleg. A3-Schweigen ist kein Korrektheitsbeleg.", claim,
        )]
    return []
