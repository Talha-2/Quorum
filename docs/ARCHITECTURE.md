# TeamTwin Architecture

## System Overview

TeamTwin is a controlled multi-agent system for engineering execution intelligence.

```
┌─────────────────────────────────────────────────────────────┐
│                      INPUT LAYER                            │
│  PRDs, PRs, Issues, Slack, Meeting Notes, Customer Feedback │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               ORCHESTRATION LAYER                           │
│                  orchestrator.py                            │
│  (Controls sequential flow, manages context, validation)    │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬───────────┬──────────┐
        │             │             │           │          │
     [1]│          [2]│          [3]│        [4]│       [5]│
   Intake        Entity      Delivery    Recom-   Critic
   Agent        Resol.        Risk      mendation Agent
                Agent          Agent      Agent
        │             │             │           │          │
        └─────────────┼─────────────┴───────────┴──────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              KNOWLEDGE LAYER                                │
│    PostgreSQL (Relational) + pgvector (Semantic Search)     │
│  Teams, Users, Projects, Tickets, Risks, Recommendations   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               OUTPUT LAYER                                  │
│   API (JSON) + Frontend Dashboard + Recommendations        │
└─────────────────────────────────────────────────────────────┘
```

## Key Principles

1. **Controlled Flow** - Not peer-to-peer. Supervisor (Orchestrator) controls execution order.
2. **Structured I/O** - Every agent returns JSON, not text.
3. **Evidence-Based** - All conclusions cite sources. No vague advice.
4. **Self-Checking** - Critic agent validates before output.
5. **Incremental** - Start simple, extend incrementally.

## Component Deep Dive

### 1. Intake Agent

**Role:** First touch - classify and route

**Input:**
```python
{
  "artifact_type": "github_pr",  # Pre-identified
  "content": "...",               # Raw text
  "artifact_type": "...",
  "metadata": {...}
}
```

**Process:**
1. Call Claude with classification prompt
2. Extract: type, urgency, project, entities, signals
3. Return confidence scores

**Output:**
```json
{
  "artifact_type": "github_pr",
  "urgency": "high",
  "related_project": "Mobile Checkout v2",
  "entities": {
    "teams": ["Mobile", "Backend"],
    "blockers": ["API schema unresolved"],
    "dependencies": ["Backend API contract"]
  },
  "needs_analysis": true,
  "signals": [
    {
      "type": "dependency_blocker",
      "description": "..."
    }
  ]
}
```

**Code:** `backend/agents/intake.py`

### 2. Entity Resolution Agent

**Role:** Map messy language to canonical entities

**Problem Solved:**
- "growth onboarding" = "Growth Onboarding Initiative"?
- "Bob from backend" = User "Robert Smith"?
- "auth team" = Team "Authentication"?

**Input:**
- List of entity mentions
- (Optional) Known canonical entities for context

**Process:**
1. Extract mentions from classification
2. Call Claude with resolution prompt + known entity list
3. Return confidence-scored canonical references

**Output:**
```json
{
  "resolved_entities": [
    {
      "type": "project",
      "raw_mention": "growth onboarding",
      "canonical_name": "Growth Onboarding Initiative",
      "confidence": 0.95,
      "alternate_names": ["new activation", "signup revamp"]
    }
  ],
  "unresolved": [
    {
      "type": "project",
      "mention": "mysterious payment thing",
      "reason": "Too vague"
    }
  ]
}
```

**Code:** `backend/agents/entity_resolution.py`

### 3. Delivery Risk Agent

**Role:** Estimate probability of delay

**Signals Evaluated:**
- Dependency blockers (external blocks)
- Review bottlenecks (single reviewer)
- Spec clarity (fuzzy requirements)
- Scope creep (growing scope)
- Key person risk (critical path concentration)
- Velocity mismatch (planned vs historical)
- Issue reopens (rework)
- PR churn (revisions)

