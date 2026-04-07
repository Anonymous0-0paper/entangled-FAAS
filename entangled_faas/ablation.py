"""
ablation.py - EFaaS ablation study runner
=========================================
Runs controlled EFaaS-only ablation variants, writes CSV artifacts,
generates plots, and prints a ranked summary table to the console.
"""

from __future__ import annotations

import csv
import os
from statistics import mean
from typing import Any, Callable, Dict, Iterable, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tabulate import tabulate

import config


def _ablation_variants() -> List[Dict[str, Any]]:
    """Return EFaaS ablation variants with parameter overrides."""
    return [
        {
            "variant": "full_efaas",
            "description": "Full EFaaS",
            "alpha": config.alpha,
            "beta": config.beta,
            "gamma": config.gamma,
            "tau_drift": config.tau_drift,
        },
        {
            "variant": "no_session_boost",
            "description": "No session-awareness (alpha=0)",
            "alpha": 0.0,
            "beta": config.beta,
            "gamma": config.gamma,
            "tau_drift": config.tau_drift,
        },
        {
            "variant": "no_drift_urgency",
            "description": "No drift urgency (beta=0)",
            "alpha": config.alpha,
            "beta": 0.0,
            "gamma": config.gamma,
            "tau_drift": config.tau_drift,
        },
        {
            "variant": "no_fair_share",
            "description": "No fair-share weighting (gamma=0)",
            "alpha": config.alpha,
            "beta": config.beta,
            "gamma": 0.0,
            "tau_drift": config.tau_drift,
        },
        {
            "variant": "no_adaptive_terms",
            "description": "No adaptive terms (alpha=beta=0)",
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": config.gamma,
            "tau_drift": config.tau_drift,
        },
        {
            "variant": "tight_drift_window",
            "description": "Tighter drift threshold (tau/2)",
            "alpha": config.alpha,
            "beta": config.beta,
            "gamma": config.gamma,
            "tau_drift": max(config.tau_drift / 2.0, 1.0),
        },
        {
            "variant": "loose_drift_window",
            "description": "Looser drift threshold (2*tau)",
            "alpha": config.alpha,
            "beta": config.beta,
            "gamma": config.gamma,
            "tau_drift": config.tau_drift * 2.0,
        },
    ]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_mean(values: Iterable[float]) -> float:
    vals = list(values)
    return float(mean(vals)) if vals else 0.0


