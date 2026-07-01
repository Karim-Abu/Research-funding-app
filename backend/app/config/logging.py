"""Structured logging with secret redaction.

Sensitive values must never reach the logs. We both (a) avoid logging secrets
at the call sites and (b) scrub known-sensitive token patterns defensively.
"""
from __future__ import annotations

import logging
import re

_REDACT_PATTERNS = [
    re.compile(r"(?i)(password\"?\s*[:=]\s*\"?)([^\"\s,}]+)"),
    re.compile(r"(?i)(csrf[_-]?token\"?\s*[:=]\s*\"?)([^\"\s,}]+)"),
    re.compile(r"(?i)(set-cookie\s*[:=]\s*)([^\s,]+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s,]+)"),
    # Milestone 9J — never let a raw web-research query text reach the logs. Only
    # ``*_hash`` fields (raw_query_hash) may carry a value; ``query``/``raw_query``/
    # ``query_text``/``query_preview`` values are scrubbed defensively.
    re.compile(r"(?i)((?:raw_)?query(?:_text|_preview)?\"?\s*[:=]\s*\"?)([^\"\n,}]+)"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern in _REDACT_PATTERNS:
            msg = pattern.sub(r"\1<redacted>", msg)
        record.msg = msg
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s level=%(levelname)s logger=%(name)s "
            "correlation_id=%(correlation_id)s msg=%(message)s",
            defaults={"correlation_id": "-"},
        )
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
