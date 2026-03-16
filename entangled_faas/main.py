"""
main.py — Entangled-FaaS Simulator Entry Point (Extended)
==========================================================
Orchestrates:
  1. All four architectural baselines (SBQ, PF, SR, EFaaS)
  2. Saves per-mode JSON metrics to output/
  3. Runs hyperparameter sensitivity analysis
  4. Generates publication-quality figures to figures/

Usage:
    cd entangled_faas/
    python main.py
"""

from __future__ import annotations

import os
import sys
import random
import time

sys.path.insert(0, os.path.dirname(__file__))

import simpy

import config
from sim_env   import ClassicalCloud, QuantumCloud
from scheduler import EntangledFaaSScheduler
from workload  import VQEJob, BackgroundBatchJobGenerator
from tracker   import MetricsTracker
import sensitivity as sens_module
import plotter


# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(
    mode:          str,
    seed_offset:   int = 0,
    alpha:         float = config.alpha,
    beta:          float = config.beta,
    gamma:         float = config.gamma,
    tau_drift:     float = config.tau_drift,
    verbose:       bool  = True,
) -> dict:
    """
    Instantiate and run one complete simulation for *mode*.
    Returns the metrics summary dict (includes per-iteration arrays).
    """
    label = config.MODE_LABELS.get(mode, mode)
    if verbose:
        print(f"\n{'─'*65}")
        print(f"  Simulation: [{label}]  —  {mode}")
        print(f"  α={alpha}  β={beta}  γ={gamma}  τ_drift={tau_drift}s")
        print(f"  QPUs={config.N_QPU}  Classical={config.N_classical}"
              f"  Iterations={config.max_iter}")
        print(f"{'─'*65}")

    seed = config.RANDOM_SEED + seed_offset
    rng  = random.Random(seed)

    env             = simpy.Environment()
    classical_cloud = ClassicalCloud(env, n_nodes=config.N_classical)
    quantum_cloud   = QuantumCloud(env, n_qpus=config.N_QPU)
    tracker         = MetricsTracker(mode=mode, n_qpus=config.N_QPU)

    scheduler = EntangledFaaSScheduler(
        env=env, quantum_cloud=quantum_cloud, tracker=tracker,
        mode=mode, rng=rng,
        alpha=alpha, beta=beta, gamma=gamma, tau_drift=tau_drift,
    )

    vqe_job = VQEJob(
        env=env, scheduler=scheduler, classical_cloud=classical_cloud,
        quantum_cloud=quantum_cloud, tracker=tracker, mode=mode, rng=rng,
    )

    bg_gen = BackgroundBatchJobGenerator(
        env=env, scheduler=scheduler, tracker=tracker,
        arrival_rate=config.bg_job_arrival_rate, rng=rng,
    )

    env.process(vqe_job.run())
    env.process(bg_gen.run())

    wall_t0 = time.perf_counter()
    env.run(until=config.SIM_TIME)
    wall_elapsed = time.perf_counter() - wall_t0

    summary                  = tracker.summary(env.now)
    summary["wall_clock_s"]  = round(wall_elapsed, 2)

    # ── Save JSON ─────────────────────────────────────────────────────────
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(config.OUTPUT_DIR, f"results_{label.lower()}.json")
    tracker.to_json(json_path, env.now)

    if verbose:
        print(f"  Completed {summary['iterations_completed']:>4d} iterations  "
              f"(wall={wall_elapsed:.1f}s)")
        print(f"  Mean TTNS         : {summary['mean_ttns_s']:.3f} s")
        print(f"  QDC               : {summary['qdc_pct']:.2f} %")
        print(f"  Drift penalties   : {summary['drift_penalties']}")
        if summary["convergence_time_s"] is not None:
            print(f"  Converged         : iter {summary['convergence_iter']}"
                  f"  (t={summary['convergence_time_s']:.1f} s)")
        else:
            print(f"  Convergence       : not reached within sim budget")

    return summary


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 65)
    print("  ENTANGLED-FaaS DISCRETE-EVENT SIMULATOR  (Extended)")
    print("  Hybrid Variational Quantum Algorithm Co-Scheduling")
    print("=" * 65)
    print(f"  Paper: 'Quantum-Classical Serverless: An Entangled Scheduler")
    print(f"          for Hybrid Variational Algorithms'")
    print(f"  VQE benchmark : LiH molecule, RealAmplitudes({config.num_qubits}q, "
          f"reps={config.ansatz_reps})")
    print(f"  Optimizer     : SPSA (max_iter={config.max_iter})")
    print(f"  Sim budget    : {config.SIM_TIME:.0f} simulated seconds")
    print("=" * 65)

    # ── 1. Run all four architectural modes ───────────────────────────────
    all_summaries = []
    for offset, mode in enumerate(config.ALL_MODES):
        s = run_simulation(mode=mode, seed_offset=offset)
        all_summaries.append(s)

    # ── 2. Comparative table ──────────────────────────────────────────────
    MetricsTracker.print_comparison(all_summaries)

    # ── 3. Improvement ratios vs SBQ baseline ─────────────────────────────
    base_s  = all_summaries[0]   # SBQ
    efaas_s = all_summaries[-1]  # EFaaS

    print("  KEY IMPROVEMENTS (Entangled-FaaS vs Standard Batch-Queue):")
    print("  " + "─" * 55)
    if base_s["mean_ttns_s"] > 0:
        tr = (base_s["mean_ttns_s"] - efaas_s["mean_ttns_s"]) / base_s["mean_ttns_s"] * 100
        print(f"  TTNS reduction        : {tr:+.1f} %")
    print(f"  QDC improvement       : {efaas_s['qdc_pct'] - base_s['qdc_pct']:+.2f} pp")
    bd = base_s.get("drift_penalties", 0)
    ed = efaas_s.get("drift_penalties", 0)
    if bd > 0:
        print(f"  Drift penalty reduction: {(bd-ed)/bd*100:+.1f} %  ({bd} → {ed})")
    bc = base_s.get("convergence_time_s")
    ec = efaas_s.get("convergence_time_s")
    if bc and ec:
        print(f"  Convergence speedup   : {(bc-ec)/bc*100:+.1f} %")
    elif ec and not bc:
        print(f"  Convergence speedup   : Baseline did NOT converge!")
    print("  " + "─" * 55 + "\n")

    # ── 4. Sensitivity analysis ───────────────────────────────────────────
    print("  [Step 4] Running hyperparameter sensitivity analysis …")
    sensitivity_results = sens_module.run_sweep()

    # ── 5. Generate publication figures ──────────────────────────────────
    print("  [Step 5] Generating publication figures …")
    figure_paths = plotter.generate_all_plots(
        summaries        = all_summaries,
        sensitivity_data = sensitivity_results,
        output_dir       = config.FIGURES_DIR,
    )

    # ── 6. Final summary ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  ALL DONE")
    print("=" * 65)
    print(f"  JSON metrics   → {config.OUTPUT_DIR}/")
    print(f"  Figures (PDF + PNG) → {config.FIGURES_DIR}/")
    for p in figure_paths:
        if p:
            print(f"    {os.path.basename(p)}")
    print("=" * 65 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
