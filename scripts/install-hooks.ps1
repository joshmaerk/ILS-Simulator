<#
.SYNOPSIS
    Installs pre-commit git hooks for the manager-ai project.

.DESCRIPTION
    Activates the 'manager-ai' conda environment and installs
    pre-commit + pre-push hooks. Run from the ILS-Simulator repo root.

.EXAMPLE
    .\scripts\install-hooks.ps1

.NOTES
    Requires: Miniconda or Anaconda with a 'manager-ai' environment.
    The conda env must already exist:
        conda create -n manager-ai python=3.12
        conda activate manager-ai
        pip install -r manager-ai/requirements.txt -r manager-ai/requirements-dev.txt
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$ManagerAi = Join-Path $RepoRoot "manager-ai"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Manager-AI  ·  Git Hook Installation           ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verify conda is available ─────────────────────────────────────────────
if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Error "conda not found on PATH. Install Miniconda/Anaconda and restart this terminal."
    exit 1
}

# ── 2. Activate conda environment ────────────────────────────────────────────
Write-Host "==> Activating conda environment 'manager-ai'..." -ForegroundColor Yellow

# Initialise conda's PowerShell integration so 'conda activate' works in scripts
(& conda shell.powershell hook) | Out-String | Invoke-Expression

try {
    conda activate manager-ai
} catch {
    Write-Error "Could not activate conda env 'manager-ai'. Does it exist?`nCreate it with: conda create -n manager-ai python=3.12"
    exit 1
}

Write-Host "    Active env: $env:CONDA_PREFIX" -ForegroundColor DarkGray

# ── 3. Install / upgrade pre-commit ──────────────────────────────────────────
Write-Host "==> Installing/upgrading pre-commit..." -ForegroundColor Yellow
pip install --quiet --upgrade pre-commit
if ($LASTEXITCODE -ne 0) { Write-Error "pip install pre-commit failed"; exit 1 }

# ── 4. Install git hooks ──────────────────────────────────────────────────────
Write-Host "==> Installing git hooks (pre-commit + pre-push)..." -ForegroundColor Yellow

Push-Location $ManagerAi
try {
    pre-commit install `
        --config .pre-commit-config.yaml `
        --hook-type pre-commit `
        --hook-type pre-push

    if ($LASTEXITCODE -ne 0) { throw "pre-commit install failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "✔  Hooks installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  pre-commit  →  ruff lint, ruff format, black --check, mypy" -ForegroundColor DarkGray
Write-Host "  pre-push    →  pytest tests/unit (fast, no Azure required)"  -ForegroundColor DarkGray
Write-Host ""
Write-Host "Run all hooks manually:" -ForegroundColor DarkGray
Write-Host "  cd manager-ai && pre-commit run --all-files" -ForegroundColor DarkGray
Write-Host ""
