#!/bin/bash
#SBATCH --job-name=entangled-faas-simple
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=03:00:00
#SBATCH --partition=default
#SBATCH --output=entangled-faas-%j.out
#SBATCH --error=entangled-faas-%j.err

set -euo pipefail

# Update this if your repository lives elsewhere on the cluster.
PROJECT_DIR="${PROJECT_DIR:-$HOME/qunatum-work}"
VENV_DIR="${VENV_DIR:-$HOME/.venvs/entangled-faas}"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
python3 -m pip install --upgrade pip
python3 -m pip install -r "$PROJECT_DIR/requirements.txt"

cd "$PROJECT_DIR/entangled_faas"
python3 main.py
