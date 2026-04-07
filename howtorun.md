# How To Run Entangled-FaaS

This document explains how to configure and run the simulator for different quantum backends and circuit sets.

## 1. Project Layout

Main files:
- `entangled_faas/main.py` - entry point for the simulator
- `entangled_faas/config.py` - all runtime options
- `entangled_faas/workload.py` - VQE circuit execution and backend selection
- `entangled_faas/scheduler.py` - scheduling logic
- `circuits/` - exported QASM circuits
- `output/` - generated JSON metrics
- `figures/` - generated plots

## 2. Install Dependencies

From the repository root:

```bash
python3 -m pip install -r requirements.txt
```

If you plan to use IBM Runtime or IBM fake backends, make sure `qiskit-ibm-runtime` is installed. It is already listed in `requirements.txt` in this workspace.

## 3. How the Code Chooses a Backend

The active backend is controlled in `entangled_faas/config.py` by:

```python
QUANTUM_BACKEND: str = "aer"
```

Supported values in this project:
- `aer` - local noisy simulator using Qiskit Aer
- `statevector` - exact noiseless fallback
- `ibm_runtime` - real IBM Quantum Runtime backend
- `fake_nighthawk` - IBM fake backend with 120 qubits
- `fake_washington` - IBM fake backend with 127 qubits
- `fake_sherbrooke` - IBM fake backend with 127 qubits
- `fake_toronto` - IBM fake backend with 27 qubits

Other related config options:
- `IBM_BACKEND_NAME` - choose a specific IBM hardware backend when using `ibm_runtime`
- `IBM_RUNTIME_CHANNEL` - optional IBM channel string, if needed for your account setup
- `IBM_PRECISION` - target estimator precision for IBM Runtime and fake-backend mode
- `IBM_RESILIENCE_LEVEL` - IBM Runtime resilience setting
- `FAKE_BACKEND_NAME` - optional explicit fake backend name if you want to override the backend selector

## 4. How To Run the Simulator

Always run from the `entangled_faas/` directory:

```bash
cd entangled_faas
python3 main.py
```

The simulator will print the active backend at startup and write results into `output/` and `figures/`.

## 5. Recommended Backend Choices

### Local development and quick checks
Use `aer`.

Why:
- fastest setup
- no IBM credentials required
- includes a noise model

Config:
```python
QUANTUM_BACKEND = "aer"
```

### Exact debugging and baseline comparison
Use `statevector`.

Why:
- noiseless
- useful for verifying circuit logic or checking whether noise is driving a result

Config:
```python
QUANTUM_BACKEND = "statevector"
```

### IBM real hardware / IBM Runtime
Use `ibm_runtime`.

Why:
- runs through IBM Quantum Runtime
- can target a real backend
- best if you want hardware execution instead of simulation

Config example:
```python
QUANTUM_BACKEND = "ibm_runtime"
IBM_BACKEND_NAME = None
IBM_RUNTIME_CHANNEL = None
IBM_PRECISION = 0.1
IBM_RESILIENCE_LEVEL = 1
```

### IBM fake backends
Use one of the `fake_*` options.

Why:
- behaves like IBM-style hardware models
- no real IBM hardware access needed
- good for testing backend-specific code paths

Recommended choices:
- `fake_nighthawk` - best match for a 100-qubit-scale test
- `fake_washington` - 127 qubits
- `fake_sherbrooke` - 127 qubits
- `fake_toronto` - smaller device, faster tests

Config example:
```python
QUANTUM_BACKEND = "fake_nighthawk"
FAKE_BACKEND_NAME = None
```

## 6. How To Use IBM Runtime

If you want to run on IBM, do this:

1. Set:

```python
QUANTUM_BACKEND = "ibm_runtime"
```

2. Make sure the IBM package is installed:

```bash
python3 -m pip install qiskit-ibm-runtime
```

3. Authenticate your IBM account.

Typical approaches are:
- save your IBM account with Qiskit Runtime once
- or load your IBM credentials according to the IBM Runtime documentation

4. Optionally choose a backend explicitly:

```python
IBM_BACKEND_NAME = "ibm_brisbane"
```

If you leave `IBM_BACKEND_NAME` empty, the code will try to use the least busy operational IBM hardware backend that has enough qubits for the circuit.

5. Run the simulator:

```bash
cd entangled_faas
python3 main.py
```

## 7. How To Use Fake IBM Backends

If you want IBM-like device behavior without real hardware, set one of these:

```python
QUANTUM_BACKEND = "fake_nighthawk"
```

Other examples:

```python
QUANTUM_BACKEND = "fake_washington"
QUANTUM_BACKEND = "fake_sherbrooke"
QUANTUM_BACKEND = "fake_toronto"
```

Useful rule:
- for circuits around 100 qubits, use `fake_nighthawk`
- for much smaller circuits, `fake_toronto` is lighter
- for large-device testing, `fake_washington` or `fake_sherbrooke` are good

## 8. Circuit Levels and QASM Files

The circuit level is chosen in `config.py` with `ALL_LEVELS`.

Current levels in the code:
- `LEVEL_SIMPLE = "Simple (BV-4q)"`
- `LEVEL_MEDIUM = "Medium (ESU2-6q)"`
- `LEVEL_COMPLEX = "Complex (ESU2-8q)"`
- extra named benchmark circuits such as:
  - `complex_efficientsu2_10q_r6_full`
  - `complex_efficientsu2_12q_r5_linear`
  - `complex_realamplitudes_10q_r7_linear`
  - `complex_twolocal_10q_r6_cz`
  - `complex_twolocal_12q_r5_cx`

The `circuits/` folder contains generated QASM files for different modes and levels, for example:
- `circuit_simple_standard.qasm`
- `circuit_simple_static.qasm`
- `circuit_simple_pure.qasm`
- `circuit_simple_pilot-quantum.qasm`
- `circuit_simple_entangled-faas.qasm`
- `circuit_medium_standard.qasm`
- `circuit_complex_standard.qasm`
- `complex_efficientsu2_10q_r6_full.qasm`

If you want to run a different circuit family, edit `ALL_LEVELS` in `config.py`.

Example:

```python
ALL_LEVELS = [
    LEVEL_SIMPLE,
    LEVEL_MEDIUM,
    LEVEL_COMPLEX,
]
```

## 9. Running Different Modes

The simulator supports these modes:
- `SBQ` - Standard Batch-Queue
- `PF` - Pure FaaS
- `SR` - Static Reservation
- `PQ` - Pilot-Quantum
- `EFaaS` - Entangled-FaaS

The active modes are controlled by `ALL_MODES` in `config.py`.

If you want to run all five modes, keep:

```python
ALL_MODES = [
    MODE_BASELINE,
    MODE_PURE_FAAS,
    MODE_STATIC_RESERVATION,
    MODE_PILOT_QUANTUM,
    MODE_ENTANGLED,
]
```

If you want faster experiments, you can comment out modes and keep only the ones you need.

Example for a reduced run:

```python
ALL_MODES = [
    MODE_BASELINE,
    MODE_ENTANGLED,
]
```

## 10. Useful Config Settings

Common settings you may want to change:
- `max_iter` - number of VQE iterations
- `SIM_TIME` - simulation budget in simulated seconds
- `N_QPU` - number of quantum resources in the simulator
- `N_classical` - number of classical resources in the simulator
- `bg_job_arrival_rate` - background traffic intensity
- `bg_t_qpu_mean` - average background QPU service time
- `alpha`, `beta`, `gamma` - scheduling weights
- `tau_drift` - how long calibration is considered valid
- `shots` - number of samples per quantum evaluation

Example for faster local testing:

```python
max_iter = 150
SIM_TIME = 1200.0
```

Example for higher contention:

```python
bg_job_arrival_rate = 0.12
```

Example for stronger Entangled-FaaS urgency:

```python
alpha = 120.0
beta = 8.0
gamma = 1.0
tau_drift = 240.0
```

## 11. Typical Run Recipes

### Recipe A: Fast local test
```python
QUANTUM_BACKEND = "aer"
ALL_LEVELS = [LEVEL_SIMPLE]
ALL_MODES = [MODE_BASELINE, MODE_ENTANGLED]
max_iter = 150
SIM_TIME = 1200.0
```

### Recipe B: Exact noiseless check
```python
QUANTUM_BACKEND = "statevector"
ALL_LEVELS = [LEVEL_SIMPLE]
```

### Recipe C: IBM hardware run
```python
QUANTUM_BACKEND = "ibm_runtime"
IBM_BACKEND_NAME = None
ALL_LEVELS = [LEVEL_SIMPLE]
```

### Recipe D: Fake IBM backend run
```python
QUANTUM_BACKEND = "fake_nighthawk"
ALL_LEVELS = [LEVEL_SIMPLE]
```

