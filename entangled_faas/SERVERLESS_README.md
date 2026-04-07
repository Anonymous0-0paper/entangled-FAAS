# Full Serverless Quantum Job Distribution System

## Overview

Complete serverless pipeline for Entangled-FaaS simulator supporting:
- **All 5 execution modes** (EFaaS, SBQ, PQ, PF, SR) for comprehensive baseline comparison
- **All 3 circuit types** (Simple, Medium, Complex) for diverse quantum workloads
- **Batch job generation** for all mode/circuit combinations
- **Parallel job execution** (local or on Qiskit Serverless provider)
- **Results aggregation** and comparative metrics calculation
- **Visualization** of improvements across all baselines
- **Customizable parameters** with full control and documentation

## Quick Start

### 1. Full Baseline Evaluation (All Modes + All Circuits)

```bash
# Run ALL 5 modes × 3 circuits = 15 total job combinations
python3 serverless_batch_submit.py \
    --modes all \
    --circuits all \
    --local \
    --output full_baseline_evaluation
```

**What this does:**
- Generates 15 job payloads (5 modes × 3 circuits)
- Executes all 15 jobs locally
- Saves results to `output/batch_results/full_baseline_evaluation_*.json`
- Ready for analysis and comparison

### 2. Generate & Execute Batch Jobs (Custom Selection)

```bash
python3 serverless_batch_submit.py \
    --modes efaas,sbq,pq,pf,sr \
    --circuits simple,medium,complex \
    --local \
    --output my_batch_run
```

**Available modes:**
- `efaas` - Entangled-FaaS (proposed scheduling method)
- `sbq` - Standard Batch-Queue (baseline)
- `pq` - Pilot-Quantum (IBM Quantum optimized)
- `pf` - Pure FaaS (container-based)
- `sr` - Static Reservation (fixed resources)

**Available circuits:**
- `simple` - Simple (BV-4q) - 4 qubit Deutsch-Jozsa variant
- `medium` - Medium (ESU2-6q) - 6 qubit efficient SU(2) ansatz
- `complex` - Complex (ESU2-8q, EfficientSU2-10q) - Complex multi-qubit circuits

**Output:**
- Payloads saved: `batch_payloads/<output>/payload_*.json`
- Results saved: `output/batch_results/<output>_*.json`

### 2. Analyze Results

```bash
python3 serverless_results_analyzer.py \
    --batch-results output/batch_results/demo_20260402_121942.json \
    --output analysis_results.json
```

**Output:**
- Summary metrics by mode and circuit
- Improvements calculated (TTNS reduction %, QDC improvement pp, convergence speedup %)
- Key findings with min/max/mean across comparisons

### 3. Generate Visualization Plots

```bash
python3 serverless_plotter.py \
    --analysis analysis_results.json \
    --output figs_improvements \
    --format png
```

**Generated plots:**
1. `improvement_ttns_reduction_pct.png` - TTNS reduction bar chart
2. `improvement_qdc_improvement_pp.png` - QDC improvement bar chart
3. `improvement_convergence_speedup_pct.png` - Convergence speedup bar chart
4. `improvements_summary.png` - All 3 metrics in one view
5. `heatmap_mean_ttns_s.png` - TTNS by mode and circuit level
6. `circuit_comparison.png` - Comprehensive 4-panel metric comparison

## Full Pipeline (Single Command)

```bash
python3 serverless_full_pipeline.py \
    --modes efaas,sbq,pq \
    --circuits simple,medium \
    --max-jobs 20 \
    --run-name my_full_run
```

This orchestrates:
1. Batch generation and execution → `batch_payloads/my_full_run/`
2. Results analysis → `output/my_full_run/analysis_results.json`
3. Plot generation → `output/my_full_run/plots/`
4. Summary report → `output/my_full_run/SUMMARY.md`

---

## Complete Examples: Step-by-Step

### Example 1: Run Full Baseline with All Modes and Circuits

