# Contributing to Quorum

## Quick start (recommended)

- Fork the repo and create a feature branch.
- Run the stack with Docker Compose:

```bash
cp .env.example .env
docker compose up -d --build
```

## Local development

### Backend

```bash
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\activate
# macOS/Linux:
# source backend/.venv/bin/activate

pip install -e "backend[dev]"
python -m uvicorn quorum_backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
backend\.venv\Scripts\python -m pytest backend\tests -q
cd frontend
npm run build
```

## Pull requests

- Keep PRs focused and small when possible.
- If you change pipeline behavior or API shape, update the docs in
  `frontend/content/docs/`.
- Include a brief test plan in the PR description.

