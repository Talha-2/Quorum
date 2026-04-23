# Extending TeamTwin

Guides for adding new agents, connectors, and features.

## Adding a New Agent

### 1. Create Agent File

Create `backend/agents/my_agent.py`:

```python
from .base import Agent, AgentInput, AgentOutput
from config import settings
from anthropic import Anthropic
import json

client = Anthropic()

MY_PROMPT = """You are the My Agent for TeamTwin.

Your job is to [specific purpose].

Respond ONLY with valid JSON...
"""

class MyAgent(Agent):
    """Description of what this agent does"""

    def __init__(self, db_session=None):
        super().__init__("MyAgent", db_session)

    async def run(self, input_data: AgentInput) -> AgentOutput:
        """Execute agent logic"""
        try:
            # Extract inputs
            some_input = input_data.context.get("some_key")
            if not some_input:
                return self._create_output(
                    status="error",
                    result={},
                    error="Missing required input"
                )

            # Call Claude
            message = client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"{MY_PROMPT}\n\nInput: {some_input}"
                    }
                ]
            )

            # Parse response
            result = json.loads(message.content[0].text)

            # Log
            self._log(f"Result: {result}")

            return self._create_output(
                status="success",
                result=result,
                evidence=[some_input]
            )

        except json.JSONDecodeError as e:
            return self._create_output(
                status="error",
                result={},
                error=f"Parse error: {str(e)}"
            )
        except Exception as e:
            return self._create_output(
                status="error",
                result={},
                error=f"Error: {str(e)}"
            )
```

### 2. Register in Orchestrator

In `backend/orchestrator.py`:

```python
from agents import MyAgent

class Orchestrator:
    def __init__(self, db_session=None):
        # ... existing agents ...
        self.my_agent = MyAgent(db_session)

    async def process_artifact(self, ...):
        # ... intake, entity resolution ...

        # Add your agent to the pipeline
        self._log("MyAgent", "Running my agent...")
        my_input = AgentInput(
            project_id=project_id,
            context={
                "data": some_data,
                "more": more_data
            }
        )
        my_result = await self.my_agent.run(my_input)
        if my_result.status != "success":
            self._log("MyAgent", f"⚠ Failed: {my_result.error}")
        else:
            self._log("MyAgent", "✓ Done")

        # Store results
        my_output = my_result.result
```

### 3. Add to Response

In `orchestrator.py` return statement:

```python
return {
    "status": "success",
    "classification": classification,
    "entities": entities,
    "my_agent_output": my_output,  # Add here
    "risk_assessment": risk_assessment,
    "recommendations": recommendations,
    "critique": critique,
    "execution_log": self.execution_log
}
```

### 4. Test It

```python
# backend/tests/agents/test_my_agent.py
import pytest
from agents import MyAgent, AgentInput

@pytest.mark.asyncio
async def test_my_agent():
    agent = MyAgent()
    input_data = AgentInput(
        context={"some_key": "some_value"}
    )
    output = await agent.run(input_data)
    assert output.status == "success"
    assert "expected_field" in output.result
```

Run:
```bash
docker-compose exec backend pytest tests/agents/test_my_agent.py
```

## Adding a Connector

### Example: GitHub Connector

Create `backend/connectors/github_connector.py`:

```python
import httpx
from models import Artifact, Team, User, Project
from config import settings
from typing import List
import json

class GitHubConnector:
    """Ingest data from GitHub"""

    def __init__(self):
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    async def ingest_prs(self, repo_owner: str, repo_name: str, db_session) -> List[Artifact]:
        """Fetch PRs and convert to artifacts"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            prs = resp.json()

        artifacts = []
        for pr in prs:
            artifact = Artifact(
                artifact_type="github_pr",
                title=pr["title"],
                content=pr["body"],
                source_url=pr["html_url"],
                metadata={
                    "number": pr["number"],
                    "author": pr["user"]["login"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "reviews": pr.get("review_comments", 0)
                }
            )
            artifacts.append(artifact)

        # Save to database
        for artifact in artifacts:
            db_session.add(artifact)
        db_session.commit()

        return artifacts

    async def ingest_issues(self, repo_owner: str, repo_name: str, db_session) -> List[Artifact]:
        """Fetch issues"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            issues = resp.json()

        artifacts = []
        for issue in issues:
            artifact = Artifact(
                artifact_type="github_issue",
                title=issue["title"],
                content=issue["body"],
                source_url=issue["html_url"],
                metadata={
                    "number": issue["number"],
                    "state": issue["state"],
                    "labels": [l["name"] for l in issue.get("labels", [])],
                    "assignee": issue["assignee"]["login"] if issue.get("assignee") else None
                }
            )
            artifacts.append(artifact)

        for artifact in artifacts:
            db_session.add(artifact)
        db_session.commit()

        return artifacts

    async def sync_repo(self, repo_owner: str, repo_name: str, project_id: str, db_session):
        """Sync entire repo: PRs + issues"""
        prs = await self.ingest_prs(repo_owner, repo_name, db_session)
        issues = await self.ingest_issues(repo_owner, repo_name, db_session)

        # Link to project
        from models import Project
        project = db_session.query(Project).filter_by(id=project_id).first()
        if project:
            for artifact in prs + issues:
                artifact.project_id = project_id
            db_session.commit()

        return {"prs": len(prs), "issues": len(issues)}
```

### Usage

