"""
Generic Quorum swarm domain.

This module turns arbitrary artifacts into a generic
multi-agent simulation workspace instead of requiring
execution-specific entities.
"""

from typing import Dict, List, Optional
import re
import uuid

try:
    from ..core.types import AgentArchetype, AgentPersonality, Entity, Relationship, Knowledge
    from ..core.knowledge import KnowledgeGraph
    from ..core.agent import Agent, AgentPool
except ImportError:  # pragma: no cover - supports direct script execution
    from core.types import AgentArchetype, AgentPersonality, Entity, Relationship, Knowledge
    from core.knowledge import KnowledgeGraph
    from core.agent import Agent, AgentPool


def _normalize_domain_label(domain: str) -> str:
    label = (domain or "generic").replace("-", " ").replace("_", " ").strip()
    return label.title() if label else "Generic"


def _base_archetype_templates(label: str) -> List[Dict[str, object]]:
    label_key = label.lower()
    return [
        {
            "name": "Systems Mapper",
            "description": f"Maps dependencies and second-order effects across the {label} system",
            "personality": {
                "optimism": 0.45,
                "risk_tolerance": 0.35,
                "caution": 0.7,
                "communication_style": "technical",
            },
            "expertise": [label_key, "systems-thinking", "causal-analysis"],
            "responsibilities": ["Map dependencies", "Identify leverage points", "Surface cascades"],
            "goals": ["Clarify the system", "Show cause and effect", "Reduce blind spots"],
            "constraints": ["Needs explicit assumptions", "Prefers structured context"],
        },
        {
            "name": "Opportunity Scout",
            "description": f"Looks for upside, momentum, and strategic openings in the {label} domain",
            "personality": {
                "optimism": 0.78,
                "risk_tolerance": 0.68,
                "caution": 0.38,
                "communication_style": "concise",
            },
            "expertise": [label_key, "strategy", "option-discovery"],
            "responsibilities": ["Find growth opportunities", "Spot momentum", "Suggest pivots"],
            "goals": ["Unlock upside", "Preserve optionality", "Increase velocity"],
            "constraints": ["Can underrate execution drag", "Pushes for movement"],
        },
        {
            "name": "Risk Radar",
            "description": f"Pressure-tests scenarios and downside exposure for the {label} system",
            "personality": {
                "optimism": 0.24,
                "risk_tolerance": 0.18,
                "caution": 0.92,
                "communication_style": "detailed",
            },
            "expertise": [label_key, "risk-analysis", "failure-modes"],
            "responsibilities": ["Stress test assumptions", "Highlight downside", "Quantify uncertainty"],
            "goals": ["Prevent surprises", "Expose fragility", "Improve resilience"],
            "constraints": ["Conservative bias", "Needs evidence before confidence"],
        },
        {
            "name": "Decision Synthesizer",
            "description": f"Converts debate into tradeoffs, choices, and next steps for the {label} domain",
            "personality": {
                "optimism": 0.56,
                "risk_tolerance": 0.48,
                "caution": 0.58,
                "communication_style": "balanced",
            },
            "expertise": [label_key, "decision-making", "synthesis"],
            "responsibilities": ["Summarize debate", "Clarify tradeoffs", "Recommend next actions"],
            "goals": ["Drive clear decisions", "Maintain coherence", "Make output actionable"],
            "constraints": ["Depends on other agents for raw analysis"],
        },
        {
            "name": "Constraint Optimizer",
            "description": f"Examines resource ceilings, sequencing pressure, and bottlenecks in the {label} system",
            "personality": {
                "optimism": 0.4,
                "risk_tolerance": 0.32,
                "caution": 0.74,
                "communication_style": "structured",
            },
            "expertise": [label_key, "operations", "resource-planning"],
            "responsibilities": ["Track bottlenecks", "Evaluate sequencing", "Flag resource limits"],
            "goals": ["Keep plans feasible", "Prevent overload", "Reduce waste"],
            "constraints": ["May deprioritize upside if capacity is thin"],
        },
        {
            "name": "Stakeholder Advocate",
            "description": f"Represents stakeholder incentives, friction, and alignment risks across the {label} environment",
            "personality": {
                "optimism": 0.52,
                "risk_tolerance": 0.36,
                "caution": 0.68,
                "communication_style": "balanced",
            },
            "expertise": [label_key, "stakeholder-mapping", "alignment"],
            "responsibilities": ["Surface incentives", "Spot friction", "Translate tradeoffs"],
            "goals": ["Maintain trust", "Preserve alignment", "Reduce hidden conflict"],
            "constraints": ["Needs clear stakeholder context to be precise"],
        },
        {
            "name": "Scenario Architect",
            "description": f"Builds compound stress cases and explores alternative futures for the {label} system",
            "personality": {
                "optimism": 0.5,
                "risk_tolerance": 0.52,
                "caution": 0.62,
                "communication_style": "exploratory",
            },
            "expertise": [label_key, "scenario-planning", "counterfactuals"],
            "responsibilities": ["Compound scenario shocks", "Test branches", "Probe thresholds"],
            "goals": ["Expand the search space", "Reveal non-obvious futures", "Sharpen decisions"],
            "constraints": ["Can generate more branches than a team can act on"],
        },
        {
            "name": "Adversarial Challenger",
            "description": f"Argues the strongest opposing case to prevent groupthink in the {label} swarm",
            "personality": {
                "optimism": 0.3,
                "risk_tolerance": 0.42,
                "caution": 0.88,
                "communication_style": "blunt",
            },
            "expertise": [label_key, "critical-reasoning", "counterarguments"],
            "responsibilities": ["Challenge assumptions", "Expose weak logic", "Force rigor"],
            "goals": ["Prevent consensus drift", "Raise reasoning quality", "Break groupthink"],
            "constraints": ["Can slow convergence when evidence is weak"],
        },
        {
            "name": "Research Analyst",
            "description": f"Collects evidence, patterns, and weak signals relevant to the {label} operating context",
            "personality": {
                "optimism": 0.47,
                "risk_tolerance": 0.28,
                "caution": 0.72,
                "communication_style": "analytical",
            },
            "expertise": [label_key, "research", "signal-detection"],
            "responsibilities": ["Track evidence", "Differentiate noise", "Support claims"],
            "goals": ["Ground debate in evidence", "Raise confidence", "Reduce speculation"],
            "constraints": ["Needs enough signal to separate trends from anecdotes"],
        },
        {
            "name": "Execution Operator",
            "description": f"Focuses on coordination, pacing, and delivery realism for the {label} workflow",
            "personality": {
                "optimism": 0.48,
                "risk_tolerance": 0.34,
                "caution": 0.76,
                "communication_style": "practical",
            },
            "expertise": [label_key, "execution", "coordination"],
            "responsibilities": ["Sequence work", "Coordinate owners", "Maintain operating rhythm"],
            "goals": ["Keep motion steady", "Reduce thrash", "Turn plans into execution"],
            "constraints": ["Prefers clarity over speculation"],
        },
    ]