def _write_csv(path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [ablation] Saved CSV -> {path}")


def _save_plots(summary_rows: List[Dict[str, Any]], figures_dir: str, base_name: str) -> List[str]:
    _ensure_dir(figures_dir)
    paths: List[str] = []

    variants = [r["variant"] for r in summary_rows]
    labels = [r["description"] for r in summary_rows]
    ttns = [r["mean_ttns_s"] for r in summary_rows]
    qdc = [r["qdc_pct"] for r in summary_rows]
    conv = [r["mean_convergence_time_s"] for r in summary_rows]
    drift = [r["mean_drift_penalties"] for r in summary_rows]

    x = np.arange(len(variants))

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    axes[0, 0].bar(x, ttns, color="#1f77b4", alpha=0.9)
    axes[0, 0].set_title("Mean TTNS (lower is better)")
    axes[0, 0].set_ylabel("Seconds")

    axes[0, 1].bar(x, qdc, color="#2ca02c", alpha=0.9)
    axes[0, 1].set_title("QDC (higher is better)")
    axes[0, 1].set_ylabel("Percent")

    axes[1, 0].bar(x, conv, color="#ff7f0e", alpha=0.9)
    axes[1, 0].set_title("Convergence Time (lower is better)")
    axes[1, 0].set_ylabel("Seconds")

    axes[1, 1].bar(x, drift, color="#d62728", alpha=0.9)
    axes[1, 1].set_title("Drift Penalties (lower is better)")
    axes[1, 1].set_ylabel("Count")

    for ax in axes.ravel():
        ax.grid(axis="y", alpha=0.25)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)

    fig.tight_layout()
    comparison_path = os.path.join(figures_dir, f"{base_name}_comparison.png")
    fig.savefig(comparison_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    paths.append(comparison_path)
    print(f"  [ablation] Saved plot -> {comparison_path}")

    baseline = next((r for r in summary_rows if r["variant"] == "full_efaas"), None)
    if baseline:
        # Positive values indicate degradation vs full EFaaS.
        delta_ttns = [r["mean_ttns_s"] - baseline["mean_ttns_s"] for r in summary_rows]
        delta_qdc = [baseline["qdc_pct"] - r["qdc_pct"] for r in summary_rows]
        delta_conv = [r["mean_convergence_time_s"] - baseline["mean_convergence_time_s"] for r in summary_rows]
        delta_drift = [r["mean_drift_penalties"] - baseline["mean_drift_penalties"] for r in summary_rows]

        heatmap = np.array([delta_ttns, delta_qdc, delta_conv, delta_drift], dtype=float)

        fig_h, ax_h = plt.subplots(figsize=(12, 4))
        im = ax_h.imshow(heatmap, aspect="auto", cmap="RdYlGn_r")
        ax_h.set_title("Ablation Degradation vs Full EFaaS")
        ax_h.set_yticks(np.arange(4))
        ax_h.set_yticklabels(["Delta TTNS (s)", "QDC loss (pp)", "Delta Conv (s)", "Delta Drift"])
        ax_h.set_xticks(x)
        ax_h.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)

        for i in range(heatmap.shape[0]):
            for j in range(heatmap.shape[1]):
                ax_h.text(j, i, f"{heatmap[i, j]:.2f}", ha="center", va="center", fontsize=7)

        fig_h.colorbar(im, ax=ax_h, shrink=0.75)
        fig_h.tight_layout()
        heatmap_path = os.path.join(figures_dir, f"{base_name}_degradation_heatmap.png")
        fig_h.savefig(heatmap_path, dpi=300, bbox_inches="tight")
        plt.close(fig_h)
        paths.append(heatmap_path)
        print(f"  [ablation] Saved plot -> {heatmap_path}")

    return paths


