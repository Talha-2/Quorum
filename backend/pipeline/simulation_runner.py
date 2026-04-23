"""
Simulation runner — round-by-round agent debate.

Quorum's pragmatic implementation of the simulation stage. Instead of running
parallel OASIS subprocesses with time-stepped per-hour activity, we run a
sequential round-by-round debate where each round selects a subset of agents
weighted by stance and influence, asks each one to reason about the brief
given the current debate state, and records their action as a debate message.

This is a clean swap point for a real OASIS integration later: the public
interface is `run_simulation(project, rounds)` returning a list of
DebateMessage dicts.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

try:
    from ..llm import get_llm, ContentFilterError
except ImportError:  # pragma: no cover
    from llm import get_llm, ContentFilterError

from .models import AgentProfile, KnowledgeGraph, Project

logger = logging.getLogger(__name__)


AGENT_TURN_PROMPT = """This is an academic, scholarly multi-agent simulation. \
You are providing a research perspective for analytical purposes only.

YOUR ASSIGNED PERSPECTIVE: {name}, a {role}.

BACKGROUND:
{bio}

ANALYTICAL APPROACH:
{persona}

KNOWN BIAS TO ACKNOWLEDGE:
{bias}

INITIAL ANALYTICAL STANCE: {stance}

THE QUESTION UNDER STUDY:
{brief}

CURRENT ROUND: {round_num} of {total_rounds}

PRIOR ANALYSIS FROM OTHER PERSPECTIVES:
{transcript}

It's your turn to contribute. In 2-4 sentences, provide your analytical \
perspective on this question. Draw on your assigned role, expertise, and \
acknowledged bias. Where relevant, respond to or build on the prior analysis. \
This is descriptive scholarship — describe how your perspective views the \
question, do not advocate. Conclude with a confidence score and an updated \
stance.

Return ONLY a JSON object:
{{
  "message": "your 2-4 sentence analytical response",
  "confidence": 0.0,
  "stance": "support" | "oppose" | "neutral"
}}

No markdown, no commentary outside the JSON.
"""


CONSENSUS_PROMPT = """You are a moderator summarizing a multi-agent debate.

THE BRIEF:
{brief}

THE FULL TRANSCRIPT:
{transcript}

Produce a single consensus statement that captures where the swarm landed. List
the dissents — agents whose final position diverged from the majority — with
their reasoning.

Return ONLY a JSON object:
{{
  "agreed_position": "1-3 sentence consensus statement",
  "agreement_rate": 0.0,
  "confidence_level": 0.0,
  "dissents": [
    {{ "agent_name": "name", "position": "their dissenting view in one sentence" }}
  ]
}}

