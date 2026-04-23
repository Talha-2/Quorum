"""
LLM abstraction layer - support multiple providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import logging
import json
import re

try:
    from .config import settings
except ImportError:  # pragma: no cover - supports direct script execution
    from config import settings

logger = logging.getLogger(__name__)


class ContentFilterError(Exception):
    """Raised when an LLM provider rejects a prompt due to a content policy.

    Callers (e.g. simulation_runner) catch this specifically so they can
    skip the turn cleanly without retrying or surfacing it as a 500.
    """
    pass


def _extract_retry_delay(error_text: str, default: float = 30.0) -> float:
    """Pull `retry_delay { seconds: N }` out of a Gemini 429 error message.

    Gemini's 429 errors include a structured retry_delay protobuf in the
    string representation. We parse it so backoff matches what the API asks
    for instead of guessing. Falls back to `default` if no match.
    """
    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_text)
    if match:
        return float(match.group(1)) + 1.0  # +1s safety margin
    return default


class LLMProvider(ABC):
    """Base class for LLM providers"""

    name: str = "unknown"

    @abstractmethod
    async def generate(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """Generate response from LLM"""
        pass


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini API provider (free tier available).

    Includes:
      - Per-request rate limiting (default 12 req/min, well under the
        gemini-2.0-flash 15 RPM free tier ceiling)
      - 429 retry with backoff that honors the API's retry_delay hint
      - Bounded retries (3 attempts) before giving up
    """

    name = "google"

    # How many requests per minute we allow ourselves to send. Set below the
    # advertised free-tier ceiling of the chosen model:
    #   gemini-2.5-flash:      5 RPM
    #   gemini-2.0-flash:     15 RPM  ← default
    #   gemini-2.0-flash-lite: 30 RPM
    DEFAULT_RPM = 12
    MAX_RETRIES = 3
    DEFAULT_BACKOFF_SECONDS = 30.0

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.client = genai
        # Local rate limiter — list of recent request timestamps
        self._recent_request_times: List[float] = []
        self._rate_lock = asyncio.Lock()

    async def _wait_for_rate_limit(self) -> None:
        """Sleep just long enough to stay under DEFAULT_RPM requests/minute."""
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            # Drop timestamps older than 60 seconds
            self._recent_request_times = [
                t for t in self._recent_request_times if now - t < 60.0
            ]
            if len(self._recent_request_times) >= self.DEFAULT_RPM:
                oldest = self._recent_request_times[0]
                sleep_for = 60.0 - (now - oldest) + 0.5
                if sleep_for > 0:
                    logger.info("Rate limit guard: sleeping %.1fs", sleep_for)
                    await asyncio.sleep(sleep_for)
                    now = asyncio.get_event_loop().time()
                    self._recent_request_times = [
                        t for t in self._recent_request_times if now - t < 60.0
                    ]
            self._recent_request_times.append(now)

    async def generate(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """Generate response using Gemini, with rate limiting and 429 retry."""
        full_prompt = f"{system}\n\n{user_message}"

        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self.MAX_RETRIES:
            await self._wait_for_rate_limit()

            try:
                model = self.client.GenerativeModel(self.model)
                # generate_content is sync; run it in a thread so we don't
                # block the event loop and we can interleave with the limiter
                response = await asyncio.to_thread(
                    model.generate_content,
                    full_prompt,
                    generation_config=self.client.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.7,
                    ),
                )
                return response.text
            except Exception as e:
                last_error = e
                err_text = str(e)
                is_quota = "429" in err_text or "quota" in err_text.lower() or "rate" in err_text.lower()
                if is_quota and attempt < self.MAX_RETRIES - 1:
                    delay = _extract_retry_delay(err_text, default=self.DEFAULT_BACKOFF_SECONDS)
                    logger.warning(
                        "Gemini 429 (attempt %d/%d). Backing off %.1fs.",
                        attempt + 1, self.MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                logger.error("Gemini API error: %s", err_text)
                raise

        # All retries exhausted
        if last_error:
            raise last_error
        raise RuntimeError("Gemini call failed without error context")


class AzureProvider(LLMProvider):
    """Azure AI Foundry / Azure OpenAI Service provider.

    Speaks the OpenAI-compatible chat completions API at:
        https://{resource}.services.ai.azure.com/models

    Designed for reasoning models like Kimi K2.5 hosted on Azure AI Foundry.
    Reasoning models split their token budget between `reasoning_content`
    (chain-of-thought) and `content` (the actual response). If max_tokens is
    too tight, all the budget goes to reasoning and `content` comes back
    None. This provider always inflates the requested budget so there's room
    for both.

    Also handles the shared-deployment 429 ("server at maximum concurrent
    capacity") with bounded retry + backoff.
    """

    name = "azure"

    MAX_RETRIES = 5
    DEFAULT_BACKOFF_SECONDS = 4.0
    # When a caller asks for N output tokens, we send max(N + REASONING_BUDGET, MIN_TOKENS)
    # so reasoning models still produce a non-empty content field.
    # Kimi K2.5's reasoning_content can easily consume 2000-3000 tokens before
    # producing the actual response, so we need substantial headroom.
    REASONING_BUDGET = 3000
    MIN_TOKENS = 2048

    def __init__(
        self,
        resource_name: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-05-01-preview",
    ):
        self.resource_name = resource_name
        self.api_key = api_key
        self.deployment = deployment
        self.api_version = api_version
        from openai import OpenAI
        endpoint = f"https://{resource_name}.services.ai.azure.com/models"
        self.client = OpenAI(
            base_url=endpoint,
            api_key=api_key,
            default_query={"api-version": api_version},
        )

    @staticmethod
    def _extract_response_text(choice) -> Optional[str]:
        """Pull the actual reply out of an OpenAI ChatCompletion choice.

        For reasoning models the standard `content` field can be None when
        the budget was consumed by reasoning. In that case we return the
        reasoning_content as a fallback so we never lose the model's output.
        """
        msg = choice.message
        if getattr(msg, "content", None):
            return str(msg.content)
        # Reasoning fallback (Kimi-style)
        for attr in ("reasoning_content", "reasoning", "thinking"):
            val = getattr(msg, attr, None)
            if val:
                return str(val)
        return None

    async def generate(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 1024,
    ) -> str:
        # Inflate budget so reasoning models leave room for actual content
        effective_max_tokens = max(max_tokens + self.REASONING_BUDGET, self.MIN_TOKENS)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self.MAX_RETRIES:
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.deployment,
                    messages=messages,
                    max_tokens=effective_max_tokens,
                    temperature=0.7,
                )
                text = self._extract_response_text(response.choices[0])
                if not text:
                    # Empty response with no reasoning either — surface as error
                    raise RuntimeError(
                        f"Azure {self.deployment} returned empty content "
                        f"(finish_reason={response.choices[0].finish_reason})"
                    )
                return text
            except Exception as e:
                last_error = e
                err_text = str(e)
                err_lower = err_text.lower()

                # Content policy violations are NOT transient — retrying will
                # always hit the same filter. Log a clear warning so the
                # caller knows why this turn was skipped.
                if "content_filter" in err_lower or "responsibleaipolicy" in err_lower:
                    logger.warning(
                        "Azure content filter blocked the prompt for %s. "
                        "This is not retryable — caller should skip this turn.",
                        self.deployment,
                    )
                    raise ContentFilterError(err_text) from e

                # Azure transient signals:
                #   429 — rate limit
                #   503 — service unavailable
                #   529 — overloaded (Kimi MaaS shared deployment)
                #   "maximum concurrent capacity" — Kimi shared deployment full
                is_transient = (
                    "429" in err_text
                    or "503" in err_text
                    or "529" in err_text
                    or "capacity" in err_lower
                    or "overloaded" in err_lower
                    or "unavailable" in err_lower
                    or "rate" in err_lower
                    or "timeout" in err_lower
                    or "timed out" in err_lower
                )
                if is_transient and attempt < self.MAX_RETRIES - 1:
                    backoff = self.DEFAULT_BACKOFF_SECONDS * (1.6 ** attempt)
                    logger.warning(
                        "Azure %s transient error (attempt %d/%d). Backing off %.1fs. Cause: %s",
                        self.deployment, attempt + 1, self.MAX_RETRIES, backoff, err_text[:160],
                    )
                    await asyncio.sleep(backoff)
                    attempt += 1
                    continue
                logger.error("Azure API error: %s", err_text[:500])
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Azure call failed without error context")


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""

    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.api_key = api_key
        self.model = model
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)

    async def generate(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """Generate response using Claude"""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            raise


class LocalDeterministicProvider(LLMProvider):
    """
    Deterministic provider for development/tests.
    Generates lightweight, locally computed responses so
    we can run the stack without external APIs.
    """

    name = "local"

    def __init__(self):
        self.counter = 0

    async def generate(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        self.counter += 1
        lower_prompt = user_message.lower()
        agent_name = system.splitlines()[0].replace("You are ", "").strip(". ") if system else "Agent"

        if "debate round" in lower_prompt:
            focus = "current focus"
            for line in user_message.splitlines():
                if line.lower().startswith("round focus:"):
                    focus = line.split(":", 1)[-1].strip()
                    break
            return (
                f"{agent_name} updates its position around {focus.lower()}. "
                f"It keeps one core claim, challenges one weak assumption in the room, "
                f"and asks the swarm to watch the most fragile dependency next."
            )

        if "simulate this scenario" in lower_prompt:
            # Return structured JSON so scenario parsing succeeds
            description = user_message.split("Simulate this scenario:", 1)[-1].strip().splitlines()[0]
            role_outcomes = {
                "Risk Radar": {
                    "outcomes": {
                        "Critical Dependency": "Higher probability of slippage and cascading risk",
                        "Stakeholder Alignment": "Confidence drops unless updates become more frequent",
                    },
                    "confidence": 0.62,
                    "reasoning": f"{agent_name} sees downside concentration around '{description}' and expects hidden fragility to surface.",
                },
                "Opportunity Scout": {
                    "outcomes": {
                        "Experiment Window": "Pressure creates room for narrower, faster bets",
                        "Decision Velocity": "Escalation can force sharper prioritization",
                    },
                    "confidence": 0.68,
                    "reasoning": f"{agent_name} treats '{description}' as a forcing function for focus and option selection.",
                },
                "Systems Mapper": {
                    "outcomes": {
                        "Dependency Network": "Second-order effects propagate through handoffs and ownership gaps",
                        "Coordination Load": "Cross-functional overhead rises before stabilizing",
                    },
                    "confidence": 0.74,
                    "reasoning": f"{agent_name} expects '{description}' to amplify the most connected nodes in the graph.",
                },
                "Decision Synthesizer": {
                    "outcomes": {
                        "Decision Queue": "Tradeoff pressure increases and unresolved choices become bottlenecks",
                        "Operating Plan": "The team needs a simpler plan with explicit thresholds",
                    },
                    "confidence": 0.71,
                    "reasoning": f"{agent_name} expects '{description}' to force earlier decisions and clearer guardrails.",
                },
            }
            chosen = next(
                (payload for key, payload in role_outcomes.items() if agent_name.startswith(key)),
                {
                    "outcomes": {
                        "System Context": f"Scenario impact assessed for '{description}'",
                        "Operating Tempo": "Moderate turbulence with recoverable disruption",
                    },
                    "confidence": 0.66,
                    "reasoning": f"{agent_name} sees meaningful but manageable change around '{description}'.",
                },
            )
            payload = {
                "outcomes": chosen["outcomes"],
                "confidence": chosen["confidence"],
                "reasoning": chosen["reasoning"],
                "assumptions": ["Local provider stub", "Knowledge graph is static"]
            }
            return json.dumps(payload)

        if "final synthesis" in lower_prompt or "produce a final synthesis" in lower_prompt:
            return (
                "Shared view: the system can absorb the shock only if it narrows scope, "
                "clarifies ownership, and watches the most connected dependency. "
                "Unresolved disagreement: how aggressively to trade resilience for speed. "
                "Most likely outcome: short-term turbulence followed by a tighter operating plan. "
                "Recommended next move: assign owners, define thresholds, and review again after the next signal update."
            )

        if "summarize the round" in lower_prompt:
            return (
                "The round converges on one main pressure point, but agents still disagree on how much speed to preserve. "
                "Confidence rises when ownership is explicit and weakens when dependencies remain ambiguous."
            )

        if "consensus" in lower_prompt or "discuss" in lower_prompt:
            return (
                "Agents agree to tighten ownership, monitor the main dependency closely, "
                "and make the next decision threshold explicit before expanding scope."
            )

        # Default: simple informative response
        return (
            f"As {system.splitlines()[0] if system else 'an agent'}, "
            f"I acknowledge: {user_message[:200]}... "
            "Key focus remains on delivery risks and cross-team alignment."
        )


def _fallback_local(reason: str) -> LLMProvider:
    """Use the local provider instead of failing application startup."""
    logger.warning("%s Falling back to LocalDeterministicProvider.", reason)
    return LocalDeterministicProvider()


def get_llm_provider() -> LLMProvider:
    """Get configured LLM provider"""

    if settings.llm_provider == "google":
        if not settings.google_api_key:
            return _fallback_local("GOOGLE_API_KEY not set.")
        logger.info(f"Using Google Gemini ({settings.google_model})")
        try:
            return GoogleGeminiProvider(
                settings.google_api_key,
                settings.google_model
            )
        except Exception as exc:
            return _fallback_local(f"Google Gemini provider initialization failed: {exc}")

    elif settings.llm_provider == "azure":
        if not settings.azure_resource_name or not settings.azure_api_key:
            return _fallback_local("AZURE_RESOURCE_NAME or AZURE_API_KEY not set.")
        deployment = settings.azure_chat_model_kimi_25
        if not deployment:
            return _fallback_local("AZURE_CHAT_MODEL_KIMI_25 not set.")
        logger.info(
            "Using Azure AI Foundry (resource=%s, deployment=%s, api_version=%s)",
            settings.azure_resource_name, deployment, settings.azure_api_version,
        )
        try:
            return AzureProvider(
                resource_name=settings.azure_resource_name,
                api_key=settings.azure_api_key,
                deployment=deployment,
                api_version=settings.azure_api_version,
            )
        except Exception as exc:
            return _fallback_local(f"Azure provider initialization failed: {exc}")

    elif settings.llm_provider == "claude":
        if not settings.anthropic_api_key:
            return _fallback_local("ANTHROPIC_API_KEY not set.")
        logger.info(f"Using Claude ({settings.claude_model})")
        try:
            return ClaudeProvider(
                settings.anthropic_api_key,
                settings.claude_model
            )
        except Exception as exc:
            return _fallback_local(f"Claude provider initialization failed: {exc}")

    elif settings.llm_provider == "local":
        logger.info("Using LocalDeterministicProvider (offline/testing mode)")
        return LocalDeterministicProvider()

    else:
        return _fallback_local(f"Unknown LLM provider: {settings.llm_provider}.")


# Global LLM instance
_llm_provider: LLMProvider = None


def init_llm():
    """Initialize LLM provider"""
    global _llm_provider
    try:
        _llm_provider = get_llm_provider()
    except Exception as exc:  # pragma: no cover - defensive startup guard
        _llm_provider = _fallback_local(f"LLM initialization failed: {exc}")


def get_llm() -> LLMProvider:
    """Get LLM provider"""
    if _llm_provider is None:
        init_llm()
    return _llm_provider
