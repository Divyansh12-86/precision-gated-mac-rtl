#!/usr/bin/env bash
# =============================================================================
# scripts/run_all.sh — Master Build, Regression & Verification Execution Script
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=================================================================="
echo "Starting Complete Precision-Gated MAC ECG Verification Pipeline"
echo "Project Root: $PROJECT_ROOT"
echo "=================================================================="

# Ensure environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run complete Makefile flow
make all

echo "=================================================================="
echo "All steps completed successfully!"
echo "Check reports/RESULTS.md for the complete executive summary."
echo "=================================================================="
