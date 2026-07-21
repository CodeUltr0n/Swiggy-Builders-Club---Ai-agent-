# Start orchestrator and write PID to .orchestrator.pid; redirect output to logs\orchestrator.log
$ErrorActionPreference = 'Stop'
$root = Get-Location
$logs = Join-Path $root 'logs'
if (!(Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$pidfile = Join-Path $root '.orchestrator.pid'
$env:ORCH_PID_FILE = $pidfile

$python = Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {
    Write-Error "Python executable not found at $python. Create virtualenv first with: py -3 -m venv .venv"
    exit 1
}

$logpath = Join-Path $logs 'orchestrator.log'
$p = Start-Process -FilePath $python -ArgumentList '-m','orchestrator' -WorkingDirectory $root -RedirectStandardOutput $logpath -RedirectStandardError $logpath -NoNewWindow -PassThru
Start-Sleep -Milliseconds 200
try {
    $p.Id | Out-File -FilePath $pidfile -Encoding ascii
    Write-Output "Started orchestrator with PID $($p.Id). Logs: $logpath"
} catch {
    Write-Warning "Started process but failed to write pidfile: $_"
}
