# Start Jack and keep him running. Ctrl+C stops him.
#     powershell -ExecutionPolicy Bypass -File .\start.ps1
#
# Exit codes from jack.py: 0 = stopped on purpose, 2 = config problem (fix .env), anything else = crash.
# Crashes restart after 2 s, doubling up to 30 s if it keeps crashing; the wait resets after
# 5 minutes of clean running.

Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force logs | Out-Null
$env:HF_HUB_OFFLINE = "1"      # models are local; event day only needs api.anthropic.com
$env:JACK_RESTART = "0"
$delay = 2

while ($true) {
    $started = Get-Date
    & $py jack.py
    $code = $LASTEXITCODE
    $ran = [int]((Get-Date) - $started).TotalSeconds
    "$((Get-Date).ToString('s')) exit=$code ran=${ran}s" | Add-Content logs\restarts.log

    if ($code -eq 0) { Write-Host "Jack stopped."; break }
    if ($code -eq 2) { Write-Host "Config problem. Fix .env (see message above), then run start.ps1 again."; break }

    if ($ran -ge 300) { $delay = 2 }
    Write-Host "Jack crashed (exit $code). Restarting in $delay s..."
    Start-Sleep -Seconds $delay
    $delay = [Math]::Min($delay * 2, 30)
    $env:JACK_RESTART = "1"
}
