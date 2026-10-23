#!/usr/bin/env bash
# scripts/fresh_clone_check.sh — Independent reproducibility check from a clean git clone
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORTS_DIR="${REPO_DIR}/reports"
LOG_FILE="${REPORTS_DIR}/fresh_clone.log"

mkdir -p "${REPORTS_DIR}"
exec > >(tee "${LOG_FILE}") 2>&1

echo "=================================================================="
echo "STARTING FRESH CLONE REPRODUCIBILITY CHECK"
echo "Date: $(date)"
echo "Source repo: ${REPO_DIR}"
echo "HEAD commit: $(git -C "${REPO_DIR}" rev-parse --short HEAD)"
echo "=================================================================="

git config --global --add safe.directory "*" 2>/dev/null || true

TMP_DIR="$(mktemp -d /tmp/fresh_clone_test_XXXXXX)"
cleanup() {
    echo "Cleaning up temporary clone directory: ${TMP_DIR}"
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "[1/5] Cloning repository into ${TMP_DIR}..."
git clone --no-hardlinks "${REPO_DIR}" "${TMP_DIR}/repo"

cd "${TMP_DIR}/repo"

echo "[2/5] Setting up environment and dataset..."
if [ -d "${REPO_DIR}/.venv" ]; then
    ln -s "${REPO_DIR}/.venv" "${TMP_DIR}/repo/.venv"
fi
mkdir -p data
if [ -d "${REPO_DIR}/data/mitbih" ]; then
    cp -r "${REPO_DIR}/data/mitbih" data/
fi

echo "[3/5] Running 'make data'..."
make data

echo "[4/5] Running 'make vectors'..."
make vectors

echo "[5/5] Running 'make sim'..."
make sim

echo "Checking git working tree in fresh clone..."
DIRTY="$(git status --porcelain)"
if [ -n "${DIRTY}" ]; then
    echo "ERROR: Fresh clone working tree is dirty after running flow:"
    echo "${DIRTY}"
    exit 1
fi

echo "=================================================================="
echo "FRESH CLONE CHECK: PASS (0 mismatches, clean working tree)"
echo "=================================================================="
