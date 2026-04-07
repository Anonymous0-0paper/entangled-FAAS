"""
config.py — Central Configuration for the Entangled-FaaS Simulator
===================================================================
All hyperparameters, scheduling weights, and simulation constants.
Variable names mirror the mathematical notation in the paper exactly.
"""

# ── Simulation modes ────────────────────────────────────────────────────────
MODE_BASELINE           = "Standard Batch-Queue (SBQ)"
MODE_PURE_FAAS          = "Pure FaaS (PF)"
MODE_STATIC_RESERVATION = "Static Reservation (SR)"
MODE_PILOT_QUANTUM      = "Pilot-Quantum (PQ)"
MODE_ENTANGLED          = "Entangled-FaaS"

ALL_MODES = [
    MODE_BASELINE,
    MODE_PURE_FAAS,
    MODE_STATIC_RESERVATION,
    MODE_PILOT_QUANTUM,
    MODE_ENTANGLED,
]

# Short labels for plots / file names
MODE_LABELS = {
    MODE_BASELINE:           "SBQ",
    MODE_PURE_FAAS:          "PF",
    MODE_STATIC_RESERVATION: "SR",
    MODE_PILOT_QUANTUM:      "PQ",
    MODE_ENTANGLED:          "EFaaS",
}

MODE_COLORS = {
    MODE_BASELINE:           "#d62728",   # Red
    MODE_PURE_FAAS:          "#ff7f0e",   # Orange
    MODE_STATIC_RESERVATION: "#1f77b4",   # Blue
    MODE_PILOT_QUANTUM:      "#9467bd",   # Purple
    MODE_ENTANGLED:          "#2ca02c",   # Green
}

# ── Scheduler Hyperparameters (Table III) ────────────────────────────────────
alpha: float = 100.0    # Session-awareness (Hot Iterator) boost weight
beta:  float = 5.0      # Drift-urgency weight
gamma: float = 1.0      # Baseline fair-share weight

# Baseline: α and β are zeroed out (pure FIFO)
alpha_baseline: float = 0.0
beta_baseline:  float = 0.0

# ── Quantum Drift Threshold (Section III-C / Table III) ──────────────────────
tau_drift: float = 300.0   # seconds — calibration validity window
t_calib:   float = 30.0    # Re-calibration penalty (cold start)
epsilon:   float = 10.0    # Safety margin ε: t_cpu ≤ τ_drift − ε

# ── Pure FaaS — container cold-start window ──────────────────────────────────
t_faas_coldstart_min: float = 2.0   # minimum container init time (s)
t_faas_coldstart_max: float = 8.0   # maximum container init time (s)
t_pilot_init:         float = 2.0   # Pilot-Quantum startup overhead (s)
t_pilot_overhead:     float = 0.5   # Pilot-Quantum middleware task latency (s)

# ── Quantum Execution Parameters (Table II) ──────────────────────────────────
shots:         int   = 4096
max_iter:      int   = 1000      # set to 1000 for full paper experiment
ansatz_reps:   int   = 4
num_qubits:    int   = 4

# ── Quantum Backend Selection ───────────────────────────────────────────────
# Valid values:
#   "aer"           → local noisy Qiskit Aer estimator (default)
#   "statevector"   → exact noiseless fallback
#   "ibm_runtime"   → IBM Quantum Runtime EstimatorV2 via saved account / token
#   "fake_nighthawk"→ local IBM fake backend with 120 qubits
#   "fake_washington" / "fake_sherbrooke" → local IBM fake backends with 127 qubits
#   "fake_toronto"   → local IBM fake backend with 27 qubits
QUANTUM_BACKEND: str = "aer"
IBM_RUNTIME_CHANNEL: str | None = None
IBM_BACKEND_NAME: str | None = None
IBM_PRECISION: float = 0.1
IBM_RESILIENCE_LEVEL: int = 1
FAKE_BACKEND_NAME: str | None = None

# ── Timing Model (all in simulated seconds) ───────────────────────────────────
t_net:       float = 0.5
t_qpu_base:  float = 2.0
t_cpu:       float = 1.5
t_async:     float = 0.8    # Speculative classical work (Quantum Future)
t_queue_base:float = 15.0   # Base queue delay for SBQ/PF
t_queue_mu:    float = 3.5    # ~33s mean in log space
t_queue_sigma: float = 0.8    # high variance

