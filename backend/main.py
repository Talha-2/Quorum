"""
Quorum - Multi-agent reasoning platform.

API endpoints for:
- Creating scenarios and running simulations
- Chat with agent pool
- Managing knowledge graphs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import asyncio
import re

try:
    from .config import settings
    from .llm import init_llm
    from .core.types import Scenario
    from .core.agent import AgentPool
    from .core.simulator import ScenarioSimulator
    from .core.chat import ChatInterface
    from .domains.execution import (
        create_execution_agents, build_execution_knowledge_graph
    )
    from .domains.generic import (
        create_generic_agents,
        create_generic_agents_dynamic,
        build_generic_knowledge_graph,
    )
except ImportError:  # pragma: no cover - supports direct script execution
    from config import settings
    from llm import init_llm
    from core.types import Scenario
    from core.agent import AgentPool
    from core.simulator import ScenarioSimulator
    from core.chat import ChatInterface
    from domains.execution import (
        create_execution_agents, build_execution_knowledge_graph
    )
    from domains.generic import (
        create_generic_agents,
        create_generic_agents_dynamic,
        build_generic_knowledge_graph,
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Quorum — multi-agent reasoning platform",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the multi-stage pipeline router
try:
    from .pipeline.router import router as pipeline_router
except ImportError:  # pragma: no cover - supports direct script execution
    from pipeline.router import router as pipeline_router

app.include_router(pipeline_router)

# Global state (in production: use database)
simulations: Dict[str, Any] = {}
chats: Dict[str, ChatInterface] = {}
agent_pools: Dict[str, AgentPool] = {}
simulation_events: Dict[str, List[Dict[str, Any]]] = {}

# ============ Models ============

class SwarmConfigRequest(BaseModel):
    agent_count: Optional[int] = None
    debate_rounds: Optional[int] = None
    max_debate_agents: Optional[int] = None
    scenario_complexity: Optional[str] = None


class InitializeRequest(BaseModel):
    artifacts: Optional[Dict[str, str]] = None
    swarm: Optional[SwarmConfigRequest] = None

class SimulationRequest(BaseModel):
    simulation_id: Optional[str] = None
    domain: str  # "execution", "finance", "policy", etc
    scenario_description: str
    scenario_changes: Dict[str, Any]
    artifacts: Optional[Dict[str, str]] = None  # Domain context
    include_consensus: bool = True
    swarm: Optional[SwarmConfigRequest] = None  # Runtime overrides for debate behavior

class ChatRequest(BaseModel):
    simulation_id: Optional[str] = None
    message: str
    get_consensus: bool = False
    swarm: Optional[SwarmConfigRequest] = None

class ScenarioComparisonRequest(BaseModel):
    simulation_ids: List[str]

# ============ Initialization ============

SUPPORTED_DOMAIN_PRESETS = {
    "generic": {
        "label": "Generic Swarm",
        "description": "Domain-agnostic multi-agent reasoning swarm",
        "mode": "generic",
    },
    "execution": {
        "label": "Execution Intelligence",
        "description": "Preset for delivery, product, and project-risk simulations",
        "mode": "preset",
    },
}


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def normalize_swarm_config(config: Optional[Any] = None) -> Dict[str, Any]:
    raw = config.model_dump(exclude_none=True) if hasattr(config, "model_dump") else dict(config or {})
    agent_count = _clamp_int(raw.get("agent_count"), 6, 2, 18)
    debate_rounds = _clamp_int(raw.get("debate_rounds"), 3, 1, 10)
    max_debate_agents = _clamp_int(raw.get("max_debate_agents"), min(agent_count, 12), 2, 18)
    scenario_complexity = str(raw.get("scenario_complexity") or "high").strip().lower()
    if scenario_complexity not in {"low", "medium", "high", "extreme"}:
        scenario_complexity = "high"

    return {
        "agent_count": agent_count,
        "debate_rounds": debate_rounds,
        "max_debate_agents": min(max_debate_agents, agent_count),
        "scenario_complexity": scenario_complexity,
    }


def resolve_runtime_swarm_config(
    base_config: Optional[Dict[str, Any]],
    override: Optional[SwarmConfigRequest] = None
) -> Dict[str, Any]:
    merged = dict(base_config or {})
    if override:
        merged.update(override.model_dump(exclude_none=True))
    return normalize_swarm_config(merged)


def default_debate_state(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": "idle",
        "mode": None,
        "round": 0,
        "total_rounds": int((config or {}).get("debate_rounds", 0) or 0),
        "focus": None,
        "active_agents": [],
        "active_node_ids": [],
        "recent_round_summaries": [],
        "updated_at": datetime.utcnow().isoformat(),
    }


def _derive_focus_node_ids(graph: Any, focus: Optional[str], round_number: int = 0) -> List[str]:
    if not getattr(graph, "entities", None):
        return []

    entities = list(graph.entities.values())
    active_ids: List[str] = []
    context = next((entity for entity in entities if entity.type == "context"), None)
    if context:
        active_ids.append(context.id)

    tokens = {
        token for token in re.findall(r"[a-z][a-z0-9-]{3,}", (focus or "").lower())
        if token not in {"round", "focus", "under", "with", "next", "most", "high", "medium", "low"}
    }

    for entity in entities:
        haystack = f"{entity.name} {entity.description or ''}".lower()
        if any(token in haystack for token in tokens):
            active_ids.append(entity.id)

    theme_nodes = [entity for entity in entities if entity.type == "theme"]
    if theme_nodes and len(active_ids) <= 1:
        active_ids.append(theme_nodes[round_number % len(theme_nodes)].id)

    seen = []
    for entity_id in active_ids:
        if entity_id not in seen:
            seen.append(entity_id)
    return seen[:6]


async def handle_swarm_progress(simulation_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    sim = simulations.get(simulation_id)
    if not sim:
        return

    debate_state = sim.setdefault("debate_state", default_debate_state(sim.get("swarm_config")))
    round_number = int(payload.get("round", debate_state.get("round", 0)) or 0)
    total_rounds = int(payload.get("total_rounds", debate_state.get("total_rounds", 0)) or 0)
    focus = payload.get("focus")
    active_agents = list(payload.get("active_agents") or debate_state.get("active_agents") or [])

    if event_type in {"debate.started", "debate.round_started", "debate.round_completed"}:
        debate_state.update(
            {
                "status": "running",
                "mode": payload.get("mode", debate_state.get("mode")),
                "round": round_number,
                "total_rounds": total_rounds,
                "focus": focus,
                "active_agents": active_agents,
                "active_node_ids": _derive_focus_node_ids(sim["graph"], focus, round_number=round_number),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

        if event_type == "debate.round_completed":
            recent = list(debate_state.get("recent_round_summaries", []))
            recent.append(
                {
                    "round": round_number,
                    "focus": focus,
                    "summary": payload.get("summary"),
                }
            )
            debate_state["recent_round_summaries"] = recent[-6:]

        title = (
            "Debate started"
            if event_type == "debate.started"
            else f"Debate round {round_number}/{max(total_rounds, 1)}"
        )
        detail = focus or "Round update"
        record_event(simulation_id, event_type, title, detail, metadata=payload)

        if settings.llm_provider == "local" and event_type in {"debate.round_started", "debate.round_completed"}:
            await asyncio.sleep(0.35)
        return

    if event_type in {"scenario.completed"}:
        debate_state.update(
            {
                "status": "completed",
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        return

    if event_type in {"scenario.analysis_started"}:
        debate_state.update(
            {
                "status": "analyzing",
                "mode": "scenario",
                "round": 0,
                "focus": "Initial analysis",
                "active_agents": [],
                "active_node_ids": _derive_focus_node_ids(sim["graph"], payload.get("scenario_description"), round_number=0),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        return

def record_event(
    simulation_id: str,
    event_type: str,
    title: str,
    detail: str,
    level: str = "info",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Store a lightweight activity event for live dashboards."""
    event = {
        "id": f"{simulation_id}-event-{len(simulation_events.get(simulation_id, []))}",
        "type": event_type,
        "title": title,
        "detail": detail,
        "level": level,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }
    simulation_events.setdefault(simulation_id, []).append(event)
    simulation_events[simulation_id] = simulation_events[simulation_id][-50:]
    return event


