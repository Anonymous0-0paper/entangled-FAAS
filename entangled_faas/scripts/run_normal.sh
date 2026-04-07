#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# run_normal.sh
# -----------------------------------------------------------------------------
# Automated runner for normal (non-serverless) simulator flow.
# It executes main.py, which reads settings from config.py.
#
# Usage:
#   bash scripts/run_normal.sh
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# ============================= USER CONFIG ====================================
# Set to 1 to create a timestamped log in output/normal_runs/
SAVE_LOG=1
# ==============================================================================

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

main() {
  require_cmd python3
  mkdir -p output/normal_runs

  if [[ "${SAVE_LOG}" == "1" ]]; then
    ts="$(date +%Y%m%d_%H%M%S)"
    log_file="output/normal_runs/normal_run_${ts}.log"
    echo "[normal] Running python3 main.py"
    echo "[normal] Logging to ${log_file}"
    python3 main.py | tee "${log_file}"
  else
    echo "[normal] Running python3 main.py"
    python3 main.py
  fi

  echo "[normal] Done. See output/ and figures/"
}

main "$@"
