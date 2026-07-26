# Start the Simular Gateway HEADLESS (no console window) using pythonw.
# Idempotent: if already listening on the port, does nothing.
$ErrorActionPreference = "Stop"
$base = $PSScriptRoot
$port = 8799
# Edit this if pythonw is not on PATH (e.g. "<path-to-python>\pythonw.exe")
$py   = "pythonw"

$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "Simular Gateway already running on port $port (pid $($listening.OwningProcess))."
    return
}

$p = Start-Process -FilePath $py -ArgumentList "server.py" -WorkingDirectory $base -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 8

$ok = $false
try {
    $h = Invoke-WebRequest "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 10
    if ($h.StatusCode -eq 200) { $ok = $true }
} catch {}

if ($ok) {
    Write-Output "Simular Gateway started headless (pid $($p.Id)) on http://127.0.0.1:$port"
} else {
    Write-Output "Simular Gateway FAILED to become healthy. Check $base\logs\gateway.log"
}

