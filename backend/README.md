# Quorum backend

This directory is an installable Python package (using a `src/` layout).

## Local development

From the repository root:

```bash
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\activate
# macOS/Linux:
# source backend/.venv/bin/activate

pip install -e "backend[dev]"
python -m uvicorn quorum_backend.main:app --reload --port 8000
```

