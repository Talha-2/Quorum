"""
Scenario Simulator - run what-if scenarios with agent pool.
"""

from .types import Scenario, ScenarioOutcome, Knowledge
from .agent import AgentPool
from typing import List, Dict, Any, Optional, Callable
import uuid
from datetime import datetime
import inspect


class ScenarioSimulator:
    """
    Run scenarios with agent pool.
    Agents predict outcomes, debate, reach consensus.
    """

    def __init__(
        self,
        agent_pool: AgentPool,
        knowledge: Knowledge,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ):
        self.agent_pool = agent_pool
        self.knowledge = knowledge
        self.simulation_history: List[Dict[str, Any]] = []
        self.progress_callback = progress_callback

    async def run_scenario(
        self,
        scenario: Scenario,
        include_consensus: bool = True,
        debate_rounds: int = 3,
        max_debate_agents: Optional[int] = None,
        scenario_complexity: str = "high",
    ) -> Dict[str, Any]:
        """
        Run scenario:
        1. All agents predict outcomes
        2. (Optional) Agents debate across multiple rounds
        3. Return combined analysis
        """

        # Step 1: Each agent simulates independently
        outcomes: List[ScenarioOutcome] = []
        participating_agents = list(self.agent_pool.agents.values())
        await self._emit_progress(
            "scenario.analysis_started",
            {
                "scenario_description": scenario.description,
                "agent_count": len(participating_agents),
                "scenario_complexity": scenario_complexity,
            },
        )
        for agent in participating_agents:
            outcome = await agent.simulate_scenario(scenario)
            outcomes.append(outcome)

        # Step 2: Analyze outcomes
        consensus = None
        if include_consensus and len(participating_agents) > 1:
            consensus = await self._reach_consensus(
                scenario,
                outcomes,
                debate_rounds=debate_rounds,
                max_debate_agents=max_debate_agents,
                scenario_complexity=scenario_complexity,
            )

        # Step 3: Aggregate results
        result = {
            "scenario": scenario.dict(),
            "simulation_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "swarm_config": {
                "agent_count": len(participating_agents),
                "debate_rounds": consensus["rounds_completed"] if consensus else 0,
                "max_debate_agents": (
                    len(consensus["agents_involved"]) if consensus else min(len(participating_agents), max_debate_agents or len(participating_agents))
                ),
                "scenario_complexity": scenario_complexity,
            },
            "agent_predictions": [
                {
                    "agent": self.agent_pool.get_agent(o.agent_id).archetype.name,
                    "outcomes": o.predicted_outcomes,
                    "confidence": o.confidence,
                    "reasoning": o.reasoning
                }
                for o in outcomes
            ],
            "consensus": consensus,
            "aggregate_analysis": self._aggregate_outcomes(
                outcomes,
                debate_rounds=consensus["rounds_completed"] if consensus else 0,
                debate_agent_count=len(consensus["agents_involved"]) if consensus else 0,
                scenario_complexity=scenario_complexity,
            )
        }

        # Store in history
        self.simulation_history.append(result)
        await self._emit_progress(
            "scenario.completed",
            {
                "scenario_id": result["simulation_id"],
                "scenario_description": scenario.description,
                "debate_rounds": result["aggregate_analysis"]["debate_rounds"],
                "debate_agent_count": result["aggregate_analysis"]["debate_agent_count"],
            },
        )

        return result

    async def _reach_consensus(
        self,
        scenario: Scenario,
        outcomes: List[ScenarioOutcome],
        debate_rounds: int = 3,
        max_debate_agents: Optional[int] = None,
        scenario_complexity: str = "high",
    ) -> Dict[str, Any]:
        """
        Agents discuss and reach consensus across multiple rounds.
        """
        rounds = max(1, min(int(debate_rounds or 1), 6))
        positions = [
            {
                "agent": self.agent_pool.get_agent(outcome.agent_id).archetype.name,
                "confidence": outcome.confidence,
                "reasoning": outcome.reasoning,
                "outcomes": outcome.predicted_outcomes,
            }
            for outcome in outcomes
            if self.agent_pool.get_agent(outcome.agent_id)
        ]
        agents = self._select_debate_agents(outcomes, max_debate_agents=max_debate_agents)
        moderator = self._select_moderator(agents)
        round_trace: List[Dict[str, Any]] = []
        round_context = self._format_positions(positions)
        focus_sequence = self._build_round_focuses(scenario_complexity, rounds)
        await self._emit_progress(
            "debate.started",
            {
                "mode": "scenario",
                "round": 0,
                "total_rounds": rounds,
                "focus": "Initial positions",
                "active_agents": [agent.archetype.name for agent in agents],
                "scenario_complexity": scenario_complexity,
            },
        )

        for index, focus in enumerate(focus_sequence, start=1):
            await self._emit_progress(
                "debate.round_started",
                {
                    "mode": "scenario",
                    "round": index,
                    "total_rounds": rounds,
                    "focus": focus,
                    "active_agents": [agent.archetype.name for agent in agents],
                    "scenario_complexity": scenario_complexity,
                },
            )
            contributions: List[Dict[str, Any]] = []
            for agent in agents:
                contribution = await agent.think(
                    f"""Scenario: {scenario.description}
Changes: {scenario.changes}

Debate round {index} of {rounds}
Round focus: {focus}

Current positions:
{round_context}

Respond in 3 short parts:
1. Your updated position
2. What assumption or argument you challenge
3. What the swarm should monitor next
"""
                )
                contributions.append({
                    "agent": agent.archetype.name,
                    "message": contribution,
                })

            summary_prompt = f"""Scenario: {scenario.description}
Round focus: {focus}

Round contributions:
{self._format_contributions(contributions)}

Summarize this round with:
- strongest agreement
- strongest disagreement
- what changed from the prior position
"""
            round_summary = await moderator.think(summary_prompt)
            round_trace.append(
                {
                    "round": index,
                    "focus": focus,
                    "summary": round_summary,
                    "contributions": contributions,
                }
            )
            round_context = self._format_round_context(round_trace)
            await self._emit_progress(
                "debate.round_completed",
                {
                    "mode": "scenario",
                    "round": index,
                    "total_rounds": rounds,
                    "focus": focus,
                    "active_agents": [agent.archetype.name for agent in agents],
                    "summary": round_summary,
                    "scenario_complexity": scenario_complexity,
                },
            )

        consensus_response = await moderator.think(
            f"""Scenario: {scenario.description}
Changes: {scenario.changes}
Scenario complexity: {scenario_complexity}

Initial positions:
{self._format_positions(positions)}

Debate summaries:
{self._format_round_context(round_trace)}

Produce a final synthesis with:
- consensus view
- key disagreements
- most likely outcome
- recommended next move
"""
        )

        return {
            "consensus": consensus_response,
            "agents_involved": [a.archetype.name for a in agents],
            "rounds_completed": rounds,
            "round_trace": round_trace,
            "scenario_complexity": scenario_complexity,
        }

    def _aggregate_outcomes(
        self,
        outcomes: List[ScenarioOutcome],
        debate_rounds: int = 0,
        debate_agent_count: int = 0,
        scenario_complexity: str = "high",
    ) -> Dict[str, Any]:
        """
        Aggregate predictions across agents.
        Calculate confidence, identify agreement/disagreement.
        """
        confidences = [o.confidence for o in outcomes]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Look for common outcomes
        outcome_mentions: Dict[str, int] = {}
        for o in outcomes:
            for entity, impact in o.predicted_outcomes.items():
                key = f"{entity}:{impact}"
                outcome_mentions[key] = outcome_mentions.get(key, 0) + 1

        # Count agreement
        agreement_rate = (max(outcome_mentions.values()) / len(outcomes)) if outcome_mentions else 0

        return {
            "avg_confidence": avg_confidence,
            "agreement_rate": agreement_rate,
            "common_outcomes": sorted(
                outcome_mentions.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "agent_count": len(outcomes),
            "debate_rounds": debate_rounds,
            "debate_agent_count": debate_agent_count,
            "scenario_complexity": scenario_complexity,
        }

    def _select_debate_agents(
        self,
        outcomes: List[ScenarioOutcome],
        max_debate_agents: Optional[int] = None,
    ) -> List[Any]:
        agents = [
            self.agent_pool.get_agent(outcome.agent_id)
            for outcome in outcomes
            if self.agent_pool.get_agent(outcome.agent_id)
        ]
        if not agents:
            return []

        limit = len(agents) if max_debate_agents is None else max(2, min(int(max_debate_agents), len(agents)))
        if len(agents) <= limit:
            return agents

        keyed = {agent.id: agent for agent in agents}
        priority_names = ("Decision Synthesizer", "Systems Mapper", "Risk Radar", "Opportunity Scout", "Adversarial Challenger", "Scenario Architect")
        selected: List[Any] = []

        for name in priority_names:
            match = next((agent for agent in agents if agent.archetype.name.startswith(name)), None)
            if match and match.id not in {agent.id for agent in selected}:
                selected.append(match)
            if len(selected) >= limit:
                return selected[:limit]

        by_confidence = sorted(outcomes, key=lambda outcome: outcome.confidence)
        for outcome in by_confidence:
            agent = keyed.get(outcome.agent_id)
            if agent and agent.id not in {item.id for item in selected}:
                selected.append(agent)
            if len(selected) >= limit:
                return selected[:limit]

        return selected[:limit]

    def _select_moderator(self, agents: List[Any]) -> Any:
        if not agents:
            return list(self.agent_pool.agents.values())[0]

        for preferred in ("Decision Synthesizer", "Systems Mapper", "Execution Operator"):
            candidate = next((agent for agent in agents if agent.archetype.name.startswith(preferred)), None)
            if candidate:
                return candidate

        return agents[0]

    def _build_round_focuses(self, scenario_complexity: str, rounds: int) -> List[str]:
        complexity = (scenario_complexity or "high").lower()
        templates = {
            "low": [
                "Immediate first-order impact",
                "Most important assumption check",
            ],
            "medium": [
                "Immediate first-order impact",
                "Assumption challenge and downside exposure",
                "Primary mitigation and next decision",
            ],
            "high": [
                "Immediate first-order impact",
                "Second-order effects and dependency cascades",
                "Stakeholder conflict, resource pressure, and downside exposure",
                "Mitigation sequence, triggers, and decision thresholds",
            ],
            "extreme": [
                "Immediate first-order disruption under maximum stress",
                "Second-order effects, feedback loops, and cascade paths",
                "Stakeholder conflict, coordination failure, and narrative risk",
                "Recovery options, containment strategy, and hidden failure modes",
                "Decision threshold, kill criteria, and high-conviction next move",
            ],
        }
        base = list(templates.get(complexity, templates["high"]))
        while len(base) < rounds:
            base.append("Refine disagreements, update priors, and tighten action thresholds")
        return base[:rounds]

    def _format_positions(self, positions: List[Dict[str, Any]]) -> str:
        lines = []
        for position in positions:
            lines.append(
                f"- {position['agent']} (confidence {position['confidence']:.2f}): "
                f"{position['reasoning']}"
            )
        return "\n".join(lines)

    def _format_contributions(self, contributions: List[Dict[str, Any]]) -> str:
        return "\n".join(
            f"- {contribution['agent']}: {contribution['message']}"
            for contribution in contributions
        )

    def _format_round_context(self, round_trace: List[Dict[str, Any]]) -> str:
        return "\n\n".join(
            f"Round {item['round']} ({item['focus']}): {item['summary']}"
            for item in round_trace
        )

    async def _emit_progress(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.progress_callback:
            return
        result = self.progress_callback(event_type, payload)
        if inspect.isawaitable(result):
            await result

    async def run_multi_scenario(
        self,
        scenarios: List[Scenario]
    ) -> List[Dict[str, Any]]:
        """
        Run multiple scenarios.
        Useful for comparing what-if branches.
        """
        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)
        return results

    def compare_scenarios(
        self,
        scenario_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Compare outcomes across scenarios.
        Which scenario is most likely? Most risky?
        """
        selected = [
            s for s in self.simulation_history
            if s["simulation_id"] in scenario_ids
        ]

        if not selected:
            return {"error": "No scenarios found"}

        comparison = {
            "scenarios": len(selected),
            "scenarios_detail": []
        }

        for sim in selected:
            avg_conf = sim["aggregate_analysis"]["avg_confidence"]
            agreement = sim["aggregate_analysis"]["agreement_rate"]

            comparison["scenarios_detail"].append({
                "scenario": sim["scenario"]["description"],
                "avg_confidence": avg_conf,
                "agent_agreement": agreement,
                "most_likely_outcome": sim["aggregate_analysis"]["common_outcomes"][0][0]
                if sim["aggregate_analysis"]["common_outcomes"] else "unknown"
            })

        return comparison

    def get_simulation_history(self) -> List[Dict[str, Any]]:
        """Get all simulations run"""
        return self.simulation_history

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of simulation results"""
        return {
            "simulations_run": len(self.simulation_history),
            "agents": self.agent_pool.get_profiles(),
            "recent_scenarios": [
                s["scenario"]["description"]
                for s in self.simulation_history[-5:]
            ]
        }
