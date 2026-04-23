Write-Host "Starting Backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (-not (Test-Path .venv)) { python -m venv .venv }; .\.venv\Scripts\activate; pip install -r requirements.txt; cd ..; python -m uvicorn backend.main:app --reload --port 8000"

Write-Host "Starting Frontend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm install; npm run dev"

Write-Host "Both services are starting in separate PowerShell windows." -ForegroundColor Green
