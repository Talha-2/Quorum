"""
Report generator — Stage 06 of the pipeline.

Two-stage report generation against the in-memory project state:

  - Stage 1: planner LLM call designs a 2-5 section outline from the
    debate transcript + consensus + agent profiles
  - Stage 2: one LLM call per section writes the section body using the
    same in-memory state as evidence
  - Streams progress to the project event log for the system dashboard

The output is a `Report` containing:
  - title, summary
  - sections: [{title, content}]
  - markdown_content: the full report rendered as markdown

Robustness: every LLM call has a try/except + fallback so a single failure
produces a partial report rather than breaking the run.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

try:
    from ..llm import get_llm, ContentFilterError
except ImportError:  # pragma: no cover
    from llm import get_llm, ContentFilterError

from .models import Project

logger = logging.getLogger(__name__)


# ============================================
# Prompts
# ============================================

PLAN_SYSTEM_PROMPT = (
    "You are a senior research analyst writing a structured prediction "
    "report from a multi-agent simulation. Return ONLY valid JSON. "
    "Plan a focused outline — minimum 2 sections, maximum 5 sections, no "
    "subsections. Each section title should describe a concrete finding "
    "from the simulation, not a generic category."
)


PLAN_USER_TEMPLATE = """A multi-agent reasoning simulation has just finished. Plan a structured report on its findings.

THE QUESTION THAT WAS DEBATED:
{brief}

CONTEXT THE SIMULATION USED:
{context}

WHAT THE SIMULATION PRODUCED:
- {n_agents} agents (representing real-world entities) participated
- {n_messages} agent messages across {n_rounds} rounds
- {n_topics} hot topics: {hot_topics}
- {dissents_summary}

CONSENSUS REACHED:
{consensus_excerpt}

Plan a 2-5 section outline that explains what the simulation revealed. Each section should be a concrete finding, not a category label.

Return ONLY this JSON:
{{
  "title": "Report title (8-15 words)",
  "summary": "One sentence capturing the core finding",
  "sections": [
    {{
      "title": "Concrete section title describing a finding",
      "description": "1 sentence about what this section will cover"
    }}
  ]
}}
"""


SECTION_SYSTEM_PROMPT = (
    "You are a senior research analyst writing one section of a multi-agent "
    "simulation report. Write in clear, factual prose. Quote agent statements "
    "verbatim where they support a point. Do not invent content the simulation "
    "did not produce. Output 200-400 words of markdown body — no headings."
)


SECTION_USER_TEMPLATE = """Write the body for this section of the report.

REPORT TITLE: {report_title}
REPORT SUMMARY: {report_summary}

THIS SECTION:
- Title: {section_title}
- Description: {section_description}

THE QUESTION DEBATED:
{brief}

RELEVANT EVIDENCE FROM THE SIMULATION:

Agents who participated:
{agent_list}

Debate transcript (round-by-round):
{transcript}

Consensus reached:
{consensus_text}