def _theme_specialist_templates(label: str, themes: List[str]) -> List[Dict[str, object]]:
    label_key = label.lower()
    templates: List[Dict[str, object]] = []

    for theme in themes:
        theme_name = theme.replace("-", " ").strip().title()
        theme_key = theme.replace(" ", "-").lower()
        if not theme_name:
            continue
        templates.append(
            {
                "name": f"{theme_name} Specialist",
                "description": f"Tracks how {theme_name.lower()} shapes choices inside the {label} system",
                "personality": {
                    "optimism": 0.5,
                    "risk_tolerance": 0.44,
                    "caution": 0.64,
                    "communication_style": "focused",
                },
                "expertise": [label_key, theme_key, "domain-analysis"],
                "responsibilities": [f"Monitor {theme_name.lower()} signals", "Connect theme to decisions", "Surface tradeoffs"],
                "goals": [f"Clarify the impact of {theme_name.lower()}", "Keep decisions grounded in context", "Reduce blind spots"],
                "constraints": ["Only as strong as the extracted artifacts"],
            }
        )

    return templates


def _instantiate_archetype(template: Dict[str, object], variant_index: int = 0) -> AgentArchetype:
    personality_payload = dict(template["personality"])
    if variant_index:
        delta = 0.04 if variant_index % 2 else -0.04
        personality_payload["optimism"] = min(max(personality_payload["optimism"] + delta, 0.05), 0.95)
        personality_payload["risk_tolerance"] = min(max(personality_payload["risk_tolerance"] + delta, 0.05), 0.95)
        personality_payload["caution"] = min(max(personality_payload["caution"] - delta, 0.05), 0.95)

    name = str(template["name"])
    if variant_index:
        name = f"{name} Cell {variant_index + 1}"

    description = str(template["description"])
    if variant_index:
        description = f"{description} This cell explores an alternative angle to widen the swarm."

    return AgentArchetype(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        personality=AgentPersonality(**personality_payload),
        expertise=list(template["expertise"]),
        responsibilities=list(template["responsibilities"]),
        goals=list(template["goals"]),
        constraints=list(template["constraints"]),
    )


def _build_generic_archetypes(
    domain: str,
    agent_count: int = 6,
    themes: Optional[List[str]] = None
) -> List[AgentArchetype]:
    label = _normalize_domain_label(domain)
    requested = max(4, min(int(agent_count or 6), 18))
    templates = _base_archetype_templates(label)
    if themes:
        templates.extend(_theme_specialist_templates(label, themes[:6]))

    archetypes: List[AgentArchetype] = []
    slot = 0
    while len(archetypes) < requested:
        template = templates[slot % len(templates)]
        variant_index = slot // len(templates)
        archetypes.append(_instantiate_archetype(template, variant_index=variant_index))
        slot += 1

    return archetypes


def create_generic_agents(
    knowledge: Knowledge,
    domain: str = "generic",
    agent_count: int = 6
) -> AgentPool:
    """Create a reusable swarm for any domain label using static templates.

    For topic-aware personas, prefer create_generic_agents_dynamic which uses
    the LLM to design a custom panel for the brief.
    """
    agent_pool = AgentPool(knowledge)
    themes = [
        entity.name.lower().replace(" ", "-")
        for entity in knowledge.entities
        if entity.type == "theme"
    ]

    for archetype in _build_generic_archetypes(domain, agent_count=agent_count, themes=themes):
        agent_pool.add_agent(Agent(archetype, knowledge))

    return agent_pool