```bash
# Step 1: Generate and execute all combinations
python3 serverless_batch_submit.py \
    --modes all \
    --circuits all \
    --local \
    --output full_baseline_v1

# Expected output:
#   Generating: 5 modes × 3 circuits = 15 jobs
#   Execution: ~15-20 minutes
#   Results:   output/batch_results/full_baseline_v1_*.json

# Step 2: Analyze results
python3 serverless_results_analyzer.py \
    --batch-results output/batch_results/full_baseline_v1_*.json \
    --output full_baseline_analysis.json

# Step 3: Generate comparison plots
python3 serverless_plotter.py \
    --analysis full_baseline_analysis.json \
    --output figs_full_baseline

# Step 4: View summary
cat output/demo_full_serverless/SUMMARY.md
```

### Example 2: Customize Simulation Time (Reduce from 800s to 200s)

```bash
# Step 1: Generate payloads
python3 serverless_batch_submit.py \
    --modes efaas,sbq,pq \
    --circuits simple \
    --local \
    --output custom_timing

# Step 2: Edit all payloads to reduce SIM_TIME
for f in batch_payloads/custom_timing/payload_*.json; do
    python3 << EOF
import json
with open('$f', 'r') as file:
    data = json.load(file)
data['config_overrides']['SIM_TIME'] = 200.0  # ← Change to 200 seconds
with open('$f', 'w') as file:
    json.dump(data, file, indent=2)
EOF
done

# Step 3: Run modified batch
python3 serverless_batch_submit.py --local --output custom_timing
```

### Example 3: Test Different Backends

```bash
# Generate payload for fake IBM backend
python3 << 'EOF'
import json

payload = {
    "mode": "Entangled-FaaS",
    "level": "complex_esu2_8q",
    "config_overrides": {
        "QUANTUM_BACKEND": "fake_nighthawk",  # ← Use fake IBM backend
        "SIM_TIME": 1500.0,
        "max_iter": 300
    }
}

with open('custom_payload.json', 'w') as f:
    json.dump(payload, f, indent=2)
EOF

# Run with custom backend
python3 serverless_job.py --payload-file custom_payload.json
```

---

## Key Metrics Explained

### TTNS (Time-to-Next-Shot) Reduction %

Time latency between consecutive VQE iterations. Lower is better.

$$\text{Reduction} = 100 \times \left(1 - \frac{\text{TTNS}_{\text{EFaaS}}}{\text{TTNS}_{\text{baseline}}}\right)$$

**Interpretation:**
- 94% reduction vs SBQ: EFaaS takes only 6% of the time of Standard Batch-Queue
- 29.7% reduction vs PQ: EFaaS still faster than Pilot-Quantum by ~30%

### QDC (Quantum Duty Cycle) Improvement (percentage points)

Percentage of time quantum processor is actively computing.

$$\text{Improvement} = \text{QDC}_{\text{EFaaS}} - \text{QDC}_{\text{baseline}}$$

**Interpretation:**
- 14.99 pp gain vs SBQ: EFaaS achieves 15% higher quantum utilization
- Higher QDC = more quantum computing per unit time

### Convergence Speedup %

Total time to reach convergence criteria.

$$\text{Speedup} = 100 \times \left(1 - \frac{T_{\text{conv,EFaaS}}}{T_{\text{conv,baseline}}}\right)$$

**Interpretation:**
- 81.6% speedup vs SBQ: Converges in ~20% of the time
- 72.3% speedup vs PQ: Significant advantage even over optimized Pilot-Quantum

---

## Demo Results Summary

**Configuration:** 3 modes (EFaaS, SBQ, PQ) × 2 circuits (simple, medium) = 6 jobs

### Headline Improvements

#### EFaaS vs Standard Batch-Queue (SBQ)
- **TTNS Reduction:** **94.0%** (3.5s vs 58.0s per iteration)
- **QDC Improvement:** **+14.99 pp** (24.2% vs 9.2% quantum utilization)
- **Convergence Speedup:** **81.6%** (53s vs 289s to convergence)

