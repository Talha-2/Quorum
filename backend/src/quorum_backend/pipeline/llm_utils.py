"""
Shared helpers for the structured-output LLM calls used across the pipeline.

Two responsibilities live here:

1. ``generate_json_with_retry`` — wraps an LLM call that should return JSON
   with one automatic retry on parse failure. Uses the provider's JSON mode
   when available (Gemini ``response_mime_type``, OpenAI ``response_format``)
   to make parse failures rare in the first place. Falls back to regex
   recovery via the supplied parser.

2. ``truncate_messages_by_chars`` and ``format_transcript`` — slice the
   message history by a *character* budget (a rough token proxy) rather
   than a fixed message count, so long debates and long reports don't
   silently lose context.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from quorum_backend.llm import LLMProvider

logger = logging.getLogger(__name__)


# --- JSON retry ----------------------------------------------------------

JsonParser = Callable[[str], Optional[dict]]


async def generate_json_with_retry(
    llm: LLMProvider,
    *,
    system: str,
    user_message: str,
    stage: str,
    parser: JsonParser,
    max_tokens: int = 1024,
    retries: int = 1,
) -> Optional[dict]:
    """Call ``llm.generate`` in JSON mode and parse the result.

    If the response is empty or fails to parse, retries up to ``retries``
    times with a follow-up reminder asking for valid JSON. Returns the parsed
    dict on success or ``None`` if every attempt fails.
    """
    follow_up = (
        "\n\nYour previous response was empty or not valid JSON. "
        "Return ONLY the JSON object the schema asked for, with no prose, "
        "no markdown fences, and no commentary."
    )

    attempt_user = user_message
    last_raw = ""
    for attempt in range(retries + 1):
        try:
            raw = await llm.generate(
                system=system,
                user_message=attempt_user,
                max_tokens=max_tokens,
                json_mode=True,
                stage=stage,
            )
        except Exception as exc:
            logger.warning("[%s] LLM call failed (attempt %d): %s", stage, attempt + 1, exc)
            raise

        last_raw = raw or ""
        parsed = parser(last_raw) if last_raw else None
        if parsed:
            if attempt > 0:
                logger.info("[%s] JSON parse recovered on attempt %d", stage, attempt + 1)
            return parsed

        if attempt < retries:
            logger.warning(
                "[%s] JSON parse failed (attempt %d). Retrying with follow-up prompt.",
                stage,
                attempt + 1,
            )
            attempt_user = user_message + follow_up

    logger.warning(
        "[%s] JSON parse failed after %d attempt(s). Raw start: %s",
        stage,
        retries + 1,
        last_raw[:200],
    )
    return None


# --- Token-budgeted transcript formatting --------------------------------

# Rough rule of thumb: ~4 characters per token for English text. The
# defaults below correspond to ~1500 tokens for an agent turn and ~5000
# tokens for a report section — comfortable for any modern LLM while still
# leaving room for the rest of the prompt.
DEFAULT_AGENT_TURN_CHAR_BUDGET = 6000
DEFAULT_REPORT_SECTION_CHAR_BUDGET = 20000


def _format_one(message: Dict[str, Any]) -> str:
    return (
        f"[R{message.get('round', '?')}] "
        f"{message.get('agent_name', '?')} ({message.get('stance', '?')}): "
        f"{message.get('content', '')}"
    )


def truncate_messages_by_chars(
    messages: Sequence[Dict[str, Any]],
    max_chars: int,
    recent_first: bool = True,
) -> List[Dict[str, Any]]:
    """Return the longest tail (or head) of ``messages`` that fits in ``max_chars``.

    ``recent_first=True`` keeps the most recent messages, dropping the oldest.
    ``recent_first=False`` keeps the earliest messages, dropping the latest.
    """
    if not messages:
        return []

    if recent_first:
        ordered = list(reversed(messages))
    else:
        ordered = list(messages)

    kept: List[Dict[str, Any]] = []
    used = 0
    for m in ordered:
        line_len = len(_format_one(m)) + 1
        if used + line_len > max_chars:
            break
        kept.append(m)
        used += line_len

    return list(reversed(kept)) if recent_first else kept


def format_transcript(
    messages: Sequence[Dict[str, Any]],
    *,
    max_chars: int,
    recent_first: bool = True,
    empty_text: str = "(no messages yet)",
    truncated_marker: str = "… (earlier rounds truncated to fit context budget) …",
) -> str:
    """Render a transcript as one message per line, char-budgeted."""
    if not messages:
        return empty_text

    kept = truncate_messages_by_chars(messages, max_chars, recent_first=recent_first)
    if not kept:
        return empty_text

    body = "\n".join(_format_one(m) for m in kept)
    truncated = len(kept) < len(messages)
    if truncated:
        if recent_first:
            return f"{truncated_marker}\n{body}"
        return f"{body}\n{truncated_marker}"
    return body