def run_efaas_ablation(
    run_once: Callable[..., Dict[str, Any]],
    levels: List[str],
    repeats: int,
    output_dir: str,
    figures_dir: str,
) -> Dict[str, Any]:
    """
    Execute EFaaS ablation runs and persist CSV + plots.

    run_once must match main.run_simulation signature for named args:
      mode, seed_offset, alpha, beta, gamma, tau_drift, level, verbose
    """
    print("\n" + "-" * 72)
    print("  EFaaS ABLATION STUDY")
    print("-" * 72)
    print(f"  Levels  : {', '.join(levels)}")
    print(f"  Repeats : {repeats} per level per variant")

    variants = _ablation_variants()
    raw_rows: List[Dict[str, Any]] = []
    total_runs = len(levels) * len(variants) * repeats
    run_idx = 0

    for level_idx, level in enumerate(levels):
        print(f"\n  [ablation] Level: {level}")
        for variant_idx, variant in enumerate(variants):
            print(f"    -> {variant['description']}")
            for rep in range(repeats):
                run_idx += 1
                seed_offset = 10000 + (level_idx * 1000) + (variant_idx * 100) + rep
                summary = run_once(
                    mode=config.MODE_ENTANGLED,
                    seed_offset=seed_offset,
                    alpha=variant["alpha"],
                    beta=variant["beta"],
                    gamma=variant["gamma"],
                    tau_drift=variant["tau_drift"],
                    level=level,
                    verbose=False,
                )
                raw_rows.append(
                    {
                        "level": level,
                        "variant": variant["variant"],
                        "description": variant["description"],
                        "repeat": rep,
                        "seed_offset": seed_offset,
                        "alpha": variant["alpha"],
                        "beta": variant["beta"],
                        "gamma": variant["gamma"],
                        "tau_drift": variant["tau_drift"],
                        "iterations_completed": summary.get("iterations_completed", 0),
                        "mean_ttns_s": summary.get("mean_ttns_s", 0.0),
                        "qdc_pct": summary.get("qdc_pct", 0.0),
                        "convergence_time_s": summary.get("convergence_time_s") or config.SIM_TIME,
                        "converged": int(summary.get("convergence_time_s") is not None),
                        "drift_penalties": summary.get("drift_penalties", 0),
                        "mean_energy_ha": summary.get("mean_energy_ha", 0.0),
                        "mean_vqe_wait_s": summary.get("mean_vqe_wait_s", 0.0),
                    }
                )
                if run_idx % 10 == 0 or run_idx == total_runs:
                    print(f"      progress: {run_idx}/{total_runs} runs")

    summary_rows: List[Dict[str, Any]] = []
    for variant in variants:
        v_name = variant["variant"]
        rows = [r for r in raw_rows if r["variant"] == v_name]
        summary_rows.append(
            {
                "variant": v_name,
                "description": variant["description"],
                "runs": len(rows),
                "mean_ttns_s": round(_safe_mean(r["mean_ttns_s"] for r in rows), 4),
                "qdc_pct": round(_safe_mean(r["qdc_pct"] for r in rows), 4),
                "mean_convergence_time_s": round(_safe_mean(r["convergence_time_s"] for r in rows), 4),
                "convergence_rate_pct": round(_safe_mean(r["converged"] for r in rows) * 100.0, 2),
                "mean_drift_penalties": round(_safe_mean(r["drift_penalties"] for r in rows), 4),
                "mean_vqe_wait_s": round(_safe_mean(r["mean_vqe_wait_s"] for r in rows), 4),
            }
        )

    base_name = config.ABLATION_OUTPUT_BASENAME
    raw_csv_path = os.path.join(output_dir, f"{base_name}_raw.csv")
    summary_csv_path = os.path.join(output_dir, f"{base_name}_summary.csv")

    _write_csv(
        raw_csv_path,
        raw_rows,
        [
            "level",
            "variant",
            "description",
            "repeat",
            "seed_offset",
            "alpha",
            "beta",
            "gamma",
            "tau_drift",
            "iterations_completed",
            "mean_ttns_s",
            "qdc_pct",
            "convergence_time_s",
            "converged",
            "drift_penalties",
            "mean_energy_ha",
            "mean_vqe_wait_s",
        ],
    )
    _write_csv(
        summary_csv_path,
        summary_rows,
        [
            "variant",
            "description",
            "runs",
            "mean_ttns_s",
            "qdc_pct",
            "mean_convergence_time_s",
            "convergence_rate_pct",
            "mean_drift_penalties",
            "mean_vqe_wait_s",
        ],
    )

    plot_paths = _save_plots(summary_rows, figures_dir, base_name)

    ranked = sorted(summary_rows, key=lambda r: (r["mean_ttns_s"], -r["qdc_pct"]))
    table = [
        [
            r["variant"],
            r["description"],
            r["mean_ttns_s"],
            r["qdc_pct"],
            r["mean_convergence_time_s"],
            r["convergence_rate_pct"],
            r["mean_drift_penalties"],
            r["mean_vqe_wait_s"],
        ]
        for r in ranked
    ]

    print("\n  EFaaS Ablation Ranking")
    print(tabulate(
        table,
        headers=[
            "Variant",
            "Description",
            "Mean TTNS (s)",
            "QDC (%)",
            "Mean Conv (s)",
            "Conv Rate (%)",
            "Mean Drift",
            "Mean VQE Wait (s)",
        ],
        tablefmt="github",
    ))

    print("\n  EFaaS ablation artifacts")
    print(f"  - raw CSV     : {raw_csv_path}")
    print(f"  - summary CSV : {summary_csv_path}")
    for p in plot_paths:
        print(f"  - plot        : {p}")
    print("-" * 72 + "\n")

    return {
        "raw_csv": raw_csv_path,
        "summary_csv": summary_csv_path,
        "plots": plot_paths,
        "summary": summary_rows,
    }