No markdown, no commentary outside the JSON.
"""


def _parse_json_object(raw: str) -> Optional[dict]:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _coerce_float(value, default: float = 0.5) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _select_active_agents(
    agents: List[AgentProfile],
    round_num: int,
    max_per_round: int = 4,
) -> List[AgentProfile]:
    """Pick a small, diverse subset of agents to speak this round.

    Strategy:
      - Round 1: balanced mix of stances (1 support, 1 oppose, 2 neutral)
      - Round 2+: pick by influence (we proxy with risk_tolerance + caution)
        and ensure each agent gets to speak roughly equal times across rounds.
    """
    if not agents:
        return []

    if round_num == 1:
        supporters = [a for a in agents if a.stance == "support"]
        opposers = [a for a in agents if a.stance == "oppose"]
        neutrals = [a for a in agents if a.stance == "neutral"]
        random.shuffle(supporters)
        random.shuffle(opposers)
        random.shuffle(neutrals)
        picked: List[AgentProfile] = []
        if supporters:
            picked.append(supporters[0])
        if opposers:
            picked.append(opposers[0])
        for n in neutrals[:max_per_round - len(picked)]:
            picked.append(n)
        # Top up from any pool if we still have room
        remaining = [a for a in agents if a not in picked]
        random.shuffle(remaining)
        picked.extend(remaining[:max(0, max_per_round - len(picked))])
        return picked[:max_per_round]

    # Round 2+: rotate through agents using a deterministic stride
    stride = max(1, len(agents) // max_per_round)
    offset = (round_num - 1) % stride
    picked = [agents[(offset + i * stride) % len(agents)] for i in range(max_per_round)]
    return picked[:max_per_round]


def _format_transcript(messages: List[Dict[str, Any]], max_recent: int = 8) -> str:
    if not messages:
        return "(no messages yet — you are the first to speak)"
    recent = messages[-max_recent:]
    return "\n".join(
        f"- {m.get('agent_name', 'unknown')} ({m.get('stance', 'neutral')}): {m.get('content', '')}"
        for m in recent
    )


async def run_simulation(
    project: Project,
    total_rounds: int = 3,
    agents_per_round: int = 4,
) -> List[Dict[str, Any]]:
    """Run the debate end-to-end. Returns the message list (also written to project)."""
    brief = project.brief
    agents = project.agents
    if not agents:
        return []

    messages: List[Dict[str, Any]] = []
    project.debate_messages = messages

    llm = get_llm()

    for round_num in range(1, total_rounds + 1):
        active = _select_active_agents(agents, round_num, max_per_round=agents_per_round)
        project.log("info", f"Round {round_num}/{total_rounds}: {len(active)} agents speaking", stage="simulating")

        for agent in active:
            transcript = _format_transcript(messages)
            user_msg = AGENT_TURN_PROMPT.format(
                name=agent.name,
                role=agent.role,
                bio=agent.bio,
                persona=agent.persona,
                bias=agent.bias or "(none stated)",
                stance=agent.stance,
                brief=brief,
                round_num=round_num,
                total_rounds=total_rounds,
                transcript=transcript,
            )

            try:
                raw = await llm.generate(
                    system=(
                        "You are a debate participant in an academic, scholarly "
                        "multi-agent simulation. You analyze the brief from your "
                        "assigned perspective for research purposes. Stay in "
                        "character. Return only the JSON object."
                    ),
                    user_message=user_msg,
                    max_tokens=900,
                )
            except ContentFilterError:
                # Content policy violation — surface to the project event log
                # so the user understands why this agent didn't speak.
                project.log(
                    "warn",
                    f"{agent.name} skipped (content filter blocked the prompt)",
                    stage="simulating",
                )
                continue
            except Exception as exc:
                logger.warning("Agent turn LLM call failed for %s: %s", agent.name, exc)
                project.log(
                    "warn",
                    f"{agent.name} skipped (LLM error)",
                    stage="simulating",
                )
                continue

            parsed = _parse_json_object(raw)
            if not parsed:
                continue

            content = str(parsed.get("message") or "").strip()
            if not content:
                continue

            stance = str(parsed.get("stance") or agent.stance).lower()
            if stance not in {"support", "oppose", "neutral"}:
                stance = "neutral"

            message = {
                "id": f"msg_{round_num}_{len(messages) + 1}",
                "agent_id": agent.id,
                "agent_user_name": agent.user_name,
                "agent_name": agent.name,
                "agent_role": agent.role,
                "round": round_num,
                "content": content,
                "confidence": _coerce_float(parsed.get("confidence"), 0.7),
                "stance": stance,
            }
            messages.append(message)
            project.log(
                "info",
                f"{agent.name} spoke ({stance}, conf={message['confidence']:.2f})",
                stage="simulating",
            )

    return messages


async def generate_consensus(project: Project) -> Optional[Dict[str, Any]]:
    """Ask the LLM to summarize the debate into a consensus statement."""
    if not project.debate_messages:
        return None

    transcript_lines = []
    for m in project.debate_messages:
        transcript_lines.append(
            f"[R{m.get('round', '?')}] {m.get('agent_name', '?')} ({m.get('stance', '?')}): {m.get('content', '')}"
        )
    transcript = "\n".join(transcript_lines)

    prompt = CONSENSUS_PROMPT.format(brief=project.brief, transcript=transcript)

    try:
        llm = get_llm()
        raw = await llm.generate(
            system="You are a neutral moderator. Return only the JSON object.",
            user_message=prompt,
            max_tokens=900,
        )
    except Exception as exc:
        logger.warning("Consensus LLM call failed: %s", exc)
        return None

    parsed = _parse_json_object(raw)
    if not parsed:
        return None

    consensus = {
        "agreed_position": str(parsed.get("agreed_position") or "").strip(),
        "agreement_rate": _coerce_float(parsed.get("agreement_rate"), 0.75),
        "confidence_level": _coerce_float(parsed.get("confidence_level"), 0.75),
        "dissents": [
            {
                "agent_name": str(d.get("agent_name") or "").strip(),
                "position": str(d.get("position") or "").strip(),
            }
            for d in (parsed.get("dissents") or [])
            if isinstance(d, dict)
        ],
    }
    project.consensus = consensus
    return consensus


async def chat_with_agent(
    project: Project,
    agent: AgentProfile,
    user_message: str,
) -> Optional[str]:
    """Stage 5: deep interaction. The user asks one specific agent a question."""
    transcript_summary = _format_transcript(project.debate_messages, max_recent=12)
    consensus_str = ""
    if project.consensus:
        consensus_str = (
            f"FINAL CONSENSUS: {project.consensus.get('agreed_position', '')}\n"
            f"AGREEMENT RATE: {project.consensus.get('agreement_rate', 0):.0%}"
        )

    system = (
        f"You are {agent.name}, a {agent.role}. Stay completely in character. "
        f"You just participated in a debate about: {project.brief}\n\n"
        f"YOUR BIO: {agent.bio}\n"
        f"YOUR PERSONA: {agent.persona}\n"
        f"YOUR BIAS: {agent.bias or '(none stated)'}\n\n"
        f"WHAT WAS DISCUSSED:\n{transcript_summary}\n\n"
        f"{consensus_str}\n\n"
        "Answer the user's follow-up question in 2-4 sentences. Speak in your "
        "voice. Do not break character."
    )

    try:
        llm = get_llm()
        raw = await llm.generate(
            system=system,
            user_message=user_message,
            max_tokens=400,
        )
    except Exception as exc:
        logger.warning("Deep interaction LLM call failed: %s", exc)
        return None

    return (raw or "").strip()
