$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

function Invoke-FreePort {
    param([int]$Port)
    & "$RepoRoot\scripts\free-port.ps1" -Port $Port
}

function Test-PortBindable {
    # True if a TCP listener can bind to 127.0.0.1:$Port right now. Detects
    # both "in use" and "in a Windows excluded port range" (Hyper-V / WinNAT
    # reserve large ranges that include 8000 on many machines, which is
    # what produces WinError 10013).
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Get-BackendPort {
    # Prefer 8000 (what docs and .env.example assume); otherwise fall back
    # to a list of ports that are usually outside the Hyper-V dynamic pool.
    $candidates = @(8000, 8200, 8800, 8888, 9000, 9100, 9200)
    foreach ($p in $candidates) {
        if (Test-PortBindable -Port $p) { return $p }
    }
    throw "No bindable backend port found from candidates: $($candidates -join ', '). Try freeing Hyper-V exclusions with 'netsh int ipv4 show excludedportrange protocol=tcp'."
}

Write-Host "Freeing port 8000 (backend, if held)..." -ForegroundColor Cyan
Invoke-FreePort -Port 8000

$backendPort = Get-BackendPort
$backendUrl  = "http://127.0.0.1:$backendPort"
if ($backendPort -ne 8000) {
    Write-Host "Port 8000 is not bindable on this host (likely in a Windows excluded range)." -ForegroundColor Yellow
    Write-Host "  Using $backendPort for the backend instead." -ForegroundColor Yellow
}

$backendCmd = @"
Set-Location '$RepoRoot'
if (-not (Test-Path backend\.venv)) { python -m venv backend\.venv }
backend\.venv\Scripts\activate
pip install -e `"backend[dev]`"
python -m uvicorn quorum_backend.main:app --reload --host 127.0.0.1 --port $backendPort
"@

$frontendCmd = @"
Set-Location '$RepoRoot\frontend'
`$env:NEXT_PUBLIC_API_BASE_URL = '$backendUrl'
npm install
npm run dev
"@

Write-Host "Starting Backend on $backendUrl ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "Starting Frontend (NEXT_PUBLIC_API_BASE_URL=$backendUrl) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "Both services are starting in separate PowerShell windows." -ForegroundColor Green
Write-Host "  Backend:  $backendUrl" -ForegroundColor Green
Write-Host "  Frontend: see the frontend window for the URL (often http://127.0.0.1:3117)" -ForegroundColor Green