#### EFaaS vs Pilot-Quantum (PQ)
- **TTNS Reduction:** **29.7%** (3.5s vs 5.0s per iteration)
- **QDC Improvement:** **+2.48 pp** (24.2% vs 21.7% quantum utilization)
- **Convergence Speedup:** **72.3%** (53s vs 192s to convergence)

---

## File Structure

```
entangled_faas/
├── serverless_batch_submit.py       ← Generate & execute batch jobs
├── serverless_results_analyzer.py   ← Analyze results & calculate improvements
├── serverless_plotter.py             ← Generate comparison plots
├── serverless_full_pipeline.py      ← Orchestrate complete workflow
├── serverless_job.py                ← Single job entrypoint
├── serverless_submit.py             ← Provider submission helper
│
output/
├── batch_results/                   ← Batch execution results
│   └── <run>_*.json
├── demo_full_serverless/            ← Pipeline run outputs
│   ├── analysis_results.json        ← Aggregated metrics
│   ├── SUMMARY.md                   ← Human-readable summary
│   └── plots/
│       ├── improvement_*.png
│       ├── heatmap_*.png
│       └── circuit_comparison.png
├── figs_demo/                       ← Direct plotter output
│   └── *.png (same as above)
```

---

## Parameter Reference Guide

### Understanding `--max-jobs`

**What it does:** Limits the total number of jobs generated to a maximum number.

**How it works:**
When you run:
```bash
python3 serverless_batch_submit.py --modes efaas,sbq,pq --circuits simple,medium --max-jobs 6
```

The system:
1. Calculates all combinations: 3 modes × 2 circuits = 6 total jobs
2. Applies limit: `--max-jobs 6` caps it at 6 jobs
3. Result: **6 jobs executed** (no change since we have exactly 6)

**Another example with limiting:**
```bash
python3 serverless_batch_submit.py --modes all --circuits all --max-jobs 20
```
- Full combinations: 5 modes × 3 circuits = 15 jobs
- With `--max-jobs 20`: **15 jobs executed** (no additional limiting needed)

```bash
python3 serverless_batch_submit.py --modes all --circuits all --max-jobs 10
```
- Full combinations: 5 modes × 3 circuits = 15 jobs
- With `--max-jobs 10`: **Only 10 jobs executed** (first 10 in alphabetical order)

**Use cases for `--max-jobs`:**
- `--max-jobs 1` - Test (dry-run) with single job
- `--max-jobs 6` - Quick demo (run a few combinations)
- `--max-jobs 20` - Mid-scale evaluation
- `--max-jobs 100` - Large baseline study
- Omit for unlimited (run all available combinations)

### Job Count Calculator

**Formula:** `Total Jobs = Number of Modes × Number of Circuits × Number of Seeds`

**Examples:**

| Modes | Circuits | Seeds | Total | --max-jobs | Actual |
|-------|----------|-------|-------|-----------|--------|
| 1 (EFaaS) | 1 (simple) | 1 | 1 | - | 1 |
| 3 (EFaaS, SBQ, PQ) | 2 (simple, medium) | 1 | 6 | - | 6 |
| **5 (all)** | **3 (all)** | **1** | **15** | **-** | **15** |
| 5 (all) | 3 (all) | 1 | 15 | 10 | 10 |
| 5 (all) | 3 (all) | 3 (3 seeds each) | 45 | - | 45 |
| 5 (all) | 3 (all) | 3 seeds | 45 | 30 | 30 |

### Command Line Options Reference

```bash
python3 serverless_batch_submit.py \
    --modes MODES                    # Comma-separated or 'all'
    --circuits CIRCUITS              # Comma-separated or 'all'  
    --seeds SEEDS                    # Number of random seeds (default: 1)
    --max-jobs MAX                   # Cap total jobs (default: unlimited)
    --local                          # Run locally (default)
    --output OUTPUT_NAME             # Subdirectory name (default: batch_run)
```