def serialize_graph(
    graph,
    agent_pool: Optional[AgentPool] = None,
    debate_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Serialize the knowledge graph plus swarm overlay for frontend visualization."""
    active_node_ids = set((debate_state or {}).get("active_node_ids") or [])
    active_agent_names = set((debate_state or {}).get("active_agents") or [])
    nodes = [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "domain": entity.domain,
            "description": entity.description,
            "attributes": {
                **entity.attributes,
                "active_debate": entity.id in active_node_ids,
                "debate_focus": (debate_state or {}).get("focus") if entity.id in active_node_ids else None,
            },
        }
        for entity in graph.entities.values()
    ]
    edges = [
        {
            "id": relationship.id,
            "source": relationship.source_id,
            "target": relationship.target_id,
            "type": relationship.type,
            "strength": min(1.0, relationship.strength + 0.18) if (
                relationship.source_id in active_node_ids or relationship.target_id in active_node_ids
            ) else relationship.strength,
            "description": relationship.description,
            "active": relationship.source_id in active_node_ids or relationship.target_id in active_node_ids,
        }
        for relationship in graph.relationships
    ]
    knowledge_node_count = len(nodes)

    if agent_pool:
        graph_entities = list(graph.entities.values())
        context_node = next(
            (
                entity for entity in graph_entities
                if entity.type in {"context", "project", "system", "initiative"}
            ),
            graph_entities[0] if graph_entities else None,
        )
        theme_nodes = [entity for entity in graph_entities if entity.type == "theme"]

        agent_profiles = agent_pool.get_profiles()
        for index, profile in enumerate(agent_profiles):
            overlay_id = f"swarm-agent-{profile['id']}"
            nodes.append(
                {
                    "id": overlay_id,
                    "name": profile["name"],
                    "type": "agent",
                    "domain": graph.domain,
                    "description": "Swarm agent participating in analysis and debate.",
                    "attributes": {
                        "expertise": profile.get("expertise", []),
                        "optimism": profile.get("personality", {}).get("optimism"),
                        "risk_tolerance": profile.get("personality", {}).get("risk_tolerance"),
                        "memory_size": profile.get("memory_size"),
                        "active_debate": profile["name"] in active_agent_names,
                        "debate_focus": (debate_state or {}).get("focus") if profile["name"] in active_agent_names else None,
                    },
                }
            )

            if context_node:
                is_active = profile["name"] in active_agent_names or (context_node and context_node.id in active_node_ids)
                edges.append(
                    {
                        "id": f"{overlay_id}-context",
                        "source": overlay_id,
                        "target": context_node.id,
                        "type": "analyzes",
                        "strength": 0.92 if is_active else 0.78,
                        "description": f"{profile['name']} analyzes the shared system context",
                        "active": is_active,
                    }
                )

            if theme_nodes:
                primary_theme = theme_nodes[index % len(theme_nodes)]
                is_active = profile["name"] in active_agent_names or primary_theme.id in active_node_ids
                edges.append(
                    {
                        "id": f"{overlay_id}-{primary_theme.id}",
                        "source": overlay_id,
                        "target": primary_theme.id,
                        "type": "specializes_in",
                        "strength": 0.82 if is_active else 0.56,
                        "description": f"{profile['name']} tracks {primary_theme.name}",
                        "active": is_active,
                    }
                )

    agent_node_count = max(0, len(nodes) - knowledge_node_count)
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            **graph.summary(),
            "knowledge_node_count": knowledge_node_count,
            "agent_node_count": agent_node_count,
            "display_node_count": len(nodes),
            "active_round": (debate_state or {}).get("round", 0),
        },
    }


def build_simulation_snapshot(simulation_id: str, include_graph: bool = False) -> Dict[str, Any]:
    """Aggregate the current simulation state for the frontend dashboard."""
    if simulation_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")

    sim = simulations[simulation_id]
    graph = sim["graph"]
    chat = chats[simulation_id]
    history = sim["simulator"].get_simulation_history()
    conversation = chat.get_conversation()

    latest_result = history[-1] if history else None
    snapshot = {
        "simulation_id": simulation_id,
        "domain": sim["domain"],
        "swarm_config": sim["swarm_config"],
        "debate_state": sim.get("debate_state", default_debate_state(sim.get("swarm_config"))),
        "knowledge_summary": graph.summary(),
        "agents": sim["agents"].get_profiles(),
        "events": simulation_events.get(simulation_id, [])[-20:],
        "history": history[-10:],
        "latest_result": latest_result,
        "conversation": [
            {
                "role": message.role,
                "agent_id": message.agent_id,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }
            for message in conversation[-20:]
        ],
        "chat_insights": chat.get_agent_insights(),
        "last_updated": datetime.utcnow().isoformat(),
    }

    if include_graph:
        snapshot["graph"] = serialize_graph(graph, sim["agents"], sim.get("debate_state"))

    return snapshot

async def init_simulation(
    domain: str,
    artifacts: Optional[Dict[str, str]] = None,
    swarm_config: Optional[SwarmConfigRequest] = None
):
    """Initialize a simulation for a preset or arbitrary domain label.

    For non-execution domains, attempts to generate topic-aware personas via
    the LLM (using the brief). Falls back to static templates if generation
    fails or no brief is supplied.
    """
    requested_domain = (domain or "generic").strip().lower()
    mode = SUPPORTED_DOMAIN_PRESETS.get(requested_domain, {}).get("mode", "generic")
    config = normalize_swarm_config(swarm_config)
    sim_id = f"{requested_domain}-{len(simulations)}"

    if requested_domain == "execution":
        graph = build_execution_knowledge_graph(artifacts or {})
        knowledge = graph.to_knowledge()
        agents = create_execution_agents(knowledge)
    else:
        graph = build_generic_knowledge_graph(requested_domain, artifacts or {})
        knowledge = graph.to_knowledge()
        agents = await create_generic_agents_dynamic(
            knowledge,
            artifacts=artifacts or {},
            domain=requested_domain,
            agent_count=config["agent_count"],
        )

    # Create simulator and chat
    async def progress_callback(event_type: str, payload: Dict[str, Any]) -> None:
        await handle_swarm_progress(sim_id, event_type, payload)

    simulator = ScenarioSimulator(agents, knowledge, progress_callback=progress_callback)
    chat = ChatInterface(agents, knowledge, progress_callback=progress_callback)

    simulations[sim_id] = {
        "domain": requested_domain,
        "mode": mode,
        "graph": graph,
        "knowledge": knowledge,
        "simulator": simulator,
        "agents": agents,
        "swarm_config": {
            **config,
            "agent_count": len(agents.agents),
        },
        "debate_state": default_debate_state(config),
    }
    chats[sim_id] = chat
    agent_pools[sim_id] = agents
    simulation_events[sim_id] = []
    record_event(
        sim_id,
        "simulation.initialized",
        f"{knowledge.name} initialized",
        "Agent pool, knowledge graph, and simulator are ready.",
        metadata={
            "domain": requested_domain,
            "agent_count": len(agents.agents),
            "entity_count": len(graph.entities),
            "relationship_count": len(graph.relationships),
            "debate_rounds": config["debate_rounds"],
            "max_debate_agents": min(config["max_debate_agents"], len(agents.agents)),
            "scenario_complexity": config["scenario_complexity"],
        },
    )

    return sim_id

# ============ Routes ============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    try:
        init_llm()
        from .llm import get_llm
        active = get_llm().name
        configured = settings.llm_provider
        if active != configured:
            logger.warning(
                "LLM provider mismatch — configured=%s active=%s. "
                "Falling back to local stub. Check that the provider's package is installed and the API key is valid.",
                configured, active,
            )
        else:
            logger.info("LLM Provider: %s", active)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {str(e)}")
        raise

@app.get("/health")
async def health():
    """Health check.

    Reports both the *configured* provider (from settings) and the *active*
    provider (the one actually serving requests). They diverge when the
    configured provider's package isn't installed or its key is invalid —
    in that case Quorum silently falls back to the local stub. /health is
    where you find that out.
    """
    try:
        from .llm import get_llm
        active = get_llm().name
    except Exception:
        active = "unknown"
    return {
        "status": "healthy",
        "service": settings.app_name,
        "llm_provider_configured": settings.llm_provider,
        "llm_provider_active": active,
        "llm_provider_ok": active == settings.llm_provider,
        # Backwards compat — older clients read this field
        "llm_provider": active,
        "simulation_count": len(simulations),
    }

@app.get("/domains")
async def get_domains():
    """List built-in domain presets and generic mode."""
    return {
        "domains": [
            {
                "id": domain_id,
                **domain_info,
            }
            for domain_id, domain_info in SUPPORTED_DOMAIN_PRESETS.items()
        ]
    }

@app.post("/initialize/{domain}")
async def initialize_simulation(domain: str, request: Optional[InitializeRequest] = None):
    """
    Initialize a new simulation in a domain.

    Domains:
    - execution: Delivery risk, project management
    - finance: Financial forecasting (future)
    - policy: Policy impact analysis (future)
    """
    try:
        artifacts = request.artifacts if request else None
        swarm = request.swarm if request else None
        sim_id = await init_simulation(domain, artifacts, swarm_config=swarm)

        agents = agent_pools[sim_id]
        return {
            "simulation_id": sim_id,
            "domain": domain,
            "agents": agents.get_profiles(),
            "status": "ready",
            "snapshot": build_simulation_snapshot(sim_id, include_graph=True),
        }

    except Exception as e:
        logger.error(f"Initialization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulate")
async def run_simulation(request: SimulationRequest):
    """
    Run a scenario simulation.

    Agents will predict outcomes, debate, reach consensus.
    """
    try:
        # Resolve the target simulation first.
        if request.simulation_id:
            if request.simulation_id not in simulations:
                raise HTTPException(status_code=404, detail="Simulation not found")
            sim_id = request.simulation_id
        elif request.domain not in [s.get("domain") for s in simulations.values()]:
            sim_id = await init_simulation(request.domain, request.artifacts, swarm_config=request.swarm)
        else:
            sim_id = next(
                k for k, v in simulations.items()
                if v.get("domain") == request.domain
            )

        sim = simulations[sim_id]
        simulator = sim["simulator"]
        runtime_swarm = resolve_runtime_swarm_config(sim["swarm_config"], request.swarm)
        live_agent_count = len(sim["agents"].agents)
        if runtime_swarm["agent_count"] != live_agent_count:
            runtime_swarm["agent_count"] = live_agent_count
        record_event(
            sim_id,
            "simulation.started",
            "Scenario run started",
            request.scenario_description,
            metadata={
                "changes": request.scenario_changes,
                "agent_count": live_agent_count,
                "debate_rounds": runtime_swarm["debate_rounds"],
                "max_debate_agents": runtime_swarm["max_debate_agents"],
                "scenario_complexity": runtime_swarm["scenario_complexity"],
            },
        )

        # Create scenario
        scenario = Scenario(
            id=f"scenario-{len(simulator.simulation_history)}",
            description=request.scenario_description,
            changes=request.scenario_changes
        )

        # Run simulation
        result = await simulator.run_scenario(
            scenario,
            include_consensus=request.include_consensus,
            debate_rounds=runtime_swarm["debate_rounds"],
            max_debate_agents=runtime_swarm["max_debate_agents"],
            scenario_complexity=runtime_swarm["scenario_complexity"],
        )
        record_event(
            sim_id,
            "simulation.completed",
            "Scenario run completed",
            request.scenario_description,
            level="success",
            metadata={
                "scenario_result_id": result["simulation_id"],
                "agreement_rate": result["aggregate_analysis"]["agreement_rate"],
                "avg_confidence": result["aggregate_analysis"]["avg_confidence"],
                "debate_rounds": result["aggregate_analysis"]["debate_rounds"],
                "debate_agent_count": result["aggregate_analysis"]["debate_agent_count"],
            },
        )

        return {
            "simulation_id": sim_id,
            "result": result,
            "status": "success",
            "snapshot": build_simulation_snapshot(sim_id, include_graph=True),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/{simulation_id}")
async def chat(simulation_id: str, request: ChatRequest):
    """
    Chat with agent pool.

    User message is routed to all agents (or specified ones).
    Agents respond collaboratively, optionally reaching consensus.
    """
    try:
        if simulation_id not in chats:
            raise HTTPException(status_code=404, detail="Simulation not found")
        if request.simulation_id and request.simulation_id != simulation_id:
            raise HTTPException(status_code=400, detail="Simulation ID mismatch")

        chat = chats[simulation_id]
        sim = simulations[simulation_id]
        runtime_swarm = resolve_runtime_swarm_config(sim["swarm_config"], request.swarm)
        runtime_swarm["agent_count"] = len(sim["agents"].agents)
        record_event(
            simulation_id,
            "chat.started",
            "Agent discussion started",
            request.message,
            metadata={
                "debate_rounds": runtime_swarm["debate_rounds"],
                "max_debate_agents": runtime_swarm["max_debate_agents"],
                "agent_count": runtime_swarm["agent_count"],
            },
        )
        response = await chat.chat(
            request.message,
            get_consensus=request.get_consensus,
            debate_rounds=runtime_swarm["debate_rounds"],
            max_debate_agents=runtime_swarm["max_debate_agents"],
        )
        record_event(
            simulation_id,
            "chat.completed",
            "Agent discussion completed",
            request.message,
            level="success",
            metadata={
                "response_count": len(response.responses),
                "has_consensus": bool(response.consensus),
                "debate_rounds": runtime_swarm["debate_rounds"] if request.get_consensus else 0,
            },
        )
        sim["debate_state"].update(
            {
                "status": "completed",
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

        return {
            "simulation_id": simulation_id,
            "user_message": request.message,
            "responses": [
                {
                    "agent": chats[simulation_id].agent_pool.get_agent(r.agent_id).archetype.name,
                    "message": r.content
                }
                for r in response.responses
            ],
            "consensus": response.consensus,
            "confidence": response.confidence,
            "snapshot": build_simulation_snapshot(simulation_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulation/{simulation_id}/history")
async def get_simulation_history(simulation_id: str):
    """Get simulation history"""
    try:
        if simulation_id not in simulations:
            raise HTTPException(status_code=404, detail="Simulation not found")

        sim = simulations[simulation_id]
        history = sim["simulator"].get_simulation_history()

        return {
            "simulation_id": simulation_id,
            "simulations_run": len(history),
            "history": history
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulation/{simulation_id}/agents")
async def get_agents(simulation_id: str):
    """Get agent pool for simulation"""
    try:
        if simulation_id not in agent_pools:
            raise HTTPException(status_code=404, detail="Simulation not found")

        agents = agent_pools[simulation_id]
        return {
            "simulation_id": simulation_id,
            "agents": agents.get_profiles()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulation/{simulation_id}/knowledge")
async def get_knowledge(simulation_id: str):
    """Get knowledge graph for simulation"""
    try:
        if simulation_id not in simulations:
            raise HTTPException(status_code=404, detail="Simulation not found")

        sim = simulations[simulation_id]
        graph = sim["graph"]

        return {
            "simulation_id": simulation_id,
            "summary": graph.summary(),
            "entity_count": len(graph.entities),
            "relationship_count": len(graph.relationships),
            "nodes": [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "description": entity.description,
                    "attributes": entity.attributes,
                }
                for entity in graph.entities.values()
            ],
            "relationships": [
                {
                    "id": relationship.id,
                    "source": relationship.source_id,
                    "target": relationship.target_id,
                    "type": relationship.type,
                    "strength": relationship.strength,
                    "description": relationship.description,
                }
                for relationship in graph.relationships
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulation/{simulation_id}/graph")
async def get_graph(simulation_id: str):
    """Get graph payload for live visualization."""
    try:
        if simulation_id not in simulations:
            raise HTTPException(status_code=404, detail="Simulation not found")

        return {
            "simulation_id": simulation_id,
            **serialize_graph(
                simulations[simulation_id]["graph"],
                simulations[simulation_id]["agents"],
                simulations[simulation_id].get("debate_state"),
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulation/{simulation_id}/snapshot")
async def get_simulation_snapshot(simulation_id: str, include_graph: bool = False):
    """Get a dashboard-friendly aggregate snapshot of simulation state."""
    try:
        return build_simulation_snapshot(simulation_id, include_graph=include_graph)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare-scenarios")
async def compare_scenarios(request: ScenarioComparisonRequest):
    """
    Compare outcomes across scenarios.
    Which is most likely? Most risky?
    """
    try:
        # Find simulation that has these scenarios
        sim = None
        for s in simulations.values():
            if any(
                sid in [sc["simulation_id"] for sc in s["simulator"].get_simulation_history()]
                for sid in request.simulation_ids
            ):
                sim = s
                break

        if not sim:
            raise HTTPException(status_code=404, detail="Scenarios not found")

        comparison = sim["simulator"].compare_scenarios(request.simulation_ids)
        sim_id = next(
            candidate_id
            for candidate_id, candidate_sim in simulations.items()
            if candidate_sim is sim
        )
        record_event(
            sim_id,
            "simulation.compared",
            "Scenario comparison generated",
            f"Compared {len(request.simulation_ids)} scenario runs",
            metadata={"scenario_ids": request.simulation_ids},
        )

        return {
            "comparison": comparison,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/docs/example-execution")
async def example_execution():
    """Example: Run a generic or execution swarm simulation"""
    return {
        "example": "Generic Swarm",
        "steps": [
            {
                "name": "Initialize",
                "endpoint": "POST /initialize/generic",
                "payload": {
                    "artifacts": {
                        "brief": "We need to evaluate a new AI product launch...",
                        "constraints": "Budget is fixed and hiring is frozen...",
                        "signals": "Customer demand is rising but implementation risk is unclear..."
                    }
                }
            },
            {
                "name": "Run Scenario",
                "endpoint": "POST /simulate",
                "payload": {
                    "domain": "generic",
                    "scenario_description": "What if one critical dependency slips two weeks?",
                    "scenario_changes": {"dependency_delay_days": 14}
                }
            },
            {
                "name": "Chat with Agents",
                "endpoint": "POST /chat/{simulation_id}",
                "payload": {
                    "message": "What are the biggest risks and leverage points?",
                    "get_consensus": True
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug
    )
