"""
Pipeline data models.

Pipeline data model: ontology with entity_types + edge_types,
graph with nodes + edges, agent profiles per entity, project state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ProjectState(str, Enum):
    CREATED = "created"
    ONTOLOGY_GENERATED = "ontology_generated"
    GRAPH_BUILDING = "graph_building"
    GRAPH_COMPLETED = "graph_completed"
    ENV_READY = "env_ready"             # Personas generated
    CONFIG_READY = "config_ready"       # Time/Event/Activity/Platform config generated
    SIMULATING = "simulating"
    SIM_COMPLETED = "sim_completed"
    REPORT_READY = "report_ready"
    FAILED = "failed"


@dataclass
class EntityType:
    name: str            # PascalCase, e.g. "MediaOutlet"
    description: str
    examples: List[str] = field(default_factory=list)
    is_individual: bool = True  # individual person vs group/org


@dataclass
class EdgeType:
    name: str            # UPPER_SNAKE_CASE, e.g. "REPORTS_ON"
    description: str
    source_targets: List[List[str]] = field(default_factory=list)  # [[srcType, tgtType], ...]


@dataclass
class Ontology:
    entity_types: List[EntityType]
    edge_types: List[EdgeType]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_types": [asdict(e) for e in self.entity_types],
            "edge_types": [asdict(e) for e in self.edge_types],
        }


@dataclass
class GraphEntityNode:
    id: str
    name: str
    type: str            # one of the ontology entity_type names
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    is_individual: bool = True


@dataclass
class GraphRelationEdge:
    id: str
    source_id: str
    target_id: str
    type: str            # one of the ontology edge_type names
    description: str = ""
    strength: float = 0.5


@dataclass
class KnowledgeGraph:
    nodes: List[GraphEntityNode] = field(default_factory=list)
    edges: List[GraphRelationEdge] = field(default_factory=list)

    @property
    def stats(self) -> Dict[str, int]:
        types = {n.type for n in self.nodes}
        return {
            "entity_nodes": len(self.nodes),
            "relation_edges": len(self.edges),
            "schema_types": len(types),
        }


@dataclass
class AgentProfile:
    """One agent generated from one entity in the graph.

    The "detailed persona" sections (background, behavior profile, unique
    memory, social network) live INSIDE the long `persona` text — they
    aren't separate fields. The frontend modal parses them out by section
    header at render time.
    """
    id: str
    user_name: str           # e.g. "ofweekcom_718"
    name: str                # human-readable, mirrors entity name
    role: str                # short title
    bio: str                 # ~200 char social media bio
    persona: str             # ~1500-2000 char long-form persona
    expertise: List[str] = field(default_factory=list)
    interested_topics: List[str] = field(default_factory=list)

    # Personality (used for stance + simulation behavior)
    optimism: float = 0.5
    risk_tolerance: float = 0.5
    caution: float = 0.5
    stance: str = "neutral"  # support / oppose / neutral
    bias: str = ""

    # Apparent demographic surface (rendered in the agent detail modal)
    age: Optional[int] = None
    gender: Optional[str] = None        # "male" / "female" / "other"
    mbti: Optional[str] = None          # one of 16 types
    country: Optional[str] = None
    profession: Optional[str] = None

    # Backreference to the source graph node
    source_entity_id: Optional[str] = None
    source_entity_type: Optional[str] = None
    is_individual: bool = True


# ============================================
# Stage 03 — Simulation Config dataclasses
# ============================================

@dataclass
class TimeSimulationConfig:
    """Time-of-day activity configuration for the swarm."""
    total_simulation_hours: int = 72
    minutes_per_round: int = 60
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20

    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5

    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05

    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4

    work_hours: List[int] = field(
        default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    )
    work_activity_multiplier: float = 0.7


@dataclass
class AgentActivityConfig:
    """Per-agent activity configuration for the simulation engine."""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str

    activity_level: float = 0.5            # 0.0-1.0 overall activity
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    response_delay_min: int = 5            # simulated minutes
    response_delay_max: int = 60
    sentiment_bias: float = 0.0            # -1.0 to 1.0
    stance: str = "neutral"                # supportive / opposing / neutral / observer
    influence_weight: float = 1.0


@dataclass
class EventConfig:
    """Initial events + narrative orchestration for the simulation."""
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    # Each post: {content, poster_type, poster_agent_id (filled by post-processor)}
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    hot_topics: List[str] = field(default_factory=list)
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Recommendation algorithm configuration for one platform."""
    platform: str                           # "feed" / "community" / "twitter" / "reddit"
    recency_weight: float = 0.4
    popularity_weight: float = 0.3
    relevance_weight: float = 0.3
    viral_threshold: int = 10
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Wrapper holding everything generated by Stage 03."""
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    event_config: EventConfig = field(default_factory=EventConfig)
    feed_config: Optional[PlatformConfig] = None
    community_config: Optional[PlatformConfig] = None
    generation_reasoning: str = ""          # " | "-joined per-step reasoning
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return {
            "time_config": asdict(self.time_config),
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "feed_config": asdict(self.feed_config) if self.feed_config else None,
            "community_config": asdict(self.community_config) if self.community_config else None,
            "generation_reasoning": self.generation_reasoning,
            "generated_at": self.generated_at,
        }


@dataclass
class PipelineEvent:
    """One log line for the system dashboard."""
    timestamp: str
    level: str           # info / warn / error / success
    message: str
    project_id: str = ""
    stage: str = ""


@dataclass
class Project:
    id: str
    title: str
    brief: str
    constraints: str = ""
    signals: str = ""
    state: ProjectState = ProjectState.CREATED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Uploaded reality-seed documents — list of {filename, text, char_count}
    uploaded_documents: List[Dict[str, Any]] = field(default_factory=list)

    ontology: Optional[Ontology] = None
    graph: Optional[KnowledgeGraph] = None
    agents: List[AgentProfile] = field(default_factory=list)
    events: List[PipelineEvent] = field(default_factory=list)

    # Stage outputs
    simulation_parameters: Optional["SimulationParameters"] = None
    debate_messages: List[Dict[str, Any]] = field(default_factory=list)
    consensus: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None

    def log(self, level: str, message: str, stage: str = "") -> PipelineEvent:
        ev = PipelineEvent(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            message=message,
            project_id=self.id,
            stage=stage,
        )
        self.events.append(ev)
        # Keep only the last 200 events to bound memory
        if len(self.events) > 200:
            self.events = self.events[-200:]
        return ev

    def transition(self, new_state: ProjectState, message: str = "") -> None:
        self.state = new_state
        self.updated_at = datetime.utcnow().isoformat()
        if message:
            self.log("info", message, stage=new_state.value)


def make_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def make_entity_id() -> str:
    return f"ent_{uuid.uuid4().hex[:10]}"


def make_edge_id() -> str:
    return f"rel_{uuid.uuid4().hex[:10]}"


def make_agent_id() -> str:
    return f"agent_{uuid.uuid4().hex[:10]}"
