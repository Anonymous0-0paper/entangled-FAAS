"""
plotter.py — Publication-Quality Figures for Entangled-FaaS
============================================================
Generates a multi-panel comparison figure and a sensitivity analysis
figure, both in publication (IEEE/Nature) style.

Figure 1: entangled_faas_main.pdf  (6 panels)
  A. TTNS over iterations — all 4 architectures
  B. Energy convergence with variance shading — all 4
  C. QDC bar chart — all 4
  D. TTNS empirical CDF — all 4
  E. Drift penalties vs iteration — all 4 (stacked bar)
  F. Mean TTNS box-plot (statistical summary) — all 4

Figure 2: entangled_faas_sensitivity.pdf  (2×4 grid)
  Row 1: Mean TTNS vs each of the 4 hyperparameters
  Row 2: QDC      vs each of the 4 hyperparameters
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")   # headless rendering
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
from matplotlib import rcParams

import config


# ─────────────────────────────────────────────────────────────────────────────
# Publication style setup
# ─────────────────────────────────────────────────────────────────────────────

def _set_pub_style() -> None:
    """Configure Matplotlib for IEEE/Nature publication aesthetics."""
    rcParams.update({
        # Font
        "font.family":          "serif",
        "font.serif":           ["DejaVu Serif", "Times New Roman", "Georgia"],
        "font.size":            9,
        "axes.titlesize":       10,
        "axes.labelsize":       9,
        "xtick.labelsize":      8,
        "ytick.labelsize":      8,
        "legend.fontsize":      8,
        "legend.framealpha":    0.9,
        "legend.edgecolor":     "#cccccc",
        # Lines & markers
        "lines.linewidth":      1.5,
        "lines.markersize":     4,
        # Axes
        "axes.spines.top":      False,
        "axes.spines.right":    False,
        "axes.grid":            True,
        "axes.grid.which":      "both",
        "grid.alpha":           0.3,
        "grid.linewidth":       0.5,
        "grid.color":           "#888888",
        "axes.facecolor":       "#fafafa",
        # Figure
        "figure.dpi":           150,
        "savefig.dpi":          300,
        "savefig.bbox":         "tight",
        "savefig.pad_inches":   0.05,
        # Math
        "mathtext.fontset":     "dejavuserif",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_MARKERS = ["o", "s", "^", "D"]
_LINESTYLES = ["-", "--", "-.", ":"]


def _mode_style(mode: str, idx: int) -> Dict:
    return {
        "color":     config.MODE_COLORS.get(mode, f"C{idx}"),
        "linestyle": _LINESTYLES[idx % len(_LINESTYLES)],
        "marker":    _MARKERS[idx % len(_MARKERS)],
        "label":     config.MODE_LABELS.get(mode, mode),
    }


def _smoothed(data: List[float], w: int = 5) -> np.ndarray:
    """Simple rolling average for smoother convergence curves."""
    arr  = np.array(data, dtype=float)
    if len(arr) < w:
        return arr
    kernel = np.ones(w) / w
    pad    = np.pad(arr, (w // 2, w // 2), mode="edge")
    return np.convolve(pad, kernel, mode="valid")[: len(arr)]


def _add_panel_label(ax, label: str) -> None:
    """Add bold panel-letter label (IEEE style) inside top-left of axis."""
    ax.text(
        0.02, 0.97, label,
        transform=ax.transAxes,
        fontsize=10, fontweight="bold",
        verticalalignment="top",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — Main Comparison (6 panels)
# ─────────────────────────────────────────────────────────────────────────────

def plot_main_comparison(summaries: List[Dict], output_dir: str) -> str:
    """
    Generate the 6-panel main comparison figure.

    Parameters
    ----------
    summaries  : list of summary dicts from MetricsTracker.summary() — one per mode
    output_dir : directory where PDF + PNG are saved

    Returns
    -------
    Path to saved PNG.
    """
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    fig = plt.figure(figsize=(14, 9))
    fig.suptitle(
        "Entangled-FaaS: Comparative Performance Evaluation of Hybrid "
        "Quantum-Classical Scheduling Architectures",
        fontsize=11, fontweight="bold", y=0.995,
    )

    # 3-column × 2-row grid with custom height ratios
    gs = fig.add_gridspec(
        2, 3, hspace=0.42, wspace=0.38,
        left=0.07, right=0.97, top=0.95, bottom=0.08,
    )

    ax_ttns  = fig.add_subplot(gs[0, 0])   # A: TTNS over iterations
    ax_energy= fig.add_subplot(gs[0, 1])   # B: Energy convergence
    ax_qdc   = fig.add_subplot(gs[0, 2])   # C: QDC bar chart
    ax_cdf   = fig.add_subplot(gs[1, 0])   # D: TTNS CDF
    ax_drift = fig.add_subplot(gs[1, 1])   # E: Drift penalties
    ax_box   = fig.add_subplot(gs[1, 2])   # F: TTNS box-plot

    # ── Legend proxy handles (shared across panels) ────────────────────────
    legend_handles = []

    for idx, s in enumerate(summaries):
        mode  = s.get("mode", f"mode{idx}")
        style = _mode_style(mode, idx)
        color = style["color"]
        ls    = style["linestyle"]
        mk    = style["marker"]
        lbl   = style["label"]

        ttns_arr   = np.array(s.get("ttns_list",   []))
        energy_arr = np.array(s.get("energy_list", []))
        var_arr    = np.array(s.get("variance_list",[]))
        iters      = np.arange(len(ttns_arr))

        # ── A: TTNS over iterations ────────────────────────────────────────
        if len(ttns_arr) > 0:
            ax_ttns.plot(
                iters, _smoothed(ttns_arr.tolist(), 7),
                color=color, linestyle=ls,
                linewidth=1.6, label=lbl, alpha=0.9,
            )
            ax_ttns.fill_between(
                iters, ttns_arr * 0.9, ttns_arr * 1.1,
                color=color, alpha=0.1,
            )

        # ── B: Energy convergence with variance band ───────────────────────
        if len(energy_arr) > 0:
            e_smooth  = _smoothed(energy_arr.tolist(), 7)
            std_proxy = np.sqrt(np.maximum(var_arr, 0))
            ax_energy.plot(
                iters, e_smooth,
                color=color, linestyle=ls, linewidth=1.6, label=lbl,
            )
            ax_energy.fill_between(
                iters,
                e_smooth - std_proxy,
                e_smooth + std_proxy,
                color=color, alpha=0.12,
            )

        # ── D: TTNS CDF ────────────────────────────────────────────────────
        if len(ttns_arr) > 0:
            sorted_t = np.sort(ttns_arr)
            cdf      = np.arange(1, len(sorted_t) + 1) / len(sorted_t)
            ax_cdf.step(sorted_t, cdf, color=color, linestyle=ls,
                        linewidth=1.6, label=lbl, where="post")

        # ── E: Drift penalty marks ─────────────────────────────────────────
        drift_iters = [
            r["iteration"] for r in s.get("shot_records_proxy", [])
            if r.get("drift_penalty")
        ]
        # Use drift_penalties count as bar proxy since records may be absent
        dp = s.get("drift_penalties", 0)
        # (bar drawn in QDC section below per-mode)

        # Legend proxy
        legend_handles.append(Line2D(
            [0], [0], color=color, linestyle=ls,
            linewidth=1.8, label=lbl,
        ))

    # ── A axis decoration ──────────────────────────────────────────────────
    ax_ttns.set_xlabel("Iteration", labelpad=4)
    ax_ttns.set_ylabel("TTNS (s)", labelpad=4)
    ax_ttns.set_title("(A)  Time-to-Next-Shot per Iteration")
    ax_ttns.set_yscale("symlog", linthresh=5)
    ax_ttns.yaxis.set_minor_formatter(ticker.NullFormatter())
    _add_panel_label(ax_ttns, "A")

    # ── B axis decoration ──────────────────────────────────────────────────
    ax_energy.axhline(
        config.lih_ground_state_energy, color="#555555",
        linestyle=":", linewidth=1.0, label="LiH reference",
    )
    ax_energy.set_xlabel("Iteration", labelpad=4)
    ax_energy.set_ylabel(r"$\langle H \rangle$ (H$_a$)", labelpad=4)
    ax_energy.set_title("(B)  Energy Convergence (± variance)")
    _add_panel_label(ax_energy, "B")

    # ── C: QDC bar chart ───────────────────────────────────────────────────
    labels_bar  = [config.MODE_LABELS.get(s["mode"], s["mode"]) for s in summaries]
    colors_bar  = [config.MODE_COLORS.get(s["mode"], "grey")    for s in summaries]
    qdc_vals    = [s.get("qdc_pct", 0)                          for s in summaries]
    drift_vals  = [s.get("drift_penalties", 0)                  for s in summaries]

    x   = np.arange(len(labels_bar))
    bar = ax_qdc.bar(x, qdc_vals, color=colors_bar, edgecolor="white",
                     linewidth=0.8, alpha=0.88, width=0.6)
    for rect, val in zip(bar, qdc_vals):
        ax_qdc.text(
            rect.get_x() + rect.get_width() / 2, val + 0.3,
            f"{val:.1f}%", ha="center", va="bottom", fontsize=7.5,
            fontweight="bold",
        )
    ax_qdc.set_xticks(x)
    ax_qdc.set_xticklabels(labels_bar, fontsize=8)
    ax_qdc.set_ylabel("Quantum Duty Cycle (%)", labelpad=4)
    ax_qdc.set_title("(C)  Quantum Duty Cycle (QDC)")
    ax_qdc.set_ylim(0, max(qdc_vals) * 1.25 if qdc_vals else 1)
    _add_panel_label(ax_qdc, "C")

    # ── D axis decoration ─────────────────────────────────────────────────
    ax_cdf.set_xlabel("TTNS (s)", labelpad=4)
    ax_cdf.set_ylabel("Cumulative Probability", labelpad=4)
    ax_cdf.set_title("(D)  TTNS Empirical CDF")
    ax_cdf.set_xlim(left=0)
    ax_cdf.set_ylim(0, 1.05)
    _add_panel_label(ax_cdf, "D")

    # ── E: Drift penalty count + convergence time dual-axis bar ───────────
    conv_vals   = [
        s.get("convergence_time_s") or config.SIM_TIME for s in summaries
    ]
    x2 = np.arange(len(labels_bar))
    width = 0.35
    ax_e2 = ax_drift.twinx()
    bars1 = ax_drift.bar(
        x2 - width / 2, drift_vals, width=width,
        color=colors_bar, alpha=0.7, edgecolor="white",
        linewidth=0.8, label="Drift Penalties",
    )
    bars2 = ax_e2.bar(
        x2 + width / 2, conv_vals, width=width,
        color=colors_bar, alpha=0.35, edgecolor="grey",
        linewidth=0.8, hatch="//", label="Conv. Time (s)",
    )
    ax_drift.set_xticks(x2)
    ax_drift.set_xticklabels(labels_bar, fontsize=8)
    ax_drift.set_ylabel("Drift Penalty Events", labelpad=4)
    ax_e2.set_ylabel("Convergence Time (s)", labelpad=4, color="#444444")
    ax_drift.set_title("(E)  Drift Penalties & Convergence Time")
    # Legends for dual axis
    h1, l1 = ax_drift.get_legend_handles_labels()
    h2, l2 = ax_e2.get_legend_handles_labels()
    ax_drift.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right")
    _add_panel_label(ax_drift, "E")

    # ── F: TTNS box-plot ───────────────────────────────────────────────────
    bp_data  = [
        s.get("ttns_list", [0]) for s in summaries
    ]
    bp = ax_box.boxplot(
        bp_data,
        patch_artist=True,
        notch=True,
        vert=True,
        widths=0.5,
        medianprops=dict(color="black", linewidth=2),
        flierprops=dict(marker=".", markersize=2, alpha=0.4),
    )
    for patch, color in zip(bp["boxes"], colors_bar):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    for whisker in bp["whiskers"]:
        whisker.set_linewidth(1.0)
    for cap in bp["caps"]:
        cap.set_linewidth(1.0)

    ax_box.set_xticks(np.arange(1, len(labels_bar) + 1))
    ax_box.set_xticklabels(labels_bar, fontsize=8)
    ax_box.set_ylabel("TTNS (s)", labelpad=4)
    ax_box.set_title("(F)  TTNS Statistical Distribution")
    ax_box.set_yscale("symlog", linthresh=5)
    _add_panel_label(ax_box, "F")

    # ── Shared legend (below figure) ──────────────────────────────────────
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(summaries),
        fontsize=9,
        frameon=True,
        bbox_to_anchor=(0.5, 0.005),
        title="Architecture",
        title_fontsize=9,
    )

    # ── Save ──────────────────────────────────────────────────────────────
    for ext in ["pdf", "png"]:
        path = os.path.join(output_dir, f"entangled_faas_main.{ext}")
        fig.savefig(path)
        print(f"  [plotter] Saved → {path}")
    plt.close(fig)
    return os.path.join(output_dir, "entangled_faas_main.png")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — Sensitivity Analysis (2 × 4 grid)
# ─────────────────────────────────────────────────────────────────────────────

_PARAM_LABELS = {
    "alpha":     r"Session Weight $\alpha$",
    "beta":      r"Urgency Weight $\beta$",
    "gamma":     r"Fair-Share Weight $\gamma$",
    "tau_drift": r"Drift Threshold $\tau_{drift}$ (s)",
}
_PARAM_COLORS = {
    "alpha":     "#d62728",
    "beta":      "#1f77b4",
    "gamma":     "#ff7f0e",
    "tau_drift": "#9467bd",
}


def plot_sensitivity(sensitivity_data: Dict, output_dir: str) -> str:
    """
    Generate the 2×4 sensitivity analysis figure.

    Parameters
    ----------
    sensitivity_data : dict returned by sensitivity.run_sweep()
                       keys = param names, values = list of result dicts
    output_dir       : save directory
    """
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    params = list(config.SENSITIVITY_GRIDS.keys())   # alpha, beta, gamma, tau_drift

    fig, axes = plt.subplots(
        2, 4,
        figsize=(14, 6),
        gridspec_kw={"hspace": 0.50, "wspace": 0.40},
    )
    fig.suptitle(
        "Entangled-FaaS: Hyperparameter Sensitivity Analysis",
        fontsize=11, fontweight="bold",
    )

    row_labels = [
        r"Mean TTNS (s)  ↓ better",
        r"Quantum Duty Cycle (%)  ↑ better",
    ]
    row_metrics = ["mean_ttns_s", "qdc_pct"]
    row_ylabels = ["Mean TTNS (s)", "QDC (%)"]

    for col_idx, param in enumerate(params):
        results = sensitivity_data.get(param, [])
        if not results:
            continue

        x_vals    = [r[param]          for r in results]
        ttns_vals = [r["mean_ttns_s"]  for r in results]
        qdc_vals  = [r["qdc_pct"]      for r in results]
        conv_vals = [r["convergence_time_s"] or config.SIM_TIME for r in results]
        iter_vals = [r["iterations_completed"] for r in results]

        color = _PARAM_COLORS.get(param, f"C{col_idx}")

        for row_idx, (metric_key, ylabel) in enumerate(
            zip(row_metrics, row_ylabels)
        ):
            ax = axes[row_idx, col_idx]
            y_vals = ttns_vals if row_idx == 0 else qdc_vals

            ax.plot(
                x_vals, y_vals,
                color=color, marker="o", linewidth=2,
                markersize=5, markerfacecolor="white",
                markeredgecolor=color, markeredgewidth=1.5,
            )
            ax.fill_between(x_vals, y_vals, alpha=0.12, color=color)

            # Highlight optimal point
            if row_idx == 0:   # minimise TTNS
                opt_idx = int(np.argmin(y_vals))
            else:              # maximise QDC
                opt_idx = int(np.argmax(y_vals))

            ax.scatter(
                [x_vals[opt_idx]], [y_vals[opt_idx]],
                color=color, s=60, zorder=5, linewidth=0,
            )
            ax.annotate(
                f"  opt={x_vals[opt_idx]}",
                (x_vals[opt_idx], y_vals[opt_idx]),
                fontsize=6.5, color=color,
                xytext=(4, 0), textcoords="offset points",
            )

            ax.set_xlabel(_PARAM_LABELS.get(param, param), labelpad=3, fontsize=8)
            ax.set_ylabel(ylabel, labelpad=3, fontsize=8)

            # Default value marker (vertical dashed line)
            default_val = {
                "alpha": config.alpha, "beta": config.beta,
                "gamma": config.gamma, "tau_drift": config.tau_drift,
            }[param]
            ax.axvline(
                default_val, color="#555555",
                linestyle="--", linewidth=0.9, alpha=0.7,
                label=f"default={default_val}",
            )
            ax.legend(fontsize=6.5, loc="best", handlelength=1.2)

            # Panel letter: A–H  (row0: A-D, row1: E-H)
            letter = chr(ord("A") + row_idx * 4 + col_idx)
            _add_panel_label(ax, letter)

            # Tick cleanup
            ax.xaxis.set_major_locator(ticker.MaxNLocator(5))
            ax.yaxis.set_major_locator(ticker.MaxNLocator(5))

    # Row-level y-axis labels
    for row_idx, label in enumerate(row_labels):
        fig.text(0.005, 0.72 - row_idx * 0.45, label,
                 va="center", ha="left", rotation=90, fontsize=8.5,
                 fontweight="bold", color="#333333")

    for ext in ["pdf", "png"]:
        path = os.path.join(output_dir, f"entangled_faas_sensitivity.{ext}")
        fig.savefig(path)
        print(f"  [plotter] Saved → {path}")
    plt.close(fig)
    return os.path.join(output_dir, "entangled_faas_sensitivity.png")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — Iteration throughput & convergence race chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_convergence_race(summaries: List[Dict], output_dir: str) -> str:
    """
    Dual-panel figure:
      Left : Energy vs simulated wall-clock time (race to convergence)
      Right: Cumulative iterations completed over simulated time
    """
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(10, 4.2),
        gridspec_kw={"wspace": 0.35},
    )
    fig.suptitle(
        "Entangled-FaaS: Convergence Race and Iteration Throughput",
        fontsize=11, fontweight="bold",
    )

    for idx, s in enumerate(summaries):
        mode  = s.get("mode", f"m{idx}")
        style = _mode_style(mode, idx)
        color = style["color"]
        ls    = style["linestyle"]
        lbl   = style["label"]

        sim_times  = np.array(s.get("sim_times",   []))
        energy_arr = np.array(s.get("energy_list", []))
        n_iters    = len(sim_times)

        if n_iters == 0:
            continue

        # Left: energy vs sim time
        ax_left.plot(
            sim_times, _smoothed(energy_arr.tolist(), 5),
            color=color, linestyle=ls, linewidth=1.7, label=lbl,
        )

        # Right: cumulative iteration count over time
        ax_right.step(
            sim_times, np.arange(1, n_iters + 1),
            color=color, linestyle=ls, linewidth=1.7, label=lbl, where="post",
        )

        # Mark convergence time
        conv_t = s.get("convergence_time_s")
        if conv_t is not None:
            ax_left.axvline(conv_t, color=color, linestyle=":", linewidth=1.0, alpha=0.7)
            ax_right.axvline(conv_t, color=color, linestyle=":", linewidth=1.0, alpha=0.7)

    ax_left.axhline(
        config.lih_ground_state_energy, color="#555555",
        linestyle=":", linewidth=1.0, label="LiH reference",
    )
    ax_left.set_xlabel("Simulated Time (s)")
    ax_left.set_ylabel(r"$\langle H \rangle$ (H$_a$)")
    ax_left.set_title("(A)  Energy Convergence Race")
    ax_left.legend(fontsize=7.5)
    _add_panel_label(ax_left, "A")

    ax_right.set_xlabel("Simulated Time (s)")
    ax_right.set_ylabel("Cumulative Iterations")
    ax_right.set_title("(B)  Iteration Throughput over Time")
    ax_right.legend(fontsize=7.5)
    _add_panel_label(ax_right, "B")

    for ext in ["pdf", "png"]:
        path = os.path.join(output_dir, f"entangled_faas_convergence_race.{ext}")
        fig.savefig(path)
        print(f"  [plotter] Saved → {path}")
    plt.close(fig)
    return os.path.join(output_dir, "entangled_faas_convergence_race.png")


# ─────────────────────────────────────────────────────────────────────────────
# Master call
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_plots(
    summaries:        List[Dict],
    sensitivity_data: Dict,
    output_dir:       str = config.FIGURES_DIR,
) -> List[str]:
    """
    Generate all publication figures. Returns list of saved PNG paths.
    """
    print("\n" + "─" * 60)
    print("  PLOTTER — Generating publication figures")
    print("─" * 60)
    paths = []
    paths.append(plot_main_comparison(summaries, output_dir))
    paths.append(plot_sensitivity(sensitivity_data, output_dir))
    paths.append(plot_convergence_race(summaries, output_dir))
    print("─" * 60)
    return paths
