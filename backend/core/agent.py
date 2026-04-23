"""
Generic Agent - stateful, with memory and personality.
Can be used in any domain.
"""

from .types import (
    AgentArchetype, AgentMemory, Knowledge,
    Scenario, ScenarioOutcome, ChatMessage
)
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import uuid


class Agent:
    """
    Generic agent with:
    - Personality (optimism, risk tolerance, etc)
    - Memory (Zep-integrated)
    - Reasoning (LLM-powered - supports Google Gemini and Claude)
    - Domain knowledge (from knowledge graph)
    """

    def __init__(
        self,
        archetype: AgentArchetype,
        knowledge: Knowledge,
        memory_backend=None  # Zep instance (optional)
    ):
        self.id = str(uuid.uuid4())
        self.archetype = archetype
        self.knowledge = knowledge
        self.memory = AgentMemory(agent_id=self.id)
        self.memory_backend = memory_backend  # Zep
        self.conversation_history: List[ChatMessage] = []

    def _get_system_prompt(self) -> str:
        """Build system prompt from archetype"""
        return f"""You are {self.archetype.name}.

Personality:
- Optimism: {self.archetype.personality.optimism * 100:.0f}%
  (0% = pessimistic, 100% = optimistic)
- Risk tolerance: {self.archetype.personality.risk_tolerance * 100:.0f}%
  (0% = risk-averse, 100% = risk-seeking)
- Communication style: {self.archetype.personality.communication_style}

Your expertise: {', '.join(self.archetype.expertise)}
Your responsibilities: {', '.join(self.archetype.responsibilities)}
Your goals: {', '.join(self.archetype.goals)}

When responding:
1. Draw on your personality and expertise
2. Reference the knowledge graph provided
3. Be honest about uncertainty
4. Explain your reasoning
5. Consider constraints and risks
"""

    def _get_context(self) -> str:
        """Build context from knowledge graph"""
        entities_str = "\n".join([
            f"- {e.name} ({e.type}): {e.description or e.attributes}"
            for e in self.knowledge.entities[:10]  # Top 10
        ])

        relationships_str = "\n".join([
            f"- {self.knowledge.get_entity(r.source_id).name} -> {r.type} -> {self.knowledge.get_entity(r.target_id).name}"
            for r in self.knowledge.relationships[:10]
        ])

        return f"""Knowledge Context:

Entities:
{entities_str}

Relationships:
{relationships_str}
"""

    async def think(self, prompt: str, include_memory: bool = True) -> str:
        """
        Agent reasons about something.
        Uses personality, memory, and knowledge.
        """
        try:
            from ..llm import get_llm
        except ImportError:  # pragma: no cover - supports direct script execution
            from llm import get_llm

        # Build context
        system = self._get_system_prompt()
        context = self._get_context()

        # Add memory if enabled
        memory_str = ""
        if include_memory and self.memory.long_term:
            memory_str = "\nRecent learnings:\n" + "\n".join([
                f"- {m.get('fact', '')}"
                for m in self.memory.long_term[-5:]
            ])

        full_prompt = f"{context}\n{memory_str}\n\nQuestion: {prompt}"

        # Call LLM (Claude or Google Gemini)
        llm = get_llm()
        response = await llm.generate(system, full_prompt, max_tokens=1024)

        # Store in memory
        self.memory.short_term.append({
            "prompt": prompt,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Save to Zep if available
        if self.memory_backend:
            await self.memory_backend.add_memory(
                session_id=self.id,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response}
                ]
            )

        return response

    async def simulate_scenario(self, scenario: Scenario) -> ScenarioOutcome:
        """
        Agent simulates a what-if scenario.
        Returns predicted outcomes.
        """
        prompt = f"""Simulate this scenario: {scenario.description}

Changes: {json.dumps(scenario.changes, indent=2)}

Based on the knowledge graph and your expertise, predict:
1. What will happen
2. Which entities will be affected
3. Your confidence level (0-1)
4. Key assumptions you're making

Format as JSON:
{{
  "outcomes": {{"entity": "impact"}},
  "confidence": 0.8,
  "assumptions": ["assumption 1"],
  "reasoning": "why you predict this"
}}
"""

        response = await self.think(prompt)

        try:
            parsed = json.loads(response)
        except:
            parsed = {
                "outcomes": {"unknown": "unable to parse"},
                "confidence": 0.3,
                "reasoning": response
            }

        return ScenarioOutcome(
            scenario_id=scenario.id,
            agent_id=self.id,
            predicted_outcomes=parsed.get("outcomes", {}),
            confidence=parsed.get("confidence", 0.5),
            reasoning=parsed.get("reasoning", response),
            affected_entities=list(parsed.get("outcomes", {}).keys())
        )

    async def negotiate(self, other_agent: "Agent", topic: str) -> str:
        """
        Two agents discuss and reach consensus.
        """
        prompt = f"""Discuss with another {other_agent.archetype.name} about: {topic}

Your position (as {self.archetype.name}):
- You are {self.archetype.personality.optimism * 100:.0f}% optimistic
- Your expertise: {', '.join(self.archetype.expertise)}

Try to reach consensus. What's your position?
"""

        return await self.think(prompt)

    async def chat(self, user_message: str) -> str:
        """
        User chats with agent.
        Agent responds in character.
        """
        response = await self.think(user_message)

        # Record in conversation history
        self.conversation_history.append(ChatMessage(
            role="user",
            content=user_message
        ))
        self.conversation_history.append(ChatMessage(
            role="agent",
            agent_id=self.id,
            content=response
        ))

        return response

    def get_profile(self) -> Dict[str, Any]:
        """Get agent's profile"""
        return {
            "id": self.id,
            "name": self.archetype.name,
            "personality": self.archetype.personality.dict(),
            "expertise": self.archetype.expertise,
            "memory_size": len(self.memory.short_term),
            "conversation_count": len(self.conversation_history) // 2
        }


class AgentPool:
    """
    Manage a pool of agents.
    """

    def __init__(self, knowledge: Knowledge):
        self.agents: Dict[str, Agent] = {}
        self.knowledge = knowledge

    def add_agent(self, agent: Agent) -> None:
        """Add agent to pool"""
        self.agents[agent.id] = agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def get_agents_by_archetype(self, archetype_name: str) -> List[Agent]:
        """Get all agents of a type"""
        return [a for a in self.agents.values() if a.archetype.name == archetype_name]

    async def ask_all(self, question: str) -> Dict[str, str]:
        """Ask all agents a question, return responses"""
        responses = {}
        for agent_id, agent in self.agents.items():
            response = await agent.think(question, include_memory=True)
            responses[agent.archetype.name] = response
        return responses

    def get_profiles(self) -> List[Dict[str, Any]]:
        """Get all agent profiles"""
        return [agent.get_profile() for agent in self.agents.values()]