**Modes available:**
```
all                          → all 5 modes
efaas,sbq,pq               → specific modes (comma-separated, no spaces)
efaas                       → single mode
```

**Circuits available:**
```
all                          → simple, medium, complex
simple,medium               → specific circuits (comma-separated)
complex                     → single circuit
```

**Execution options:**
```
--local                      → Execute locally (default, recommended)
(omit --local)              → Submit to Qiskit Serverless provider [requires setup]
```

**Timing options:**
```
--seeds 1                    → Single run (default)
--seeds 3                    → 3 different random seeds for each job (3× runs)
```

### Configuration Override Reference

Configuration overrides in payloads:

```python
"config_overrides": {
    # Simulation timing
    "SIM_TIME": 800.0           # Simulation wall-clock budget (seconds)
    "max_iter": 200,            # Max VQE iterations
    
    # Quantum backend
    "QUANTUM_BACKEND": "aer",   # Options: aer, statevector, ibm_runtime, 
                                #          fake_nighthawk, fake_washington, etc.
    
    # Scheduler weights (EFaaS parameters)
    "alpha": 100.0,             # Session-awareness weight (0-∞)
    "beta": 5.0,                # Drift-urgency weight (0-∞)
    "gamma": 1.0,               # Fair-share weight (0-∞)
    
    # Hardware/timing parameters
    "tau_drift": 300.0,         # Quantum drift window (seconds)
    "shots": 4096,              # Measurement shots per iteration
}
```

**Recommended SIM_TIME values:**
- Simple circuits: 500-1000 seconds
- Medium circuits: 800-1500 seconds
- Complex circuits: 1200-3000 seconds

**Recommended max_iter values:**
- Simple: 100-300 iterations
- Medium: 200-500 iterations
- Complex: 300-1000 iterations

**Quantum backends:**
- `aer` - Noisy local Aer simulator (default, fastest)
- `statevector` - Exact noiseless (slower, used for comparison)
- `ibm_runtime` - Real IBM Quantum hardware (requires credentials)
- `fake_nighthawk` - Local IBM fake backend (120 qubits)
- `fake_washington` - Local IBM fake backend (127 qubits)

---

## Advanced Customization

### 1. How Modes Differ (What Each Baseline Tests)

Each execution mode tests a different scheduling/resource allocation strategy. The modes differ in their **scheduler weights** (alpha, beta, gamma):

```python
# These parameters control how the scheduler prioritizes jobs:
# alpha (α):   Session-awareness weight (keep warm sessions active)
# beta (β):    Drift-urgency weight (avoid quantum drift)
# gamma (γ):   Fair-share weight (balance between fairness and efficiency)

Mode characteristics:
├─ EFaaS (Proposed):
│  ├─ alpha=100.0   ← Strongly prioritize keeping hot sessions
│  ├─ beta=5.0      ← Also prioritize drift avoidance
│  └─ gamma=1.0     ← Fair baseline scheduling
│  └─ Result: Aggressive optimization for our approach
│
├─ SBQ (Standard Batch-Queue):
│  ├─ alpha=0.0     ← No session awareness (pure FIFO)
│  ├─ beta=0.0      ← No drift awareness
│  └─ gamma=1.0     ← Just basic fair-share
│  └─ Result: Traditional queue (baseline for comparison)
│
├─ PQ (Pilot-Quantum):
│  ├─ alpha=50.0    ← Light session awareness
│  ├─ beta=0.0      ← No drift awareness
│  └─ gamma=1.0
│  └─ Result: Moderate optimization (IBM's approach)
│
├─ PF (Pure FaaS):
│  ├─ alpha=0.0
│  ├─ beta=0.0
│  └─ gamma=1.0
│  └─ Result: Container-based with cold-start overhead
│
└─ SR (Static Reservation):
   ├─ alpha=0.0
   ├─ beta=0.0
   └─ gamma=1.0
   └─ Result: Pre-allocated resources (fixed but inflexible)
```

