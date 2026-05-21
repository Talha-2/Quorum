"""
FastAPI router for the production Quorum pipeline.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from quorum_backend.config import settings
from quorum_backend.domains import get_domain, is_valid_domain, list_domains
from quorum_backend.observability import llm_metrics
from quorum_backend.pipeline import db
from quorum_backend.pipeline import jobs as job_store
from quorum_backend.pipeline.deid import DeidMode, redact, scan_for_phi, summary as phi_summary
from quorum_backend.pipeline.env_setup import build_roster_agents, generate_agents_for_graph
from quorum_backend.pipeline.file_parser import (
    SUPPORTED_EXTENSIONS,
    aggregate_documents,
    extract_text_from_bytes,
)
from quorum_backend.pipeline.graph_builder import InMemoryGraphBuilder
from quorum_backend.pipeline.models import Project, ProjectState, make_project_id
from quorum_backend.pipeline.ontology_generator import generate_ontology
from quorum_backend.pipeline.report_generator import generate_report
from quorum_backend.pipeline.simulation_config_generator import (
    generate_initial_activation,
    generate_simulation_parameters,
)
from quorum_backend.pipeline.simulation_runner import chat_with_agent, generate_consensus, run_simulation

logger = logging.getLogger(__name__)


_projects_lock: asyncio.Lock = asyncio.Lock()
_project_stage_locks: Dict[str, asyncio.Lock] = {}
_projects: Dict[str, Project] = {}


def _save_project(project: Project) -> None:
    """Write a single project through to the database."""
    try:
        db.save_project(project)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to persist project %s: %s", project.id, exc)


def load_projects_into_cache() -> None:
    """Populate the in-memory cache from the database. Called at app startup."""
    global _projects
    _projects = db.load_all_projects()


def get_project_store_summary() -> Dict[str, Any]:
    url = settings.resolved_database_url
    return {
        "project_count": len(_projects),
        "store_path": url.split("@")[-1] if "@" in url else url,
    }


def clear_project_store_for_tests() -> None:
    """Reset the store to empty. Used by tests."""
    global _projects
    db.init_db()
    db.clear_all_projects()
    job_store.clear_all_jobs_for_tests()
    _projects = {}
    _project_stage_locks.clear()


router = APIRouter(prefix="/api", tags=["pipeline"])


class CreateProjectRequest(BaseModel):
    title: Optional[str] = None
    brief: str
    constraints: Optional[str] = ""
    signals: Optional[str] = ""
    domain: Optional[str] = "general"


class SimulationStartRequest(BaseModel):
    rounds: int = 3
    agents_per_round: int = 4


class AgentChatRequest(BaseModel):
    message: str


class RunNextStageRequest(BaseModel):
    rounds: int = 3
    agents_per_round: int = 4


def _get_project_or_404(project_id: str) -> Project:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _get_project_lock(project_id: str) -> asyncio.Lock:
    lock = _project_stage_locks.get(project_id)
    if lock is None:
        lock = asyncio.Lock()
        _project_stage_locks[project_id] = lock
    return lock


def _serialize_project(project: Project, include_graph: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": project.id,
        "title": project.title,
        "brief": project.brief,
        "constraints": project.constraints,
        "signals": project.signals,
        "domain": getattr(project, "domain", "general"),
        "state": project.state.value,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "last_error": project.last_error,
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
    if project.uploaded_documents:
        data["uploaded_documents"] = [
            {
                "filename": d.get("filename", "untitled"),
                "char_count": d.get("char_count", 0),
                "phi_findings_count": len(d.get("phi_findings") or []),
                "phi_redacted": bool(d.get("phi_redacted")),
            }
            for d in project.uploaded_documents
        ]
    if project.agents:
        data["agents"] = [asdict(a) for a in project.agents]
    if project.simulation_parameters:
        data["simulation_parameters"] = project.simulation_parameters.to_dict()
    if project.activation:
        data["activation"] = project.activation.to_dict()
    if project.debate_messages:
        data["debate_messages"] = project.debate_messages
    if project.consensus:
        data["consensus"] = project.consensus
    if project.report:
        data["report"] = project.report
    data["pipeline"] = get_pipeline_progress(project)
    return data


def _persist_and_serialize(project: Project, include_graph: bool = True) -> Dict[str, Any]:
    _save_project(project)
    return _serialize_project(project, include_graph=include_graph)


def _build_project_context(project: Project) -> str:
    parts: list[str] = []
    if project.constraints:
        parts.append(f"Constraints: {project.constraints}")
    if project.signals:
        parts.append(f"Signals: {project.signals}")
    if project.uploaded_documents:
        doc_pairs = [(d.get("filename", "doc"), d.get("text", "")) for d in project.uploaded_documents]
        doc_blob = aggregate_documents(doc_pairs)
        if doc_blob:
            parts.append(doc_blob)
    return "\n\n".join(parts)


def _fail_project(project: Project, detail: str, stage: str) -> None:
    project.last_error = detail
    project.state = ProjectState.FAILED
    project.log("error", detail, stage=stage)


def get_pipeline_progress(project: Project) -> Dict[str, Any]:
    n_docs = len(project.uploaded_documents)
    has_ontology = project.ontology is not None
    has_graph = bool(project.graph and project.graph.nodes)
    has_agents = bool(project.agents)
    has_config = project.simulation_parameters is not None
    has_activation = project.activation is not None
    has_simulation = bool(project.debate_messages) and project.state in {
        ProjectState.SIMULATING,
        ProjectState.SIM_COMPLETED,
        ProjectState.REPORT_READY,
    }
    has_report = project.report is not None

    steps = [
        {"id": "create", "order": 0, "label": "Create project", "detail": "Brief and metadata", "done": True, "optional": False},
        {"id": "upload", "order": 1, "label": "Reality-seed files", "detail": f"{n_docs} file(s)" if n_docs else "Optional", "done": n_docs > 0, "optional": True},
        {"id": "ontology", "order": 2, "label": "Ontology", "detail": "Entity and relation types", "path": f"/api/projects/{project.id}/graph/ontology/generate", "done": has_ontology, "optional": False},
        {"id": "graph", "order": 3, "label": "Knowledge graph", "detail": "Typed nodes and edges", "path": f"/api/projects/{project.id}/graph/build", "done": has_graph, "optional": False},
        {"id": "env", "order": 4, "label": "Agent personas", "detail": "One agent per speaker-capable entity", "path": f"/api/projects/{project.id}/env/setup", "done": has_agents, "optional": False},
        {"id": "prepare", "order": 5, "label": "Simulation config", "detail": "Time, activity, and platform config", "path": f"/api/projects/{project.id}/simulation/prepare", "done": has_config, "optional": False},
        {"id": "activate", "order": 6, "label": "Initial activation", "detail": "Narrative direction, hot topics, starter posts", "path": f"/api/projects/{project.id}/simulation/activate", "done": has_activation, "optional": False},
        {"id": "simulate", "order": 7, "label": "Run simulation", "detail": "Round-by-round debate and consensus", "path": f"/api/projects/{project.id}/simulation/start", "done": has_simulation and project.state in {ProjectState.SIM_COMPLETED, ProjectState.REPORT_READY}, "optional": False},
        {"id": "report", "order": 8, "label": "Generate report", "detail": "Structured synthesis and markdown export", "path": f"/api/projects/{project.id}/report/generate", "done": has_report, "optional": False},
    ]

    current_step = None
    if project.state == ProjectState.GRAPH_BUILDING:
        current_step = "graph"
    elif project.state == ProjectState.SIMULATING:
        current_step = "simulate"
    else:
        for step in steps:
            if step["optional"] or step["id"] == "create":
                continue
            if not step["done"]:
                current_step = step["id"]
                break
    if current_step is None and has_report:
        current_step = "complete"

    return {
        "project_id": project.id,
        "state": project.state.value,
        "failed": project.state == ProjectState.FAILED,
        "last_error": project.last_error,
        "steps": steps,
        "current_step": current_step,
    }


def _next_stage_id(project: Project) -> Optional[str]:
    progress = get_pipeline_progress(project)
    current = progress.get("current_step")
    if not current or current == "complete":
        return None
    return str(current)


async def _run_ontology_stage(project: Project) -> None:
    if project.ontology is not None:
        return

    # Domains with a fixed ontology skip the LLM entirely: the schema is
    # deterministic and auditable, which matters for clinical domains.
    domain = get_domain(getattr(project, "domain", "general"))
    if domain.fixed_ontology is not None:
        ontology = copy.deepcopy(domain.fixed_ontology)
        project.ontology = ontology
        project.transition(
            ProjectState.ONTOLOGY_GENERATED,
            f"Applied fixed {domain.name} ontology: "
            f"{len(ontology.entity_types)} entity types, "
            f"{len(ontology.edge_types)} edge types",
        )
        return

    n_docs = len(project.uploaded_documents)
    project.log("info", f"Generating ontology with {n_docs} reality-seed document(s)…" if n_docs else "Generating ontology…", stage="ontology")

    context = _build_project_context(project)
    ontology = await generate_ontology(brief=project.brief, context=context)
    if ontology is None:
        _fail_project(project, "Ontology generation failed", "ontology")
        raise HTTPException(status_code=500, detail="Ontology generation failed")

    project.ontology = ontology
    project.transition(
        ProjectState.ONTOLOGY_GENERATED,
        f"Ontology ready: {len(ontology.entity_types)} entity types, {len(ontology.edge_types)} edge types",
    )


async def _run_graph_stage(project: Project) -> None:
    if project.graph and project.graph.nodes:
        return
    if not project.ontology:
        raise HTTPException(status_code=409, detail="Ontology must be generated first")

    project.log("info", "Building knowledge graph…", stage="graph")
    project.state = ProjectState.GRAPH_BUILDING

    context = _build_project_context(project)
    builder = InMemoryGraphBuilder()
    graph = await builder.build(brief=project.brief, ontology=project.ontology, context=context)
    if graph is None:
        _fail_project(project, "Graph extraction failed", "graph")
        raise HTTPException(status_code=500, detail="Graph extraction failed")

    project.graph = graph
    project.transition(
        ProjectState.GRAPH_COMPLETED,
        f"Graph built: {graph.stats['entity_nodes']} nodes, {graph.stats['relation_edges']} edges",
    )


async def _run_env_stage(project: Project) -> None:
    if project.agents:
        return
    if not project.graph or not project.graph.nodes:
        raise HTTPException(status_code=409, detail="Graph must be built first")

    # A fixed-roster domain convenes its standing panel deterministically.
    domain = get_domain(getattr(project, "domain", "general"))
    if domain.uses_fixed_roster:
        project.log(
            "info",
            f"Convening the fixed {domain.name} panel ({len(domain.fixed_agent_roster)} seats)…",
            stage="env",
        )
        agents = build_roster_agents(domain.fixed_agent_roster)
        project.agents = agents
        project.transition(
            ProjectState.ENV_READY,
            f"Environment ready: {len(agents)}-seat {domain.name} panel convened",
        )
        return

    project.log("info", f"Generating {min(12, len(project.graph.nodes))} agent personas…", stage="env")
    agents = await generate_agents_for_graph(brief=project.brief, graph=project.graph, max_agents=12)
    if not agents:
        _fail_project(project, "Agent generation failed", "env")
        raise HTTPException(status_code=500, detail="Agent generation failed")

    project.agents = agents
    project.transition(
        ProjectState.ENV_READY,
        f"Environment ready: {len(agents)} agents instantiated from {len(project.graph.nodes)} entities",
    )


async def _run_prepare_stage(project: Project) -> None:
    if project.simulation_parameters is not None:
        return
    if not project.agents:
        raise HTTPException(status_code=409, detail="Agents must be generated first (run env/setup)")

    project.log("info", "Generating simulation configuration…", stage="prepare")

    def _on_step(msg: str) -> None:
        project.log("info", msg, stage="prepare")

    params = await generate_simulation_parameters(project, progress_callback=_on_step)
    project.simulation_parameters = params
    project.transition(
        ProjectState.CONFIG_READY,
        f"Simulation config ready: {len(params.agent_configs)} agent profiles and platform configuration generated",
    )


async def _run_activation_stage(project: Project) -> None:
    if project.activation is not None:
        return
    if not project.simulation_parameters:
        raise HTTPException(status_code=409, detail="Simulation config must be generated first (run simulation/prepare)")

    project.log("info", "Generating initial activation plan…", stage="activate")

    def _on_step(msg: str) -> None:
        project.log("info", msg, stage="activate")

    activation = await generate_initial_activation(project, progress_callback=_on_step)
    project.activation = activation
    project.transition(
        ProjectState.ACTIVATION_READY,
        f"Activation ready: {len(activation.hot_topics)} topics and {len(activation.initial_posts)} starter posts",
    )


async def _run_simulation_stage(project: Project, req: SimulationStartRequest) -> None:
    if project.consensus is not None and project.debate_messages:
        return
    if not project.agents:
        raise HTTPException(status_code=409, detail="Agents must be generated first (run env/setup)")
    if not project.simulation_parameters:
        raise HTTPException(status_code=409, detail="Simulation config must be generated first")
    if not project.activation:
        raise HTTPException(status_code=409, detail="Initial activation must be generated first")

    project.log("info", f"Starting simulation: {req.rounds} rounds × {req.agents_per_round} agents", stage="simulate")
    project.state = ProjectState.SIMULATING

    messages = await run_simulation(project, total_rounds=req.rounds, agents_per_round=req.agents_per_round)
    project.log("success", f"Debate complete: {len(messages)} messages across {req.rounds} rounds", stage="simulate")

    consensus = await generate_consensus(project)
    if consensus:
        project.log("success", "Consensus reached", stage="simulate")

    project.transition(ProjectState.SIM_COMPLETED, "Simulation finished")


async def _run_report_stage(project: Project) -> None:
    if project.report is not None:
        return
    if not project.consensus and not project.debate_messages:
        raise HTTPException(status_code=409, detail="Run the simulation first (no debate messages found)")

    project.log("info", "Starting report generation…", stage="report")

    def _on_step(msg: str) -> None:
        project.log("info", msg, stage="report")

    report = await generate_report(project, progress_callback=_on_step)
    project.report = report
    project.transition(ProjectState.REPORT_READY, f"Report ready: {len(report.get('sections') or [])} sections")


@router.get("/domains")
async def get_domains():
    """List the domain profiles a project can be created with."""
    return {
        "domains": [
            {
                "key": d.key,
                "name": d.name,
                "description": d.description,
                "fixed_ontology": d.uses_fixed_ontology,
            }
            for d in list_domains()
        ]
    }


@router.get("/metrics")
async def get_metrics():
    """Operational metrics: LLM-call aggregates and project counts."""
    return {
        "llm": llm_metrics.snapshot(),
        "projects": {"count": len(_projects)},
    }


@router.get("/projects/{project_id}/pipeline")
async def get_pipeline_status(project_id: str):
    project = _get_project_or_404(project_id)
    return get_pipeline_progress(project)


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    async with _projects_lock:
        brief = (req.brief or "").strip()
        if not brief:
            raise HTTPException(status_code=400, detail="brief is required")

        domain_key = (req.domain or "general").strip() or "general"
        if not is_valid_domain(domain_key):
            known = ", ".join(d.key for d in list_domains())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown domain '{domain_key}'. Known domains: {known}",
            )

        project = Project(
            id=make_project_id(),
            title=(req.title or brief[:60]).strip(),
            brief=brief,
            constraints=(req.constraints or "").strip(),
            signals=(req.signals or "").strip(),
            domain=domain_key,
        )
        domain = get_domain(domain_key)
        project.log(
            "info",
            f"Project created: {project.id} (domain: {domain.name})",
            stage="create",
        )
        _projects[project.id] = project
        return _persist_and_serialize(project)


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = _get_project_or_404(project_id)
    return _serialize_project(project)


@router.post("/projects/{project_id}/upload")
async def upload_document(project_id: str, file: UploadFile = File(...)):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        if project.ontology is not None or project.state != ProjectState.CREATED:
            raise HTTPException(status_code=409, detail="Uploads are only allowed before ontology generation starts")

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
            raise HTTPException(status_code=400, detail=f"Could not extract any text from {filename}")

        # De-identification gate. Surfaces or redacts common PHI patterns
        # before the case enters the pipeline. Not a substitute for a real
        # de-id service under a BAA — see deid.py.
        mode = DeidMode.parse(settings.deid_mode)
        phi_findings: list = []
        phi_redacted = False
        if mode is not DeidMode.OFF:
            if mode is DeidMode.REDACT:
                text, finds = redact(text)
                phi_findings = [f.to_dict() for f in finds]
                phi_redacted = bool(finds)
            else:
                finds = scan_for_phi(text)
                phi_findings = [f.to_dict() for f in finds]
                if finds and mode is DeidMode.STRICT:
                    counts = phi_summary(finds)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"PHI detected in {filename} ({counts}); "
                            "upload rejected by strict de-identification gate."
                        ),
                    )

        if phi_findings:
            kinds: dict = {}
            for f in phi_findings:
                kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
            level = "info" if phi_redacted else "warning"
            project.log(
                level,
                f"De-id gate ({mode.value}): {len(phi_findings)} PHI finding(s) in {filename} — {kinds}",
                stage="upload",
            )

        project.uploaded_documents.append(
            {
                "filename": filename,
                "text": text,
                "char_count": len(text),
                "phi_findings": phi_findings,
                "phi_redacted": phi_redacted,
            }
        )
        project.log("info", f"Uploaded {filename} ({len(text)} chars extracted)", stage="upload")
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/graph/ontology/generate")
async def stage_01_ontology(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_ontology_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/graph/build")
async def stage_02_graph(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_graph_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/env/setup")
async def stage_03_env(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_env_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/simulation/prepare")
async def stage_04_prepare(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_prepare_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/simulation/activate")
async def stage_05_activate(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_activation_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/simulation/start")
async def stage_06_simulation(project_id: str, req: SimulationStartRequest):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_simulation_stage(project, req)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/report/generate")
async def stage_07_report(project_id: str):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        await _run_report_stage(project)
        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/pipeline/run-next")
async def run_next_pipeline_stage(project_id: str, req: RunNextStageRequest):
    async with _get_project_lock(project_id):
        project = _get_project_or_404(project_id)
        next_stage = _next_stage_id(project)
        if next_stage is None:
            return _persist_and_serialize(project)

        if next_stage == "ontology":
            await _run_ontology_stage(project)
        elif next_stage == "graph":
            await _run_graph_stage(project)
        elif next_stage == "env":
            await _run_env_stage(project)
        elif next_stage == "prepare":
            await _run_prepare_stage(project)
        elif next_stage == "activate":
            await _run_activation_stage(project)
        elif next_stage == "simulate":
            await _run_simulation_stage(project, SimulationStartRequest(rounds=req.rounds, agents_per_round=req.agents_per_round))
        elif next_stage == "report":
            await _run_report_stage(project)
        else:
            raise HTTPException(status_code=409, detail=f"Unknown next stage: {next_stage}")

        return _persist_and_serialize(project)


@router.post("/projects/{project_id}/pipeline/run-async")
async def run_next_pipeline_stage_async(project_id: str, req: RunNextStageRequest):
    """Enqueue a job that advances the project by one stage.

    Returns immediately with the job id. The actual stage is executed by the
    background worker. Poll ``GET /api/jobs/{job_id}`` for status.
    """
    project = _get_project_or_404(project_id)
    job = job_store.enqueue(
        project_id=project.id,
        job_type="run_next",
        payload={"rounds": req.rounds, "agents_per_round": req.agents_per_round},
    )
    return job.to_dict()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()


@router.get("/projects/{project_id}/jobs")
async def list_project_jobs(project_id: str):
    _get_project_or_404(project_id)
    return {"jobs": [j.to_dict() for j in job_store.list_for_project(project_id)]}


@router.post("/projects/{project_id}/agents/{agent_id}/chat")
async def stage_08_agent_chat(project_id: str, agent_id: str, req: AgentChatRequest):
    project = _get_project_or_404(project_id)
    agent = next((a for a in project.agents if a.id == agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found in this project")

    reply = await chat_with_agent(project, agent, req.message)
    if reply is None:
        raise HTTPException(status_code=500, detail="Agent chat failed")

    project.log("info", f"User chatted with {agent.name}", stage="deep_interaction")
    _save_project(project)
    return {"agent_id": agent.id, "agent_name": agent.name, "user_message": req.message, "reply": reply}

