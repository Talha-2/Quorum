$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

function Invoke-FreePort {
    param([int]$Port)
    & "$RepoRoot\scripts\free-port.ps1" -Port $Port
}

Write-Host "Freeing port 8000 (backend)..." -ForegroundColor Cyan
Invoke-FreePort -Port 8000

$backendCmd = @"
Set-Location '$RepoRoot'
if (-not (Test-Path backend\.venv)) { python -m venv backend\.venv }
backend\.venv\Scripts\activate
pip install -e `"backend[dev]`"
python -m uvicorn quorum_backend.main:app --reload --host 127.0.0.1 --port 8000
"@

$frontendCmd = @"
Set-Location '$RepoRoot\frontend'
npm install
npm run dev
"@

Write-Host "Starting Backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "Starting Frontend (auto-picks bindable port, often 3117+ on Windows) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "Both services are starting in separate PowerShell windows." -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Frontend: see the frontend window for the URL (often http://127.0.0.1:3117)" -ForegroundColor Green
