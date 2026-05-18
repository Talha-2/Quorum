param(
    [Parameter(Mandatory = $true)]
    [int]$Port
)

function Stop-ProcessOnPort {
    param([int]$TargetPort)

    $stopped = @()

    # Prefer Get-NetTCPConnection when available (Windows 8+)
    try {
        $connections = Get-NetTCPConnection -LocalPort $TargetPort -ErrorAction Stop |
            Where-Object { $_.State -eq "Listen" }

        foreach ($conn in $connections) {
            $processId = $conn.OwningProcess
            if ($processId -and $processId -gt 0 -and $stopped -notcontains $processId) {
                $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
                $name = if ($proc) { $proc.ProcessName } else { "pid-$processId" }
                Write-Host "  Stopping $name (PID $processId) on port $TargetPort..." -ForegroundColor Yellow
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                $stopped += $processId
            }
        }
    } catch {
        # Fallback: netstat + taskkill
        $pattern = ":$TargetPort\s"
        netstat -ano | Select-String $pattern | ForEach-Object {
            $parts = ($_.ToString().Trim() -split '\s+')
            $processId = [int]$parts[-1]
            if ($processId -gt 0 -and $stopped -notcontains $processId) {
                Write-Host "  Stopping PID $processId on port $TargetPort..." -ForegroundColor Yellow
                taskkill /F /PID $processId 2>$null | Out-Null
                $stopped += $processId
            }
        }
    }

    if ($stopped.Count -eq 0) {
        Write-Host "  Port $TargetPort is already free." -ForegroundColor DarkGray
    } else {
        Start-Sleep -Milliseconds 400
        Write-Host "  Port $TargetPort cleared." -ForegroundColor Green
    }
}

Write-Host "Checking port $Port..." -ForegroundColor Cyan
Stop-ProcessOnPort -TargetPort $Port
