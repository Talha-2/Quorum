"""
Document parser — extract text from uploaded reality-seed files.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
MAX_DOC_BYTES = 8 * 1024 * 1024  # 8 MB per doc
MAX_TOTAL_TEXT_CHARS = 60_000  # Cap aggregate extracted text per project


def _decode_text_with_fallback(data: bytes) -> str:
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
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("pypdf is not installed. Run: pip install pypdf") from exc

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
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")
    if len(data) > MAX_DOC_BYTES:
        raise ValueError(f"File too large: {len(data)} bytes (max {MAX_DOC_BYTES})")
    if suffix == ".pdf":
        return extract_text_from_pdf_bytes(data)
    return _decode_text_with_fallback(data)


def aggregate_documents(
    documents: List[Tuple[str, str]],
    max_total_chars: int = MAX_TOTAL_TEXT_CHARS,
) -> str:
    if not documents:
        return ""

    parts: List[str] = []
    used = 0
    min_content_per_doc = 50
    for idx, (filename, text) in enumerate(documents, 1):
        if not text or not text.strip():
            continue
        header = f"\n\n=== Document {idx}: {filename} ===\n"
        remaining = max_total_chars - used - len(header)
        if remaining < min_content_per_doc:
            parts.append("\n\n=== (additional documents truncated) ===")
            break
        snippet = text.strip()[:remaining]
        parts.append(header + snippet)
        used += len(header) + len(snippet)

    return "".join(parts).strip()

