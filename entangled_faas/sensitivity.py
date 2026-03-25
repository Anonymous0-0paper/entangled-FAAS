"""
sensitivity.py — Hyperparameter Sensitivity Analysis
=====================================================
Sweeps each of the four Entangled-FaaS hyperparameters independently,
running the full simulation for each value and collecting:
  - Mean TTNS
  - QDC
  - Convergence time
  - Drift penalty count

Results are saved to JSON in the output/ directory.

Sweep grids (from config.SENSITIVITY_GRIDS):
  alpha:     [0, 10, 50, 100, 200]
  beta:      [0, 1, 5, 10, 20]
  gamma:     [0.1, 0.5, 1.0, 2.0, 5.0]
  tau_drift: [60, 150, 300, 600, 900]
"""

from __future__ import annotations

import json
import os
import random
from typing import Dict, List

import simpy

import config
from sim_env   import ClassicalCloud, QuantumCloud
from scheduler import EntangledFaaSScheduler
from workload  import VQEJob, BackgroundBatchJobGenerator
from tracker   import MetricsTracker


# ─────────────────────────────────────────────────────────────────────────────

def _run_one_point(
    *,
    alpha:     float,
    beta:      float,
    gamma:     float,
    tau_drift: float,
    seed:      int = config.RANDOM_SEED + 99,
) -> Dict:
    """
    Run a single Entangled-FaaS simulation with the given hyperparameters.
    Returns the summary dict with scalar metrics only.
    """
    rng = random.Random(seed)
    env = simpy.Environment()

    classical_cloud = ClassicalCloud(env, n_nodes=config.N_classical)
    quantum_cloud   = QuantumCloud(env, n_qpus=config.N_QPU)
    tracker         = MetricsTracker(mode=config.MODE_ENTANGLED, n_qpus=config.N_QPU)

    scheduler = EntangledFaaSScheduler(
        env=env, quantum_cloud=quantum_cloud, classical_cloud=classical_cloud, tracker=tracker,
        mode=config.MODE_ENTANGLED, rng=rng,
        alpha=alpha, beta=beta, gamma=gamma, tau_drift=tau_drift,
    )

    vqe = VQEJob(
        env=env, scheduler=scheduler, classical_cloud=classical_cloud,
        quantum_cloud=quantum_cloud, tracker=tracker,
        mode=config.MODE_ENTANGLED, rng=rng,
    )
    bg = BackgroundBatchJobGenerator(
        env=env, scheduler=scheduler, tracker=tracker,
        arrival_rate=config.bg_job_arrival_rate, rng=rng,
    )

    env.process(vqe.run())
    env.process(bg.run())
    env.run(until=config.SIM_TIME)

    s = tracker.summary(env.now)
    # Keep only scalar fields for the sensitivity output (no large arrays)
    return {
        "alpha":              alpha,
        "beta":               beta,
        "gamma":              gamma,
        "tau_drift":          tau_drift,
        "mean_ttns_s":        s["mean_ttns_s"],
        "std_ttns_s":         s["std_ttns_s"],
        "qdc_pct":            s["qdc_pct"],
        "convergence_time_s": s["convergence_time_s"],
        "convergence_iter":   s["convergence_iter"],
        "drift_penalties":    s["drift_penalties"],
        "iterations_completed": s["iterations_completed"],
    }


# ─────────────────────────────────────────────────────────────────────────────

def run_sweep() -> Dict[str, List[Dict]]:
    """
    Perform the full sensitivity sweep over all four hyperparameters.
    Each parameter is varied independently while the others stay at their
    default values (α=100, β=5, γ=1, τ_drift=300).

    Saves individual JSON files and returns the full results dict.
    """
    print("\n" + "─" * 60)
    print("  SENSITIVITY ANALYSIS — Hyperparameter Sweep")
    print("─" * 60)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # Defaults for non-swept parameters
    defaults = dict(
        alpha=config.alpha,
        beta=config.beta,
        gamma=config.gamma,
        tau_drift=config.tau_drift,
    )

    all_results: Dict[str, List[Dict]] = {}

    for param_name, values in config.SENSITIVITY_GRIDS.items():
        print(f"  Sweeping {param_name}: {values}")
        param_results = []
        for i, val in enumerate(values):
            kw = {**defaults, param_name: val}
            print(f"    [{i+1}/{len(values)}] {param_name}={val} ...", end="", flush=True)
            result = _run_one_point(**kw, seed=config.RANDOM_SEED + i * 13)
            param_results.append(result)
            print(f" → TTNS={result['mean_ttns_s']:.2f}s  QDC={result['qdc_pct']:.2f}%")

        all_results[param_name] = param_results

        # Save per-parameter JSON
        fname = os.path.join(config.OUTPUT_DIR, f"sensitivity_{param_name}.json")
        with open(fname, "w") as f:
            json.dump({"parameter": param_name, "results": param_results}, f, indent=2)
        print(f"  Saved → {fname}")

    # Also save combined sensitivity JSON
    combined_path = os.path.join(config.OUTPUT_DIR, "sensitivity_combined.json")
    with open(combined_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"  Saved combined → {combined_path}")
    print("─" * 60)

    return all_results
