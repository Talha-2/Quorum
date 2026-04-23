"""
Chat Interface - interactive conversation with agent pool.
"""

from .types import ChatMessage, ChatResponse, Knowledge
from .agent import AgentPool
from typing import List, Optional, Dict, Any, Callable
import uuid
from datetime import datetime
import inspect


class ChatInterface:
    """
    Interactive chat with agent pool.
    Route messages to relevant agents, aggregate responses.
    """

    def __init__(
        self,
        agent_pool: AgentPool,
        knowledge: Knowledge,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ):
        self.agent_pool = agent_pool
        self.knowledge = knowledge
        self.conversation_id = str(uuid.uuid4())
        self.messages: List[ChatMessage] = []
        self.progress_callback = progress_callback

    async def chat(
        self,
        user_message: str,
        agent_ids: Optional[List[str]] = None,
        get_consensus: bool = False,
        debate_rounds: int = 2,
        max_debate_agents: Optional[int] = None,
    ) -> ChatResponse:
        """
        User sends message, agents respond.

        Args:
            user_message: What user asks
            agent_ids: Which agents to ask (None = all)
            get_consensus: Should agents debate and reach consensus?
            debate_rounds: Number of follow-up deliberation rounds
            max_debate_agents: Cap on agents in consensus rounds

        Returns:
            ChatResponse with agent responses + consensus
        """

        # Record user message
        user_msg = ChatMessage(
            role="user",
            content=user_message
        )
        self.messages.append(user_msg)

        # Route to agents
        if agent_ids is None:
            agents = list(self.agent_pool.agents.values())
        else:
            agents = [self.agent_pool.get_agent(aid) for aid in agent_ids if aid in self.agent_pool.agents]

        if not agents:
            return ChatResponse(
                user_message=user_message,
                responses=[],
                confidence=0
            )

        # Get responses from agents
        responses: List[ChatMessage] = []
        for agent in agents:
            response_text = await agent.chat(user_message)
            response_msg = ChatMessage(
                role="agent",
                agent_id=agent.id,
                content=response_text
            )
            responses.append(response_msg)
            self.messages.append(response_msg)

        # Optionally get consensus
        consensus = None
        if get_consensus and len(agents) > 1:
            consensus_payload = await self._get_consensus(
                user_message,
                responses,
                agents,
                debate_rounds=debate_rounds,
                max_debate_agents=max_debate_agents,
            )
            for round_item in consensus_payload["round_trace"]:
                for contribution in round_item["contributions"]:
                    agent = next((candidate for candidate in agents if candidate.archetype.name == contribution["agent"]), None)
                    round_message = ChatMessage(
                        role="agent",
                        agent_id=agent.id if agent else None,
                        content=contribution["message"],
                        metadata={
                            "kind": "debate",
                            "round": round_item["round"],
                            "focus": round_item["focus"],
                        },
                    )
                    self.messages.append(round_message)

                self.messages.append(
                    ChatMessage(
                        role="system",
                        content=round_item["summary"],
                        metadata={
                            "kind": "round-summary",
                            "round": round_item["round"],
                            "focus": round_item["focus"],
                        },
                    )
                )

            consensus = consensus_payload["consensus"]
            self.messages.append(
                ChatMessage(
                    role="system",
                    content=consensus,
                    metadata={
                        "kind": "consensus",
                        "rounds_completed": consensus_payload["rounds_completed"],
                        "agents_involved": consensus_payload["agents_involved"],
                    },
                )
            )

        # Aggregate confidence
        avg_confidence = sum(
            agent.archetype.personality.optimism
            for agent in agents
        ) / len(agents) if agents else 0.5

        return ChatResponse(
            user_message=user_message,
            responses=responses,
            consensus=consensus,
            confidence=avg_confidence
        )

    async def _get_consensus(
        self,
        topic: str,
        responses: List[ChatMessage],
        agents: List,
        debate_rounds: int = 2,
        max_debate_agents: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Have agents negotiate consensus through multiple rounds.
        """
        rounds = max(1, min(int(debate_rounds or 1), 5))
        debate_agents = agents
        if max_debate_agents is not None and len(debate_agents) > max_debate_agents:
            limit = max(2, min(int(max_debate_agents), len(debate_agents)))
            debate_agents = debate_agents[:limit]

        moderator = next(
            (agent for agent in debate_agents if agent.archetype.name.startswith("Decision Synthesizer")),
            debate_agents[0],
        )
        position_context = self._format_positions(responses)
        focus_sequence = self._build_round_focuses(rounds)
        round_trace: List[Dict[str, Any]] = []
        await self._emit_progress(
            "debate.started",
            {
                "mode": "chat",
                "round": 0,
                "total_rounds": rounds,
                "focus": "Initial responses",
                "active_agents": [agent.archetype.name for agent in debate_agents],
            },
        )

        for index, focus in enumerate(focus_sequence, start=1):
            await self._emit_progress(
                "debate.round_started",
                {
                    "mode": "chat",
                    "round": index,
                    "total_rounds": rounds,
                    "focus": focus,
                    "active_agents": [agent.archetype.name for agent in debate_agents],
                },
            )
            contributions: List[Dict[str, Any]] = []
            for agent in debate_agents:
                contribution = await agent.think(
                    f"""Topic: {topic}

Debate round {index} of {rounds}
Round focus: {focus}

Current positions:
{position_context}

Respond with:
1. your updated stance
2. what you disagree with
3. the most important next consideration
"""
                )
                contributions.append({
                    "agent": agent.archetype.name,
                    "message": contribution,
                })

            round_summary = await moderator.think(
                f"""Topic: {topic}
Round focus: {focus}

Round contributions:
{self._format_contributions(contributions)}

Summarize the round with the strongest agreement and disagreement.
"""
            )
            round_trace.append(
                {
                    "round": index,
                    "focus": focus,
                    "summary": round_summary,
                    "contributions": contributions,
                }
            )
            position_context = self._format_round_context(round_trace)
            await self._emit_progress(
                "debate.round_completed",
                {
                    "mode": "chat",
                    "round": index,
                    "total_rounds": rounds,
                    "focus": focus,
                    "active_agents": [agent.archetype.name for agent in debate_agents],
                    "summary": round_summary,
                },
            )

        consensus = await moderator.think(
            f"""Topic: {topic}

Initial positions:
{self._format_positions(responses)}

Debate summaries:
{self._format_round_context(round_trace)}

Produce a final synthesis with:
- shared view
- unresolved disagreement
- recommended next move
"""
        )

        return {
            "consensus": consensus,
            "agents_involved": [agent.archetype.name for agent in debate_agents],
            "rounds_completed": rounds,
            "round_trace": round_trace,
        }

    async def multi_turn_conversation(
        self,
        messages: List[str],
        agent_ids: Optional[List[str]] = None
    ) -> List[ChatResponse]:
        """
        Multi-turn conversation.
        Context accumulates across turns.
        """
        responses = []
        for msg in messages:
            response = await self.chat(msg, agent_ids=agent_ids, get_consensus=True)
            responses.append(response)

        return responses

    def get_conversation(self) -> List[ChatMessage]:
        """Get full conversation history"""
        return self.messages

    def get_agent_insights(self) -> Dict[str, Any]:
        """
        Analyze what agents have said.
        Themes, agreements, disagreements.
        """
        agent_statements = {}

        for msg in self.messages:
            if msg.role == "agent":
                agent = self.agent_pool.get_agent(msg.agent_id)
                if not agent:
                    continue
                if agent.archetype.name not in agent_statements:
                    agent_statements[agent.archetype.name] = []
                agent_statements[agent.archetype.name].append(msg.content)

        return {
            "agents_spoken": list(agent_statements.keys()),
            "total_messages": len(self.messages),
            "agent_message_counts": {
                name: len(statements)
                for name, statements in agent_statements.items()
            }
        }

    def export_conversation(self) -> Dict[str, Any]:
        """Export conversation for analysis/sharing"""
        return {
            "conversation_id": self.conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [m.dict() for m in self.messages],
            "agents": self.agent_pool.get_profiles()
        }

    def _format_positions(self, responses: List[ChatMessage]) -> str:
        lines = []
        for response in responses:
            agent = self.agent_pool.get_agent(response.agent_id)
            if not agent:
                continue
            lines.append(f"- {agent.archetype.name}: {response.content}")
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

    def _build_round_focuses(self, rounds: int) -> List[str]:
        base = [
            "Clarify first-order position and confidence",
            "Challenge assumptions and expose disagreement",
            "Resolve tradeoffs and next action thresholds",
            "Tighten the recommendation under pressure",
        ]
        while len(base) < rounds:
            base.append("Reconcile remaining disagreement and sharpen next steps")
        return base[:rounds]

    async def _emit_progress(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.progress_callback:
            return
        result = self.progress_callback(event_type, payload)
        if inspect.isawaitable(result):
            await result