# ── Infrastructure ────────────────────────────────────────────────────────────
N_QPU:       int = 3
N_classical: int = 4

# ── Background traffic ────────────────────────────────────────────────────────
bg_job_arrival_rate: float = 0.05   # Poisson jobs/second
bg_t_qpu_mean:       float = 5.0

# ── Total simulation wall-clock budget (simulated seconds) ─────────────────
SIM_TIME: float = 3000.0

# ── Convergence / Fidelity ────────────────────────────────────────────────────
energy_convergence_threshold: float = 0.05
lih_ground_state_energy:      float = -7.882

# ── Noise ────────────────────────────────────────────────────────────────────
base_depol_error: float = 0.001
max_drift_factor: float = 2.0

# ── Reproducibility ───────────────────────────────────────────────────────────
RANDOM_SEED: int = 42

# ── Paths ─────────────────────────────────────────────────────────────────────
import os as _os
_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
OUTPUT_DIR  = _os.path.join(_BASE, "output")
FIGURES_DIR = _os.path.join(_BASE, "figures")
CIRCUITS_DIR = _os.path.join(_BASE, "circuits")

# ── Complexity Levels ─────────────────────────────────────────────────────────
LEVEL_SIMPLE  = "Simple (BV-4q)"
LEVEL_MEDIUM  = "Medium (ESU2-6q)"
LEVEL_COMPLEX = "Complex (ESU2-8q)"

# # Extra complex benchmark circuits (all parameterized, hardware-relevant ansatze) (mqt-bench)
LEVEL_COMPLEX_EFFSU2_10Q_R6_FULL   = "complex_efficientsu2_10q_r6_full"
LEVEL_COMPLEX_EFFSU2_12Q_R5_LINEAR = "complex_efficientsu2_12q_r5_linear"
LEVEL_COMPLEX_REALAMP_10Q_R7       = "complex_realamplitudes_10q_r7_linear"
LEVEL_COMPLEX_TWOLOCAL_10Q_R6_CZ   = "complex_twolocal_10q_r6_cz"
LEVEL_COMPLEX_TWOLOCAL_12Q_R5_CX   = "complex_twolocal_12q_r5_cx"

ALL_LEVELS = [
    LEVEL_SIMPLE,
    # LEVEL_MEDIUM,
    # LEVEL_COMPLEX,
    # LEVEL_COMPLEX_EFFSU2_10Q_R6_FULL,
    # LEVEL_COMPLEX_EFFSU2_12Q_R5_LINEAR,
    # LEVEL_COMPLEX_REALAMP_10Q_R7,
    # LEVEL_COMPLEX_TWOLOCAL_10Q_R6_CZ,
    # LEVEL_COMPLEX_TWOLOCAL_12Q_R5_CX,
]

# ── Sensitivity analysis parameter grids ─────────────────────────────────────
# SENSITIVITY_GRIDS = {
#     "alpha":     [0.0, 10.0, 50.0, 100.0, 200.0],
#     "beta":      [0.0, 1.0,  5.0,  10.0,  20.0],
#     "gamma":     [0.1, 0.5,  1.0,  2.0,   5.0],
#     "tau_drift": [60.0, 150.0, 300.0, 600.0, 900.0],
# }

# EFaaS ablation study
ABLATION_REPEATS: int = 3
ABLATION_OUTPUT_BASENAME: str = "efaas_ablation"

# Standard circuit catalog controls (used by main.py)
# CIRCUITS_PER_LEVEL controls how many circuits to use per complexity band.
# ENABLED_COMPLEXITY_BANDS chooses which groups are run.
CIRCUITS_PER_LEVEL: int = 10
# ENABLED_COMPLEXITY_BANDS: list[str] = ["simple", "medium", "complex"]
ENABLED_COMPLEXITY_BANDS: list[str] = ["simple"]
SENSITIVITY_GRIDS = {
    "alpha":     [0.0, 10.0, 50.0, 100.0, 200.0],
    "beta":      [0.0, 1.0, 5.0, 10.0, 20.0],
    "gamma":     [0.1, 0.5, 1.0, 2.0, 5.0],
    "tau_drift": [60.0, 150.0, 300.0, 600.0, 900.0],
}

