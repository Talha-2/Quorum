# Quorum backend — FastAPI + the seven-stage reasoning pipeline
#
# Build context: the repository root (NOT the backend/ directory).
# This is required so the `backend` Python package can be imported as a
# top-level module by uvicorn.
#
#   docker build -f backend/Dockerfile -t quorum-backend .
#
# (docker-compose.yml already sets context: . for this service.)

FROM python:3.11-slim

WORKDIR /app

# System packages: gcc for any C extensions, curl for the healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so they cache between code changes
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the backend package — preserves the `backend.<module>` import path
COPY backend /app/backend

# Persistent project store directory — mount a volume here in production
RUN mkdir -p /app/data
ENV QUORUM_PROJECT_STORE_PATH=/app/data/projects.pkl
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Container-level health check hits /health every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
