"""
FastAPI router for the 5-stage Quorum pipeline.

Endpoints:

  POST /api/projects                                  → create project
  GET  /api/projects/{id}                             → fetch project state
  POST /api/projects/{id}/graph/ontology/generate     → Stage 1a: ontology
  POST /api/projects/{id}/graph/build                 → Stage 1b: build graph
  POST /api/projects/{id}/env/setup                   → Stage 2: generate agents
  POST /api/projects/{id}/simulation/start            → Stage 3: run debate
  POST /api/projects/{id}/report/generate             → Stage 4: report
  POST /api/projects/{id}/agents/{agent_id}/chat      → Stage 5: deep interaction

The whole pipeline runs against an in-process project store. State is held in
the `_projects` dict. For production this would be a database — the swap is
isolated to this file.
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from .env_setup import generate_agents_for_graph
from .file_parser import (
    SUPPORTED_EXTENSIONS,
    aggregate_documents,
    extract_text_from_bytes,
)
from .graph_builder import InMemoryGraphBuilder
from .models import Project, ProjectState, make_project_id
from .ontology_generator import generate_ontology
from .report_generator import generate_report
from .simulation_config_generator import generate_simulation_parameters
from .simulation_runner import chat_with_agent, generate_consensus, run_simulation

logger = logging.getLogger(__name__)


# ============================================
# In-process project store + on-disk persistence
# ============================================
#
# Projects are kept in memory for performance but also pickled to disk so
# they survive backend restarts (uvicorn --reload) — that was a constant
# source of friction during dev. Pickle is fine here because:
#   - this is a local dev tool, not a multi-tenant service
#   - the project dataclasses have nested dataclass fields that JSON can't
#     reconstruct without an explicit schema-aware loader
#   - any pickle incompatibility (e.g. after a model schema change) is
#     handled by the load function — it just logs a warning and starts fresh
#
# The store path can be overridden via QUORUM_PROJECT_STORE_PATH for tests.

_projects: Dict[str, Project] = {}
_PROJECT_STORE_PATH = Path(
    os.environ.get(
        "QUORUM_PROJECT_STORE_PATH",
        str(Path(__file__).resolve().parent.parent / ".quorum_projects.pkl"),
    )
)


def _save_projects_to_disk() -> None:
    """Persist the entire project store atomically (write-then-rename)."""
    try:
        _PROJECT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = _PROJECT_STORE_PATH.with_suffix(".pkl.tmp")
        with tmp_path.open("wb") as f:
            pickle.dump(_projects, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(_PROJECT_STORE_PATH)
    except Exception as exc:
        # Persistence failure should never break a request — log and move on
        logger.warning("Failed to save project store: %s", exc)


def _load_projects_from_disk() -> None:
    """Load any previously-persisted projects on startup."""
    global _projects
    if not _PROJECT_STORE_PATH.exists():
        return
    try:
        with _PROJECT_STORE_PATH.open("rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            _projects = data
            logger.info(
                "Loaded %d project(s) from %s",
                len(_projects), _PROJECT_STORE_PATH,
            )
    except Exception as exc:
        # Likely a schema mismatch from an updated dataclass. Drop the file
        # and start fresh — the user can always recreate the project.
        logger.warning(
            "Failed to load project store at %s (%s). Starting with empty store.",
            _PROJECT_STORE_PATH, exc,
        )
        try:
            _PROJECT_STORE_PATH.rename(
                _PROJECT_STORE_PATH.with_suffix(".pkl.broken")
            )
        except Exception:
            pass


# Eager-load on module import
_load_projects_from_disk()


router = APIRouter(prefix="/api", tags=["pipeline"])


# ============ Request models ============


class CreateProjectRequest(BaseModel):
    title: Optional[str] = None
    brief: str
    constraints: Optional[str] = ""
    signals: Optional[str] = ""


class SimulationStartRequest(BaseModel):
    rounds: int = 3
    agents_per_round: int = 4


class AgentChatRequest(BaseModel):
    message: str


# ============ Helpers ============


def _get_project_or_404(project_id: str) -> Project:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _serialize_project(project: Project, include_graph: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": project.id,
        "title": project.title,
        "brief": project.brief,
        "constraints": project.constraints,
        "signals": project.signals,
        "state": project.state.value,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "ontology": project.ontology.to_dict() if project.ontology else None,
        "graph_stats": project.graph.stats if project.graph else None,
        "agent_count": len(project.agents),
        "events": [asdict(e) for e in project.events[-30:]],
    }
    if include_graph and project.graph:
        data["graph"] = {
            "nodes": [asdict(n) for n in project.graph.nodes],
            "edges": [asdict(e) for e in project.graph.edges],
        }
    # Include uploaded document metadata (filename + char_count) but NOT the
    # full extracted text — that would bloat every project response.
    if project.uploaded_documents:
        data["uploaded_documents"] = [
            {
                "filename": d.get("filename", "untitled"),
                "char_count": d.get("char_count", 0),
            }
            for d in project.uploaded_documents
        ]
    if project.agents:
        data["agents"] = [asdict(a) for a in project.agents]
    if project.simulation_parameters:
        data["simulation_parameters"] = project.simulation_parameters.to_dict()
    if project.debate_messages:
        data["debate_messages"] = project.debate_messages
    if project.consensus:
        data["consensus"] = project.consensus
    if project.report:
        data["report"] = project.report
    return data


def _persist_and_serialize(project: Project, include_graph: bool = True) -> Dict[str, Any]:
    """Save the in-memory store to disk, then serialize the project for the API response.

    Every endpoint that mutates a project should return this instead of
    `_serialize_project` directly. The persistence is best-effort: a failed
    write logs a warning but does not break the request.
    """
    _save_projects_to_disk()
    return _serialize_project(project, include_graph=include_graph)


# ============ Endpoints ============


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    """Stage 0: create a project from a brief."""
    project = Project(
        id=make_project_id(),
        title=req.title or req.brief[:60],
        brief=req.brief,
        constraints=req.constraints or "",
        signals=req.signals or "",
    )
    project.log("info", f"Project created: {project.id}", stage="created")
    _projects[project.id] = project
    return _persist_and_serialize(project)


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Fetch full project state including graph + events. Read-only — no save."""
    project = _get_project_or_404(project_id)
    return _serialize_project(project)


