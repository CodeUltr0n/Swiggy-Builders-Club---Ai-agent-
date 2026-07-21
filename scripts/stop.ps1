# Stop orchestrator using PID in .orchestrator.pid
$ErrorActionPreference = 'Stop'
$root = Get-Location
$pidfile = Join-Path $root '.orchestrator.pid'
if (!(Test-Path $pidfile)) {
    Write-Warning "Pidfile not found at $pidfile. Is the service running?"
    exit 1
}

$pid = Get-Content $pidfile | Select-Object -First 1
try {
    Stop-Process -Id $pid -ErrorAction SilentlyContinue
    Remove-Item $pidfile -ErrorAction SilentlyContinue
    Write-Output "Stopped process $pid (if it existed). Removed pidfile."
} catch {
    Write-Warning "Failed to stop process $pid: $_"
}
