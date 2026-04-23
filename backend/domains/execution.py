"""
Execution Intelligence Domain

Agents for analyzing delivery risk, project management, and organizational execution.
"""

from typing import List, Dict, Optional
import uuid

try:
    from ..core.types import AgentArchetype, AgentPersonality, Entity, Relationship, Knowledge
    from ..core.knowledge import KnowledgeGraph
    from ..core.agent import Agent, AgentPool
except ImportError:  # pragma: no cover - supports direct script execution
    from core.types import AgentArchetype, AgentPersonality, Entity, Relationship, Knowledge
    from core.knowledge import KnowledgeGraph
    from core.agent import Agent, AgentPool


# Define execution domain agents

RISK_OFFICER = AgentArchetype(
    id=str(uuid.uuid4()),
    name="Risk Officer",
    description="Conservative, focuses on identifying and mitigating risks",
    personality=AgentPersonality(
        optimism=0.3,  # Cautious
        risk_tolerance=0.2,  # Risk-averse
        caution=0.9,  # Very careful
        communication_style="technical"
    ),
    expertise=["project-risk", "delivery-forecasting", "dependency-analysis"],
    responsibilities=["Identify blockers", "Predict delays", "Surface risks early"],
    goals=["Prevent project failures", "Enable informed decisions", "Reduce surprises"],
    constraints=["Conservative estimates", "Evidence-based only"]
)

PM_AGENT = AgentArchetype(
    id=str(uuid.uuid4()),
    name="Product Manager",
    description="Optimistic, focused on value delivery and stakeholder management",
    personality=AgentPersonality(
        optimism=0.8,  # Very optimistic
        risk_tolerance=0.7,  # Risk-seeking
        caution=0.4,  # Willing to take chances
        communication_style="verbose"
    ),
    expertise=["product-strategy", "stakeholder-management", "scope-management"],
    responsibilities=["Drive delivery", "Manage expectations", "Prioritize features"],
    goals=["Ship value", "Delight stakeholders", "Achieve OKRs"],
    constraints=["Must deliver on time", "Customer focus"]
)

TECH_LEAD = AgentArchetype(
    id=str(uuid.uuid4()),
    name="Tech Lead",
    description="Practical, focuses on technical feasibility and quality",
    personality=AgentPersonality(
        optimism=0.5,  # Balanced
        risk_tolerance=0.4,  # Somewhat risk-averse
        caution=0.6,  # Careful about quality
        communication_style="technical"
    ),
    expertise=["architecture", "implementation", "technical-debt"],
    responsibilities=["Ensure quality", "Manage technical scope", "Mentor team"],
    goals=["Build sustainable systems", "Enable team velocity", "Reduce technical debt"],
    constraints=["Code quality matters", "Team sustainability"]
)

QA_AGENT = AgentArchetype(
    id=str(uuid.uuid4()),
    name="QA Lead",
    description="Critical, focused on quality and edge cases",
    personality=AgentPersonality(
        optimism=0.2,  # Pessimistic
        risk_tolerance=0.1,  # Very risk-averse
        caution=0.95,  # Extremely careful
        communication_style="detailed"
    ),
    expertise=["quality-assurance", "testing-strategy", "edge-cases"],
    responsibilities=["Ensure quality", "Find edge cases", "Prevent bugs"],
    goals=["Zero critical bugs", "Comprehensive coverage", "Customer confidence"],
    constraints=["Quality first", "No shortcuts"]
)


def create_execution_agents(knowledge: Knowledge) -> AgentPool:
    """
    Create agents for execution intelligence domain.
    """
    agent_pool = AgentPool(knowledge)

    risk_agent = Agent(RISK_OFFICER, knowledge)
    pm_agent = Agent(PM_AGENT, knowledge)
    tech_agent = Agent(TECH_LEAD, knowledge)
    qa_agent = Agent(QA_AGENT, knowledge)

    agent_pool.add_agent(risk_agent)
    agent_pool.add_agent(pm_agent)
    agent_pool.add_agent(tech_agent)
    agent_pool.add_agent(qa_agent)

    return agent_pool


def build_execution_knowledge_graph(
    artifacts: Dict[str, str]
) -> KnowledgeGraph:
    """
    Build knowledge graph from execution artifacts.

    Args:
        artifacts: Dict of artifact_type -> content
            e.g., {"prd": "...", "github_pr": "...", "issues": "..."}

    Returns:
        KnowledgeGraph with entities and relationships
    """
    graph = KnowledgeGraph("Execution Intelligence", "execution")

    # Create entities from artifacts (simplified - real version would parse deeply)
    project_entity = Entity(
        id="proj-001",
        name="Mobile Checkout v2",
        type="project",
        domain="execution",
        description="Mobile payment checkout redesign",
        attributes={"status": "in_progress", "priority": "high"}
    )
    graph.add_entity(project_entity)

    # Add team entities
    backend_team = Entity(
        id="team-001",
        name="Backend Team",
        type="team",
        domain="execution",
        description="Server-side development",
        attributes={"size": 5}
    )
    graph.add_entity(backend_team)

    mobile_team = Entity(
        id="team-002",
        name="Mobile Team",
        type="team",
        domain="execution",
        description="iOS/Android development",
        attributes={"size": 4}
    )
    graph.add_entity(mobile_team)

    # Add key people
    sarah = Entity(
        id="person-001",
        name="Sarah",
        type="person",
        domain="execution",
        attributes={"role": "PM"}
    )
    graph.add_entity(sarah)

    # Add risk/blocker entities
    api_blocker = Entity(
        id="risk-001",
        name="API Schema Unresolved",
        type="blocker",
        domain="execution",
        description="Backend and mobile haven't locked API contract"
    )
    graph.add_entity(api_blocker)

    # Add relationships
    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()),
        source_id="proj-001",
        target_id="team-001",
        type="depends_on",
        strength=0.9,
        description="Project depends on backend implementation"
    ))

    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()),
        source_id="proj-001",
        target_id="team-002",
        type="depends_on",
        strength=0.9,
        description="Project depends on mobile implementation"
    ))

    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()),
        source_id="proj-001",
        target_id="person-001",
        type="owned_by",
        strength=1.0,
        description="Sarah is PM/owner"
    ))

    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()),
        source_id="risk-001",
        target_id="proj-001",
        type="blocks",
        strength=0.85,
        description="Unresolved API blocks project progress"
    ))

    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()),
        source_id="team-001",
        target_id="team-002",
        type="blocks",
        strength=0.7,
        description="Backend changes impact mobile team"
    ))

    return graph


# Example usage:
# graph = build_execution_knowledge_graph({"prd": "...", "pr": "..."})
# knowledge = graph.to_knowledge()
# agents = create_execution_agents(knowledge)
