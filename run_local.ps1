# ============================================================================
#  SaverFrom - local development launcher (Windows / PowerShell)
#
#  Serves the FastAPI backend AND the static frontend from one process:
#      Frontend : http://127.0.0.1:8000/
#      API docs : http://127.0.0.1:8000/api/docs
#      Health   : http://127.0.0.1:8000/api/v1/health
#
#  Usage:
#      .\run_local.ps1                 # dev mode, auto-reload, port 8000
#      .\run_local.ps1 -Port 9000      # use another port
#      .\run_local.ps1 -NoReload       # no file watching (faster start)
#      .\run_local.ps1 -Host 0.0.0.0   # reachable from other devices on the LAN
#
#  First run creates backend\.venv and installs backend\requirements.txt.
# ============================================================================

[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000,
    [switch]$NoReload,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$venvDir    = Join-Path $PSScriptRoot 'backend\.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$requirements = Join-Path $PSScriptRoot 'backend\requirements.txt'

# ── 1. Virtual environment ───────────────────────────────────────────────────
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[setup] Creating virtual environment in backend\.venv ..." -ForegroundColor Cyan
    python -m venv $venvDir
}

# ── 2. Dependencies ──────────────────────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Host "[setup] Installing/verifying dependencies ..." -ForegroundColor Cyan
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -r $requirements
}

# ── 3. .env (optional - defaults work without it) ────────────────────────────
$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host "[setup] No .env found - copying .env.example (defaults already work)." -ForegroundColor Yellow
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination $envFile
}

# ── 4. Start the server ──────────────────────────────────────────────────────
$displayHost = if ($BindHost -eq '0.0.0.0') { '127.0.0.1' } else { $BindHost }
$uvicornArgs = @('-m', 'uvicorn', 'backend.main:app', '--host', $BindHost, '--port', "$Port")
if (-not $NoReload) { $uvicornArgs += '--reload' }

Write-Host ''
Write-Host "  SaverFrom running ->  http://${displayHost}:$Port/" -ForegroundColor Green
Write-Host "  API documentation ->  http://${displayHost}:$Port/api/docs" -ForegroundColor Green
Write-Host "  Health check      ->  http://${displayHost}:$Port/api/v1/health" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ''

& $venvPython @uvicornArgs