## 12. Qiskit Serverless Integration

This repository now includes minimal Qiskit Serverless scaffolding:

- `entangled_faas/serverless_job.py` - single simulation job entrypoint
- `entangled_faas/serverless_submit.py` - submit helper
- `entangled_faas/serverless_payload_example.json` - sample payload

### 12.1 What it runs

The serverless entrypoint runs one simulation task per payload (one mode + one level + one hyperparameter set), then returns a JSON result containing:
- input payload
- simulation summary metrics

This is ideal for distributing sweeps over:
- modes
- circuit levels
- hyperparameters

### 12.2 Local dry-run (no serverless provider needed)

Use this to validate payloads and logic locally:

```bash
cd entangled_faas
python3 serverless_job.py --payload-file serverless_payload_example.json
```

You can also pass inline JSON:

```bash
cd entangled_faas
python3 serverless_job.py --payload '{"mode":"EFaaS","level":"Simple (BV-4q)","config_overrides":{"QUANTUM_BACKEND":"aer"}}'
```

### 12.3 Payload format

Supported payload keys:
- `mode`: one of `SBQ`, `PF`, `SR`, `PQ`, `EFaaS` or full mode strings
- `level`: one of your configured level strings (for example `Simple (BV-4q)`)
- `seed_offset`: integer
- `alpha`, `beta`, `gamma`, `tau_drift`: optional scheduler overrides
- `verbose`: `true/false`
- `config_overrides`: dictionary of temporary config overrides
- `output_filename`: optional filename saved into `output/`

Example:

```json
{
    "mode": "EFaaS",
    "level": "Simple (BV-4q)",
    "seed_offset": 0,
    "alpha": 100.0,
    "beta": 5.0,
    "gamma": 1.0,
    "tau_drift": 300.0,
    "verbose": false,
    "config_overrides": {
        "QUANTUM_BACKEND": "aer",
        "SIM_TIME": 1200.0,
        "max_iter": 200
    },
    "output_filename": "serverless_single_run_result.json"
}
```

### 12.4 Submit to Qiskit Serverless

After your Qiskit Serverless environment/provider is configured:

```bash
cd entangled_faas
python3 serverless_submit.py --payload-file serverless_payload_example.json
```

The submit helper tries common qiskit-serverless APIs to be compatible with minor version differences.

### 12.5 How to run many jobs

Recommended pattern:
- create one payload per mode/level combination
- submit jobs in parallel
- aggregate output JSON files from `output/`

Examples:
- Sweep modes at fixed circuit: keep `level` constant, vary `mode`
- Sweep levels at fixed mode: keep `mode` constant, vary `level`
- Sweep backend: vary `config_overrides.QUANTUM_BACKEND`

### 12.6 IBM Runtime in serverless payload

To run hardware-backed jobs through the same entrypoint, set in `config_overrides`:

```json
{
    "QUANTUM_BACKEND": "ibm_runtime",
    "IBM_BACKEND_NAME": "ibm_brisbane",
    "IBM_PRECISION": 0.1,
    "IBM_RESILIENCE_LEVEL": 1
}
```

If `IBM_BACKEND_NAME` is omitted or `null`, the code chooses the least busy operational backend with enough qubits.

### 12.7 Fake IBM backends in serverless payload

Set one of:
- `QUANTUM_BACKEND = "fake_nighthawk"`
- `QUANTUM_BACKEND = "fake_washington"`
- `QUANTUM_BACKEND = "fake_sherbrooke"`
- `QUANTUM_BACKEND = "fake_toronto"`

For around 100 qubits, use `fake_nighthawk` first.

## 13. Troubleshooting

- If Python cannot import `config`, run the simulator from inside `entangled_faas/`.
- If IBM Runtime fails, verify that your IBM account is saved and active.
- If a fake backend says the circuit is too large, choose a backend with more qubits.
- If execution is slow, reduce `ALL_LEVELS`, `ALL_MODES`, or `max_iter`.
- If you only want to verify code paths, use `statevector`.

Serverless-specific checks:
- If submission fails, confirm your qiskit-serverless version and provider setup.
- Test with `serverless_job.py --payload-file ...` locally before remote submission.
- Start with `QUANTUM_BACKEND = "aer"` in payloads, then switch to IBM Runtime.

## 14. Short Version

Most common commands:

```bash
cd entangled_faas
python3 main.py
```

To switch backend, edit `entangled_faas/config.py` and set `QUANTUM_BACKEND` to one of the supported values.
