.PHONY: help setup dev stop logs clean backend-install backend-dev backend-test frontend-install frontend-dev frontend-build test

ifeq ($(OS),Windows_NT)
	VENV_PY = backend\.venv\Scripts\python
	VENV_PIP = backend\.venv\Scripts\pip
else
	VENV_PY = backend/.venv/bin/python
	VENV_PIP = backend/.venv/bin/pip
endif

help:
	@echo "Quorum Development"
	@echo ""
	@echo "  make setup       - Setup (copy .env)"
	@echo "  make dev         - Start all services"
	@echo "  make stop        - Stop services"
	@echo "  make logs        - Tail logs"
	@echo "  make clean       - Clean up"
	@echo ""

setup:
	cp .env.example .env
	@echo "✓ Created .env - edit it and add the credentials for your chosen LLM provider"

dev:
	docker compose up -d --build
	@echo "✓ Services starting..."
	@echo ""
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	@echo "✓ Cleaned"

backend-install:
	python -m venv backend/.venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PIP) install -e "backend[dev]"

backend-dev:
	$(VENV_PY) -m uvicorn quorum_backend.main:app --reload --port 8000

backend-test:
	$(VENV_PY) -m pytest backend/tests -q

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

test: backend-test frontend-build
