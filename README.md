# Quorum

A self-hosted multi-agent reasoning platform.

Upload a document, design a topic-specific knowledge graph, instantiate one
AI agent per real-world entity, run them through a structured debate, and
generate a prediction report — all with the LLM provider of your choice.

## Quick start

You need Python 3.11+, Node.js 20+, and an LLM API key. The free Google
Gemini tier works fine for development.

```bash
# 1. Clone
git clone https://github.com/Talha-2/Quorum.git
cd Quorum

# 2. Configure
cp .env.example .env.local
# Edit .env.local — set LLM_PROVIDER and the API key for your chosen provider

# 3. Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
python -m uvicorn backend.main:app --reload --port 8000

# 4. Frontend (in a second terminal)
cd frontend
npm install
npm run dev

# 5. Open
# http://localhost:3000             ← landing
# http://localhost:3000/workspace   ← live workspace
# http://localhost:3000/docs        ← documentation
```

Drag a PDF onto the workspace, type your brief, click **Generate ontology +
graph**, and walk through the seven stages.

## Pipeline

```
01  Ontology Generation       → topic-specific entity + edge type schema
02  GraphRAG Build            → typed knowledge graph from your brief + docs
03  Environment Setup         → one LLM-designed agent per entity
04  Generate Config           → time + per-agent activity + platform configs
05  Initial Activation        → narrative + hot topics + starter posts
06  Run Simulation            → round-by-round debate with consensus
07  Generate Report           → multi-section markdown prediction report
```

There's also a Stage 0 (document upload) and a Stage 8 (chat with any
individual agent post-simulation).

## Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend (Next.js 14 + React + d3-force)   │
│  ─ landing  /  workspace  /  docs           │
│  ─ live graph + debate stream + dashboard   │
└──────────────────┬──────────────────────────┘
                   │ REST (JSON + multipart)
┌──────────────────▼──────────────────────────┐
│  Backend (FastAPI + Python 3.11)            │
│  ─ pipeline.router    7-stage endpoints     │
│  ─ pipeline.models    typed dataclasses     │
│  ─ pipeline.*         per-stage services    │
│  ─ llm.py             provider abstraction  │
└──────────────────┬──────────────────────────┘
                   │
   ┌───────────────┼────────────────┐
   ▼               ▼                ▼
 Google         Azure AI        Anthropic
 Gemini         Foundry         Claude
```

No required external dependencies beyond your chosen LLM provider. Project
state is persisted to a local pickle file so projects survive backend
restarts.

## What's in the box

- **Workspace** — three-view UI (Workbench / Graph / Agents) with the
  seven-stage pipeline, force-directed knowledge graph, agent gallery,
  and live system dashboard
- **Backend** — FastAPI service exposing the full pipeline as a typed
  REST API
- **Document upload** — PDF, Markdown, and plain text reality seeds
- **LLM-agnostic** — Google Gemini (free), Anthropic Claude (paid), or
  Azure AI Foundry (Kimi K2.5 and others)
- **On-disk persistence** — projects survive backend restarts
- **Prediction reports** — multi-section Markdown reports with
  agent-quoted blockquotes, downloadable as `.md`

## Documentation

Full docs live inside the frontend at `/docs` and source MDX is in
[frontend/content/docs/](frontend/content/docs/).

- **Quickstart** — install and run your first simulation in five minutes
- **Concepts** — the data model and architecture
- **Pipeline stages** — detailed reference for each stage
- **Workspace guide** — UI walkthrough
- **API reference** — every endpoint with JSON schemas
- **Configuration** — env vars, LLM providers, persistence
- **Deployment** — Docker Compose, reverse proxy, systemd
- **Troubleshooting** — common errors and fixes

## Docker Compose

```bash
cp .env.example .env
# Edit .env with your LLM credentials
docker-compose up -d
```

The stack runs the backend on port 8000 and the frontend on port 3000,
with project state persisted to a named volume.

## License

MIT.
