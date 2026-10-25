#!/usr/bin/env bash
# scripts/fresh_clone_check.sh — Independent reproducibility check from a clean git clone (v2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORTS_DIR="${REPO_DIR}/reports"
LOG_FILE="${REPORTS_DIR}/fresh_clone.log"

mkdir -p "${REPORTS_DIR}"
exec > >(tee "${LOG_FILE}") 2>&1

HEAD_HASH="$(git -C "${REPO_DIR}" rev-parse HEAD)"

# Check if network is available to download data
DATA_MSG="OFFLINE: copied local data from ${REPO_DIR}/data/mitbih"
if ping -c 1 -W 2 physionet.org >/dev/null 2>&1; then
    DATA_MSG="ONLINE: downloaded fresh from PhysioNet"
fi

echo "=================================================================="
echo "HEAD commit: ${HEAD_HASH}"
echo "DATA: ${DATA_MSG}"
echo "=================================================================="
echo "STARTING FRESH CLONE REPRODUCIBILITY CHECK (v2)"

git config --global --add safe.directory "*" 2>/dev/null || true

TMP_DIR="$(mktemp -d /tmp/fresh_clone_test_XXXXXX)"
cleanup() {
    echo "Cleaning up temporary clone directory: ${TMP_DIR}"
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "[1/6] Cloning repository into ${TMP_DIR}..."
git clone --no-hardlinks "${REPO_DIR}" "${TMP_DIR}/repo"

cd "${TMP_DIR}/repo"

echo "[2/6] Creating clean virtualenv and installing requirements..."
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt

echo "[3/6] Setting up dataset..."
if [[ "${DATA_MSG}" == *"ONLINE"* ]]; then
    make data
else
    mkdir -p data
    cp -r "${REPO_DIR}/data/mitbih" data/
    echo "OFFLINE: copied local data from ${REPO_DIR}/data/mitbih"
fi

echo "[4/6] Generating standard and full nightly test vectors..."
make vectors full-vectors

echo "[5/6] Executing standard and full nightly regression suites..."
make sim
make nightly

echo "[6/6] Executing master verification harness..."
export INSIDE_FRESH_CLONE_CHECK=1
python3 scripts/verify_all.py --skip-fresh-clone-dependent

echo "Checking git working tree in fresh clone..."
DIRTY="$(git status --porcelain | grep -v '^ M reports/' || true)"
if [ -n "${DIRTY}" ]; then
    echo "ERROR: Fresh clone working tree is dirty after running flow:"
    echo "${DIRTY}"
    exit 1
fi

echo "=================================================================="
echo "FRESH CLONE CHECK: PASS (0 mismatches, clean working tree)"
echo "=================================================================="