```python
# backend/sync.py
from connectors import GitHubConnector
from orchestrator import Orchestrator
from sqlalchemy.orm import Session

async def sync_github_repo(db: Session):
    connector = GitHubConnector()
    orchestrator = Orchestrator(db_session=db)

    # Sync repo
    result = await connector.sync_repo(
        repo_owner="your-org",
        repo_name="repo-name",
        project_id="project-id",
        db_session=db
    )
    print(f"Synced {result['prs']} PRs and {result['issues']} issues")

    # Analyze each
    for artifact in db.query(Artifact).filter_by(artifact_type="github_pr").all():
        analysis = await orchestrator.process_artifact(
            artifact_type="github_pr",
            content=artifact.content,
            project_id=artifact.project_id,
            metadata=artifact.metadata
        )
        print(f"Analyzed {artifact.title}")
```

## Customizing Risk Scoring

### Current Approach

The `DeliveryRiskAgent` uses Claude to assess risk based on signals.

### Option 1: Rule-Based Scoring

Create `backend/scoring.py`:

```python
def calculate_risk_score(signals: Dict) -> float:
    """Deterministic risk scoring based on signals"""

    score = 0.0

    # Blockers: +0.25 per blocker
    if "blockers" in signals:
        score += min(len(signals["blockers"]) * 0.25, 0.5)

    # Review bottleneck: +0.15 if single reviewer
    if signals.get("single_reviewer"):
        score += 0.15

    # Spec clarity: +0.20 if unclear
    if not signals.get("spec_clear"):
        score += 0.20

    # Scope creep: +0.20 if >20% growth
    if signals.get("scope_growth", 0) > 0.2:
        score += 0.20

    # Key person risk: +0.10 per risk
    score += min(signals.get("key_person_risks", 0) * 0.10, 0.30)

    return min(score, 1.0)
```

### Option 2: Custom Prompt

Modify `backend/agents/delivery_risk.py`:

```python
CUSTOM_RISK_PROMPT = """You are assessing delivery risk.

Weight these signals:
1. Unresolved dependencies: high weight (0.4-0.6)
2. Review bottlenecks: medium weight (0.15-0.25)
3. Scope creep: medium weight (0.15-0.20)
4. Specification clarity: low weight (0.10-0.15)

Consider time to deadline and team capacity.

Return JSON with score and drivers.
"""
```

### Option 3: Weighted Combination

```python
def calculate_weighted_risk(claude_score: float, rule_score: float) -> float:
    """Blend Claude assessment with rule-based scoring"""
    # 70% Claude (better for nuance)
    # 30% Rule-based (consistent, explainable)
    return (claude_score * 0.7) + (rule_score * 0.3)
```

## Adding Dashboard Views

### Example: Dependency Graph View

Create `frontend/app/dependencies/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import axios from 'axios'

interface Dependency {
  source: string
  target: string
  type: string
}

export default function DependenciesPage() {
  const [dependencies, setDependencies] = useState<Dependency[]>([])

  useEffect(() => {
    // Fetch dependencies for project
    const fetchDeps = async () => {
      try {
        const resp = await axios.get(
          'http://localhost:8000/projects/mobile-v2/dependencies'
        )
        setDependencies(resp.data.dependencies)
      } catch (error) {
        console.error('Failed to fetch dependencies', error)
      }
    }
    fetchDeps()
  }, [])

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Dependency Graph</h1>

      {/* Simple list view (replace with D3/Cytoscape for interactive graph) */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="font-semibold">Dependencies</h2>
        </div>
        <div className="divide-y">
          {dependencies.map((dep, i) => (
            <div key={i} className="p-4">
              <p className="text-sm">
                <span className="font-medium">{dep.source}</span>
                <span className="mx-2 text-gray-400">→</span>
                <span className="font-medium">{dep.target}</span>
                <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                  {dep.type}
                </span>
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

## Database Migrations

As you add new models, manage schema changes:

```bash
# Use Alembic for migrations
alembic init migrations

# After changing models.py
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head
```

## Performance Optimization

### 1. Cache Known Entities

```python
# backend/cache.py
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_canonical_project(mention: str) -> str:
    """Cache project name mappings"""
    # Query DB or return cached result
    pass
```

### 2. Batch Processing

```python
# Process multiple artifacts in parallel
from celery import group

task_group = group([
    analyze_artifact.s(artifact)
    for artifact in artifacts
])
result = task_group.apply_async()
```

### 3. Index Database

```sql
-- Add indexes for common queries
CREATE INDEX idx_projects_team_id ON projects(team_id);
CREATE INDEX idx_tickets_project_id ON tickets(project_id);
CREATE INDEX idx_risks_project_id ON risks(project_id);
```

## Testing New Agents

```bash
# Unit test
docker-compose exec backend pytest tests/agents/test_my_agent.py

# Integration test
docker-compose exec backend pytest tests/integration/test_orchestration.py

# E2E test
curl -X POST http://localhost:8000/analyze -d '{...}'
```

## Deploying Changes

```bash
# Build new images
docker-compose build

# Stop old services
docker-compose down

# Start new services
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

## Best Practices

1. **Always return structured JSON** from agents
2. **Include evidence** - cite what led to conclusion
3. **Set confidence scores** - be honest about uncertainty
4. **Log execution** - aid debugging
5. **Test incrementally** - unit → integration → e2e
6. **Version your prompts** - track changes to agent behavior
7. **Monitor in production** - track accuracy over time

---

For more, see [ARCHITECTURE.md](ARCHITECTURE.md)
