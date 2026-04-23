"""
Document parser — extract text from uploaded reality-seed files.

Uses `pypdf` for PDF extraction (pure Python, easy install). Supports PDF,
Markdown, and plain text. The extracted text is fed into the ontology
generator + graph builder as `context` so the schema design is grounded in
the actual document content.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
MAX_DOC_BYTES = 8 * 1024 * 1024     # 8 MB per doc
MAX_TOTAL_TEXT_CHARS = 60_000       # Cap aggregate extracted text per project


# ============================================
# Bytes → text extractors
# ============================================


def _decode_text_with_fallback(data: bytes) -> str:
    """Decode bytes to text, falling back through charset detection.

    Strategy:
      1. Try UTF-8.
      2. Try common encodings (latin-1, cp1252, gb18030).
      3. Final fallback: UTF-8 with replace.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in ("utf-8-sig", "latin-1", "cp1252", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract all text from a PDF given its raw bytes."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "pypdf is not installed. Run: pip install pypdf"
        ) from exc

    reader = PdfReader(BytesIO(data))
    parts: List[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("Failed to extract page text: %s", exc)
            text = ""
        text = text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    """Top-level dispatcher: extract text from any supported file type."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    if len(data) > MAX_DOC_BYTES:
        raise ValueError(
            f"File too large: {len(data)} bytes (max {MAX_DOC_BYTES})"
        )
    if suffix == ".pdf":
        return extract_text_from_pdf_bytes(data)
    return _decode_text_with_fallback(data)


# ============================================
# Multi-document aggregator
# ============================================


def aggregate_documents(
    documents: List[Tuple[str, str]],
    max_total_chars: int = MAX_TOTAL_TEXT_CHARS,
) -> str:
    """Combine multiple parsed documents into a single context blob.

    Each document is prefixed with `=== Document N: filename ===` so the LLM
    can keep them straight when generating the ontology and graph. Truncates
    to a safe total length to keep prompt sizes bounded.

    Args:
        documents: list of (filename, extracted_text) tuples
        max_total_chars: hard cap on the returned string length

    Returns:
        a single string ready to drop into an LLM prompt as `context`
    """
    if not documents:
        return ""

    parts: List[str] = []
    used = 0
    MIN_CONTENT_PER_DOC = 50  # don't bother adding a doc with < 50 chars left
    for idx, (filename, text) in enumerate(documents, 1):
        if not text or not text.strip():
            continue
        header = f"\n\n=== Document {idx}: {filename} ===\n"
        remaining = max_total_chars - used - len(header)
        if remaining < MIN_CONTENT_PER_DOC:
            parts.append("\n\n=== (additional documents truncated) ===")
            break
        snippet = text.strip()[:remaining]
        parts.append(header + snippet)
        used += len(header) + len(snippet)

    return "".join(parts).strip()
