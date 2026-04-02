@echo off
:: ============================================================================
:: install-hooks.cmd  —  Manager-AI Git Hook Installation (Windows CMD)
:: ============================================================================
:: Run from the ILS-Simulator repo root:
::   scripts\install-hooks.cmd
::
:: Requires: Miniconda / Anaconda with 'manager-ai' environment.
:: Create the env first if needed:
::   conda create -n manager-ai python=3.12
::   conda activate manager-ai
::   pip install -r manager-ai\requirements.txt -r manager-ai\requirements-dev.txt
:: ============================================================================

setlocal enabledelayedexpansion

echo.
echo  ======================================================
echo   Manager-AI  .  Git Hook Installation
echo  ======================================================
echo.

:: Store repo root (parent of scripts/)
set "REPO_ROOT=%~dp0.."
set "MANAGER_AI=%REPO_ROOT%\manager-ai"

:: ── 1. Activate conda environment ────────────────────────────────────────────
echo =^> Activating conda environment 'manager-ai'...
call conda activate manager-ai
if errorlevel 1 (
    echo.
    echo ERROR: Could not activate conda env 'manager-ai'.
    echo        Does it exist? Create it with:
    echo          conda create -n manager-ai python=3.12
    exit /b 1
)
echo     Environment active.

:: ── 2. Install / upgrade pre-commit ──────────────────────────────────────────
echo =^> Installing/upgrading pre-commit...
pip install --quiet --upgrade pre-commit
if errorlevel 1 (
    echo ERROR: pip install pre-commit failed.
    exit /b 1
)

:: ── 3. Install git hooks ──────────────────────────────────────────────────────
echo =^> Installing git hooks (pre-commit + pre-push)...
cd /d "%MANAGER_AI%"
if errorlevel 1 (
    echo ERROR: Cannot navigate to manager-ai directory.
    exit /b 1
)

pre-commit install ^
    --config .pre-commit-config.yaml ^
    --hook-type pre-commit ^
    --hook-type pre-push

if errorlevel 1 (
    echo ERROR: pre-commit install failed.
    cd /d "%REPO_ROOT%"
    exit /b 1
)

cd /d "%REPO_ROOT%"

echo.
echo  Hooks installed successfully!
echo.
echo    pre-commit  --^>  ruff lint, ruff format, black --check, mypy
echo    pre-push    --^>  pytest tests/unit (fast, no Azure required)
echo.
echo  Run all hooks manually:
echo    cd manager-ai ^&^& pre-commit run --all-files
echo.

endlocal
exit /b 0