def _build_project_context(project: Project) -> str:
    """Compose constraints + signals + uploaded document text into one context blob."""
    parts: list[str] = []
    if project.constraints:
        parts.append(f"Constraints: {project.constraints}")
    if project.signals:
        parts.append(f"Signals: {project.signals}")
    # Uploaded reality-seed documents — feed extracted text directly to the LLM
    if project.uploaded_documents:
        doc_pairs = [
            (d.get("filename", "doc"), d.get("text", ""))
            for d in project.uploaded_documents
        ]
        doc_blob = aggregate_documents(doc_pairs)
        if doc_blob:
            parts.append(doc_blob)
    return "\n\n".join(parts)


@router.post("/projects/{project_id}/upload")
async def upload_document(project_id: str, file: UploadFile = File(...)):
    """Stage 0: upload a reality-seed document (PDF, MD, or TXT).

    The extracted text is stored on the project and fed into the ontology
    generator + graph builder as additional context. Exposed as a separate
    endpoint so the frontend can show per-file upload progress before
    kicking off the ontology stage.
    """
    project = _get_project_or_404(project_id)

    filename = file.filename or "untitled"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{suffix}" not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{suffix}. Supported: PDF, MD, TXT",
        )

    try:
        data = await file.read()
        text = extract_text_from_bytes(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        project.log("error", f"Failed to parse {filename}: {exc}", stage="upload")
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {exc}")

    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract any text from {filename}",
        )

    project.uploaded_documents.append({
        "filename": filename,
        "text": text,
        "char_count": len(text),
    })
    project.log(
        "info",
        f"Uploaded {filename} ({len(text)} chars extracted)",
        stage="upload",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/graph/ontology/generate")
async def stage_1a_ontology(project_id: str):
    """Stage 1a: LLM generates the ontology (entity + edge types).

    If reality-seed documents were uploaded, their extracted text is
    threaded into the LLM context so the generated ontology is grounded
    in the document content.
    """
    project = _get_project_or_404(project_id)
    n_docs = len(project.uploaded_documents)
    if n_docs:
        project.log(
            "info",
            f"Generating ontology with {n_docs} reality-seed document(s)…",
            stage="graph_building",
        )
    else:
        project.log("info", "Generating ontology…", stage="graph_building")

    context = _build_project_context(project)

    ontology = await generate_ontology(brief=project.brief, context=context)
    if ontology is None:
        project.log("error", "Ontology generation failed", stage="graph_building")
        project.state = ProjectState.FAILED
        raise HTTPException(status_code=500, detail="Ontology generation failed")

    project.ontology = ontology
    project.transition(
        ProjectState.ONTOLOGY_GENERATED,
        f"Ontology ready: {len(ontology.entity_types)} entity types, {len(ontology.edge_types)} edge types",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/graph/build")
async def stage_1b_graph_build(project_id: str):
    """Stage 1b: extract entities + relations from the brief, matching ontology.

    Also pulls in uploaded document text so the graph extraction sees the
    same context the ontology was designed against.
    """
    project = _get_project_or_404(project_id)
    if not project.ontology:
        raise HTTPException(status_code=400, detail="Ontology must be generated first")

    project.log("info", "Building knowledge graph…", stage="graph_building")
    project.state = ProjectState.GRAPH_BUILDING

    context = _build_project_context(project)

    builder = InMemoryGraphBuilder()
    graph = await builder.build(
        brief=project.brief,
        ontology=project.ontology,
        context=context,
    )
    if graph is None:
        project.log("error", "Graph extraction failed", stage="graph_building")
        project.state = ProjectState.FAILED
        raise HTTPException(status_code=500, detail="Graph extraction failed")

    project.graph = graph
    project.transition(
        ProjectState.GRAPH_COMPLETED,
        f"Graph built: {graph.stats['entity_nodes']} nodes, {graph.stats['relation_edges']} edges",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/env/setup")
async def stage_2_env_setup(project_id: str):
    """Stage 2: generate one agent per entity in the graph."""
    project = _get_project_or_404(project_id)
    if not project.graph or not project.graph.nodes:
        raise HTTPException(status_code=400, detail="Graph must be built first")

    project.log("info", f"Generating {min(12, len(project.graph.nodes))} agent personas…", stage="env_setup")
    agents = await generate_agents_for_graph(
        brief=project.brief,
        graph=project.graph,
        max_agents=12,
    )
    if not agents:
        project.log("error", "Agent generation failed", stage="env_setup")
        project.state = ProjectState.FAILED
        raise HTTPException(status_code=500, detail="Agent generation failed")

    project.agents = agents
    project.transition(
        ProjectState.ENV_READY,
        f"Environment ready: {len(agents)} agents instantiated from {len(project.graph.nodes)} entities",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/simulation/prepare")
async def stage_3_prepare(project_id: str):
    """Stage 3: generate the full simulation parameters (time + activity + event + platform configs).

    This is the bridge between Stage 02 (Generate Profiles) and Stage 04
    (Run Simulation). It produces the time-of-day activity configuration,
    per-agent behavior
    profiles, narrative direction with hot topics + initial posts, and the
    two platform recommendation algorithm configs.

    Each LLM step has its own fallback so a single failure doesn't tank
    the whole prep run.
    """
    project = _get_project_or_404(project_id)
    if not project.agents:
        raise HTTPException(
            status_code=400,
            detail="Agents must be generated first (run env/setup)",
        )

    project.log("info", "Generating simulation parameters…", stage="config_ready")

    def _on_step(msg: str) -> None:
        project.log("info", msg, stage="config_ready")

    params = await generate_simulation_parameters(project, progress_callback=_on_step)
    project.simulation_parameters = params

    n_posts = len(params.event_config.initial_posts)
    n_topics = len(params.event_config.hot_topics)
    n_agent_configs = len(params.agent_configs)
    project.transition(
        ProjectState.CONFIG_READY,
        f"Sim config ready: {n_agent_configs} agent profiles, "
        f"{n_topics} hot topics, {n_posts} initial posts",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/simulation/start")
async def stage_4_simulation(project_id: str, req: SimulationStartRequest):
    """Stage 4: run the round-by-round debate."""
    project = _get_project_or_404(project_id)
    if not project.agents:
        raise HTTPException(status_code=400, detail="Agents must be generated first (run env/setup)")

    project.log("info", f"Starting simulation: {req.rounds} rounds × {req.agents_per_round} agents", stage="simulating")
    project.state = ProjectState.SIMULATING

    messages = await run_simulation(project, total_rounds=req.rounds, agents_per_round=req.agents_per_round)
    project.log("success", f"Debate complete: {len(messages)} messages across {req.rounds} rounds", stage="simulating")

    consensus = await generate_consensus(project)
    if consensus:
        project.log("success", "Consensus reached", stage="simulating")

    project.transition(ProjectState.SIM_COMPLETED, "Simulation finished")
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/report/generate")
async def stage_5_report(project_id: str):
    """Stage 5: generate a structured prediction report from the simulation.

    Two-stage report generation: a planner LLM call produces the outline,
    then one LLM call per section writes the section body using the
    in-memory simulation state directly.
    """
    project = _get_project_or_404(project_id)
    if not project.consensus and not project.debate_messages:
        raise HTTPException(
            status_code=400,
            detail="Run the simulation first (no debate messages found)",
        )

    project.log("info", "Starting report generation…", stage="report_ready")

    def _on_step(msg: str) -> None:
        project.log("info", msg, stage="report_ready")

    report = await generate_report(project, progress_callback=_on_step)
    project.report = report

    n_sections = len(report.get("sections") or [])
    project.transition(
        ProjectState.REPORT_READY,
        f"Report ready: {n_sections} sections",
    )
    return _persist_and_serialize(project)


@router.post("/projects/{project_id}/agents/{agent_id}/chat")
async def stage_5_agent_chat(project_id: str, agent_id: str, req: AgentChatRequest):
    """Stage 5: deep interaction with one specific agent."""
    project = _get_project_or_404(project_id)
    agent = next((a for a in project.agents if a.id == agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found in this project")

    reply = await chat_with_agent(project, agent, req.message)
    if reply is None:
        raise HTTPException(status_code=500, detail="Agent chat failed")

    project.log("info", f"User chatted with {agent.name}", stage="deep_interaction")
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "user_message": req.message,
        "reply": reply,
    }
