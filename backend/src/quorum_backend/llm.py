"""
LLM abstraction layer - support multiple providers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from quorum_backend.config import settings
from quorum_backend.observability import llm_metrics

logger = logging.getLogger(__name__)


class ContentFilterError(Exception):
    """Raised when an LLM provider rejects a prompt due to a content policy."""


def _extract_retry_delay(error_text: str, default: float = 30.0) -> float:
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
        max_tokens: int = 1024,
    ) -> str:
        raise NotImplementedError


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini API provider (free tier available)."""

    name = "google"
    DEFAULT_RPM = 12
    MAX_RETRIES = 3
    DEFAULT_BACKOFF_SECONDS = 30.0

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.client = genai
        self._recent_request_times: List[float] = []
        self._rate_lock = asyncio.Lock()

    async def _wait_for_rate_limit(self) -> None:
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            self._recent_request_times = [t for t in self._recent_request_times if now - t < 60.0]
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

    async def generate(self, system: str, user_message: str, max_tokens: int = 1024) -> str:
        full_prompt = f"{system}\n\n{user_message}"

        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self.MAX_RETRIES:
            await self._wait_for_rate_limit()
            try:
                model = self.client.GenerativeModel(self.model)
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
                is_quota = (
                    "429" in err_text
                    or "quota" in err_text.lower()
                    or "rate" in err_text.lower()
                )
                if is_quota and attempt < self.MAX_RETRIES - 1:
                    delay = _extract_retry_delay(err_text, default=self.DEFAULT_BACKOFF_SECONDS)
                    logger.warning(
                        "Gemini 429 (attempt %d/%d). Backing off %.1fs.",
                        attempt + 1,
                        self.MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                logger.error("Gemini API error: %s", err_text)
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Gemini call failed without error context")


class AzureProvider(LLMProvider):
    """Azure AI Foundry / Azure OpenAI Service provider."""

    name = "azure"

    MAX_RETRIES = 5
    DEFAULT_BACKOFF_SECONDS = 4.0
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
        msg = choice.message
        if getattr(msg, "content", None):
            return str(msg.content)
        for attr in ("reasoning_content", "reasoning", "thinking"):
            val = getattr(msg, attr, None)
            if val:
                return str(val)
        return None

    async def generate(self, system: str, user_message: str, max_tokens: int = 1024) -> str:
        effective_max_tokens = max(max_tokens + self.REASONING_BUDGET, self.MIN_TOKENS)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_message}]

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
                    raise RuntimeError(
                        f"Azure {self.deployment} returned empty content "
                        f"(finish_reason={response.choices[0].finish_reason})"
                    )
                return text
            except Exception as e:
                last_error = e
                err_text = str(e)
                err_lower = err_text.lower()

                if "content_filter" in err_lower or "responsibleaipolicy" in err_lower:
                    logger.warning(
                        "Azure content filter blocked the prompt for %s. Not retryable.",
                        self.deployment,
                    )
                    raise ContentFilterError(err_text) from e

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
                    backoff = self.DEFAULT_BACKOFF_SECONDS * (1.6**attempt)
                    logger.warning(
                        "Azure %s transient error (attempt %d/%d). Backing off %.1fs. Cause: %s",
                        self.deployment,
                        attempt + 1,
                        self.MAX_RETRIES,
                        backoff,
                        err_text[:160],
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

    async def generate(self, system: str, user_message: str, max_tokens: int = 1024) -> str:
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error("Claude API error: %s", str(e))
            raise


class LocalDeterministicProvider(LLMProvider):
    """Deterministic provider for development/tests."""

    name = "local"

    def __init__(self):
        self.counter = 0

    @staticmethod
    def _extract_section(user_message: str, header: str) -> str:
        pattern = re.escape(header) + r"\s*(.*?)(?:\n[A-Z][A-Z \-/()]+:\n|\Z)"
        match = re.search(pattern, user_message, re.DOTALL)
        return (match.group(1).strip() if match else "").strip()

    @staticmethod
    def _extract_brief(user_message: str) -> str:
        for header in (
            "RESEARCH BRIEF:",
            "BRIEF:",
            "THE QUESTION UNDER STUDY:",
            "THE QUESTION DEBATED:",
        ):
            text = LocalDeterministicProvider._extract_section(user_message, header)
            if text:
                return " ".join(text.splitlines()).strip()
        return "the brief"

    @staticmethod
    def _extract_entity_types(user_message: str) -> list[str]:
        entity_types: list[str] = []
        capture = False
        for raw_line in user_message.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Entity types"):
                capture = True
                continue
            if line.startswith("Edge types"):
                break
            if capture and line.startswith("- "):
                entity_types.append(line[2:].split(":", 1)[0].strip())
        return entity_types

    @staticmethod
    def _extract_edge_types(user_message: str) -> list[str]:
        edge_types: list[str] = []
        capture = False
        for raw_line in user_message.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Edge types"):
                capture = True
                continue
            if capture and line.startswith("- "):
                edge_types.append(line[2:].split(":", 1)[0].strip())
        return edge_types

    @staticmethod
    def _extract_persona_entities(user_message: str) -> list[tuple[str, str, str]]:
        entities: list[tuple[str, str, str]] = []
        for raw_line in user_message.splitlines():
            line = raw_line.strip()
            match = re.match(r"^\d+\.\s+(.*?)\s+\(([^)]+)\)\s+[—-]\s+(.*)$", line)
            if match:
                entities.append((match.group(1).strip(), match.group(2).strip(), match.group(3).strip()))
        return entities

    @staticmethod
    def _extract_json_block(user_message: str) -> list[dict[str, Any]]:
        match = re.search(r"```json\s*(.*?)\s*```", user_message, re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    # The following helpers mirror the existing pipeline expectations.
    def _ontology_payload(self, brief: str) -> str:
        topic = brief[:60] or "Scenario"
        payload = {
            "entity_types": [
                {
                    "name": "DecisionMaker",
                    "description": f"An individual responsible for key choices about {topic}.",
                    "examples": ["Program lead", "Minister", "Executive sponsor"],
                    "is_individual": True,
                },
                {
                    "name": "Expert",
                    "description": "A specialist whose analysis shapes credibility and interpretation.",
                    "examples": ["Researcher", "Analyst", "Advisor"],
                    "is_individual": True,
                },
                {
                    "name": "MediaOutlet",
                    "description": "A publication or broadcast organization framing the public narrative.",
                    "examples": ["Industry newsletter", "National daily", "Trade press"],
                    "is_individual": False,
                },
                {
                    "name": "CommunityGroup",
                    "description": "A community or advocacy constituency affected by the decision.",
                    "examples": ["Users", "Residents", "Interest group"],
                    "is_individual": False,
                },
                {
                    "name": "GovernmentAgency",
                    "description": "A regulator or public institution with formal authority.",
                    "examples": ["Regulator", "Department", "Authority"],
                    "is_individual": False,
                },
                {
                    "name": "Company",
                    "description": "A firm whose incentives or operations are implicated.",
                    "examples": ["Vendor", "Platform", "Operator"],
                    "is_individual": False,
                },
                {
                    "name": "StakeholderGroup",
                    "description": "A coalition or internal bloc with aligned interests.",
                    "examples": ["Employees", "Investors", "Partners"],
                    "is_individual": False,
                },
                {
                    "name": "ResearchInstitution",
                    "description": "An institution producing evidence, precedent, or domain insight.",
                    "examples": ["Lab", "University", "Think tank"],
                    "is_individual": False,
                },
                {
                    "name": "Person",
                    "description": "An individual person whose role is not covered by other types.",
                    "examples": ["Independent commentator"],
                    "is_individual": True,
                },
                {
                    "name": "Organization",
                    "description": "A group or institution whose role is not covered by other types.",
                    "examples": ["Association", "Consortium"],
                    "is_individual": False,
                },
            ],
            "edge_types": [
                {
                    "name": "INFLUENCES",
                    "description": "One actor affects another actor's choices.",
                    "source_targets": [["DecisionMaker", "Company"], ["Expert", "DecisionMaker"]],
                },
                {
                    "name": "RESPONDS_TO",
                    "description": "One actor publicly reacts to another.",
                    "source_targets": [["CommunityGroup", "GovernmentAgency"], ["Company", "MediaOutlet"]],
                },
                {
                    "name": "REPORTS_ON",
                    "description": "A media actor covers another actor or event.",
                    "source_targets": [["MediaOutlet", "Company"], ["MediaOutlet", "GovernmentAgency"]],
                },
                {
                    "name": "REGULATES",
                    "description": "A public authority governs the conduct of another actor.",
                    "source_targets": [["GovernmentAgency", "Company"], ["GovernmentAgency", "StakeholderGroup"]],
                },
                {
                    "name": "PARTNERS_WITH",
                    "description": "Two institutions collaborate on the topic.",
                    "source_targets": [["Company", "ResearchInstitution"], ["Organization", "Company"]],
                },
                {
                    "name": "REPRESENTS",
                    "description": "An actor speaks for or organizes a constituency.",
                    "source_targets": [["StakeholderGroup", "CommunityGroup"], ["DecisionMaker", "StakeholderGroup"]],
                },
            ],
        }
        return json.dumps(payload)

    def _graph_payload(self, user_message: str) -> str:
        entity_types = self._extract_entity_types(user_message) or [
            "DecisionMaker",
            "Expert",
            "MediaOutlet",
            "CommunityGroup",
            "GovernmentAgency",
            "Company",
            "StakeholderGroup",
            "ResearchInstitution",
            "Person",
            "Organization",
        ]
        edge_types = self._extract_edge_types(user_message) or [
            "INFLUENCES",
            "RESPONDS_TO",
            "REPORTS_ON",
            "REGULATES",
            "PARTNERS_WITH",
            "REPRESENTS",
        ]
        names = [
            "Program Lead",
            "Independent Analyst",
            "Daily Ledger",
            "Customer Coalition",
            "National Authority",
            "Core Platform Co",
            "Investor Forum",
            "Policy Lab",
            "Operations Director",
            "Trade Association",
            "Regional Press",
            "Research Council",
        ]
        nodes = []
        for idx, name in enumerate(names):
            node_type = entity_types[idx % len(entity_types)]
            nodes.append(
                {
                    "name": name,
                    "type": node_type,
                    "description": f"{name} is a {node_type} relevant to the project brief.",
                    "is_individual": node_type.lower() in {"decisionmaker", "expert", "person"},
                }
            )

        edges = []
        for idx in range(len(nodes) - 1):
            edges.append(
                {
                    "source": nodes[idx]["name"],
                    "target": nodes[idx + 1]["name"],
                    "type": edge_types[idx % len(edge_types)],
                    "description": f"{nodes[idx]['name']} is connected to {nodes[idx + 1]['name']}.",
                }
            )
        extra_pairs = [(0, 5), (1, 4), (2, 5), (3, 0), (6, 0), (7, 1)]
        for idx, (source_idx, target_idx) in enumerate(extra_pairs, start=len(edges)):
            edges.append(
                {
                    "source": nodes[source_idx]["name"],
                    "target": nodes[target_idx]["name"],
                    "type": edge_types[idx % len(edge_types)],
                    "description": f"{nodes[source_idx]['name']} relates to {nodes[target_idx]['name']}.",
                }
            )
        return json.dumps({"nodes": nodes[:12], "edges": edges[:18]})

    def _persona_payload(self, user_message: str) -> str:
        entities = self._extract_persona_entities(user_message)
        if not entities:
            return "[]"

        roles = [
            ("Strategic lead", "support", 0.62, 0.58, 0.42, "ENTJ"),
            ("Skeptical analyst", "oppose", 0.41, 0.32, 0.78, "INTJ"),
            ("Narrative interpreter", "neutral", 0.56, 0.44, 0.52, "ENFJ"),
        ]
        payload = []
        for idx, (name, entity_type, description) in enumerate(entities):
            role, stance, optimism, risk, caution, mbti = roles[idx % len(roles)]
            payload.append(
                {
                    "role": f"{role} for {entity_type}",
                    "bio": f"{name} tracks the brief closely and interprets it through {entity_type.lower()} incentives.",
                    "persona": (
                        f"Background: {name} is positioned close to the issue and understands why it matters. "
                        f"{description}\n\n"
                        f"Behavior Profile: {name} speaks in concise analytical language, references trade-offs, "
                        f"and tests assumptions before agreeing.\n\n"
                        f"Unique Memory: {name} recalls a previous decision cycle where weak coordination caused "
                        f"avoidable churn and uses that precedent here.\n\n"
                        f"Social Network: {name} is influenced by adjacent stakeholders, institutional peers, "
                        f"and the audiences that reward consistent reasoning."
                    ),
                    "expertise": [entity_type.lower(), "risk", "coordination"],
                    "interested_topics": ["governance", "execution", "public response"],
                    "age": 42
                    if entity_type.lower()
                    not in {
                        "organization",
                        "mediaoutlet",
                        "communitygroup",
                        "governmentagency",
                        "company",
                        "stakeholdergroup",
                        "researchinstitution",
                    }
                    else 30,
                    "gender": "other"
                    if entity_type.lower()
                    in {
                        "organization",
                        "mediaoutlet",
                        "communitygroup",
                        "governmentagency",
                        "company",
                        "stakeholdergroup",
                        "researchinstitution",
                    }
                    else ("female" if idx % 2 else "male"),
                    "mbti": mbti,
                    "country": "United States",
                    "profession": role,
                    "optimism": optimism,
                    "risk_tolerance": risk,
                    "caution": caution,
                    "stance": stance,
                    "bias": "prefers explicit trade-offs over vague optimism",
                }
            )
        return json.dumps(payload)

    def _time_config_payload(self) -> str:
        return json.dumps(
            {
                "total_simulation_hours": 72,
                "minutes_per_round": 60,
                "agents_per_hour_min": 1,
                "agents_per_hour_max": 4,
                "peak_hours": [9, 10, 11, 14, 15, 16, 19, 20],
                "off_peak_hours": [0, 1, 2, 3, 4, 5],
                "morning_hours": [7, 8],
                "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
                "reasoning": "The stub uses a conservative daytime-heavy cadence with an evening tail for commentary.",
            }
        )

    def _event_config_payload(self, user_message: str) -> str:
        type_names = []
        for raw_line in user_message.splitlines():
            line = raw_line.strip()
            if line.startswith("- "):
                type_names.append(line[2:].split(":", 1)[0].strip())
        available = type_names[:4] or ["DecisionMaker", "MediaOutlet", "CommunityGroup"]
        posts = []
        for idx, poster_type in enumerate(available[:3], start=1):
            posts.append(
                {
                    "content": (
                        f"{poster_type} account {idx} frames the issue as a balance between speed, evidence, "
                        f"and stakeholder trust."
                    ),
                    "poster_type": poster_type,
                }
            )
        payload = {
            "hot_topics": ["execution-risk", "stakeholder-trust", "decision-quality", "timing"],
            "narrative_direction": (
                "Early discussion centers on risk and accountability, then shifts toward sequencing and "
                "governance once concrete trade-offs appear."
            ),
            "initial_posts": posts,
            "reasoning": (
                "Starter posts are distributed across the main speaker types so the activation phase begins "
                "with multiple frames in the room."
            ),
        }
        return json.dumps(payload)

    def _agent_config_payload(self, user_message: str) -> str:
        batch = self._extract_json_block(user_message)
        configs = []
        for idx, item in enumerate(batch):
            agent_id = int(item.get("agent_id", idx))
            entity_type = str(item.get("entity_type") or "person").lower()
            is_org = any(
                token in entity_type
                for token in ("agency", "company", "group", "institution", "outlet", "organization")
            )
            configs.append(
                {
                    "agent_id": agent_id,
                    "activity_level": 0.35 if is_org else 0.72,
                    "posts_per_hour": 0.8 if is_org else 1.6,
                    "comments_per_hour": 1.4 if is_org else 3.2,
                    "active_hours": list(range(9, 18)) if is_org else [12, 13, 18, 19, 20, 21, 22],
                    "response_delay_min": 20 if is_org else 3,
                    "response_delay_max": 120 if is_org else 18,
                    "sentiment_bias": 0.1 if idx % 2 == 0 else -0.1,
                    "stance": "supportive" if idx % 3 == 0 else ("opposing" if idx % 3 == 1 else "neutral"),
                    "influence_weight": 2.2 if is_org else 1.0,
                }
            )
        return json.dumps({"agent_configs": configs})

    def _agent_turn_payload(self, user_message: str) -> str:
        name_match = re.search(r"YOUR ASSIGNED PERSPECTIVE:\s*(.*?),\s+a\s+(.*?)\.", user_message)
        agent_name = name_match.group(1).strip() if name_match else "Agent"
        stance_match = re.search(r"INITIAL ANALYTICAL STANCE:\s*(\w+)", user_message)
        stance = (stance_match.group(1).strip().lower() if stance_match else "neutral")
        if stance not in {"support", "oppose", "neutral"}:
            stance = "neutral"
        brief = self._extract_brief(user_message)
        payload = {
            "message": (
                f"{agent_name} reads the brief as a sequencing problem rather than a binary yes-or-no choice. "
                f"It argues that {brief[:90]} requires explicit owners, tighter evidence, and smaller reversible steps."
            ),
            "confidence": 0.72,
            "stance": stance,
        }
        return json.dumps(payload)

    def _consensus_payload(self) -> str:
        return json.dumps(
            {
                "agreed_position": (
                    "The swarm favors a staged approach with explicit owners, concrete thresholds, and evidence "
                    "review before expansion."
                ),
                "agreement_rate": 0.78,
                "confidence_level": 0.74,
                "dissents": [
                    {
                        "agent_name": "Independent Analyst",
                        "position": "Pushes for a slower rollout until external uncertainty is reduced.",
                    }
                ],
            }
        )

    def _report_outline_payload(self) -> str:
        return json.dumps(
            {
                "title": "Structured Findings From The Multi-Agent Debate",
                "summary": (
                    "The debate converged on controlled sequencing, explicit ownership, and tighter validation "
                    "before broader rollout."
                ),
                "sections": [
                    {"title": "Where the swarm converged", "description": "The shared operating pattern that most agents supported."},
                    {"title": "What remained contested", "description": "The main disagreements around timing, confidence, and downside exposure."},
                    {"title": "Operational implications", "description": "Concrete execution implications suggested by the debate."},
                ],
            }
        )

    def _report_section_payload(self, user_message: str) -> str:
        title_match = re.search(r"- Title:\s*(.*)", user_message)
        title = title_match.group(1).strip() if title_match else "Findings"
        return (
            f"The section **{title}** shows a consistent pattern across the debate transcript. "
            "Most agents treat the problem as one of sequencing, ownership, and credibility rather than raw ambition.\n\n"
            "> The system can move faster only if the next dependency is made explicit and governed tightly.\n\n"
            "That position is reinforced by agents who prefer evidence-backed pacing, while dissenters mainly "
            "disagree on how much uncertainty remains acceptable. In operational terms, the debate supports "
            "narrower scope, clearer decision thresholds, and a shorter review loop before further escalation."
        )

    async def generate(self, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.counter += 1
        lower_prompt = user_message.lower()
        system_lower = system.lower()
        agent_name = system.splitlines()[0].replace("You are ", "").strip(". ") if system else "Agent"

        if "ontology designer for a multi-agent simulation engine" in system_lower:
            return self._ontology_payload(self._extract_brief(user_message))
        if "information extraction engine" in system_lower:
            return self._graph_payload(user_message)
        if "persona designer for a scholarly multi-agent reasoning simulation" in system_lower:
            return self._persona_payload(user_message)
        if "social media simulation expert" in system_lower:
            return self._time_config_payload()
        if "public-opinion analyst" in system_lower:
            return self._event_config_payload(user_message)
        if "social media behavior analyst" in system_lower:
            return self._agent_config_payload(user_message)
        if "debate participant in an academic, scholarly multi-agent simulation" in system_lower:
            return self._agent_turn_payload(user_message)
        if "neutral moderator" in system_lower:
            return self._consensus_payload()
        if "senior research analyst writing a structured prediction report" in system_lower:
            return self._report_outline_payload()
        if "senior research analyst writing one section of a multi-agent" in system_lower:
            return self._report_section_payload(user_message)

        if "simulate this scenario" in lower_prompt:
            description = user_message.split("Simulate this scenario:", 1)[-1].strip().splitlines()[0]
            payload = {
                "outcomes": {"System Context": f"Scenario impact assessed for '{description}'"},
                "confidence": 0.66,
                "reasoning": f"{agent_name} sees meaningful but manageable change around '{description}'.",
                "assumptions": ["Local provider stub", "Knowledge graph is static"],
            }
            return json.dumps(payload)

        if "final synthesis" in lower_prompt or "produce a final synthesis" in lower_prompt:
            return (
                "Shared view: the system can absorb the shock only if it narrows scope, clarifies ownership, "
                "and watches the most connected dependency. Unresolved disagreement: how aggressively to trade "
                "resilience for speed. Most likely outcome: short-term turbulence followed by a tighter operating "
                "plan. Recommended next move: assign owners, define thresholds, and review again after the next signal update."
            )

        if "summarize the round" in lower_prompt:
            return (
                "The round converges on one main pressure point, but agents still disagree on how much speed to preserve. "
                "Confidence rises when ownership is explicit and weakens when dependencies remain ambiguous."
            )

        if "consensus" in lower_prompt or "discuss" in lower_prompt:
            return (
                "Agents agree to tighten ownership, monitor the main dependency closely, and make the next decision threshold "
                "explicit before expanding scope."
            )

        return (
            f"As {system.splitlines()[0] if system else 'an agent'}, "
            f"I acknowledge: {user_message[:200]}... "
            "Key focus remains on delivery risks and cross-team alignment."
        )


class InstrumentedProvider(LLMProvider):
    """Wraps a provider to time and record every call (see observability)."""

    def __init__(self, inner: LLMProvider):
        self._inner = inner
        self.name = inner.name

    async def generate(self, system: str, user_message: str, max_tokens: int = 1024) -> str:
        start = time.perf_counter()
        prompt_chars = len(system) + len(user_message)
        completion = ""
        ok = True
        try:
            completion = await self._inner.generate(system, user_message, max_tokens)
            return completion
        except Exception:
            ok = False
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            llm_metrics.record(
                self.name, latency_ms, prompt_chars, len(completion), ok
            )
            logger.info(
                "llm.call provider=%s ok=%s latency_ms=%.0f "
                "prompt_chars=%d completion_chars=%d",
                self.name,
                ok,
                latency_ms,
                prompt_chars,
                len(completion),
            )


def _fallback_local(reason: str) -> LLMProvider:
    logger.warning("%s Falling back to LocalDeterministicProvider.", reason)
    return LocalDeterministicProvider()


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "google":
        if not settings.google_api_key:
            return _fallback_local("GOOGLE_API_KEY not set.")
        logger.info("Using Google Gemini (%s)", settings.google_model)
        try:
            return GoogleGeminiProvider(settings.google_api_key, settings.google_model)
        except Exception as exc:
            return _fallback_local(f"Google Gemini provider initialization failed: {exc}")

    if settings.llm_provider == "azure":
        if not settings.azure_resource_name or not settings.azure_api_key:
            return _fallback_local("AZURE_RESOURCE_NAME or AZURE_API_KEY not set.")
        deployment = settings.azure_chat_model_kimi_25
        if not deployment:
            return _fallback_local("AZURE_CHAT_MODEL_KIMI_25 not set.")
        logger.info(
            "Using Azure AI Foundry (resource=%s, deployment=%s, api_version=%s)",
            settings.azure_resource_name,
            deployment,
            settings.azure_api_version,
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

    if settings.llm_provider == "claude":
        if not settings.anthropic_api_key:
            return _fallback_local("ANTHROPIC_API_KEY not set.")
        logger.info("Using Claude (%s)", settings.claude_model)
        try:
            return ClaudeProvider(settings.anthropic_api_key, settings.claude_model)
        except Exception as exc:
            return _fallback_local(f"Claude provider initialization failed: {exc}")

    if settings.llm_provider == "local":
        logger.info("Using LocalDeterministicProvider (offline/testing mode)")
        return LocalDeterministicProvider()

    return _fallback_local(f"Unknown LLM provider: {settings.llm_provider}.")


_llm_provider: Optional[LLMProvider] = None


def init_llm() -> None:
    global _llm_provider
    try:
        provider = get_llm_provider()
    except Exception as exc:  # pragma: no cover
        provider = _fallback_local(f"LLM initialization failed: {exc}")
    _llm_provider = InstrumentedProvider(provider)


def get_llm() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        init_llm()
    return _llm_provider

