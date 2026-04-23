# Adding Domains to GenericSwarm

How to add a new domain (finance, policy, creative, etc).

## 5-Step Process

### Step 1: Define Agents

Create `backend/domains/your_domain.py`:

```python
from core.types import AgentArchetype, AgentPersonality, Entity, Relationship
from core.knowledge import KnowledgeGraph
from core.agent import Agent, AgentPool
import uuid

# Define agents for your domain
ANALYST = AgentArchetype(
    id=str(uuid.uuid4()),
    name="Market Analyst",
    description="...",
    personality=AgentPersonality(
        optimism=0.5,
        risk_tolerance=0.4,
        communication_style="technical"
    ),
    expertise=["markets", "finance"],
    responsibilities=["Analyze trends", "Identify risks"],
    goals=["Accurate forecasts", "Risk mitigation"],
    constraints=["Evidence-based"]
)

TRADER = AgentArchetype(
    # Similar structure
)

def create_your_domain_agents(knowledge: Knowledge) -> AgentPool:
    """Create agents for this domain"""
    pool = AgentPool(knowledge)
    
    analyst = Agent(ANALYST, knowledge)
    trader = Agent(TRADER, knowledge)
    
    pool.add_agent(analyst)
    pool.add_agent(trader)
    
    return pool
```

### Step 2: Build Knowledge Graph

```python
def build_knowledge_graph(artifacts: Dict[str, str]) -> KnowledgeGraph:
    """Build knowledge graph from domain artifacts"""
    
    graph = KnowledgeGraph("Your Domain", "your_domain")
    
    # Add entities
    entity1 = Entity(
        id="ent-001",
        name="Entity Name",
        type="entity_type",  # Your domain types
        domain="your_domain",
        attributes={...}  # Domain-specific data
    )
    graph.add_entity(entity1)
    
    # Add relationships
    rel = Relationship(
        id=str(uuid.uuid4()),
        source_id="ent-001",
        target_id="ent-002",
        type="relationship_type",  # Your relationship types
        strength=0.8
    )
    graph.add_relationship(rel)
    
    return graph
```

### Step 3: Register in API

Edit `backend/main.py`:

```python
from domains.your_domain import (
    create_your_domain_agents,
    build_knowledge_graph
)

@app.post("/initialize/your_domain")
async def initialize_your_domain(artifacts: Optional[Dict[str, str]] = None):
    """Initialize your domain simulation"""
    try:
        sim_id = "your_domain-" + str(len(simulations))
        
        # Build knowledge
        graph = build_knowledge_graph(artifacts or {})
        knowledge = graph.to_knowledge()
        
        # Create agents
        agents = create_your_domain_agents(knowledge)
        
        # Setup simulation
        simulator = ScenarioSimulator(agents, knowledge)
        chat = ChatInterface(agents, knowledge)
        
        simulations[sim_id] = {
            "domain": "your_domain",
            "graph": graph,
            "knowledge": knowledge,
            "simulator": simulator,
            "agents": agents
        }
        chats[sim_id] = chat
        agent_pools[sim_id] = agents
        
        return {
            "simulation_id": sim_id,
            "domain": "your_domain",
            "agents": agents.get_profiles(),
            "status": "ready"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 4: Test

```bash
# Initialize
curl -X POST http://localhost:8000/initialize/your_domain

# Chat
curl -X POST http://localhost:8000/chat/{sim_id} \
  -H "Content-Type: application/json" \
  -d '{"message": "Your question here", "get_consensus": true}'

# Run scenario
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "your_domain",
    "scenario_description": "What if X?",
    "scenario_changes": {...}
  }'
```

### Step 5: Add to Frontend

Update `frontend/app/page.tsx` to support your domain:

```tsx
const initializeDomain = async (domain: string) => {
  const res = await fetch(`http://localhost:8000/initialize/${domain}`, {
    method: 'POST'
  })
  // Handle response
}

// In JSX:
<button onClick={() => initializeDomain('your_domain')}>
  Start Your Domain
