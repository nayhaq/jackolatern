# One-time setup on the Windows laptop. Run from the jack-o-intern folder:
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Needs: Python 3.11 x64 (py launcher), and network access to pypi.org, huggingface.co, github.com.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/5 Python 3.11 virtual environment"
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "== 2/5 Packages"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "== 3/5 .env"
if (-not (Test-Path .env)) {
    Copy-Item config.example.env .env
    Write-Host "   Created .env. Open it and paste ANTHROPIC_API_KEY."
}

Write-Host "== 4/5 Models (wake word features, Whisper, Piper voices)"
$env:HF_HUB_OFFLINE = "0"
& $py tools\download_models.py
if ($LASTEXITCODE -ne 0) { throw "model download failed" }

Write-Host "== 5/5 Offline unit tests"
& $py -m pytest -q -m "not live"
if ($LASTEXITCODE -ne 0) { throw "unit tests failed" }

Write-Host ""
Write-Host "SETUP OK"
Write-Host "Next: put hey_jack.onnx in models\, paste the API key in .env, then follow RUNBOOK.md."
