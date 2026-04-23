"""
Knowledge Graph - manage entities and relationships.
Generic graph structure for any domain.
"""

from .types import Entity, Relationship, Knowledge
from typing import List, Dict, Set, Optional, Tuple
import networkx as nx
import uuid
from datetime import datetime


class KnowledgeGraph:
    """
    Manage knowledge as graph of entities and relationships.
    """

    def __init__(self, name: str, domain: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.domain = domain
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.graph = nx.DiGraph()  # NetworkX graph
        self.created_at = datetime.utcnow()

    def add_entity(self, entity: Entity) -> Entity:
        """Add entity to graph"""
        self.entities[entity.id] = entity
        self.graph.add_node(entity.id, data=entity)
        return entity

    def add_relationship(self, relationship: Relationship) -> Relationship:
        """Add relationship between entities"""
        # Verify entities exist
        if relationship.source_id not in self.entities:
            raise ValueError(f"Source entity {relationship.source_id} not found")
        if relationship.target_id not in self.entities:
            raise ValueError(f"Target entity {relationship.target_id} not found")

        self.relationships.append(relationship)
        self.graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            data=relationship
        )
        return relationship

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID"""
        return self.entities.get(entity_id)

    def get_related_entities(self, entity_id: str, rel_type: Optional[str] = None) -> List[Tuple[str, Relationship]]:
        """
        Get entities related to given entity.
        Returns list of (entity_id, relationship)
        """
        result = []
        for rel in self.relationships:
            if rel.source_id == entity_id:
                if rel_type is None or rel.type == rel_type:
                    result.append((rel.target_id, rel))
            elif rel.target_id == entity_id:
                if rel_type is None or rel.type == rel_type:
                    result.append((rel.source_id, rel))
        return result

    def find_paths(self, source_id: str, target_id: str) -> List[List[str]]:
        """
        Find all paths between two entities.
        Useful for dependency analysis.
        """
        try:
            paths = list(nx.all_simple_paths(self.graph, source_id, target_id))
            return paths
        except nx.NetworkXNoPath:
            return []

    def get_critical_path(self) -> List[str]:
        """
        Find critical path in dependency graph.
        (Nodes with highest dependency depth)
        """
        if not self.graph or not self.graph.nodes():
            return []
        try:
            return nx.dag_longest_path(self.graph)
        except nx.NetworkXUnfeasible:
            return []

    def get_bottlenecks(self) -> List[Dict[str, any]]:
        """
        Find bottlenecks (nodes with high in-degree).
        Entities that many things depend on.
        """
        bottlenecks = []
        for node in self.graph.nodes():
            in_degree = self.graph.in_degree(node)
            if in_degree > 2:  # Threshold
                bottlenecks.append({
                    "entity_id": node,
                    "entity_name": self.entities[node].name,
                    "dependents": in_degree
                })
        return sorted(bottlenecks, key=lambda x: x["dependents"], reverse=True)

    def get_disconnected_entities(self) -> List[Entity]:
        """
        Find isolated entities (no relationships).
        May indicate missing data or standalone items.
        """
        isolated = []
        for entity_id, entity in self.entities.items():
            if self.graph.degree(entity_id) == 0:
                isolated.append(entity)
        return isolated

    def to_knowledge(self) -> Knowledge:
        """Convert to Knowledge type"""
        return Knowledge(
            id=self.id,
            name=self.name,
            domain=self.domain,
            entities=list(self.entities.values()),
            relationships=self.relationships,
            graph_metadata={
                "nodes": len(self.graph.nodes()),
                "edges": len(self.graph.edges()),
                "bottlenecks": [b["entity_name"] for b in self.get_bottlenecks()],
                "isolated": [e.name for e in self.get_disconnected_entities()]
            }
        )

    def summary(self) -> Dict[str, any]:
        """Get summary of knowledge graph"""
        bottlenecks = self.get_bottlenecks()
        isolated = self.get_disconnected_entities()

        return {
            "name": self.name,
            "domain": self.domain,
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "critical_path": self.get_critical_path(),
            "bottlenecks": bottlenecks[:5],  # Top 5
            "isolated_entities": [e.name for e in isolated],
            "entity_types": list(set(e.type for e in self.entities.values()))
        }
