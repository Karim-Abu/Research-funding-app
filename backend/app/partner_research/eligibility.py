"""Conservative matcher for the versioned local Innosuisse reference snapshot."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

_SNAPSHOT = Path(__file__).parent / "data" / "innosuisse_eligible_2025-01.json"


@dataclass(frozen=True)
class EligibilityMatch:
    status: str
    institution: str | None
    reference_date: str
    source_url: str


def _norm(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().removeprefix("www.").rstrip(".")


@lru_cache(maxsize=1)
def snapshot() -> dict:
    return json.loads(_SNAPSHOT.read_text(encoding="utf-8"))


def match_eligibility(organization: str, evidence_url: str) -> EligibilityMatch:
    data = snapshot()
    org = _norm(organization)
    host = _host(evidence_url)
    domain_only = None
    for entry in data["institutions"]:
        names = {_norm(entry["name"]), *(_norm(alias) for alias in entry["aliases"])}
        exact_name = org in names
        domain_match = any(
            host == domain or host.endswith(f".{domain}") for domain in entry["domains"]
        )
        if exact_name and domain_match:
            return EligibilityMatch(
                "eligibility_verified", entry["name"], data["reference_status"],
                data["source_url"],
            )
        if domain_match:
            domain_only = entry["name"]
    if domain_only:
        return EligibilityMatch(
            "likely_eligible", domain_only, data["reference_status"], data["source_url"]
        )
    return EligibilityMatch(
        "needs_human_check", None, data["reference_status"], data["source_url"]
    )
