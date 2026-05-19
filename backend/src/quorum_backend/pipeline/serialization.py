"""
Project (de)serialization.

The :class:`Project` aggregate is persisted as a single JSON document. These
helpers convert it to and from a plain dict so it can be stored in a SQL
``JSON`` column — no pickling of Python objects, which keeps the store
portable, inspectable, and safe to load.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Dict, Optional, Type, TypeVar

from quorum_backend.pipeline.models import (
    AgentActivityConfig,
    AgentProfile,
    EdgeType,
    EntityType,
    EventConfig,
    GraphEntityNode,
    GraphRelationEdge,
    KnowledgeGraph,
    Ontology,
    PipelineEvent,
    PlatformConfig,
    Project,
    ProjectState,
    SimulationParameters,
    TimeSimulationConfig,
)

# Bump when the persisted shape changes in a way that needs a data migration.
SCHEMA_VERSION = 1

_T = TypeVar("_T")


def project_to_dict(project: Project) -> Dict[str, Any]:
    """Serialize a project to a JSON-safe dict."""
    data = asdict(project)
    data["state"] = project.state.value  # store the plain enum value
    data["_schema_version"] = SCHEMA_VERSION
    return data


def _build(cls: Type[_T], data: Optional[dict]) -> Optional[_T]:
    """Construct a flat dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return None
    valid = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})


def project_from_dict(data: Dict[str, Any]) -> Project:
    """Reconstruct a project from a dict produced by :func:`project_to_dict`."""
    ontology = None
    if data.get("ontology"):
        ont = data["ontology"]
        ontology = Ontology(
            entity_types=[_build(EntityType, e) for e in ont.get("entity_types", [])],
            edge_types=[_build(EdgeType, e) for e in ont.get("edge_types", [])],
        )

    graph = None
    if data.get("graph"):
        g = data["graph"]
        graph = KnowledgeGraph(
            nodes=[_build(GraphEntityNode, n) for n in g.get("nodes", [])],
            edges=[_build(GraphRelationEdge, e) for e in g.get("edges", [])],
        )

    simulation_parameters = None
    if data.get("simulation_parameters"):
        sp = data["simulation_parameters"]
        simulation_parameters = SimulationParameters(
            time_config=_build(TimeSimulationConfig, sp.get("time_config"))
            or TimeSimulationConfig(),
            agent_configs=[
                _build(AgentActivityConfig, a) for a in sp.get("agent_configs", [])
            ],
            event_config=_build(EventConfig, sp.get("event_config")),
            feed_config=_build(PlatformConfig, sp.get("feed_config")),
            community_config=_build(PlatformConfig, sp.get("community_config")),
            generation_reasoning=sp.get("generation_reasoning", ""),
            generated_at=sp.get("generated_at") or "",
        )

    project = Project(
        id=data["id"],
        title=data.get("title", ""),
        brief=data.get("brief", ""),
        constraints=data.get("constraints", ""),
        signals=data.get("signals", ""),
        domain=data.get("domain", "general"),
        state=ProjectState(data.get("state", ProjectState.CREATED.value)),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        uploaded_documents=list(data.get("uploaded_documents", [])),
        ontology=ontology,
        graph=graph,
        agents=[_build(AgentProfile, a) for a in data.get("agents", [])],
        events=[_build(PipelineEvent, e) for e in data.get("events", [])],
        simulation_parameters=simulation_parameters,
        activation=_build(EventConfig, data.get("activation")),
        debate_messages=list(data.get("debate_messages", [])),
        consensus=data.get("consensus"),
        report=data.get("report"),
        last_error=data.get("last_error"),
    )
    return project
