"""
Generic types for multi-agent simulation.
Domain-agnostic data structures.
"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class Entity(BaseModel):
    """Generic domain entity (person, project, market, policy, etc)"""
    id: str
    name: str
    type: str  # "project", "person", "team", "service", "policy", "market", etc
    description: Optional[str] = None
    attributes: Dict[str, Any] = {}  # Flexible schema
    domain: str = "generic"  # Which domain this entity belongs to
    created_at: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "id": "proj-001",
                "name": "Mobile Checkout v2",
                "type": "project",
                "domain": "execution",
                "attributes": {"status": "in_progress", "owner": "sarah"}
            }
        }


class Relationship(BaseModel):
    """Generic relationship between entities"""
    id: str
    source_id: str
    target_id: str
    type: str  # "depends_on", "owns", "blocks", "influences", "requires", etc
    strength: float = 0.5  # 0-1, confidence/importance
    description: Optional[str] = None
    temporal: Optional[Dict[str, datetime]] = None  # start_date, end_date
    created_at: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rel-001",
                "source_id": "proj-001",
                "target_id": "person-123",
                "type": "depends_on",
                "strength": 0.85,
                "description": "Project depends on person's approval"
            }
        }


class Knowledge(BaseModel):
    """Complete knowledge base - entities + relationships"""
    id: str
    name: str
    domain: str  # "execution", "finance", "policy", "creative"
    entities: List[Entity] = []
    relationships: List[Relationship] = []
    graph_metadata: Dict[str, Any] = {}
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return next((e for e in self.entities if e.id == entity_id), None)

    def get_relationships(self, source_id: Optional[str] = None, target_id: Optional[str] = None) -> List[Relationship]:
        rels = self.relationships
        if source_id:
            rels = [r for r in rels if r.source_id == source_id]
        if target_id:
            rels = [r for r in rels if r.target_id == target_id]
        return rels


class Scenario(BaseModel):
    """What-if scenario to simulate"""
    id: str
    description: str  # "Backend slips 2 weeks", "Interest rates rise 2%"
    changes: Dict[str, Any]  # What changes in this scenario
    constraints: Optional[List[str]] = None
    created_at: datetime = datetime.utcnow()


class ScenarioOutcome(BaseModel):
    """Result of simulating a scenario"""
    scenario_id: str
    agent_id: str
    predicted_outcomes: Dict[str, Any]  # What agent predicts happens
    confidence: float  # 0-1
    reasoning: str
    affected_entities: List[str]  # Which entities are impacted
    created_at: datetime = datetime.utcnow()


class AgentPersonality(BaseModel):
    """Personality traits for an agent"""
    optimism: float = 0.5  # 0-1, how optimistic is this agent
    risk_tolerance: float = 0.5  # 0-1, how risk-averse
    caution: float = 0.5  # 0-1, how cautious in predictions
    speed_preference: float = 0.5  # 0-1, prefers fast vs thorough
    communication_style: str = "balanced"  # verbose, concise, technical, informal
    bias: Optional[str] = None  # Known biases (optimistic_bias, pessimistic_bias, etc)


class AgentArchetype(BaseModel):
    """Template for agent type"""
    id: str
    name: str  # "Risk Officer", "PM", "Tech Lead", "Analyst"
    description: str
    personality: AgentPersonality
    expertise: List[str]  # Domains of expertise
    responsibilities: List[str]  # What this agent cares about
    goals: List[str]  # What this agent wants to achieve
    constraints: List[str]  # Limitations


class AgentMemory(BaseModel):
    """Agent's memory state (for Zep integration)"""
    agent_id: str
    short_term: List[Dict[str, Any]] = []  # Recent interactions
    long_term: List[Dict[str, Any]] = []  # Important facts
    relationships: Dict[str, str] = {}  # Known relationships with other agents
    past_predictions: List[Dict[str, Any]] = []  # Historical accuracy tracking
    created_at: datetime = datetime.utcnow()


class ChatMessage(BaseModel):
    """Message in conversation"""
    role: str  # "user", "agent", "system"
    agent_id: Optional[str] = None
    content: str
    timestamp: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response from chat interface"""
    user_message: str
    responses: List[ChatMessage]  # May be multiple agents responding
    consensus: Optional[str] = None
    confidence: float = 0.5
    next_steps: Optional[List[str]] = None
