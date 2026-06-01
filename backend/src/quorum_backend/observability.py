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
from typing import Any, Dict, Optional

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
    """Process-wide aggregate of every LLM call, grouped by provider and stage."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_provider: Dict[str, _ProviderStat] = {}
        self._by_stage: Dict[str, _ProviderStat] = {}

    def record(
        self,
        provider: str,
        latency_ms: float,
        prompt_chars: int,
        completion_chars: int,
        ok: bool,
        stage: Optional[str] = None,
    ) -> None:
        with self._lock:
            for bucket in (
                self._by_provider.setdefault(provider, _ProviderStat()),
                self._by_stage.setdefault(stage or "unspecified", _ProviderStat()),
            ):
                bucket.calls += 1
                if not ok:
                    bucket.failures += 1
                bucket.latency_ms_total += latency_ms
                bucket.prompt_chars += prompt_chars
                bucket.completion_chars += completion_chars

    @staticmethod
    def _rollup(stats: Dict[str, _ProviderStat]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, s in stats.items():
            est_tokens = (s.prompt_chars + s.completion_chars) // 4
            out[name] = {
                "calls": s.calls,
                "failures": s.failures,
                "avg_latency_ms": round(s.latency_ms_total / s.calls, 1)
                if s.calls
                else 0.0,
                "estimated_tokens": est_tokens,
            }
        return out

    def snapshot(self) -> Dict[str, Any]:
        """A JSON-safe view of the metrics. Token counts are estimates
        (~4 characters per token), suitable for trend and cost tracking."""
        with self._lock:
            providers = self._rollup(self._by_provider)
            stages = self._rollup(self._by_stage)
            t_calls = sum(p["calls"] for p in providers.values())
            t_failures = sum(p["failures"] for p in providers.values())
            t_tokens = sum(p["estimated_tokens"] for p in providers.values())
            t_latency = sum(s.latency_ms_total for s in self._by_provider.values())
            return {
                "providers": providers,
                "stages": stages,
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
            self._by_stage.clear()


# Process-wide singleton.
llm_metrics = LLMMetrics()