**To test custom scheduler parameters:**

```bash
# Generate batch
python3 serverless_batch_submit.py --modes efaas --circuits simple --local --output test_custom_alpha

# Edit payloads to try different alpha values
python3 << 'EOF'
import json, glob
for f in glob.glob('batch_payloads/test_custom_alpha/payload_*.json'):
    with open(f) as file: 
        payload = json.load(file)
    # Try higher alpha (more aggressive session awareness)
    payload['alpha'] = 200.0    # ← Increase from 100.0 to 200.0
    payload['beta'] = 10.0      # ← Also increase drift weight
    with open(f, 'w') as file: 
        json.dump(payload, file, indent=2)
EOF

# Run modified batch
python3 serverless_batch_submit.py --local --output test_custom_alpha
```

### 2. Modify Simulation Time and Iterations

**Without editing code:**

```bash
# Generate payloads
python3 serverless_batch_submit.py --modes all --circuits simple --local --output fast_sims

# Batch edit all payloads to run FASTER (for testing)
python3 << 'EOF'
import json, glob
for payload_file in glob.glob('batch_payloads/fast_sims/payload_*.json'):
    with open(payload_file) as f:
        payload = json.load(f)
    
    # REDUCE simulation time (run faster, less data)
    payload['config_overrides']['SIM_TIME'] = 200.0   # Was 800s → Now 200s (4x faster)
    payload['config_overrides']['max_iter'] = 50      # Was 200 → Now 50 (4x fewer iterations)
    
    with open(payload_file, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f"Updated: {payload_file}")
EOF

# Now run the FAST modified batch
python3 serverless_batch_submit.py --local --output fast_sims

# Compare timing: original (~20 min) vs modified (~5 min)
```

### 3. Switch Quantum Backends

Test with different quantum simulators or hardware:

```bash
# Generate payloads with default backend
python3 serverless_batch_submit.py --modes efaas,sbq --circuits simple --local --output backend_comparison

# Modify to use FAKE IBM backend (more realistic noise)
python3 << 'EOF'
import json, glob
for payload_file in glob.glob('batch_payloads/backend_comparison/payload_*.json'):
    with open(payload_file) as f:
        payload = json.load(f)
    
    # Switch from Aer to Fake IBM backend
    payload['config_overrides']['QUANTUM_BACKEND'] = 'fake_nighthawk'  # Was: aer
    
    with open(payload_file, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f"Updated to use fake_nighthawk: {payload_file}")
EOF

# Run with simulated IBM quantum processor
python3 serverless_batch_submit.py --local --output backend_comparison
```

**Available backends:**
- `aer` - Noisy simulator (fast, default)
- `statevector` - Exact classical simulation (slower, reference)
- `fake_nighthawk` - IBM backend simulator (120 qubits, realistic noise)
- `fake_washington` - IBM backend simulator (127 qubits)
- `ibm_runtime` - Real IBM quantum hardware (requires credentials)

### 4. Hyperparameter Sweep (Scientific Experiment)

Compare results across a range of parameter values:

