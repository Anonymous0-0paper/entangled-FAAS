#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# run_serverless.sh
# -----------------------------------------------------------------------------
# Automated runner for serverless workflows.
# Supports:
#   1) batch mode    -> serverless_batch_submit.py
#   2) pipeline mode -> serverless_full_pipeline.py
#
# Usage:
#   bash scripts/run_serverless.sh
#
# Customize by editing the variables in "USER CONFIG" below.
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# ============================= USER CONFIG ====================================
# RUN_STYLE:
#   batch    -> generate + execute jobs, optional analysis/plots
#   pipeline -> full orchestrated flow in one command
RUN_STYLE="batch"

# For batch mode (serverless_batch_submit.py uses --mode (singular)).
# Examples: all | efaas,sbq,pq | efaas,sbq,pq,pf,sr
BATCH_MODES="all"

# For pipeline mode (serverless_full_pipeline.py uses --modes (plural)).
PIPELINE_MODES="efaas,sbq,pq,pf,sr"

# Circuits: all | simple | medium | complex | simple,medium | simple,medium,complex
CIRCUITS="all"

# Number of random seeds per job.
SEEDS=1

# Max number of jobs. Leave empty for unlimited.
MAX_JOBS=""

# Local execution flag for batch mode: 1=yes, 0=no
LOCAL=1

# Name used for outputs.
RUN_NAME="auto_serverless_run"

# If RUN_STYLE=batch, optionally run analyzer and plotter after execution.
DO_ANALYSIS=1
DO_PLOTS=1
# ==============================================================================

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

latest_result_file() {
  local pattern="output/batch_results/${RUN_NAME}_*.json"
  ls -1t ${pattern} 2>/dev/null | head -n 1 || true
}

run_batch() {
  local cmd=(python3 serverless_batch_submit.py
    --mode "${BATCH_MODES}"
    --circuits "${CIRCUITS}"
    --seeds "${SEEDS}"
    --output "${RUN_NAME}"
  )

  if [[ -n "${MAX_JOBS}" ]]; then
    cmd+=(--max-jobs "${MAX_JOBS}")
  fi

  if [[ "${LOCAL}" == "1" ]]; then
    cmd+=(--local)
  fi

  echo "[serverless] Running batch command: ${cmd[*]}"
  "${cmd[@]}"

  local result_file
  result_file="$(latest_result_file)"
  if [[ -z "${result_file}" ]]; then
    echo "[serverless] No batch result file found in output/batch_results"
    exit 1
  fi

  echo "[serverless] Batch result file: ${result_file}"

  if [[ "${DO_ANALYSIS}" == "1" ]]; then
    mkdir -p "output/${RUN_NAME}"
    local analysis_file="output/${RUN_NAME}/analysis_results.json"

    local analyze_cmd=(python3 serverless_results_analyzer.py
      --batch-results "${result_file}"
      --output "${analysis_file}"
    )

    echo "[serverless] Running analyzer: ${analyze_cmd[*]}"
    "${analyze_cmd[@]}"

    if [[ "${DO_PLOTS}" == "1" ]]; then
      local plot_cmd=(python3 serverless_plotter_enhanced.py
        --analysis "${analysis_file}"
        --output "output/${RUN_NAME}/plots_enhanced"
        --format png
      )

      echo "[serverless] Running enhanced plotter: ${plot_cmd[*]}"
      "${plot_cmd[@]}"
    fi
  fi

  echo "[serverless] Done. See output/${RUN_NAME}/ and output/batch_results/"
}

run_pipeline() {
  local cmd=(python3 serverless_full_pipeline.py
    --modes "${PIPELINE_MODES}"
    --circuits "${CIRCUITS}"
    --run-name "${RUN_NAME}"
  )

  if [[ -n "${MAX_JOBS}" ]]; then
    cmd+=(--max-jobs "${MAX_JOBS}")
  fi

  echo "[serverless] Running pipeline command: ${cmd[*]}"
  "${cmd[@]}"

  echo "[serverless] Done. See output/${RUN_NAME}/"
}

main() {
  require_cmd python3

  case "${RUN_STYLE}" in
    batch)
      run_batch
      ;;
    pipeline)
      run_pipeline
      ;;
    *)
      echo "Invalid RUN_STYLE='${RUN_STYLE}'. Use 'batch' or 'pipeline'."
      exit 1
      ;;
  esac
}

main "$@"
