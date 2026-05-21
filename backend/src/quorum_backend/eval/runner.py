"""Run :class:`EvalCase`\\ s through the full pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from quorum_backend.domains import get_domain
from quorum_backend.eval.cases import CASES, EvalCase
from quorum_backend.eval.scoring import Score, score_report
from quorum_backend.pipeline.env_setup import generate_agents_for_graph
from quorum_backend.pipeline.graph_builder import InMemoryGraphBuilder
from quorum_backend.pipeline.models import Project, ProjectState, make_project_id
from quorum_backend.pipeline.ontology_generator import generate_ontology
from quorum_backend.pipeline.report_generator import generate_report
from quorum_backend.pipeline.simulation_config_generator import (
    generate_initial_activation,
    generate_simulation_parameters,
)
from quorum_backend.pipeline.simulation_runner import generate_consensus, run_simulation


@dataclass
class EvalResult:
    """One case run + its scorecard."""

    case: EvalCase
    score: Score
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


async def _run_pipeline(case: EvalCase) -> Dict[str, Any]:
    """Drive the full pipeline for ``case`` and return the generated report.

    Mirrors the router's stage handlers but skips the HTTP and DB layers so
    the eval harness is self-contained and fast.
    """
    project = Project(
        id=make_project_id(),
        title=case.title or case.brief[:60],
        brief=case.brief,
        domain=case.domain,
    )

    domain = get_domain(case.domain)

    # Stage 01: ontology — fixed or LLM-generated.
    if domain.fixed_ontology is not None:
        from copy import deepcopy

        project.ontology = deepcopy(domain.fixed_ontology)
    else:
        project.ontology = await generate_ontology(brief=case.brief)
        assert project.ontology, "ontology generation failed"
    project.state = ProjectState.ONTOLOGY_GENERATED

    # Stage 02: graph.
    builder = InMemoryGraphBuilder()
    project.graph = await builder.build(brief=case.brief, ontology=project.ontology, context="")
    assert project.graph, "graph build failed"
    project.state = ProjectState.GRAPH_COMPLETED

    # Stage 03: agents — fixed roster or LLM-generated.
    if domain.uses_fixed_roster:
        from quorum_backend.pipeline.env_setup import build_roster_agents

        project.agents = build_roster_agents(domain.fixed_agent_roster)
    else:
        project.agents = await generate_agents_for_graph(
            brief=case.brief, graph=project.graph, max_agents=8
        )
    project.state = ProjectState.ENV_READY

    # Stage 04 + 05: config + activation.
    project.simulation_parameters = await generate_simulation_parameters(project)
    project.state = ProjectState.CONFIG_READY
    project.activation = await generate_initial_activation(project)
    project.state = ProjectState.ACTIVATION_READY

    # Stage 06: simulation.
    project.debate_messages = await run_simulation(project, total_rounds=2, agents_per_round=3)
    project.consensus = await generate_consensus(project)
    project.state = ProjectState.SIM_COMPLETED

    # Stage 07: report.
    report = await generate_report(project)
    project.report = report
    project.state = ProjectState.REPORT_READY
    return report


async def run_case(case: EvalCase) -> EvalResult:
    """Run one case and score the output. Never raises."""
    try:
        report = await _run_pipeline(case)
        return EvalResult(case=case, score=score_report(case, report), report=report)
    except Exception as exc:  # pragma: no cover - defensive
        return EvalResult(
            case=case,
            score=Score(case_name=case.name, passed=False, checks={"ran": False}, notes=[str(exc)]),
            error=str(exc),
        )


async def run_suite(cases: Optional[List[EvalCase]] = None) -> List[EvalResult]:
    """Run every case (or a supplied subset) and collect results."""
    selected = cases if cases is not None else CASES
    results: List[EvalResult] = []
    for case in selected:
        results.append(await run_case(case))
    return results
