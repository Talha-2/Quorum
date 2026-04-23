"""
Quorum pipeline services.

The pipeline turns a brief (and optional uploaded documents) into:
1. an ontology (entity + edge types)
2. a knowledge graph (entities + relations matching the ontology)
3. a population of agents (one per extracted entity)
4. a simulated debate
5. a report and post-sim deep interaction

Each stage is a thin service class that holds no state — all state lives on
the Project object so the pipeline can be paused, replayed, and inspected.

The graph storage abstraction (`GraphMemoryStore`) is in-memory by default but
can be swapped for a Zep Cloud impl without touching anything else.
"""
