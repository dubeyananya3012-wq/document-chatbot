"""
Lightweight PII redaction, applied to extracted document text before
it's chunked and embedded.

This is regex-based pattern matching, not a trained PII-detection
model - it catches common, well-structured patterns (emails, phone
numbers, SSNs, credit card numbers) and will miss anything less
regular (names, addresses, free-text identifiers). It's a floor, not
a guarantee. Redaction happens before embedding so redacted values
never enter the vector store or get echoed back in an answer.
"""
import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # US-style SSN: 123-45-6789
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Credit-card-like: 13-19 digits, optionally grouped with spaces/dashes
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # Phone numbers: reasonably permissive international/US formats
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{3,4}[ -]?\d{3,4}\b")),
]


def redact_pii(text: str) -> str:
    redacted = text
    for label, pattern in _PATTERNS:
        redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
    return redacted
