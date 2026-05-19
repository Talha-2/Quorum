"""
Observability — structured logging and LLM-call metrics.

A production LLM system has to be observable: every model call's latency,
size, and outcome is recorded so cost and reliability can be tracked. This
module provides a JSON log formatter and a process-wide metrics collector;
the LLM layer feeds it via an instrumenting provider wrapper.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict

# --- Structured logging --------------------------------------------------


class JsonLogFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Anything attached via logger.info(..., extra={"context": {...}}).
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        return json.dumps(payload, default=str)


def configure_logging(log_format: str = "plain", level: int = logging.INFO) -> None:
    """Install a single root handler in the chosen format.

    ``log_format="json"`` emits structured logs (for log aggregators);
    anything else uses a readable plain-text format.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    if log_format.strip().lower() == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        )
    root.addHandler(handler)


# --- LLM-call metrics ----------------------------------------------------


@dataclass
class _ProviderStat:
    calls: int = 0
    failures: int = 0
    latency_ms_total: float = 0.0
    prompt_chars: int = 0
    completion_chars: int = 0


class LLMMetrics:
    """Process-wide aggregate of every LLM call, grouped by provider."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_provider: Dict[str, _ProviderStat] = {}

    def record(
        self,
        provider: str,
        latency_ms: float,
        prompt_chars: int,
        completion_chars: int,
        ok: bool,
    ) -> None:
        with self._lock:
            stat = self._by_provider.setdefault(provider, _ProviderStat())
            stat.calls += 1
            if not ok:
                stat.failures += 1
            stat.latency_ms_total += latency_ms
            stat.prompt_chars += prompt_chars
            stat.completion_chars += completion_chars

    def snapshot(self) -> Dict[str, Any]:
        """A JSON-safe view of the metrics. Token counts are estimates
        (~4 characters per token), suitable for trend and cost tracking."""
        with self._lock:
            providers: Dict[str, Any] = {}
            t_calls = t_failures = t_tokens = 0
            t_latency = 0.0
            for name, s in self._by_provider.items():
                est_tokens = (s.prompt_chars + s.completion_chars) // 4
                providers[name] = {
                    "calls": s.calls,
                    "failures": s.failures,
                    "avg_latency_ms": round(s.latency_ms_total / s.calls, 1)
                    if s.calls
                    else 0.0,
                    "estimated_tokens": est_tokens,
                }
                t_calls += s.calls
                t_failures += s.failures
                t_tokens += est_tokens
                t_latency += s.latency_ms_total
            return {
                "providers": providers,
                "totals": {
                    "calls": t_calls,
                    "failures": t_failures,
                    "estimated_tokens": t_tokens,
                    "avg_latency_ms": round(t_latency / t_calls, 1) if t_calls else 0.0,
                },
            }

    def reset(self) -> None:
        """Clear all metrics. Used by tests."""
        with self._lock:
            self._by_provider.clear()


# Process-wide singleton.
llm_metrics = LLMMetrics()
