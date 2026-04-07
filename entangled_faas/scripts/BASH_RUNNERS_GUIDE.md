# Bash Runners Guide

This guide explains how to automatically run serverless and normal simulator flows, and exactly what to change.

## Files

- scripts/run_serverless.sh
- scripts/run_normal.sh

## 1) Serverless Automatic Runner

Run:

```bash
bash scripts/run_serverless.sh
```

Edit variables at the top of scripts/run_serverless.sh:

- RUN_STYLE
- BATCH_MODES
- PIPELINE_MODES
- CIRCUITS
- SEEDS
- MAX_JOBS
- LOCAL
- RUN_NAME
- DO_ANALYSIS
- DO_PLOTS

### What each variable changes

- RUN_STYLE
  - batch: uses serverless_batch_submit.py
  - pipeline: uses serverless_full_pipeline.py

- BATCH_MODES (used only when RUN_STYLE=batch)
  - all
  - efaas,sbq,pq
  - efaas,sbq,pq,pf,sr

- PIPELINE_MODES (used only when RUN_STYLE=pipeline)
  - efaas,sbq,pq
  - efaas,sbq,pq,pf,sr

- CIRCUITS
  - all
  - simple
  - medium
  - complex
  - simple,medium
  - simple,medium,complex

- SEEDS
  - Multiplies jobs by seed count.
  - Example: SEEDS=2 with full mode/circuit sweep doubles jobs.

- MAX_JOBS
  - Empty means unlimited.
  - Numeric value caps total generated jobs.
  - Example: MAX_JOBS="10" limits run to 10 jobs.

- LOCAL
  - 1 means local run.
  - 0 means no --local flag (provider path).

- RUN_NAME
  - Controls output folder and result file naming.

- DO_ANALYSIS / DO_PLOTS
  - Only for RUN_STYLE=batch.
  - If DO_ANALYSIS=1, analyzer runs after batch execution.
  - If DO_PLOTS=1, plotter runs after analysis.

### Common presets

Quick demo:

- RUN_STYLE="batch"
- BATCH_MODES="efaas,sbq"
- CIRCUITS="simple"
- SEEDS=1
- MAX_JOBS=""

Full baseline:

- RUN_STYLE="batch"
- BATCH_MODES="all"
- CIRCUITS="all"
- SEEDS=1
- MAX_JOBS=""

Full baseline with cap:

- RUN_STYLE="batch"
- BATCH_MODES="all"
- CIRCUITS="all"
- MAX_JOBS="10"

Full end-to-end pipeline:

- RUN_STYLE="pipeline"
- PIPELINE_MODES="efaas,sbq,pq,pf,sr"
- CIRCUITS="all"
- MAX_JOBS=""

## 2) Normal (Non-Serverless) Automatic Runner

Run:

```bash
bash scripts/run_normal.sh
```

This executes:

```bash
python3 main.py
```

main.py uses config.py values. To change normal behavior, edit config.py.

### What to change in config.py

For mode selection:

- ALL_MODES list

For circuit complexity selection:

- ALL_LEVELS list

For scheduling weights:

- alpha
- beta
- gamma
- tau_drift

For run duration and optimizer budget:

- SIM_TIME
- max_iter

For backend:

- QUANTUM_BACKEND
- IBM_BACKEND_NAME / IBM_RUNTIME_CHANNEL / IBM_PRECISION / IBM_RESILIENCE_LEVEL

For infrastructure size:

- N_QPU
- N_classical

For random reproducibility:

- RANDOM_SEED

### Typical normal-mode edits

Fast local check:

- SIM_TIME = 600.0
- max_iter = 200
- ALL_LEVELS = [LEVEL_SIMPLE]
- ALL_MODES = [MODE_BASELINE, MODE_ENTANGLED]

Full study:

- SIM_TIME = 3000.0
- max_iter = 1000
- ALL_LEVELS with simple/medium/complex entries enabled
- ALL_MODES with all baselines enabled

## 3) Make scripts executable (optional)

```bash
chmod +x scripts/run_serverless.sh scripts/run_normal.sh
```

Then run directly:

```bash
./scripts/run_serverless.sh
./scripts/run_normal.sh
```
