"""URL + SSRF safety for public web research (Milestone 9I-A, controls
CTRL.PUBLIC_URL_VALIDATION / CTRL.SSRF_PREVENTION / CTRL.REDIRECT_REVALIDATION).

Every URL — the candidate, every redirect target, and the final fetched URL — must be
re-validated here before any fetch/import. HTTPS only; no credentials; DNS resolved and
every resolved IP checked against loopback/private/link-local/metadata/reserved ranges.

The provider (Firecrawl) performs the actual network access; this module is the
deterministic gate around it and is fully unit-testable without a network (DNS lookups
can be injected via ``resolver`` for tests).
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Content types we accept for import (textual / document sources only).
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/pdf", "application/xhtml+xml")
# Cloud metadata endpoints (link-local already blocks 169.254.169.254, kept explicit).
_METADATA_HOSTS = {"metadata.google.internal"}


@dataclass(frozen=True)
class UrlCheck:
    ok: bool
    reason: str
    host: str | None = None
    ips: tuple[str, ...] = field(default_factory=tuple)


Resolver = Callable[[str], list[str]]


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    return [info[4][0] for info in infos]


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return bool(
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or (getattr(ip, "is_site_local", False))
    )


def validate_public_url(url: str, *, resolver: Resolver | None = None) -> UrlCheck:
    """Validate a single URL for public, non-SSRF fetching. Resolves DNS and rejects
    any URL whose host resolves to a non-public address. Does not follow redirects —
    the caller must re-validate each redirect target and the final URL."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return UrlCheck(False, "url_unparseable")

    scheme = (parts.scheme or "").lower()
    if scheme != "https":
        return UrlCheck(False, "scheme_not_https")
    if parts.username or parts.password or "@" in (parts.netloc or ""):
        return UrlCheck(False, "credentials_in_url")

    host = parts.hostname
    if not host:
        return UrlCheck(False, "missing_host")
    host_l = host.lower()
    if host_l in _METADATA_HOSTS or host_l == "localhost" or host_l.endswith(".localhost"):
        return UrlCheck(False, "blocked_host", host=host)

    # If the host is a literal IP, validate it directly; otherwise resolve via DNS.
    resolve = resolver or _default_resolver
    raw_ips: list[str]
    try:
        ipaddress.ip_address(host_l)
        raw_ips = [host_l]
    except ValueError:
        try:
            raw_ips = resolve(host_l)
        except Exception:  # noqa: BLE001 — DNS failure ⇒ treat as unverifiable/blocked
            return UrlCheck(False, "dns_resolution_failed", host=host)

    if not raw_ips:
        return UrlCheck(False, "dns_no_records", host=host)

    checked: list[str] = []
    for raw in raw_ips:
        try:
            ip = ipaddress.ip_address(raw.split("%")[0])  # strip scope id
        except ValueError:
            return UrlCheck(False, "invalid_resolved_ip", host=host)
        if _ip_is_blocked(ip):
            return UrlCheck(False, "private_or_reserved_target", host=host, ips=tuple(checked + [raw]))
        checked.append(raw)

    return UrlCheck(True, "public_url_ok", host=host, ips=tuple(checked))


def content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    base = content_type.split(";", 1)[0].strip().lower()
    return base in ALLOWED_CONTENT_TYPES


def canonical_public_url(url: str) -> str:
    """Canonical identity for exact URL de-duplication; never performs I/O."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    tracking = {"fbclid", "gclid", "mc_cid", "mc_eid"}
    query = urlencode([
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in tracking and not key.lower().startswith("utm_")
    ])
    return urlunsplit((scheme, netloc, path, query, ""))
