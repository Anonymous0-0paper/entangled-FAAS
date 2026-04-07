# Entangled-FaaS Discrete-Event Simulator

This repository simulates hybrid quantum-classical scheduling strategies for iterative variational workloads using a SimPy discrete-event model.

Implemented modes:
- `SBQ` (Standard Batch-Queue)
- `PF` (Pure FaaS)
- `SR` (Static Reservation)
- `PQ` (Pilot-Quantum)
- `EFaaS` (Entangled-FaaS)

The simulator runs these modes across multiple circuit complexity levels, produces JSON metrics, computes per-circuit and averaged improvements, and generates publication-style plots.

## Real-Scenario Modeling

The current setup is configured to stay grounded in realistic execution assumptions:
- Real variational ansatz families from Qiskit (`EfficientSU2`, `RealAmplitudes`, `TwoLocal`).
- Drift-aware noisy QPU estimation through Aer noise models.
- Multi-tenant contention via Poisson background arrivals.
- Queueing delays sampled from a high-variance lognormal distribution.
- Physics-based fallback for expectation values using statevector expectation (not synthetic decay curves).
- Pilot-Quantum modeled as one pilot startup followed by warm task dispatch overhead.

## Project Layout

- `entangled_faas/main.py`: Main entrypoint for all runs, comparisons, and plots.
- `entangled_faas/config.py`: Central configuration for modes, timings, resources, levels, and sensitivity grids.
- `entangled_faas/scheduler.py`: Mode-specific scheduler logic.
- `entangled_faas/workload.py`: VQE loop, circuit construction, energy evaluation, background traffic.
- `entangled_faas/plotter.py`: Figure generation.
- `output/`: JSON outputs.
- `figures/`: Generated plots (`.png` and `.pdf`).
- `circuits/`: Exported circuit QASM files.

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

If your system has multiple Python versions, use:

```bash
python3 -m pip install -r requirements.txt
```

## How To Run

Run the full simulation suite:

```bash
cd entangled_faas
python main.py
```

What this does:
- Runs all modes in `config.ALL_MODES` across all levels in `config.ALL_LEVELS`.
- Writes per-mode/per-level JSON files to `output/`.
- Writes aggregate cross-level report to `output/results_by_circuit_and_average.json`.
- Runs sensitivity sweeps (`alpha`, `beta`, `gamma`, `tau_drift`).
- Generates plots in `figures/`.

## Key Outputs

Per-level mode results:
- `output/results_sbq_<level>.json`
- `output/results_pf_<level>.json`
- `output/results_sr_<level>.json`
- `output/results_pq_<level>.json`
- `output/results_efaas_<level>.json`

Cross-level summary:
- `output/results_by_circuit_and_average.json`

Sensitivity:
- `output/sensitivity_alpha.json`
- `output/sensitivity_beta.json`
- `output/sensitivity_gamma.json`
- `output/sensitivity_tau_drift.json`
- `output/sensitivity_combined.json`

Per-circuit and average plots:
- `figures/entangled_faas_circuit_avg_L_ttns.png`
- `figures/entangled_faas_circuit_avg_M_qdc.png`
- `figures/entangled_faas_circuit_avg_N_improvement_ttns.png`

## How To Change Config

Edit `entangled_faas/config.py`.

Most useful settings:
- `ALL_LEVELS`: choose which circuit levels are executed.
- `max_iter`: number of VQE iterations.
- `SIM_TIME`: total simulated time budget.
- `N_QPU`, `N_classical`: infrastructure size.
- `bg_job_arrival_rate`, `bg_t_qpu_mean`: background traffic intensity.
- `alpha`, `beta`, `gamma`, `tau_drift`: scheduler and drift controls.
- `QUANTUM_BACKEND`: choose the quantum execution path.
- `SENSITIVITY_GRIDS`: parameter ranges for sweeps.

Quantum backend options:
- `aer`: local noisy Qiskit Aer estimator. This is the default and works without IBM credentials.
- `statevector`: exact noiseless fallback for debugging or baseline comparisons.
- `ibm_runtime`: IBM Quantum Runtime EstimatorV2 using a saved IBM account or token.
- `fake_nighthawk`: IBM fake backend with 120 qubits. Best fit here for a 100-qubit-scale test.
- `fake_washington`: IBM fake backend with 127 qubits. Good for large-device testing.
- `fake_sherbrooke`: IBM fake backend with 127 qubits. Also good for large-device testing.
- `fake_toronto`: IBM fake backend with 27 qubits. Good for smaller circuits.

IBM Runtime setup:
- Install the extra dependency with `pip install -r requirements.txt`.
- Save your IBM account once with Qiskit Runtime, or provide the usual IBM credentials.
- Set `QUANTUM_BACKEND = "ibm_runtime"` in `entangled_faas/config.py`.
- Optionally set `IBM_BACKEND_NAME` to a specific backend, or leave it empty to use the least busy IBM hardware backend with enough qubits.
- Optionally tune `IBM_PRECISION` and `IBM_RESILIENCE_LEVEL` for runtime execution.

Fake backend setup:
- Set `QUANTUM_BACKEND = "fake_nighthawk"` for a 100-qubit-scale local test.
- Use `fake_washington` or `fake_sherbrooke` if you want a 127-qubit fake IBM device.
- Use `fake_toronto` for smaller circuits or faster tests.
- If you want to override the backend name explicitly, set `FAKE_BACKEND_NAME` too.

How to use IBM Runtime:
- Set `QUANTUM_BACKEND = "ibm_runtime"`.
- Make sure `qiskit-ibm-runtime` is installed.
- Save your IBM credentials with Qiskit Runtime so the service can load your account.
- Optionally set `IBM_BACKEND_NAME` to the exact hardware backend you want.
- Run the simulator from the `entangled_faas/` directory with `python3 main.py`.

Example changes:

1. Run faster local experiments:

```python
max_iter = 150
SIM_TIME = 1200.0
```

2. Increase contention realism:

```python
bg_job_arrival_rate = 0.12
```

3. Limit to a subset of levels:

```python
ALL_LEVELS = [
	LEVEL_SIMPLE,
	LEVEL_COMPLEX,
]
```

4. Tune Entangled-FaaS urgency behavior:

```python
alpha = 120.0
beta = 8.0
gamma = 1.0
tau_drift = 240.0
```

5. Run on IBM Runtime:

```python
QUANTUM_BACKEND = "ibm_runtime"
IBM_BACKEND_NAME = None
IBM_PRECISION = 0.1
IBM_RESILIENCE_LEVEL = 1
```

After changing config, rerun:

```bash
cd entangled_faas
python main.py
```

## Additional Circuit Generation

To generate 5 additional complex circuits (with printed names and depths):

```bash
cd entangled_faas
python generate_extra_complex_circuits.py
```

QASM files are written into `circuits/`.

## Notes

- Filenames for output JSONs include sanitized level names.
- Some Qiskit classes may emit deprecation warnings depending on installed version; these warnings do not stop simulation execution.