async def create_generic_agents_dynamic(
    knowledge: Knowledge,
    artifacts: Optional[Dict[str, str]] = None,
    domain: str = "generic",
    agent_count: int = 6,
) -> AgentPool:
    """Create a swarm whose personas are designed by the LLM for this brief.

    Falls back to the static template pool if the LLM call fails or the brief
    is empty. The pool always contains agent_count agents.
    """
    try:
        from .dynamic_personas import generate_dynamic_personas
    except ImportError:  # pragma: no cover
        from domains.dynamic_personas import generate_dynamic_personas

    artifacts = artifacts or {}
    brief = (artifacts.get("brief") or "").strip()
    constraints = (artifacts.get("constraints") or "").strip()
    signals = (artifacts.get("signals") or "").strip()

    context_parts = []
    if constraints:
        context_parts.append(f"Constraints: {constraints}")
    if signals:
        context_parts.append(f"Signals: {signals}")
    context = "\n".join(context_parts)

    archetypes = None
    if brief:
        archetypes = await generate_dynamic_personas(
            brief=brief,
            context=context,
            count=agent_count,
        )

    if not archetypes:
        # Fallback: static templates
        return create_generic_agents(knowledge, domain=domain, agent_count=agent_count)

    agent_pool = AgentPool(knowledge)
    for archetype in archetypes:
        agent_pool.add_agent(Agent(archetype, knowledge))
    return agent_pool


def _extract_keywords(artifacts: Dict[str, str]) -> List[str]:
    corpus = " ".join(artifacts.values()).lower()
    tokens = re.findall(r"[a-z][a-z0-9-]{3,}", corpus)
    stop_words = {
        "that", "with", "from", "this", "have", "into", "should", "would",
        "there", "about", "their", "which", "while", "where", "when", "needs",
        "still", "after", "before", "team", "project", "system", "domain",
        "because", "through", "these", "those", "being", "using", "issue",
    }

    seen: List[str] = []
    for token in tokens:
        if token in stop_words or token in seen:
            continue
        seen.append(token)
        if len(seen) == 4:
            break

    return seen


def build_generic_knowledge_graph(domain: str, artifacts: Dict[str, str]) -> KnowledgeGraph:
    """Build a generic graph from arbitrary artifacts."""
    label = _normalize_domain_label(domain)
    graph = KnowledgeGraph(f"{label} Swarm", domain or "generic")

    context = Entity(
        id="context-001",
        name=f"{label} System",
        type="context",
        domain=domain or "generic",
        description=f"Primary decision context for the {label} swarm",
        attributes={"artifact_count": len(artifacts)},
    )
    graph.add_entity(context)

    artifact_entities: List[Entity] = []
    for index, (artifact_type, content) in enumerate(artifacts.items(), start=1):
        entity = Entity(
            id=f"artifact-{index:03d}",
            name=artifact_type.replace("_", " ").title(),
            type="artifact",
            domain=domain or "generic",
            description=(content[:180] + "...") if len(content) > 180 else content,
            attributes={
                "source_key": artifact_type,
                "length": len(content),
            },
        )
        graph.add_entity(entity)
        artifact_entities.append(entity)

        graph.add_relationship(Relationship(
            id=str(uuid.uuid4()),
            source_id=entity.id,
            target_id=context.id,
            type="informs",
            strength=0.82,
            description=f"{entity.name} informs the shared decision context",
        ))

    for index, keyword in enumerate(_extract_keywords(artifacts), start=1):
        theme = Entity(
            id=f"theme-{index:03d}",
            name=keyword.replace("-", " ").title(),
            type="theme",
            domain=domain or "generic",
            description=f"Potential theme extracted from {label} artifacts",
            attributes={"signal": "inferred"},
        )
        graph.add_entity(theme)

        graph.add_relationship(Relationship(
            id=str(uuid.uuid4()),
            source_id=context.id,
            target_id=theme.id,
            type="focuses_on",
            strength=0.64,
            description=f"{label} system focuses on {theme.name}",
        ))

        for artifact in artifact_entities[:2]:
            graph.add_relationship(Relationship(
                id=str(uuid.uuid4()),
                source_id=artifact.id,
                target_id=theme.id,
                type="signals",
                strength=0.58,
                description=f"{artifact.name} signals relevance to {theme.name}",
            ))

    if not artifact_entities:
        default_signal = Entity(
            id="artifact-000",
            name="Seed Brief",
            type="artifact",
            domain=domain or "generic",
            description="No artifacts supplied yet; swarm booted with a minimal default brief.",
            attributes={"source_key": "seed"},
        )
        graph.add_entity(default_signal)
        graph.add_relationship(Relationship(
            id=str(uuid.uuid4()),
            source_id=default_signal.id,
            target_id=context.id,
            type="informs",
            strength=0.5,
            description="Seed brief initializes the swarm context",
        ))

    return graph
