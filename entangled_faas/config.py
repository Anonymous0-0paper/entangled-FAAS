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
MODE_ENTANGLED          = "Entangled-FaaS"

ALL_MODES = [
    MODE_BASELINE,
    MODE_PURE_FAAS,
    MODE_STATIC_RESERVATION,
    MODE_ENTANGLED,
]

# Short labels for plots / file names
MODE_LABELS = {
    MODE_BASELINE:           "SBQ",
    MODE_PURE_FAAS:          "PF",
    MODE_STATIC_RESERVATION: "SR",
    MODE_ENTANGLED:          "EFaaS",
}

MODE_COLORS = {
    MODE_BASELINE:           "#d62728",   # Red
    MODE_PURE_FAAS:          "#ff7f0e",   # Orange
    MODE_STATIC_RESERVATION: "#1f77b4",   # Blue
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

# ── Quantum Execution Parameters (Table II) ──────────────────────────────────
shots:         int   = 4096
max_iter:      int   = 150      # set to 1000 for full paper experiment
ansatz_reps:   int   = 4
num_qubits:    int   = 4

# ── Timing Model (all in simulated seconds) ───────────────────────────────────
t_net:       float = 0.5
t_qpu_base:  float = 2.0
t_cpu:       float = 1.5
t_async:     float = 0.8    # Speculative classical work (Quantum Future)
t_queue_base:float = 15.0   # Base queue delay for SBQ/PF

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

# ── Sensitivity analysis parameter grids ─────────────────────────────────────
SENSITIVITY_GRIDS = {
    "alpha":     [0.0, 10.0, 50.0, 100.0, 200.0],
    "beta":      [0.0, 1.0,  5.0,  10.0,  20.0],
    "gamma":     [0.1, 0.5,  1.0,  2.0,   5.0],
    "tau_drift": [60.0, 150.0, 300.0, 600.0, 900.0],
}