```bash
# Sweep alpha from 50 to 200 in steps of 50
for alpha in 50 100 150 200; do
    echo "Testing alpha=$alpha"
    
    python3 serverless_batch_submit.py \
        --modes efaas \
        --circuits simple,medium \
        --local \
        --output sweep_alpha_$alpha
    
    # Modify all payloads for this alpha value
    python3 << EOF
import json, glob
for f in glob.glob('batch_payloads/sweep_alpha_$alpha/payload_*.json'):
    with open(f) as file: 
        data = json.load(file)
    data['alpha'] = $alpha
    with open(f, 'w') as file: 
        json.dump(data, file, indent=2)
EOF
    
    python3 serverless_batch_submit.py --local --output sweep_alpha_$alpha
done

# Collect and compare results
python3 << 'EOF'
import json, glob, statistics
print("\nAlpha Sweep Results:")
print("Alpha | Mean TTNS | Std Dev")
print("------|-----------|----------")

for alpha in [50, 100, 150, 200]:
    batch_files = glob.glob(f'output/batch_results/sweep_alpha_{alpha}*.json')
    ttns_values = []
    
    for batch_file in batch_files:
        with open(batch_file) as f:
            batch_data = json.load(f)
        for result in batch_data['results']:
            if result.get('status') == 'completed':
                ttns = result['output']['mean_ttns_s']
                ttns_values.append(ttns)
    
    if ttns_values:
        mean_ttns = statistics.mean(ttns_values)
        std_ttns = statistics.stdev(ttns_values) if len(ttns_values) > 1 else 0
        print(f"{alpha:5d} | {mean_ttns:9.2f}s | {std_ttns:8.2f}s")
EOF
```

### 5. Multiple Random Seeds for Statistical Significance

Run each job multiple times with different random seeds:

```bash
# Generate with 3 random seeds (3x more jobs)
python3 serverless_batch_submit.py \
    --modes efaas,sbq \
    --circuits simple \
    --seeds 3 \
    --local \
    --output three_seeds

# This generates: 2 modes × 1 circuit × 3 seeds = 6 jobs
# Each has different random initialization for VQE

# Results will include:
# - payload_0000.json (mode 0, seed 0)
# - payload_0001.json (mode 0, seed 1)
# - payload_0002.json (mode 0, seed 2)
# - payload_0003.json (mode 1, seed 0)
# - etc.

# Analysis will show mean ± std across the 3 seeds
```

### 6. Custom Payload Creation

```python
import json

payload = {
    "mode": "Entangled-FaaS",
    "level": "complex_esu2_8q",
    "seed_offset": 42,
    "alpha": 100.0,
    "beta": 5.0,
    "gamma": 1.0,
    "tau_drift": 300.0,
    "verbose": True,
    "config_overrides": {
        "SIM_TIME": 2000.0,
        "max_iter": 500,
        "QUANTUM_BACKEND": "aer",
    },
    "output_filename": "custom_run_001"
}

# Save and run
with open('my_custom_payload.json', 'w') as f:
    json.dump(payload, f, indent=2)

# Local execution
python3 serverless_job.py --payload-file my_custom_payload.json

# Provider submission  
python3 serverless_submit.py --payload-file my_custom_payload.json
```

---

## Extensions & Future Work

### 1. Cloud Deployment
- Configure Qiskit Serverless provider credentials
- Execute with `--output provider --local` removed
- Jobs run on distributed quantum cloud

### 2. Monitoring & Aggregation
- Implement job status polling
- Real-time result aggregation as jobs complete
- Streaming plot updates

### 3. Hyperparameter Sweeps
- Systematically vary alpha/beta/gamma parameters
- Generate sensitivity analysis plots
- Optimize scheduling weights

### 4. Custom Circuit Generation
- Parameterize circuit depth, qubit count, gate types
- Generate circuit families for systematic evaluation
- ML-based circuit importance sampling

---

## References

**Key papers:**
- "Entangled-FaaS: Accelerating Quantum Variational Algorithms with Adaptive Session Management"
- Section V: Performance Metrics (TTNS, QDC, Convergence Time, Drift Penalties)

**Quantum execution modes:**
- **EFaaS** (Entangled-FaaS): Adaptive session-aware scheduling
- **SBQ** (Standard Batch-Queue): FIFO baseline with queue delays
- **PQ** (Pilot-Quantum): Pre-allocated pilot program (IBM Quantum)
- **PF** (Pure FaaS): Container-based with cold-start penalties
- **SR** (Static Reservation): Fixed resource reservation

---

**Last updated:** 2026-04-02  
**Status:** Production-ready for local execution, serverless provider integration available
