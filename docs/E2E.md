# End-to-End Flow Guide

This repo contains a fastapi backend plus next.js frontend that together simulate "GenericSwarm" multi-agent debates across domains. The deterministic e2e path below runs entirely offline using the new local LLM provider, so you can validate the system without Gemini/Claude keys.

## Backend architecture recap
- ackend/core: generic agents, chat interface, simulator, knowledge graph primitives.
- ackend/domains/execution.py: seeds the execution-intelligence domain with archetypes + knowledge graph.
- ackend/main.py: FastAPI app that wires initialization, simulation, chat, history, and comparison endpoints.
- ackend/llm.py: now supports LLM_PROVIDER=local for deterministic responses alongside Google Gemini or Claude.

## Frontend recap
- rontend/app/page.tsx: Next.js client that hits the /initialize, /chat, and /simulate endpoints.
- Uses Tailwind for UI and fetch for API calls; no server components are required for the e2e.

## Running the e2e test (backend only)
1. Install backend dependencies (FastAPI, etc.):
   `ash
   cd backend
   pip install -r requirements.txt
   `
2. Export the local provider flag and run pytest:
   `ash
   set LLM_PROVIDER=local   # Windows PowerShell:  = "local"
   pytest backend/tests/test_e2e_execution.py -q
   `
3. The test spins up the FastAPI app in-process, executes the following sequence, and asserts the responses:
   - POST /initialize/execution
   - POST /simulate
   - POST /chat/{simulation_id} with consensus
   - GET /simulation/{simulation_id}/history

Because it exercises the public API instead of lower-level units, it represents the full data/agent/chat flow end to end.

## Manual e2e check (full stack)
1. Copy .env.example to .env, set LLM_PROVIDER=local (or google / claude with keys) plus usual FastAPI config.
2. Start services:
   `ash
   docker-compose up -d
   `
3. Initialize execution domain using curl or the frontend “Start Execution Domain” button.
4. Use the frontend chat to ask questions with consensus toggled on. The deterministic provider ensures the simulation stays offline but still returns structured predictions.

## Extending beyond execution
To add domains, duplicate the execution domain pattern: define archetypes, build the knowledge graph, wire it via /initialize/{domain} plus scenario builders. The same e2e hook (local provider + pytest) can be copied for new domain-level tests by targeting the new initialization route.
