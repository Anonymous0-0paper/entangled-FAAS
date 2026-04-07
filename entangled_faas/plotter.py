"""
plotter.py — Publication-Quality Figures for Entangled-FaaS
============================================================
Updates to save all plots individually with figsize(8,4).
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

_MARKERS = ["o", "s", "^", "D", "v"]
_LINESTYLES = ["-", "--", "-.", ":", (0, (3, 5, 1, 5))]


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

def plot_main_comparison(summaries: List[Dict], output_dir: str) -> List[str]:
    """
    Generate the 6 main comparison figures individually.
    """
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    fig_ttns, ax_ttns = plt.subplots(figsize=(8, 4))
    fig_energy, ax_energy = plt.subplots(figsize=(8, 4))
    fig_qdc, ax_qdc = plt.subplots(figsize=(8, 4))
    fig_cdf, ax_cdf = plt.subplots(figsize=(8, 4))
    fig_drift, ax_drift = plt.subplots(figsize=(8, 4))
    fig_box, ax_box = plt.subplots(figsize=(8, 4))

    legend_handles = []

    for idx, s in enumerate(summaries):
        mode  = s.get("mode", f"mode{idx}")
        style = _mode_style(mode, idx)
        color = style["color"]
        ls    = style["linestyle"]
        lbl   = style["label"]

        ttns_arr   = np.array(s.get("ttns_list",   []))
        energy_arr = np.array(s.get("energy_list", []))
        var_arr    = np.array(s.get("variance_list",[]))
        iters      = np.arange(len(ttns_arr))

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

        if len(ttns_arr) > 0:
            sorted_t = np.sort(ttns_arr)
            cdf      = np.arange(1, len(sorted_t) + 1) / len(sorted_t)
            ax_cdf.step(sorted_t, cdf, color=color, linestyle=ls,
                        linewidth=1.6, label=lbl, where="post")

        drift_iters = [
            r["iteration"] for r in s.get("shot_records_proxy", [])
            if r.get("drift_penalty")
        ]
        dp = s.get("drift_penalties", 0)

        legend_handles.append(Line2D(
            [0], [0], color=color, linestyle=ls,
            linewidth=1.8, label=lbl,
        ))

    ax_ttns.set_xlabel("Iteration", labelpad=4)
    ax_ttns.set_ylabel("TTNS (s)", labelpad=4)
    ax_ttns.set_title("(A)  Time-to-Next-Shot per Iteration")
    ax_ttns.set_yscale("symlog", linthresh=5)
    ax_ttns.yaxis.set_minor_formatter(ticker.NullFormatter())
    _add_panel_label(ax_ttns, "A")

    ax_energy.axhline(
        config.lih_ground_state_energy, color="#555555",
        linestyle=":", linewidth=1.0, label="LiH reference",
    )
    ax_energy.set_xlabel("Iteration", labelpad=4)
    ax_energy.set_ylabel(r"$\langle H \rangle$ (H$_a$)", labelpad=4)
    ax_energy.set_title("(B)  Energy Convergence (± variance)")
    _add_panel_label(ax_energy, "B")

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

    vqe_wait_vals = [s.get("mean_vqe_wait_s", 0) for s in summaries]
    for rect, v_wait in zip(bar, vqe_wait_vals):
        ax_qdc.text(
            rect.get_x() + rect.get_width() / 2, rect.get_height() / 2,
            f"V-Wait:\n{v_wait:.1f}s", ha="center", va="center", fontsize=6.5,
            color="white", fontweight="bold",
        )
    _add_panel_label(ax_qdc, "C")

    ax_cdf.set_xlabel("TTNS (s)", labelpad=4)
    ax_cdf.set_ylabel("Cumulative Probability", labelpad=4)
    ax_cdf.set_title("(D)  TTNS Empirical CDF")
    ax_cdf.set_xlim(left=0)
    ax_cdf.set_ylim(0, 1.05)
    _add_panel_label(ax_cdf, "D")

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
    h1, l1 = ax_drift.get_legend_handles_labels()
    h2, l2 = ax_e2.get_legend_handles_labels()
    ax_drift.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right")
    _add_panel_label(ax_drift, "E")

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

    preempt_vals = [s.get("preemptions", 0) for s in summaries]
    for i, p_val in enumerate(preempt_vals):
         ax_box.text(
              i + 1, ax_box.get_ylim()[0] * 1.5,
              f"{p_val} interrupts", ha="center", va="bottom",
              fontsize=7, color="#d62728" if p_val > 0 else "#888888",
         )
    _add_panel_label(ax_box, "F")

    def _save_fig(fig, name):
        if name != "entangled_faas_main_E_drift":
            fig.legend(
                handles=legend_handles, loc="lower center", ncol=len(summaries),
                fontsize=9, frameon=True, bbox_to_anchor=(0.5, -0.05),
                title="Architecture", title_fontsize=9,
            )
        
        png_path = ""
        for ext in ["pdf", "png"]:
            path = os.path.join(output_dir, f"{name}.{ext}")
            fig.savefig(path, bbox_inches="tight")
            print(f"  [plotter] Saved → {path}")
            if ext == "png":
                png_path = path
        plt.close(fig)
        return png_path

    paths = []
    paths.append(_save_fig(fig_ttns, "entangled_faas_main_A_ttns"))
    paths.append(_save_fig(fig_energy, "entangled_faas_main_B_energy"))
    paths.append(_save_fig(fig_qdc, "entangled_faas_main_C_qdc"))
    paths.append(_save_fig(fig_cdf, "entangled_faas_main_D_cdf"))
    paths.append(_save_fig(fig_drift, "entangled_faas_main_E_drift"))
    paths.append(_save_fig(fig_box, "entangled_faas_main_F_ttns_box"))

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — Sensitivity Analysis (individual plots)
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

def plot_sensitivity(sensitivity_data: Dict, output_dir: str) -> List[str]:
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    params = list(config.SENSITIVITY_GRIDS.keys())
    row_metrics = ["mean_ttns_s", "qdc_pct"]
    row_ylabels = ["Mean TTNS (s)", "QDC (%)"]

    paths = []

    for col_idx, param in enumerate(params):
        results = sensitivity_data.get(param, [])
        if not results:
            continue

        x_vals    = [r[param]          for r in results]
        ttns_vals = [r["mean_ttns_s"]  for r in results]
        qdc_vals  = [r["qdc_pct"]      for r in results]

        color = _PARAM_COLORS.get(param, f"C{col_idx}")

        for row_idx, (metric_key, ylabel) in enumerate(zip(row_metrics, row_ylabels)):
            fig, ax = plt.subplots(figsize=(8, 4))
            y_vals = ttns_vals if row_idx == 0 else qdc_vals

            ax.plot(
                x_vals, y_vals,
                color=color, marker="o", linewidth=2,
                markersize=5, markerfacecolor="white",
                markeredgecolor=color, markeredgewidth=1.5,
            )
            ax.fill_between(x_vals, y_vals, alpha=0.12, color=color)

            if row_idx == 0:
                opt_idx = int(np.argmin(y_vals))
            else:
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
            ax.set_title(f"Sensitivity: {ylabel} vs {_PARAM_LABELS.get(param, param)}", fontsize=10)

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

            letter = chr(ord("A") + row_idx * 4 + col_idx)
            _add_panel_label(ax, letter)

            ax.xaxis.set_major_locator(ticker.MaxNLocator(5))
            ax.yaxis.set_major_locator(ticker.MaxNLocator(5))

            name = f"entangled_faas_sensitivity_{param}_{metric_key}"
            png_path = ""
            for ext in ["pdf", "png"]:
                path = os.path.join(output_dir, f"{name}.{ext}")
                fig.savefig(path, bbox_inches="tight")
                print(f"  [plotter] Saved → {path}")
                if ext == "png":
                    png_path = path
            plt.close(fig)
            paths.append(png_path)

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — Iteration throughput & convergence race chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_convergence_race(summaries: List[Dict], output_dir: str) -> List[str]:
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    fig_energy, ax_energy = plt.subplots(figsize=(8, 4))
    fig_iter, ax_iter = plt.subplots(figsize=(8, 4))

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

        ax_energy.plot(
            sim_times, _smoothed(energy_arr.tolist(), 5),
            color=color, linestyle=ls, linewidth=1.7, label=lbl,
        )

        ax_iter.step(
            sim_times, np.arange(1, n_iters + 1),
            color=color, linestyle=ls, linewidth=1.7, label=lbl, where="post",
        )

        conv_t = s.get("convergence_time_s")
        if conv_t is not None:
            ax_energy.axvline(conv_t, color=color, linestyle=":", linewidth=1.0, alpha=0.7)
            ax_iter.axvline(conv_t, color=color, linestyle=":", linewidth=1.0, alpha=0.7)

    ax_energy.axhline(
        config.lih_ground_state_energy, color="#555555",
        linestyle=":", linewidth=1.0, label="LiH reference",
    )
    ax_energy.set_xlabel("Simulated Time (s)")
    ax_energy.set_ylabel(r"$\langle H \rangle$ (H$_a$)")
    ax_energy.set_title("(A)  Energy Convergence Race")
    ax_energy.legend(fontsize=7.5)
    _add_panel_label(ax_energy, "A")

    ax_iter.set_xlabel("Simulated Time (s)")
    ax_iter.set_ylabel("Cumulative Iterations")
    ax_iter.set_title("(B)  Iteration Throughput over Time")
    ax_iter.legend(fontsize=7.5)
    _add_panel_label(ax_iter, "B")

    paths = []
    
    png_path_e = ""
    for ext in ["pdf", "png"]:
        path = os.path.join(output_dir, f"entangled_faas_convergence_race_A_energy.{ext}")
        fig_energy.savefig(path, bbox_inches="tight")
        print(f"  [plotter] Saved → {path}")
        if ext == "png":
            png_path_e = path
    plt.close(fig_energy)
    paths.append(png_path_e)

    png_path_i = ""
    for ext in ["pdf", "png"]:
        path = os.path.join(output_dir, f"entangled_faas_convergence_race_B_iters.{ext}")
        fig_iter.savefig(path, bbox_inches="tight")
        print(f"  [plotter] Saved → {path}")
        if ext == "png":
            png_path_i = path
    plt.close(fig_iter)
    paths.append(png_path_i)
    
    return paths

def plot_enhanced_metrics(summaries: List[Dict], output_dir: str) -> List[str]:
    """Plot 5 additional evaluation metrics as bar charts."""
    _set_pub_style()
    
    metrics = [
        ("mean_queue_wait_s", "Avg Queue Wait (s)", "G"),
        ("calib_ratio_pct", "Calibration Ratio (%)", "H"),
        ("classical_util_pct", "Classical Utilization (%)", "I"),
        ("cache_hit_rate_pct", "Cache Hit Rate (%)", "J"),
        ("reconcile_failure_rate_pct", "Reconcile Failure Rate (%)", "K"),
    ]
    
    paths = []
    for key, title, panel in metrics:
        fig, ax = plt.subplots(figsize=(8, 4))
        
        labels = [config.MODE_LABELS.get(s["mode"], s["mode"]) for s in summaries]
        values = [s.get(key, 0) for s in summaries]
        colors = [config.MODE_COLORS.get(s["mode"], "gray") for s in summaries]
        
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor="#444444")
        
        # Add values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=8)

        ax.set_title(f"({panel})  {title}")
        ax.set_ylabel(title)
        _add_panel_label(ax, panel)
        
        png_path = ""
        for ext in ["pdf", "png"]:
            path = os.path.join(output_dir, f"entangled_faas_enhanced_{panel}_{key}.{ext}")
            fig.savefig(path)
            if ext == "png":
                png_path = path
        plt.close(fig)
        paths.append(png_path)
        
    return paths


def plot_circuit_and_average(all_summaries_by_level: Dict[str, List[Dict]], output_dir: str) -> List[str]:
    """Plot per-circuit and average metrics, including EFaaS improvements."""
    _set_pub_style()
    os.makedirs(output_dir, exist_ok=True)

    levels = list(all_summaries_by_level.keys())
    level_tags = [lvl.split(" ")[0] for lvl in levels]
    group_labels = level_tags + ["Average"]
    modes = config.ALL_MODES
    mode_labels = [config.MODE_LABELS[m] for m in modes]
    mode_colors = [config.MODE_COLORS[m] for m in modes]

    per_mode_ttns = {m: [] for m in modes}
    per_mode_qdc = {m: [] for m in modes}

    for level in levels:
        level_summaries = all_summaries_by_level.get(level, [])
        by_mode = {s["mode"]: s for s in level_summaries}
        for m in modes:
            per_mode_ttns[m].append(by_mode.get(m, {}).get("mean_ttns_s", 0.0))
            per_mode_qdc[m].append(by_mode.get(m, {}).get("qdc_pct", 0.0))

    for m in modes:
        per_mode_ttns[m].append(float(np.mean(per_mode_ttns[m])) if per_mode_ttns[m] else 0.0)
        per_mode_qdc[m].append(float(np.mean(per_mode_qdc[m])) if per_mode_qdc[m] else 0.0)

    x = np.arange(len(group_labels))
    width = 0.14
    paths = []

    # Plot 1: Mean TTNS per circuit + average
    fig_ttns, ax_ttns = plt.subplots(figsize=(9, 4))
    for i, m in enumerate(modes):
        offset = (i - (len(modes) - 1) / 2) * width
        ax_ttns.bar(x + offset, per_mode_ttns[m], width=width,
                    color=mode_colors[i], alpha=0.85, label=mode_labels[i])
    ax_ttns.set_xticks(x)
    ax_ttns.set_xticklabels(group_labels)
    ax_ttns.set_ylabel("Mean TTNS (s)")
    ax_ttns.set_title("Per-Circuit and Average TTNS")
    ax_ttns.legend(ncol=3, fontsize=7)
    _add_panel_label(ax_ttns, "L")

    png_ttns = ""
    for ext in ["pdf", "png"]:
        p = os.path.join(output_dir, f"entangled_faas_circuit_avg_L_ttns.{ext}")
        fig_ttns.savefig(p, bbox_inches="tight")
        print(f"  [plotter] Saved → {p}")
        if ext == "png":
            png_ttns = p
    plt.close(fig_ttns)
    paths.append(png_ttns)

    # Plot 2: QDC per circuit + average
    fig_qdc, ax_qdc = plt.subplots(figsize=(9, 4))
    for i, m in enumerate(modes):
        offset = (i - (len(modes) - 1) / 2) * width
        ax_qdc.bar(x + offset, per_mode_qdc[m], width=width,
                   color=mode_colors[i], alpha=0.85, label=mode_labels[i])
    ax_qdc.set_xticks(x)
    ax_qdc.set_xticklabels(group_labels)
    ax_qdc.set_ylabel("QDC (%)")
    ax_qdc.set_title("Per-Circuit and Average QDC")
    ax_qdc.legend(ncol=3, fontsize=7)
    _add_panel_label(ax_qdc, "M")

    png_qdc = ""
    for ext in ["pdf", "png"]:
        p = os.path.join(output_dir, f"entangled_faas_circuit_avg_M_qdc.{ext}")
        fig_qdc.savefig(p, bbox_inches="tight")
        print(f"  [plotter] Saved → {p}")
        if ext == "png":
            png_qdc = p
    plt.close(fig_qdc)
    paths.append(png_qdc)

    # Plot 3: EFaaS improvements per circuit + average (TTNS reduction)
    fig_imp_ttns, ax_imp_ttns = plt.subplots(figsize=(9, 4))
    efaas_mode = config.MODE_ENTANGLED
    baseline_modes = [m for m in modes if m != efaas_mode]
    for i, bm in enumerate(baseline_modes):
        vals = []
        for level in levels:
            level_summaries = {s["mode"]: s for s in all_summaries_by_level.get(level, [])}
            base = level_summaries.get(bm, {})
            ef = level_summaries.get(efaas_mode, {})
            b_ttns = base.get("mean_ttns_s", 0.0)
            e_ttns = ef.get("mean_ttns_s", 0.0)
            red = ((b_ttns - e_ttns) / b_ttns * 100.0) if b_ttns > 0 else 0.0
            vals.append(red)
        vals.append(float(np.mean(vals)) if vals else 0.0)
        ax_imp_ttns.plot(group_labels, vals,
                         marker=_MARKERS[i % len(_MARKERS)],
                         linestyle=_LINESTYLES[i % len(_LINESTYLES)],
                         color=config.MODE_COLORS[bm],
                         linewidth=1.8,
                         label=f"EFaaS vs {config.MODE_LABELS[bm]}")
    ax_imp_ttns.axhline(0.0, color="#666666", linestyle=":", linewidth=1.0)
    ax_imp_ttns.set_ylabel("TTNS Reduction (%)")
    ax_imp_ttns.set_title("EFaaS Improvement by Circuit and on Average")
    ax_imp_ttns.legend(fontsize=7)
    _add_panel_label(ax_imp_ttns, "N")

    png_imp = ""
    for ext in ["pdf", "png"]:
        p = os.path.join(output_dir, f"entangled_faas_circuit_avg_N_improvement_ttns.{ext}")
        fig_imp_ttns.savefig(p, bbox_inches="tight")
        print(f"  [plotter] Saved → {p}")
        if ext == "png":
            png_imp = p
    plt.close(fig_imp_ttns)
    paths.append(png_imp)

    return paths

# ─────────────────────────────────────────────────────────────────────────────
# Master call
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_plots(
    summaries:        List[Dict],
    sensitivity_data: Dict,
    output_dir:       str = config.FIGURES_DIR,
    all_summaries_by_level: Optional[Dict[str, List[Dict]]] = None,
) -> List[str]:
    """
    Generate all publication figures. Returns list of saved PNG paths.
    """
    print("\n" + "─" * 60)
    print("  PLOTTER — Generating publication figures")
    print("─" * 60)
    paths = []
    paths.extend(plot_main_comparison(summaries, output_dir))
    paths.extend(plot_sensitivity(sensitivity_data, output_dir))
    paths.extend(plot_convergence_race(summaries, output_dir))
    paths.extend(plot_enhanced_metrics(summaries, output_dir))
    if all_summaries_by_level:
        paths.extend(plot_circuit_and_average(all_summaries_by_level, output_dir))
    print("─" * 60)
    return paths
