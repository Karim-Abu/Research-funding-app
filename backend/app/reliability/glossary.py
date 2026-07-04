"""Core-term glossary + semantic-drift patterns (Milestone 9K, STEP 7).

A versioned glossary of the terms whose meaning must not drift, and deterministic
co-occurrence patterns that flag the common drift failure modes. Each pattern fires when an
``anchor`` term and a ``drift`` term co-occur in the same sentence. All terms are normalized
(NFKC + casefold); phrases are matched as substrings.
"""
from __future__ import annotations

# term -> the correct, non-drifted meaning (surfaced in docs / finding rationale).
GLOSSARY: dict[str, str] = {
    "Innovation": "Neuheit gegenüber dem Stand der Technik mit belegter Differenzierung — "
                  "nicht generische Forschungsneuheit.",
    "Eligibility": "Deterministische Förderfähigkeits-Plausibilität — keine rechtliche/"
                   "finanzielle Förderentscheidung.",
    "Value Creation": "Belegte volkswirtschaftliche/betriebliche Wertschöpfung — keine "
                      "generischen Business-Schlagworte.",
    "Partner Fit": "Belegte Eignung des Partners (Expertise/Track Record).",
    "Evidence": "Deterministisch verifizierter Beleg (Anchor) — kein Snippet, kein Payload.",
    "Review Approval": "Menschliche Freigabe der internen Prüfung — keine Einreichungs-/"
                       "Portalfreigabe.",
    "Technical Verification": "Exakte Positions-/Quote-Verifikation — kein fachliches Urteil.",
    "Market Claim": "Aussage über Markt/Kunden/Wettbewerb — braucht quellenbelegte Angaben.",
    "Competition Claim": "Aussage über Konkurrenz — braucht quellenbelegte Angaben.",
    "NDA": "Rechtlich gesperrt (D3) — nie extern verarbeitet.",
    "Confidential": "Vertraulich (D2) — nie roh an externe Werkzeuge.",
}

# (code, description, anchor terms, drift terms). Normalized/casefolded, substring match.
DRIFT_PATTERNS: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "exact_verified_as_approved",
        "Semantische Drift: „exact_verified“ (nur Quote existiert) wird als fachliche "
        "Freigabe/Genehmigung dargestellt.",
        ("exact_verified", "exakt verifiziert", "verifizierter beleg", "technisch verifiziert"),
        ("genehmigt", "freigegeben", "approved", "fachlich bestätigt", "abgesegnet",
         "geprüft und korrekt", "als wahr bestätigt"),
    ),
    (
        "review_approval_as_submission",
        "Semantische Drift: „Review Approval“ (interne Prüfung) wird als Einreichungs-/"
        "Portalfreigabe dargestellt.",
        ("review approval", "reviewapproval", "prüffreigabe", "review-freigabe",
         "freigabe der prüfung"),
        ("einreichung", "eingereicht", "submission", "submitted", "beim portal eingereicht",
         "antrag eingereicht", "zur einreichung freigegeben"),
    ),
    (
        "eligibility_as_decision",
        "Semantische Drift: Förderfähigkeits-Plausibilität wird als rechtliche/finanzielle "
        "Förderentscheidung dargestellt.",
        ("förderfähig", "foerderfaehig", "eligibility", "eligible", "förderfähigkeit"),
        ("garantiert", "zusage", "bewilligt", "guaranteed", "entscheidung getroffen",
         "sicher finanziert", "förderung sicher", "genehmigt durch innosuisse"),
    ),
    (
        "public_as_confidential_safe",
        "Semantische Drift: „öffentliche Quelle“ wird als vertraulich-sicher-zu-teilen "
        "dargestellt.",
        ("öffentliche quelle", "public source", "public_source", "öffentlich zugänglich"),
        ("vertraulich", "confidential", "sicher zu teilen", "safe to share", "geheim"),
    ),
    (
        "innovation_reduced_to_generic",
        "Semantische Drift: „Innovation“ wird auf generische Neuheit reduziert (ohne "
        "Differenzierung zum Stand der Technik).",
        ("innovation",),
        ("lediglich neuartig", "nur eine neue idee", "generische neuheit",
         "einfach etwas neues", "nichts besonderes neues"),
    ),
    (
        "value_creation_buzzwords",
        "Semantische Drift: „Value Creation/Wertschöpfung“ wird durch generische "
        "Schlagworte ersetzt (ohne belegten Nutzen).",
        ("value creation", "wertschöpfung"),
        ("disruptiv", "paradigmenwechsel", "game changer", "revolutioniert die welt",
         "synergien heben", "next level"),
    ),
]