**Input:**
```json
{
  "project_name": "Mobile Checkout v2",
  "target_date": "2026-04-30",
  "signals": {
    "blockers": ["API schema unresolved"],
    "pr_churn": 12,
    "scope_growth": 0.22
  }
}
```

**Process:**
1. Format signals for Claude
2. Call risk assessment prompt
3. Parse response, extract score + drivers

**Output:**
```json
{
  "risk_score": 0.78,
  "risk_level": "high",
  "predicted_delay_days": 12,
  "confidence": 0.71,
  "drivers": [
    {
      "type": "dependency_blocker",
      "description": "Backend API schema unresolved",
      "weight": 0.4,
      "evidence": ["issue_123", "slack_456"]
    }
  ],
  "critical_path": [
    "Feature A (owned by person X)",
    "Integration test suite"
  ]
}
```

**Code:** `backend/agents/delivery_risk.py`

### 4. Recommendation Agent

**Role:** Propose specific interventions

**Input:**
- Project name
- Full risk assessment

**Process:**
1. Format risk assessment
2. Call recommendation prompt
3. Generate specific, evidence-backed actions

**Output:**
```json
{
  "recommendations": [
    {
      "action": "Lock API contract by Friday",
      "impact": "high",
      "priority": "high",
      "owner": "Backend Lead (Sarah)",
      "effort": "4 hours",
      "evidence": [
        "Blocking 3 dependent features",
        "Currently in 5 day review"
      ],
      "next_steps": [
        "Schedule contract review with mobile team",
        "Document decisions in design doc"
      ]
    }
  ]
}
```

**Code:** `backend/agents/recommendation.py`

### 5. Critic Agent

**Role:** Challenge conclusions

**Questions:**
- Enough evidence?
- Contradictory signals?
- Generic advice?
- Causation vs correlation?

**Input:**
- Full analysis (classification + risk + recommendations)

**Process:**
1. Format analysis
2. Call critic prompt (adversarial)
3. Identify weaknesses

**Output:**
```json
{
  "issues": [
    {
      "type": "insufficient_evidence",
      "severity": "medium",
      "description": "Risk score based on only 1-2 signals",
      "recommendation": "Lower confidence to 0.3"
    }
  ],
  "overall_assessment": "Analysis is sound / needs revision",
  "confidence_adjustment": -0.15
}
```

**Code:** `backend/agents/critic.py`

## Data Model

### Core Tables

```sql
-- Organization structure
teams (id, name, description, owner_id)
users (id, name, email, github_handle)
team_members (team_id, user_id)

-- Work tracking
projects (id, name, team_id, owner_id, status, target_date)
tickets (id, project_id, title, assignee_id, status, priority)
dependencies (id, ticket_a_id, ticket_b_id, type, confidence)

-- Intelligence layer
risks (id, project_id, type, description, score, predicted_delay, drivers)
recommendations (id, project_id, risk_id, action, impact, status)
artifacts (id, type, title, content, embedding, project_id, metadata)
observation_events (id, type, project_id, data)
```

### Key Relationships

```
Team --has-many--> Project --has-many--> Ticket
                    ^           |
                    |      has-many-deps
                    |           |
                  owns        Dependency
                    |
                    +-- has-many--> Risk
                    +-- has-many--> Recommendation
```

## API Layer

### Main Endpoints

```
POST /analyze
  Input: artifact_type, content, project_id, metadata
  Output: Full analysis with classification, risk, recommendations

POST /projects/{id}/analyze-batch
  Input: List of artifacts
  Output: Analysis for each

GET /projects/{id}/risks
  Output: All risks for project

GET /projects/{id}/recommendations
  Output: All recommendations for project

GET /health
  Output: Service status
```

### Response Structure

All responses follow this pattern:

```json
{
  "status": "success|error|partial",
  "result": {...},
  "execution_log": [...],
  "error": null|"error message"
}
```

## Orchestration Flow

```python
orchestrator.process_artifact(
    artifact_type="github_pr",
    content="...",
    project_id="mobile-v2",
    metadata={...}
)
```