Write 200-400 words of markdown body for this section. No heading. Quote agents directly with `>` blockquote syntax where relevant. Be concrete — name specific agents, cite specific things they said.
"""


# ============================================
# JSON parsing
# ============================================


def _parse_json_object(raw: str) -> Optional[dict]:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", s)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# ============================================
# Context builders
# ============================================


def _build_agent_list(project: Project, max_agents: int = 12) -> str:
    """Compact agent roster for the section-writer prompt."""
    if not project.agents:
        return "(no agents available)"
    lines: List[str] = []
    for a in project.agents[:max_agents]:
        line = f"- {a.name} (@{a.user_name}, {a.role}, stance: {a.stance})"
        if a.bias:
            line += f" — bias: {a.bias}"
        lines.append(line)
    if len(project.agents) > max_agents:
        lines.append(f"- … plus {len(project.agents) - max_agents} more agents")
    return "\n".join(lines)


def _build_transcript(project: Project, max_messages: int = 30) -> str:
    """Compact debate transcript for the section-writer prompt."""
    if not project.debate_messages:
        return "(no debate messages recorded)"
    msgs = project.debate_messages[:max_messages]
    lines: List[str] = []
    for m in msgs:
        round_num = m.get("round", "?")
        agent_name = m.get("agent_name", "?")
        stance = m.get("stance", "?")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"[R{round_num}] {agent_name} ({stance}): {content}")
    if len(project.debate_messages) > max_messages:
        lines.append(f"… plus {len(project.debate_messages) - max_messages} more messages")
    return "\n".join(lines)


def _build_consensus_text(project: Project) -> str:
    if not project.consensus:
        return "(no consensus reached)"
    c = project.consensus
    parts = [f"Agreed position: {c.get('agreed_position', '(none)')}"]
    if c.get("agreement_rate") is not None:
        parts.append(f"Agreement rate: {(c['agreement_rate'] * 100):.0f}%")
    if c.get("confidence_level") is not None:
        parts.append(f"Confidence: {(c['confidence_level'] * 100):.0f}%")
    dissents = c.get("dissents") or []
    if dissents:
        parts.append("Dissents:")
        for d in dissents:
            parts.append(f"  - {d.get('agent_name', '?')}: {d.get('position', '')}")
    return "\n".join(parts)


# ============================================
# Stage 1 — outline planner
# ============================================


def _fallback_outline(project: Project) -> Dict[str, Any]:
    """Used when the planner LLM call fails. Always produces a usable outline."""
    return {
        "title": f"Simulation findings: {project.title[:60]}",
        "summary": (
            project.consensus.get("agreed_position", "Agents debated the brief.")
            if project.consensus
            else "Agents debated the brief."
        )[:200],
        "sections": [
            {
                "title": "What the agents agreed on",
                "description": "The shared position the swarm converged on.",
            },
            {
                "title": "Where the agents disagreed",
                "description": "The dissents and the reasoning behind them.",
            },
            {
                "title": "Key implications",
                "description": "What the debate suggests for next steps.",
            },
        ],
    }


async def _plan_outline(project: Project) -> Dict[str, Any]:
    """Run the planner LLM call. Returns dict with title/summary/sections."""
    n_agents = len(project.agents)
    n_messages = len(project.debate_messages)
    rounds = {m.get("round", 0) for m in project.debate_messages}
    n_rounds = max(rounds) if rounds else 0

    hot_topics: List[str] = []
    if project.simulation_parameters and project.simulation_parameters.event_config:
        hot_topics = project.simulation_parameters.event_config.hot_topics
    n_topics = len(hot_topics)

    consensus_excerpt = "(no consensus)"
    dissents_summary = "no dissents recorded"
    if project.consensus:
        consensus_excerpt = (project.consensus.get("agreed_position") or "")[:300]
        n_dissents = len(project.consensus.get("dissents") or [])
        dissents_summary = (
            f"{n_dissents} dissenting agents" if n_dissents else "no dissenting agents"
        )

    context = (
        f"Constraints: {project.constraints}" if project.constraints else "(no extra context)"
    )

    user = PLAN_USER_TEMPLATE.format(
        brief=project.brief,
        context=context,
        n_agents=n_agents,
        n_messages=n_messages,
        n_rounds=n_rounds,
        n_topics=n_topics,
        hot_topics=", ".join(hot_topics) if hot_topics else "(none)",
        dissents_summary=dissents_summary,
        consensus_excerpt=consensus_excerpt,
    )

    try:
        llm = get_llm()
        raw = await llm.generate(
            system=PLAN_SYSTEM_PROMPT,
            user_message=user,
            max_tokens=1500,
        )
    except ContentFilterError:
        logger.warning("Report planning blocked by content filter; using fallback outline")
        return _fallback_outline(project)
    except Exception as exc:
        logger.warning("Report planning LLM call failed: %s; using fallback outline", exc)
        return _fallback_outline(project)

    parsed = _parse_json_object(raw or "")
    if not parsed or not isinstance(parsed, dict):
        return _fallback_outline(project)

    sections_raw = parsed.get("sections") or []
    sections: List[Dict[str, str]] = []
    for s in sections_raw[:5]:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or "").strip()
        desc = str(s.get("description") or "").strip()
        if title:
            sections.append({"title": title, "description": desc})

    if len(sections) < 2:
        return _fallback_outline(project)

    return {
        "title": str(parsed.get("title") or f"Findings: {project.title[:60]}").strip(),
        "summary": str(parsed.get("summary") or "").strip(),
        "sections": sections,
    }


# ============================================
# Stage 2 — section writer
# ============================================


async def _write_section(
    project: Project,
    report_title: str,
    report_summary: str,
    section_title: str,
    section_description: str,
) -> str:
    """Run the section-writer LLM call. Returns the section markdown body."""
    user = SECTION_USER_TEMPLATE.format(
        report_title=report_title,
        report_summary=report_summary,
        section_title=section_title,
        section_description=section_description,
        brief=project.brief,
        agent_list=_build_agent_list(project),
        transcript=_build_transcript(project),
        consensus_text=_build_consensus_text(project),
    )

    try:
        llm = get_llm()
        raw = await llm.generate(
            system=SECTION_SYSTEM_PROMPT,
            user_message=user,
            max_tokens=1800,
        )
    except ContentFilterError:
        logger.warning("Section '%s' blocked by content filter", section_title)
        return f"_(Section blocked by content filter — see project events for details.)_"
    except Exception as exc:
        logger.warning("Section '%s' LLM call failed: %s", section_title, exc)
        return f"_(Section failed: {exc})_"

    body = (raw or "").strip()
    if not body:
        return "_(Empty response — section unavailable.)_"
    return body


# ============================================
# Top-level orchestrator
# ============================================


async def generate_report(
    project: Project,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Generate the full report. Returns a dict ready to assign to project.report.

    The dict shape:
        {
            "title": str,
            "summary": str,
            "sections": [{"title": str, "content": str}],
            "markdown": str,        # full rendered report
            "generated_at": str,
        }
    """
    from datetime import datetime

    def _report(msg: str) -> None:
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass
        logger.info(msg)

    _report("Step 1/2: planning report outline…")
    outline = await _plan_outline(project)

    title = outline["title"]
    summary = outline["summary"]
    sections_meta: List[Dict[str, str]] = outline["sections"]

    written_sections: List[Dict[str, str]] = []
    for i, sec in enumerate(sections_meta):
        _report(f"Step 2/2: writing section {i + 1}/{len(sections_meta)} — {sec['title']}")
        content = await _write_section(
            project=project,
            report_title=title,
            report_summary=summary,
            section_title=sec["title"],
            section_description=sec.get("description", ""),
        )
        written_sections.append({"title": sec["title"], "content": content})

    # Render the full markdown
    md_parts: List[str] = [f"# {title}\n"]
    if summary:
        md_parts.append(f"> {summary}\n")
    for sec in written_sections:
        md_parts.append(f"\n## {sec['title']}\n\n{sec['content']}\n")
    markdown = "\n".join(md_parts)

    return {
        "title": title,
        "summary": summary,
        "sections": written_sections,
        "markdown": markdown,
        "generated_at": datetime.utcnow().isoformat(),
    }
