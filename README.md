# Quorum

A self-hosted multi-agent reasoning platform.

Quorum turns a brief and optional source documents into a structured,
inspectable multi-agent run:

1. create a project
2. upload reality-seed documents
3. generate an ontology
4. build a knowledge graph
5. instantiate agents from graph entities
6. generate simulation config
7. generate an activation plan
8. run a debate
9. generate a markdown report

The stack is provider-agnostic and supports Google Gemini, Anthropic Claude,
Azure AI Foundry, and a local deterministic provider for offline testing.

## Quick start

You need Python 3.11+ and Node.js 20+.

```bash
# 1. Clone
git clone https://github.com/Talha-2/Quorum.git
cd Quorum

# 2. Configure
cp .env.example .env.local
# Edit .env.local and choose an LLM provider

# 3. Backend (local dev)
python -m venv backend/.venv
# Windows
backend\.venv\Scripts\activate
# macOS / Linux
# source backend/.venv/bin/activate
pip install -e "backend[dev]"
python -m uvicorn quorum_backend.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev
```

Open:

- `http://localhost:3000`
- `http://localhost:3000/workspace`
- `http://localhost:3000/docs`

## Production pipeline

```text
00  Create Project / Upload     -> brief + optional source documents
01  Ontology Generation         -> topic-specific entity and edge schema
02  Graph Build                 -> typed graph from the brief and source docs
03  Environment Setup           -> one agent per speaker-capable entity
04  Simulation Config           -> time, activity, and platform configuration
05  Initial Activation          -> narrative direction, hot topics, starter posts
06  Run Simulation              -> round-by-round debate + consensus
07  Generate Report             -> markdown report
08  Agent Chat                  -> post-run follow-up with one agent
```

The backend enforces stage ordering and serializes mutations per project so the
pipeline runs one stage at a time.

## Architecture

- `backend/src/quorum_backend/main.py`: application entrypoint and health endpoint
- `backend/src/quorum_backend/pipeline/router.py`: project store, stage
  orchestration, locking, and persistence
- `backend/src/quorum_backend/pipeline/*`: per-stage services
- `backend/src/quorum_backend/llm.py`: provider abstraction and local
  deterministic provider
- `frontend/components/workspace/quorum-pipeline.tsx`: active workspace UI
- `frontend/content/docs/*`: canonical Fumadocs documentation

The previous legacy simulation branch has been removed. The repository now has
one production path.

## Verification

Backend end-to-end tests:

```bash
backend\.venv\Scripts\python -m pytest backend\tests -q
```

Frontend production build:

```bash
cd frontend
npm run build
```

## Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

The compose stack serves the backend on port `8000` and the frontend on port
`3000`.

## Documentation

The full documentation site ships in the app at `/docs`.

Key pages:

- `Introduction`
- `Architecture`
- `Agent Architecture`
- `Concepts`
- `Pipeline stages`
- `API reference`
- `Production readiness`
- `Testing`

## License

MIT
