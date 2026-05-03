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
import json
import re
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))

import simpy

import config
from sim_env   import ClassicalCloud, QuantumCloud
from scheduler import EntangledFaaSScheduler
from workload  import VQEJob, BackgroundBatchJobGenerator
from tracker   import MetricsTracker
import sensitivity as sens_module
import plotter
import ablation


# ─────────────────────────────────────────────────────────────────────────────

def _build_standard_circuit_catalog() -> Dict[str, List[dict]]:
    """
    Curated, reproducible, standard variational benchmarks.
    Families are from Qiskit's circuit library and widely used in VQA studies.
    """
    return {
        # 2-5 qubits
        "simple": [
            {"level": "std_efficientsu2_2q_r1_linear", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_2q_r2_linear", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_3q_r1_cx_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_3q_r2_linear", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_3q_r3_full", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_4q_r2_cz_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_4q_r3_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_4q_r4_linear", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_5q_r3_cx_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_5q_r4_full", "citation": "Qiskit EfficientSU2"},
        ],
        # 6-10 qubits
        "medium": [
            {"level": "std_efficientsu2_6q_r2_linear", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_6q_r3_linear", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_6q_r3_cx_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_7q_r3_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_7q_r4_linear", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_8q_r3_cz_full", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_8q_r4_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_9q_r4_linear", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_10q_r4_cx_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_10q_r5_full", "citation": "Qiskit EfficientSU2"},
        ],
        # 10-16 qubits
        "complex": [
            {"level": "std_efficientsu2_10q_r6_linear", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_10q_r6_full", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_11q_r7_cx_linear", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_11q_r7_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_12q_r5_full", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_12q_r6_cz_full", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_13q_r6_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_13q_r7_full", "citation": "Qiskit RealAmplitudes"},
            {"level": "std_twolocal_14q_r7_cx_full", "citation": "Qiskit TwoLocal"},
            {"level": "std_efficientsu2_14q_r8_full", "citation": "Qiskit EfficientSU2"},
            {"level": "std_realamplitudes_16q_r5_linear", "citation": "Qiskit RealAmplitudes"},
            ],
    }


def _select_circuit_levels(circuits_per_level: int, enabled_bands: List[str] | None = None) -> Dict[str, List[dict]]:
    catalog = _build_standard_circuit_catalog()
    ordered_bands = ["simple", "medium", "complex"]
    active_bands = enabled_bands or ordered_bands
    active_set = {b.strip().lower() for b in active_bands if b.strip()}

    selected = {}
    for band in ordered_bands:
        if band not in active_set:
            continue
        rows = catalog[band]
        selected[band] = rows[: max(1, min(circuits_per_level, len(rows)))]
    return selected


def _print_selected_catalog(selected: Dict[str, List[dict]]) -> None:
    print("\n" + "=" * 65)
    print("STANDARD CIRCUIT TEST MATRIX (REPRODUCIBLE)")
    print("Families: EfficientSU2, RealAmplitudes, TwoLocal (Qiskit)")
    print("=" * 65)
    for band in ["simple", "medium", "complex"]:
        rows = selected.get(band, [])
        if not rows:
            continue
        print(f"  {band.upper()} ({len(rows)} circuits)")
        for r in rows:
            print(f"    - {r['level']}  [{r['citation']}]")
    print("=" * 65)


def _flatten_levels(selected: Dict[str, List[dict]]) -> List[str]:
    ordered = []
    for band in ["simple", "medium", "complex"]:
        ordered.extend([r["level"] for r in selected.get(band, [])])
    return ordered


def _save_circuit_catalog(selected: Dict[str, List[dict]]) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.OUTPUT_DIR, "standard_circuit_catalog_for_paper.json")
    payload = {
        "note": "Use these circuit families as citations in the paper: Qiskit EfficientSU2, RealAmplitudes, TwoLocal.",
        "catalog": selected,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  [catalog] Saved reproducible circuit list -> {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(
    mode:          str,
    seed_offset:   int = 0,
    alpha:         float = config.alpha,
    beta:          float = config.beta,
    gamma:         float = config.gamma,
    tau_drift:     float = config.tau_drift,
    level:         str = config.LEVEL_SIMPLE,
    verbose:       bool  = True,
) -> dict:
    """
    Instantiate and run one complete simulation for *mode*.
    Returns the metrics summary dict (includes per-iteration arrays).
    """
    label = config.MODE_LABELS.get(mode, mode)
    if verbose:
        print(f"\n{'─'*65}")
        print(f"  Simulation: [{label}]  —  {mode}  (Circuit: {level})")
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
        env=env, quantum_cloud=quantum_cloud, classical_cloud=classical_cloud, tracker=tracker,
        mode=mode, rng=rng,
        alpha=alpha, beta=beta, gamma=gamma, tau_drift=tau_drift,
    )

    vqe_job = VQEJob(
        env=env, scheduler=scheduler, classical_cloud=classical_cloud,
        quantum_cloud=quantum_cloud, tracker=tracker, mode=mode, rng=rng,
        level=level,
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
    level_tag = re.sub(r"[^a-z0-9]+", "_", level.lower()).strip("_")
    json_path = os.path.join(config.OUTPUT_DIR, f"results_{label.lower()}_{level_tag}.json")
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
    circuits_per_level = int(
        os.getenv("EFAAS_CIRCUITS_PER_LEVEL", str(getattr(config, "CIRCUITS_PER_LEVEL", 10)))
    )

    config_bands = list(getattr(config, "ENABLED_COMPLEXITY_BANDS", ["simple", "medium", "complex"]))
    env_bands = os.getenv("EFAAS_COMPLEXITY_BANDS", "").strip()
    if env_bands:
        selected_bands = [b.strip().lower() for b in env_bands.split(",") if b.strip()]
    else:
        selected_bands = [b.strip().lower() for b in config_bands if b.strip()]

    selected_catalog = _select_circuit_levels(circuits_per_level, selected_bands)
    selected_levels = _flatten_levels(selected_catalog)
    if not selected_levels:
        raise ValueError("No circuit levels selected. Check ENABLED_COMPLEXITY_BANDS or EFAAS_COMPLEXITY_BANDS.")

    print("\n" + "=" * 65)
    print("ENTANGLED-FaaS DISCRETE-EVENT SIMULATOR (Extended)")
    print("Hybrid Variational Quantum Algorithm Co-Scheduling")
    print("=" * 65)
    print("Paper: Quantum-Classical Serverless: An Entangled Scheduler")
    print("       for Hybrid Variational Algorithms")
    print(
        f"VQE benchmark: LiH molecule, RealAmplitudes({config.num_qubits}q, "
        f"reps={config.ansatz_reps})"
    )
    print(f"Quantum backend: {config.QUANTUM_BACKEND}")
    print(f"Optimizer: SPSA (max_iter={config.max_iter})")
    print(f"Sim budget: {config.SIM_TIME:.0f} simulated seconds")
    print(f"Complexity bands: {', '.join(selected_bands)}")
    print(f"Circuits per complexity level: {circuits_per_level}")
    print(f"Total circuit benchmarks: {len(selected_levels)}")
    print("Queue Trace: Lognormal Simulation (IBM Eagle r3 equivalent)")
    print("=" * 65)

    _print_selected_catalog(selected_catalog)
    catalog_path = _save_circuit_catalog(selected_catalog)

    # ── 1. Run all architectural modes across all levels ──────────────────
    all_summaries_by_level = {}
    for level in selected_levels:
        print(f"\n\n{'='*65}\n  RUNNING COMPLEXITY LEVEL: {level}\n{'='*65}")
        level_summaries = []
        for offset, mode in enumerate(config.ALL_MODES):
            # Seed offset depends on both mode and level for determinism
            level_offset = selected_levels.index(level) * 10
            s = run_simulation(mode=mode, seed_offset=offset + level_offset, level=level)
            level_summaries.append(s)
        all_summaries_by_level[level] = level_summaries

    # ── 2. Comparative table for the last level ───────────────────────────
    # (Just to show a sample in the console)
    last_level = selected_levels[-1]
    MetricsTracker.print_comparison(all_summaries_by_level[last_level])

    def _level_tag(level_name: str) -> str:
        return level_name.split(" ")[0].lower()

    def _avg(items):
        return sum(items) / len(items) if items else 0.0

    def _improvement(base: dict, efaas: dict) -> dict:
        out = {
            "qdc_improvement_pp": round(efaas.get("qdc_pct", 0.0) - base.get("qdc_pct", 0.0), 4),
        }
        base_ttns = base.get("mean_ttns_s", 0.0)
        if base_ttns > 0:
            out["ttns_reduction_pct"] = round((base_ttns - efaas.get("mean_ttns_s", 0.0)) / base_ttns * 100.0, 4)

        base_drift = base.get("drift_penalties", 0)
        if base_drift > 0:
            out["drift_penalty_reduction_pct"] = round((base_drift - efaas.get("drift_penalties", 0)) / base_drift * 100.0, 4)

        base_conv = base.get("convergence_time_s")
        efaas_conv = efaas.get("convergence_time_s")
        if base_conv and efaas_conv:
            out["convergence_speedup_pct"] = round((base_conv - efaas_conv) / base_conv * 100.0, 4)
        return out

    # ── 2b. Save per-circuit and average report ─────────────────────────
    per_circuit = {}
    for level in selected_levels:
        level_data = all_summaries_by_level[level]
        tag = _level_tag(level)
        per_mode = {
            s["label"]: {
                "mean_ttns_s": s.get("mean_ttns_s", 0.0),
                "qdc_pct": s.get("qdc_pct", 0.0),
                "convergence_time_s": s.get("convergence_time_s"),
                "drift_penalties": s.get("drift_penalties", 0),
                "mean_energy_ha": s.get("mean_energy_ha"),
                "mean_vqe_wait_s": s.get("mean_vqe_wait_s", 0.0),
                "iterations_completed": s.get("iterations_completed", 0),
            }
            for s in level_data
        }

        efaas_s = next(s for s in level_data if s.get("mode") == config.MODE_ENTANGLED)
        improvements = {}
        for s in level_data:
            if s.get("mode") == config.MODE_ENTANGLED:
                continue
            improvements[s["label"]] = _improvement(s, efaas_s)

        per_circuit[tag] = {
            "name": level,
            "per_mode": per_mode,
            "improvements_entangled_vs_baselines": improvements,
        }

    avg_by_mode = {}
    for mode in config.ALL_MODES:
        label = config.MODE_LABELS.get(mode, mode)
        mode_points = [
            next(s for s in all_summaries_by_level[level] if s.get("mode") == mode)
            for level in selected_levels
        ]
        avg_by_mode[label] = {
            "mean_ttns_s": round(_avg([s.get("mean_ttns_s", 0.0) for s in mode_points]), 4),
            "qdc_pct": round(_avg([s.get("qdc_pct", 0.0) for s in mode_points]), 4),
            "convergence_time_s": round(_avg([s.get("convergence_time_s") for s in mode_points if s.get("convergence_time_s") is not None]), 4),
            "drift_penalties": round(_avg([s.get("drift_penalties", 0) for s in mode_points]), 4),
            "mean_energy_ha": round(_avg([s.get("mean_energy_ha", 0.0) for s in mode_points]), 6),
            "mean_vqe_wait_s": round(_avg([s.get("mean_vqe_wait_s", 0.0) for s in mode_points]), 4),
            "iterations_completed": round(_avg([s.get("iterations_completed", 0) for s in mode_points]), 4),
        }

    avg_efaas = avg_by_mode[config.MODE_LABELS[config.MODE_ENTANGLED]]
    avg_improvements = {}
    for mode in config.ALL_MODES:
        if mode == config.MODE_ENTANGLED:
            continue
        label = config.MODE_LABELS[mode]
        avg_improvements[label] = _improvement(avg_by_mode[label], avg_efaas)

    aggregate_report = {
        "per_circuit": per_circuit,
        "average_across_circuits": {
            "per_mode": avg_by_mode,
            "improvements_entangled_vs_baselines": avg_improvements,
        },
    }
    report_path = os.path.join(config.OUTPUT_DIR, "results_by_circuit_and_average.json")
    with open(report_path, "w") as f:
        json.dump(aggregate_report, f, indent=2)
    print(f"  [report] Saved per-circuit + average summary → {report_path}")

    # ── 3. Improvement ratios vs individual baselines (Last Level) ────────
    all_summaries = all_summaries_by_level[last_level]
    efaas_s = all_summaries[-1]  # EFaaS is the last mode

    for i in range(len(all_summaries) - 1):
        base_s = all_summaries[i]
        label  = base_s["label"]
        
        print(f"  KEY IMPROVEMENTS (Entangled-FaaS vs {label}):")
        print("  " + "─" * 55)
        
        if base_s["mean_ttns_s"] > 0:
            tr = (base_s["mean_ttns_s"] - efaas_s["mean_ttns_s"]) / base_s["mean_ttns_s"] * 100
            print(f"  TTNS reduction        : {tr:+.1f} %")
        
            print(f"  VQE benchmark : LiH molecule, RealAmplitudes({config.num_qubits}q, reps={config.ansatz_reps})")
        bd = base_s.get("drift_penalties", 0)
        ed = efaas_s.get("drift_penalties", 0)
        if bd > 0:
            print(f"  Drift penalty reduction: {(bd-ed)/bd*100:+.1f} %  ({bd} → {ed})")
        
        bc = base_s.get("convergence_time_s")
        ec = efaas_s.get("convergence_time_s")
        if bc and ec:
            print(f"  Convergence speedup   : {(bc-ec)/bc*100:+.1f} %")
        elif ec and not bc:
            print(f"  Convergence speedup   : {label} did NOT converge!")
        
        print("  " + "─" * 55 + "\n")

    # ── 4. Sensitivity analysis ───────────────────────────────────────────
    print("  [Step 4] Running hyperparameter sensitivity analysis …")
    sensitivity_results = sens_module.run_sweep()

    # ── 5. EFaaS ablation study ──────────────────────────────────────────
    print("  [Step 5] Running EFaaS ablation study …")
    ablation_results = ablation.run_efaas_ablation(
        run_once=run_simulation,
        levels=selected_levels,
        repeats=config.ABLATION_REPEATS,
        output_dir=config.OUTPUT_DIR,
        figures_dir=config.FIGURES_DIR,
    )

    # ── 6. Generate publication figures ──────────────────────────────────
    print("  [Step 6] Generating publication figures …")
    figure_paths = plotter.generate_all_plots(
        summaries        = all_summaries,
        sensitivity_data = sensitivity_results,
        output_dir       = config.FIGURES_DIR,
        all_summaries_by_level=all_summaries_by_level,
    )

    # ── 7. Final summary ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  ALL DONE")
    print("=" * 65)
    print(f"  JSON metrics   → {config.OUTPUT_DIR}/")
    print(f"  Ablation CSV   → {ablation_results['raw_csv']}")
    print(f"  Ablation CSV   → {ablation_results['summary_csv']}")
    print(f"  Circuit catalog for paper citations → {catalog_path}")
    print(f"  Figures (PDF + PNG) → {config.FIGURES_DIR}/")
    for p in ablation_results.get("plots", []):
        if p:
            print(f"    {os.path.basename(p)}")
    for p in figure_paths:
        if p:
            print(f"    {os.path.basename(p)}")
    print("=" * 65 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
