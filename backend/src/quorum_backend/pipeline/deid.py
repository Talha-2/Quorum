"""
De-identification gate at upload.

A first-pass safety check that scans uploaded document text for common,
high-confidence PHI patterns (SSN, phone, email, MRN, DOB) and surfaces
findings before the case enters the pipeline.

This is **not** a substitute for HIPAA Safe-Harbor de-identification:
- Free-text names, addresses, and small geographic subdivisions are not
  detected here (those need NER or a dedicated de-id service).
- A proper production deployment should run a real de-id pipeline
  (e.g., Microsoft Presidio, Philter, or a clinical-NLP service) under
  the appropriate BAAs, with this gate as a final guard.

What this module does well: catches the obvious patterns that a copy-pasted
clinical note frequently contains, and gives the operator a choice — warn,
strict, or redact — for how to react to a finding.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class DeidMode(str, Enum):
    """How the upload endpoint reacts to PHI findings."""

    OFF = "off"
    """No scanning. Use only when input is known-clean upstream."""

    WARN = "warn"
    """Scan, attach findings to the document, allow the upload."""

    STRICT = "strict"
    """Scan; reject the upload (HTTP 400) if any finding is detected."""

    REDACT = "redact"
    """Scan; replace findings with [REDACTED:<kind>] before storing."""

    @classmethod
    def parse(cls, value: object) -> "DeidMode":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        for member in cls:
            if member.value == text:
                return member
        return cls.WARN


@dataclass(frozen=True)
class PhiFinding:
    """A single detected PHI match in a document."""

    kind: str
    match: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


# High-confidence regex patterns. Each is anchored or context-keyed where
# possible to keep false positives low. Names/addresses are deliberately
# excluded — they need NER, not regex.
_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    # US SSN — three-digit, two-digit, four-digit groups with dashes.
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # US phone numbers: (310) 555-1212, 310-555-1212, 310.555.1212, +1 310 555 1212.
    # \b does not anchor before "(", so we use word lookarounds instead.
    (
        "phone",
        re.compile(
            r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s*|\d{3}[-.\s])\d{3}[-.\s]?\d{4}(?!\w)"
        ),
    ),
    # Email — keep simple but anchored.
    ("email", re.compile(r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b")),
    # Medical record number — context-keyed to keep false positives low.
    (
        "mrn",
        re.compile(
            r"\b(?:MRN|Medical\s+Record\s+(?:Number|No\.?|#))[\s:#]*([A-Z0-9-]{4,})\b",
            re.IGNORECASE,
        ),
    ),
    # Date of birth — context-keyed for the same reason.
    (
        "dob",
        re.compile(
            r"\b(?:DOB|Date\s+of\s+Birth)[\s:]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            re.IGNORECASE,
        ),
    ),
]


def scan_for_phi(text: str) -> List[PhiFinding]:
    """Return every PHI match found in ``text``."""
    if not text:
        return []
    findings: List[PhiFinding] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            findings.append(
                PhiFinding(kind=kind, match=m.group(0), start=m.start(), end=m.end())
            )
    # Order by position so the report is readable.
    findings.sort(key=lambda f: f.start)
    return findings


def redact(text: str) -> Tuple[str, List[PhiFinding]]:
    """Replace every PHI match with ``[REDACTED:<kind>]``. Returns the
    sanitized text and the findings list (positions refer to the original)."""
    findings = scan_for_phi(text)
    if not findings:
        return text, []
    # Rebuild from the end so earlier offsets stay valid.
    out_chars = list(text)
    for f in reversed(findings):
        out_chars[f.start : f.end] = list(f"[REDACTED:{f.kind}]")
    return "".join(out_chars), findings


def summary(findings: List[PhiFinding]) -> Dict[str, int]:
    """Counts by kind, for logging and the document record."""
    counts: Dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    return counts