**Steps:**
1. Intake classification
2. If fails → return error
3. Entity resolution
4. If has project → risk assessment
5. If risk high → recommendations
6. Critic review
7. Store results in database
8. Return full structured output

**Failure Handling:**
- Partial failures don't stop pipeline
- Each agent failure logged
- Critic flags issues
- Output includes execution_log for debugging

## Extension Points

### Add an Agent

1. Create `backend/agents/new_agent.py`
2. Extend `Agent` base class
3. Implement `async def run()`
4. Return `AgentOutput`
5. Register in `Orchestrator.__init__()`
6. Add to pipeline in `process_artifact()`

### Add a Connector

1. Create `backend/connectors/github_connector.py`
2. Implement source-specific ETL
3. Convert to `Artifact` objects
4. Store in database
5. Trigger analysis via orchestrator

### Add a Dashboard View

1. Create page in `frontend/app/new-page/page.tsx`
2. Fetch from API endpoints
3. Render with React components
4. Use Tailwind for styling

## Performance Considerations

### Bottlenecks

1. **Claude API calls** - Each agent makes 1-2 calls
   - Latency: 2-5 seconds per call
   - Cost: ~0.1-0.5 cents per artifact
   
2. **Database queries** - Context gathering
   - Optimization: Index by project_id, timestamp
   
3. **Embedding generation** - For semantic search
   - Only on demand, not required for basic functionality

### Optimization Strategy

1. **Cache** - Known entities, past analyses
2. **Async** - Use Celery for batch processing
3. **Parallel** - Some agents can run in parallel (with careful ordering)
4. **Model routing** - Smaller models for classification, larger for reasoning

## Deployment

### Local Development

```bash
docker-compose up -d
```

### Production

1. Use managed PostgreSQL (AWS RDS, etc)
2. Use managed Redis (AWS ElastiCache, etc)
3. Container orchestration (k8s, ECS, etc)
4. Add auth/RBAC layer
5. Rate limiting on API
6. Observability (logs, metrics, traces)

## Monitoring & Observability

### Metrics to Track

```
- Request latency (per agent)
- Token usage (Claude API)
- Error rate (per agent)
- Confidence distribution (risk scores)
- Recommendation acceptance rate
- Forecast accuracy (actual vs predicted delays)
```

### Logging

All agent runs logged to `execution_log`. Example:

```json
{
  "timestamp": "2026-04-09T10:30:00Z",
  "agent": "DeliveryRiskAgent",
  "message": "Risk score: 0.78 (high)",
  "status": "success"
}
```

### Debugging

Check `execution_log` in response to understand agent execution:

```bash
curl http://localhost:8000/analyze | jq '.execution_log'

[
  {
    "timestamp": "2026-04-09T10:30:00Z",
    "agent": "Intake",
    "message": "Classified as github_pr"
  },
  ...
]
```

## Testing Strategy

### Unit Tests

```python
# backend/tests/agents/test_intake.py
async def test_intake_classifies_pr():
    agent = IntakeAgent()
    input = AgentInput(context={
        "content": "PR description...",
        "artifact_type": "github_pr"
    })
    output = await agent.run(input)
    assert output.status == "success"
    assert output.result["artifact_type"] == "github_pr"
```

### Integration Tests

```python
# Test full orchestration pipeline
async def test_end_to_end_analysis():
    orch = Orchestrator(db_session)
    result = await orch.process_artifact(
        artifact_type="github_pr",
        content="..."
    )
    assert result["status"] == "success"
    assert "risk_assessment" in result
```

### E2E Tests

```bash
# backend/tests/e2e_test.sh
curl -X POST http://localhost:8000/analyze -d '{...}'
# Verify response structure
```

## Next Steps

See [EXTENDING.md](EXTENDING.md) for guides on:
- Adding new agents
- Building connectors
- Customizing risk scoring
- Adding new dashboard views