</button>
```

## Example Domains

### Finance Domain

```python
# Entities: Stock, Company, Market, Index, Portfolio
# Relationships: correlates_with, influences, owns, tracks
# Agents: Analyst, Trader, Risk Manager, Economist
# Scenarios: "Interest rates rise", "Market crashes", "Fed changes policy"
```

### Policy Domain

```python
# Entities: Policy, Stakeholder, Impact, Regulation, Sector
# Relationships: affects, influenced_by, opposes, supports
# Agents: Policy Expert, Economist, Industry Rep, Citizen
# Scenarios: "Carbon tax", "New regulation", "Subsidy cut"
```

### Creative Domain

```python
# Entities: Character, Plot, Setting, Theme, Conflict
# Relationships: interacts_with, occurs_in, explores
# Agents: Novelist, Editor, Critic, Storyteller
# Scenarios: "What if character did X?", "Different ending"
```

## Domain Design Checklist

- [ ] **Agents** - Define 3-5 agent archetypes with distinct personalities
- [ ] **Entities** - List entity types in your domain (5-10 types)
- [ ] **Relationships** - Define relationship types (5-10 types)
- [ ] **Scenarios** - What "what-if" questions make sense?
- [ ] **Knowledge Graph** - How to extract entities/relationships from artifacts?
- [ ] **API endpoint** - Register `/initialize/{domain}`
- [ ] **Testing** - Can you initialize, chat, and simulate?

## Agent Personality Guide

When defining personalities, consider:

| Trait | Range | Meaning |
|-------|-------|---------|
| **optimism** | 0-1 | How optimistic (1) vs pessimistic (0) |
| **risk_tolerance** | 0-1 | Risk-averse (0) vs risk-seeking (1) |
| **caution** | 0-1 | Cautious (1) vs bold (0) |
| **communication** | | verbose, concise, technical, informal |

Example combinations:
- **Analyst**: optimism=0.5, risk=0.3, caution=0.8 (balanced, careful)
- **Trader**: optimism=0.7, risk=0.7, caution=0.3 (bold, aggressive)
- **CEO**: optimism=0.8, risk=0.6, caution=0.4 (visionary, pragmatic)
- **Critic**: optimism=0.2, risk=0.1, caution=0.95 (skeptical, thorough)

## Knowledge Graph Design

Good knowledge graphs have:

1. **Rich Entities**
   - Diverse types (not all "project" or "person")
   - Meaningful attributes
   - Time-bound if relevant

2. **Meaningful Relationships**
   - Types that convey direction (depends_on ≠ supports)
   - Strength scores (0-1 confidence)
   - Temporal info if relevant

3. **Bottleneck Detection**
   - Entities many things depend on
   - Critical paths
   - Isolated nodes (data quality issues)

Example: Execution domain
```
Entities:
- Type: project, team, person, blocker, service
- Attributes: status, owner, priority, size

Relationships:
- depends_on (project → service)
- owns (team → project)
- blocks (blocker → project)
- overloaded (person has too much)
```

## Testing Your Domain

```bash
# 1. Initialize
curl http://localhost:8000/initialize/your_domain
# Check: agents created, knowledge loaded

# 2. Chat with agents
curl http://localhost:8000/chat/{id} \
  -d '{"message": "Basic question"}'
# Check: agents respond in character

# 3. Run scenario
curl http://localhost:8000/simulate \
  -d '{
    "domain": "your_domain",
    "scenario_description": "...",
    "scenario_changes": {...}
  }'
# Check: agents predict outcomes, confidence > 0

# 4. Get consensus
curl http://localhost:8000/chat/{id} \
  -d '{"get_consensus": true, "message": "..."}'
# Check: agents debate, reach consensus
```

## Tips for Good Domains

1. **Diverse agents** - Different perspectives, not all agreeing
2. **Rich knowledge** - Enough entities/relationships for agents to reason over
3. **Meaningful scenarios** - "What-ifs" that people actually care about
4. **Clear expertise** - Each agent understands specific aspects
5. **Believable personalities** - Agents behave consistently with their traits

## Quick Reference

**File Structure:**
```
backend/domains/
├── execution.py    # Done
├── your_domain.py  # Add here
└── finance.py      # Future
```

**Domain Module Template:**
```python
from core.types import AgentArchetype, Entity, Relationship, Knowledge
from core.knowledge import KnowledgeGraph
from core.agent import Agent, AgentPool

# 1. Define agents
AGENT_1 = AgentArchetype(...)
AGENT_2 = AgentArchetype(...)

# 2. Create agents
def create_your_domain_agents(knowledge: Knowledge) -> AgentPool:
    pool = AgentPool(knowledge)
    pool.add_agent(Agent(AGENT_1, knowledge))
    pool.add_agent(Agent(AGENT_2, knowledge))
    return pool

# 3. Build knowledge
def build_knowledge_graph(artifacts: Dict) -> KnowledgeGraph:
    graph = KnowledgeGraph("...", "your_domain")
    graph.add_entity(...)
    graph.add_relationship(...)
    return graph
```

That's it! Add agents, build knowledge graph, register endpoint.

---

**Got a domain idea? Follow these steps to add it!**
