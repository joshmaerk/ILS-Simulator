#!/usr/bin/env bash
# =============================================================================
# install-hooks.sh  —  Manager-AI Git Hook Installation (Linux / WSL / macOS)
# =============================================================================
# Run from the ILS-Simulator repo root:
#   bash scripts/install-hooks.sh
#
# Requires: Miniconda / Anaconda with 'manager-ai' environment.
# Create the env first if needed:
#   conda create -n manager-ai python=3.12
#   conda activate manager-ai
#   pip install -r manager-ai/requirements.txt -r manager-ai/requirements-dev.txt
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANAGER_AI="$REPO_ROOT/manager-ai"

echo ""
echo "======================================================="
echo "  Manager-AI  ·  Git Hook Installation"
echo "======================================================="
echo ""

# ── 1. Verify conda is available ─────────────────────────────────────────────
if ! command -v conda &>/dev/null; then
    echo "ERROR: conda not found on PATH."
    echo "       Install Miniconda/Anaconda and initialise your shell:"
    echo "       conda init bash  (or conda init zsh)"
    exit 1
fi

# ── 2. Install / upgrade pre-commit inside the conda env ─────────────────────
# Use 'conda run' to avoid needing shell init (works in non-interactive scripts)
echo "==> Installing/upgrading pre-commit in 'manager-ai' conda env..."
conda run -n manager-ai pip install --quiet --upgrade pre-commit

# ── 3. Install git hooks ──────────────────────────────────────────────────────
echo "==> Installing git hooks (pre-commit + pre-push)..."
cd "$MANAGER_AI"

conda run -n manager-ai \
    pre-commit install \
        --config .pre-commit-config.yaml \
        --hook-type pre-commit \
        --hook-type pre-push

cd "$REPO_ROOT"

echo ""
echo "✔  Hooks installed successfully!"
echo ""
echo "  pre-commit  →  ruff lint, ruff format, black --check, mypy"
echo "  pre-push    →  pytest tests/unit (fast, no Azure required)"
echo ""
echo "Run all hooks manually:"
echo "  cd manager-ai && conda run -n manager-ai pre-commit run --all-files"
echo ""
