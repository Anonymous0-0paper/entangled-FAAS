"""
circuit_plotter.py — IEEE Publication-Quality Circuit Benchmark Visualizations
===============================================================================
Reads per-circuit JSON results from output/ and generates publication-ready
figures AND rendered table figures organized by complexity band
(simple / medium / complex).

Rules applied to every figure
──────────────────────────────
 • figsize  — single-panel (8, 5); multi-panel scales by column count
 • No axes background color (white)
 • No titles on axes — title text becomes the saved filename
 • ylim — auto data-driven + 10 % headroom above the max

Usage:
    python circuit_plotter.py [--output-dir output] [--figures-dir figures/circuits_ieee]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib import rcParams
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap

# ─────────────────────────────────────────────────────────────────────────────
# Circuit catalog
# ─────────────────────────────────────────────────────────────────────────────

CATALOG: Dict[str, List[str]] = {
    "simple": [
        "std_efficientsu2_2q_r1_linear",
        "std_realamplitudes_2q_r2_linear",
        "std_twolocal_3q_r1_cx_linear",
        "std_efficientsu2_3q_r2_linear",
        "std_realamplitudes_3q_r3_full",
        "std_twolocal_4q_r2_cz_linear",
        "std_efficientsu2_4q_r3_full",
        "std_realamplitudes_4q_r4_linear",
        "std_twolocal_5q_r3_cx_linear",
        "std_efficientsu2_5q_r4_full",
    ],
    "medium": [
        "std_efficientsu2_6q_r2_linear",
        "std_realamplitudes_6q_r3_linear",
        "std_twolocal_6q_r3_cx_linear",
        "std_efficientsu2_7q_r3_full",
        "std_realamplitudes_7q_r4_linear",
        "std_twolocal_8q_r3_cz_full",
        "std_efficientsu2_8q_r4_full",
        "std_realamplitudes_9q_r4_linear",
        "std_twolocal_10q_r4_cx_linear",
        "std_efficientsu2_10q_r5_full",
    ],
    "complex": [
        "std_efficientsu2_10q_r6_linear",
        "std_realamplitudes_10q_r6_full",
        "std_twolocal_11q_r7_cx_linear",
        "std_efficientsu2_11q_r7_full",
        "std_realamplitudes_12q_r5_full",
        "std_twolocal_12q_r6_cz_full",
        "std_efficientsu2_13q_r6_full",
        "std_realamplitudes_13q_r7_full",
        "std_twolocal_14q_r7_cx_full",
        "std_efficientsu2_14q_r8_full",
        "std_realamplitudes_16q_r5_linear",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Mode definitions
# ─────────────────────────────────────────────────────────────────────────────

MODES: Dict[str, str] = {
    "sbq":   "Standard Batch-Queue (SBQ)",
    "pf":    "Pure FaaS (PF)",
    "sr":    "Static Reservation (SR)",
    "pq":    "Pilot-Quantum (PQ)",
    "efaas": "Entangled-FaaS",
}
BASELINES = [m for m in MODES if m != "efaas"]

MODE_LABELS: Dict[str, str] = {
    "sbq": "SBQ", "pf": "PF", "sr": "SR", "pq": "PQ", "efaas": "EFaaS",
}
MODE_COLORS: Dict[str, str] = {
    "sbq": "#d62728", "pf": "#ff7f0e", "sr": "#1f77b4",
    "pq": "#9467bd",  "efaas": "#2ca02c",
}
MODE_MARKERS: Dict[str, str] = {
    "sbq": "s", "pf": "^", "sr": "D", "pq": "v", "efaas": "o",
}
MODE_HATCHES: Dict[str, str] = {
    "sbq": "//", "pf": "\\\\", "sr": "xx", "pq": "..", "efaas": "",
}

BAND_COLORS: Dict[str, str] = {
    "simple": "#4878cf", "medium": "#e67e22", "complex": "#8e44ad",
}
BAND_LABELS: Dict[str, str] = {
    "simple":  "Simple (2–5 qubits)",
    "medium":  "Medium (6–10 qubits)",
    "complex": "Complex (10–16 qubits)",
}

LIH_REFERENCE = -7.882

# ─────────────────────────────────────────────────────────────────────────────
# Style constants
# ─────────────────────────────────────────────────────────────────────────────

_W1, _H1 = 8, 4          # single-panel canonical size
_MARGIN   = 0.10          # 10 % ylim headroom

_HDR_BG   = "#1a2744"; _HDR_FG = "white"
_ROW_A_BG = "#f0f4fb";  _ROW_B_BG = "white"
_BEST_BG  = "#c8f0d0";  _WORST_BG = "#fde8e8"
_EFAAS_BG = "#d4edda";  _EFAAS_FG = "#155724"
_BAND_BG  = {"simple": "#dce8f8", "medium": "#fce8d4", "complex": "#ede0f8"}


# ─────────────────────────────────────────────────────────────────────────────
# Publication style
# ─────────────────────────────────────────────────────────────────────────────

def _set_pub_style() -> None:
    rcParams.update({
        "font.family":        "serif",
        "font.serif":         ["DejaVu Serif", "Times New Roman", "Georgia"],
        "font.size":          18,
        "axes.titlesize":     18,
        "axes.labelsize":     18,
        "xtick.labelsize":    20,
        "ytick.labelsize":    18,
        "legend.fontsize":    18,
        "legend.framealpha":  0.92,
        "legend.edgecolor":   "#cccccc",
        "legend.borderpad":   0.5,
        "lines.linewidth":    1.6,
        "lines.markersize":   4.5,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.grid":          True,
        "axes.grid.which":    "major",
        "grid.alpha":         0.28,
        "grid.linewidth":     0.5,
        "grid.color":         "#888888",
        "axes.facecolor":     "white",       # no background tint
        "figure.facecolor":   "white",
        "figure.dpi":         150,
        "savefig.dpi":        300,
        "savefig.bbox":       "tight",
        "savefig.pad_inches": 0.06,
        "mathtext.fontset":   "dejavuserif",
        "axes.axisbelow":     True,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _figsize(ncols: int = 1, nrows: int = 1) -> Tuple[float, float]:
    """Scale (8,5) per panel, capped for readability."""
    w = min(_W1 * ncols, 22)
    h = min(_H1 * nrows, 20)
    return (w, h)


def _title_to_slug(title: str) -> str:
    """Convert a human-readable title to a safe filename slug."""
    s = re.sub(r'\([A-Z0-9]+\)\s*', '', title)   # drop panel letters
    s = re.sub(r'[^\w\s]', ' ', s)               # strip special chars
    s = re.sub(r'\s+', '_', s.strip())            # spaces → underscores
    return s.lower()[:80].strip('_')


def _ylim_margin(ax, margin: float = _MARGIN, bottom: Optional[float] = None) -> None:
    """Extend the top ylim by `margin` fraction; optionally pin the bottom."""
    lo, hi = ax.get_ylim()
    if bottom is not None:
        lo = bottom
    span = hi - lo
    ax.set_ylim(lo, hi + span * margin)


def _short_label(level: str) -> str:
    for prefix, abbr in [("std_efficientsu2", "ESU2"),
                         ("std_realamplitudes", "RA"),
                         ("std_twolocal", "TL")]:
        if level.startswith(prefix):
            rest  = level[len(prefix) + 1:].split("_")
            qubits = rest[0]
            reps   = rest[1] if len(rest) > 1 else ""
            return f"{abbr}\n{qubits} {reps}"
    return level[:12]


def _extract_qubits(level: str) -> int:
    m = re.search(r"_(\d+)q_", level)
    return int(m.group(1)) if m else 0


def _extract_reps(level: str) -> int:
    m = re.search(r"_r(\d+)_", level)
    return int(m.group(1)) if m else 0


def _family(level: str) -> str:
    if "efficientsu2"   in level: return "EfficientSU2"
    if "realamplitudes" in level: return "RealAmplitudes"
    if "twolocal"       in level: return "TwoLocal"
    return "Other"


def _panel_label(ax, letter: str, x: float = 0.02, y: float = 0.97) -> None:
    pass


def _smoothed(data: List[float], w: int = 7) -> np.ndarray:
    arr = np.array(data, dtype=float)
    if len(arr) < w:
        return arr
    kernel = np.ones(w) / w
    pad = np.pad(arr, (w // 2, w // 2), mode="edge")
    return np.convolve(pad, kernel, mode="valid")[: len(arr)]


def _save(fig: plt.Figure, output_dir: str, slug: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    png_path = ""
    for ext in ("pdf", "png"):
        p = os.path.join(output_dir, f"{slug}.{ext}")
        fig.savefig(p, bbox_inches="tight")
        print(f"  [circuit_plotter] Saved → {p}")
        if ext == "png":
            png_path = p
    plt.close(fig)
    return png_path


def _legend_handles() -> List[Line2D]:
    return [
        Line2D([0], [0], color=MODE_COLORS[m], marker=MODE_MARKERS[m],
               linestyle="-", linewidth=1, markersize=5, label=MODE_LABELS[m])
        for m in MODES
    ]


def _pct_change(baseline: float, improved: float, lower_better: bool = True) -> float:
    if baseline == 0:
        return 0.0
    delta = baseline - improved if lower_better else improved - baseline
    return delta / abs(baseline) * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_all(output_dir: str) -> Dict[str, Dict[str, Dict]]:
    data: Dict[str, Dict[str, Dict]] = {b: {} for b in CATALOG}
    for band, levels in CATALOG.items():
        for level in levels:
            data[band][level] = {}
            for mprefix in MODES:
                fpath = os.path.join(output_dir, f"results_{mprefix}_{level}.json")
                if os.path.exists(fpath):
                    with open(fpath) as fh:
                        d = json.load(fh)
                    data[band][level][mprefix] = d.get("summary", d)
                else:
                    data[band][level][mprefix] = None
    return data


def load_shot_records(output_dir: str, band: str, level: str, mprefix: str) -> List[Dict]:
    fpath = os.path.join(output_dir, f"results_{mprefix}_{level}.json")
    if not os.path.exists(fpath):
        return []
    with open(fpath) as fh:
        d = json.load(fh)
    return d.get("shot_records", [])


# ─────────────────────────────────────────────────────────────────────────────
# ═══════════════════════  FIGURES  ══════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

# ── F1  Per-band TTNS grouped bar ────────────────────────────────────────────

def fig_ttns_per_band(data: Dict, output_dir: str, band: str) -> str:
    _set_pub_style()
    title   = f"Time-to-Next-Shot per Circuit — {BAND_LABELS[band]}"
    levels  = CATALOG[band]
    n       = len(levels)
    n_modes = len(MODES)
    width   = 0.14
    x       = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(_W1, n * 1.0), _H1))
    for i, mprefix in enumerate(MODES):
        means = [(data[band][l].get(mprefix) or {}).get("mean_ttns_s", 0.0) for l in levels]
        stds  = [(data[band][l].get(mprefix) or {}).get("std_ttns_s",  0.0) for l in levels]
        offset = (i - (n_modes - 1) / 2) * width
        ax.bar(x + offset, means, width=width, color=MODE_COLORS[mprefix],
               alpha=0.88, edgecolor="white", linewidth=0.6,
               hatch=MODE_HATCHES[mprefix], label=MODE_LABELS[mprefix], zorder=3)
        ax.errorbar(x + offset, means, yerr=stds, fmt="none",
                    ecolor="#333333", elinewidth=0.8, capsize=2, capthick=0.8, zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([_short_label(l) for l in levels], fontsize=17)
    ax.set_ylabel("Mean TTNS (s)", labelpad=4)
    ax.legend(handles=_legend_handles(), ncol=n_modes, fontsize=14, loc="best")
    _ylim_margin(ax, bottom=0)
    _panel_label(ax, "A")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F2  Per-band QDC grouped bar ─────────────────────────────────────────────

def fig_qdc_per_band(data: Dict, output_dir: str, band: str) -> str:
    _set_pub_style()
    title   = f"Quantum Duty Cycle per Circuit — {BAND_LABELS[band]}"
    levels  = CATALOG[band]
    n       = len(levels)
    n_modes = len(MODES)
    width   = 0.14
    x       = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(_W1, n * 1.0), _H1))
    for i, mprefix in enumerate(MODES):
        vals = [(data[band][l].get(mprefix) or {}).get("qdc_pct", 0.0) for l in levels]
        offset = (i - (n_modes - 1) / 2) * width
        ax.bar(x + offset, vals, width=width, color=MODE_COLORS[mprefix],
               alpha=0.88, edgecolor="white", linewidth=0.6,
               hatch=MODE_HATCHES[mprefix], label=MODE_LABELS[mprefix], zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([_short_label(l) for l in levels], fontsize=17)
    ax.set_ylabel("Quantum Duty Cycle (%)", labelpad=2)
    ax.legend(handles=_legend_handles(), ncol=n_modes, fontsize=16, loc="best")
    ax.set_ylim(0, 35)
    _ylim_margin(ax, bottom=0)
    _panel_label(ax, "B")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F3  Cross-band aggregated 4-metric summary ───────────────────────────────

def fig_band_summary(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title   = "Aggregated Performance by Circuit Complexity Band"
    metrics = [
        ("mean_ttns_s",        "Mean TTNS (s)"),
        ("qdc_pct",            "Quantum Duty Cycle (%)"),
        ("convergence_time_s", "Convergence Time (s)"),
        ("drift_penalties",    "Drift Penalty Events"),
    ]
    bands   = list(CATALOG.keys())
    n_modes = len(MODES)
    width   = 0.15
    x       = np.arange(len(bands))

    fig, axes = plt.subplots(1, 4, figsize=_figsize(ncols=4))
    panels = ["C", "D", "E", "F"]
    for ax, (metric, ylabel), panel in zip(axes, metrics, panels):
        for i, mprefix in enumerate(MODES):
            band_means, band_errs = [], []
            for band in bands:
                vals = [float((data[band][l].get(mprefix) or {}).get(metric, 0) or 0)
                        for l in CATALOG[band]]
                band_means.append(np.mean(vals))
                band_errs.append(np.std(vals))
            offset = (i - (n_modes - 1) / 2) * width
            ax.bar(x + offset, band_means, width=width, color=MODE_COLORS[mprefix],
                   alpha=0.87, edgecolor="white", linewidth=0.5,
                   hatch=MODE_HATCHES[mprefix], label=MODE_LABELS[mprefix], zorder=3)
            ax.errorbar(x + offset, band_means, yerr=band_errs, fmt="none",
                        ecolor="#333333", elinewidth=0.8, capsize=2.5, capthick=0.8, zorder=4)
        ax.set_xticks(x)
        ax.set_xticklabels([b.capitalize() for b in bands], fontsize=14)
        ax.set_ylabel(ylabel, labelpad=3, fontsize=14)
        _ylim_margin(ax, bottom=0)
        _panel_label(ax, panel)

    axes[0].legend(handles=_legend_handles(), ncol=2, fontsize=14, loc="best")
    fig.tight_layout(w_pad=1.8)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F4  EFaaS TTNS improvement ratio ─────────────────────────────────────────

def fig_efaas_improvement(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "EFaaS TTNS Improvement Over All Baselines Across All Circuits"
    all_circuits: List[Tuple[str, str]] = [
        (band, lvl) for band in CATALOG for lvl in CATALOG[band]
    ]
    xs = np.arange(len(all_circuits))

    fig, ax = plt.subplots(figsize=(_W1 * 2, _H1))
    for idx, bm in enumerate(BASELINES):
        ys = []
        for band, lvl in all_circuits:
            s_ef = data[band][lvl].get("efaas")
            s_bm = data[band][lvl].get(bm)
            b_t  = (s_bm or {}).get("mean_ttns_s", 0)
            e_t  = (s_ef or {}).get("mean_ttns_s", 0)
            ys.append(_pct_change(b_t, e_t) if b_t > 0 else 0.0)
        ls = ["-", "--", "-.", ":"][idx % 4]
        ax.plot(xs, ys, color=MODE_COLORS[bm], linestyle=ls,
                marker=MODE_MARKERS[bm], linewidth=1.7, markersize=5,
                label=f"EFaaS vs {MODE_LABELS[bm]}", zorder=3)
        ax.fill_between(xs, ys, 0, color=MODE_COLORS[bm], alpha=0.07, zorder=2)

    # Band shading
    start = 0
    for band, bc in zip(CATALOG.keys(), BAND_COLORS.values()):
        end = start + len(CATALOG[band])
        ax.axvspan(start - 0.5, end - 0.5, alpha=0.06, color=bc, zorder=1)
        start = end

    ax.axhline(0, color="#555555", linestyle=":", linewidth=0.9, zorder=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([_short_label(lvl).replace("\n", " ") for _, lvl in all_circuits],
                       rotation=45, ha="right", fontsize=14)
    ax.set_ylabel("TTNS Reduction vs Baseline (%)", labelpad=4)
    ax.legend(fontsize=16, loc="best", ncol=2)
    _ylim_margin(ax)
    _panel_label(ax, "G")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F5  Scaling: qubits vs TTNS / QDC ────────────────────────────────────────

def fig_scaling(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Qubit Count Scaling TTNS and QDC"
    band_size = {"simple": 30, "medium": 55, "complex": 85}

    fig, axes = plt.subplots(1, 2, figsize=_figsize(ncols=2))
    ax_ttns, ax_qdc = axes

    for mprefix in MODES:
        q_vals, ttns_vals, qdc_vals, sizes = [], [], [], []
        for band in CATALOG:
            for lvl in CATALOG[band]:
                s = data[band][lvl].get(mprefix)
                if not s: continue
                q_vals.append(_extract_qubits(lvl))
                ttns_vals.append(s["mean_ttns_s"])
                qdc_vals.append(s["qdc_pct"])
                sizes.append(band_size[band])
        q_arr = np.array(q_vals); sort_i = np.argsort(q_arr)
        for ax, yvals in [(ax_ttns, ttns_vals), (ax_qdc, qdc_vals)]:
            ax.scatter(q_arr, yvals, s=sizes, alpha=0.65,
                       color=MODE_COLORS[mprefix], edgecolors="white", linewidths=0.5, zorder=3)
            ax.plot(q_arr[sort_i], np.array(yvals)[sort_i],
                    color=MODE_COLORS[mprefix], linestyle="--", linewidth=1.2,
                    alpha=0.75, zorder=2, label=MODE_LABELS[mprefix])

    for ax in axes:
        for qb in [5.5, 10.5]:
            ax.axvline(qb, color="#888888", linestyle=":", linewidth=0.8, alpha=0.7)

    ax_ttns.set_xlabel("Number of Qubits"); ax_ttns.set_ylabel("Mean TTNS (s)")
    ax_ttns.legend(handles=_legend_handles(), fontsize=14, loc="best")
    _ylim_margin(ax_ttns, bottom=0)
    _panel_label(ax_ttns, "H")

    ax_qdc.set_xlabel("Number of Qubits"); ax_qdc.set_ylabel("QDC (%)")
    _ylim_margin(ax_qdc, bottom=0)
    _panel_label(ax_qdc, "I")

    fig.tight_layout(w_pad=2.0)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F6  Performance heatmap ───────────────────────────────────────────────────

def fig_heatmap(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Per-Circuit Performance Heatmap TTNS and QDC"
    all_circuits, row_labels, row_dividers, cumulative = [], [], [], 0
    for band in CATALOG:
        for lvl in CATALOG[band]:
            all_circuits.append((band, lvl))
            row_labels.append(_short_label(lvl).replace("\n", " "))
        row_dividers.append(cumulative + len(CATALOG[band]))
        cumulative += len(CATALOG[band])

    n_rows    = len(all_circuits)
    mode_keys = list(MODES.keys())
    n_cols    = len(mode_keys)
    efaas_col = mode_keys.index("efaas")
    ttns_mat  = np.zeros((n_rows, n_cols))
    qdc_mat   = np.zeros((n_rows, n_cols))

    for r, (band, lvl) in enumerate(all_circuits):
        for c, mp in enumerate(mode_keys):
            s = data[band][lvl].get(mp)
            ttns_mat[r, c] = s["mean_ttns_s"] if s else np.nan
            qdc_mat[r, c]  = s["qdc_pct"]     if s else np.nan

    def row_norm(mat, lower_better=True):
        norm = np.zeros_like(mat)
        for r in range(mat.shape[0]):
            row = mat[r]; rmin, rmax = np.nanmin(row), np.nanmax(row)
            norm[r] = (row - rmin) / (rmax - rmin) if rmax > rmin else np.full_like(row, 0.5)
        return norm if lower_better else 1.0 - norm

    ttns_norm = row_norm(ttns_mat, True)
    qdc_norm  = row_norm(qdc_mat,  False)
    cmap_ttns = LinearSegmentedColormap.from_list("ttns", ["#2ca02c", "#ffffcc", "#d62728"], N=256)
    cmap_qdc  = LinearSegmentedColormap.from_list("qdc",  ["#d62728", "#ffffcc", "#2ca02c"], N=256)
    col_labels = [MODE_LABELS[m] for m in mode_keys]
    fig_h = max(_H1, n_rows * 0.36 + 1.5)

    fig, axes = plt.subplots(1, 2, figsize=_figsize(ncols=2, nrows=max(1, int(fig_h / _H1))))
    for ax, norm_mat, raw_mat, cmap, panel in [
        (axes[0], ttns_norm, ttns_mat, cmap_ttns, "J"),
        (axes[1], qdc_norm,  qdc_mat,  cmap_qdc,  "K"),
    ]:
        im = ax.imshow(norm_mat, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                       interpolation="nearest")
        for r in range(n_rows):
            for c in range(n_cols):
                val = raw_mat[r, c]
                txt = f"{val:.1f}" if not np.isnan(val) else "—"
                fc  = norm_mat[r, c]
                ax.text(c, r, txt, ha="center", va="center", fontsize=6,
                        color="white" if (fc < 0.25 or fc > 0.75) else "black")
        for r in range(n_rows):
            ax.add_patch(mpatches.FancyBboxPatch(
                (efaas_col - 0.48, r - 0.48), 0.96, 0.96,
                boxstyle="round,pad=0.0", linewidth=1.2,
                edgecolor="#2ca02c", facecolor="none", zorder=5))
        for div in row_dividers[:-1]:
            ax.axhline(div - 0.5, color="#444444", linewidth=1.0)
        ax.set_xticks(range(n_cols)); ax.set_xticklabels(col_labels, fontsize=14, fontweight="bold")
        ax.set_yticks(range(n_rows)); ax.set_yticklabels(row_labels, fontsize=14)
        plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="0=best, 1=worst")
        _panel_label(ax, panel)

    fig.tight_layout(w_pad=2.0)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F7  Energy convergence race ───────────────────────────────────────────────

def fig_energy_race(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Energy Convergence Race Representative Circuit per Band"
    fig, axes = plt.subplots(1, 3, figsize=_figsize(ncols=3))
    panels = ["L", "M", "N"]
    for ax, (band, panel) in zip(axes, zip(CATALOG.keys(), panels)):
        levels = CATALOG[band]; rep = levels[len(levels) // 2]
        for mprefix in MODES:
            s = data[band][rep].get(mprefix)
            if not s: continue
            e_arr = np.array(s.get("energy_list", [])); sim_t = np.array(s.get("sim_times", []))
            if len(e_arr) == 0: continue
            ax.plot(sim_t, _smoothed(e_arr.tolist(), 9),
                    color=MODE_COLORS[mprefix],
                    linestyle="-" if mprefix == "efaas" else "--",
                    linewidth=2.0 if mprefix == "efaas" else 1.2,
                    alpha=0.9 if mprefix == "efaas" else 0.75,
                    label=MODE_LABELS[mprefix], zorder=4 if mprefix == "efaas" else 3)
            conv_t = s.get("convergence_time_s")
            if conv_t:
                ax.axvline(conv_t, color=MODE_COLORS[mprefix],
                           linestyle=":", linewidth=0.9, alpha=0.55)
        ax.axhline(LIH_REFERENCE, color="#555555", linestyle=":", linewidth=1.0,
                   label="LiH ref")
        ax.set_xlabel("Simulated Time (s)"); ax.set_ylabel(r"$\langle H \rangle$ (H$_a$)")
        ax.legend(fontsize=16, loc="best")
        _ylim_margin(ax)
        _panel_label(ax, panel)
    fig.tight_layout(w_pad=1.5)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F8  TTNS box-plot per band ────────────────────────────────────────────────

def fig_ttns_boxplot(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "TTNS Statistical Distribution Pooled per Band"
    fig, axes = plt.subplots(1, 3, figsize=_figsize(ncols=3))
    panels = ["O", "P", "Q"]
    for ax, (band, panel) in zip(axes, zip(CATALOG.keys(), panels)):
        box_data = []
        for mprefix in MODES:
            pool = []
            for lvl in CATALOG[band]:
                s = data[band][lvl].get(mprefix)
                if s and s.get("ttns_list"): pool.extend(s["ttns_list"])
            box_data.append(pool if pool else [0])
        bp = ax.boxplot(box_data, patch_artist=True, notch=False, widths=0.55,
                        medianprops=dict(color="black", linewidth=2.0),
                        flierprops=dict(marker=".", markersize=2.5, alpha=0.35),
                        whiskerprops=dict(linewidth=1.0), capprops=dict(linewidth=1.0), zorder=3)
        for patch, mp in zip(bp["boxes"], MODES):
            patch.set_facecolor(MODE_COLORS[mp]); patch.set_alpha(0.80)
        ax.set_xticks(range(1, len(MODES) + 1))
        ax.set_xticklabels(list(MODE_LABELS.values()), fontsize=14)
        ax.set_ylabel("TTNS (s)")
        ax.set_yscale("symlog", linthresh=5)
        ax.yaxis.set_minor_formatter(ticker.NullFormatter())
        _panel_label(ax, panel)
    fig.tight_layout(w_pad=1.8)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F9  Radar chart per band ──────────────────────────────────────────────────

def fig_radar(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Multi-Metric Radar Profile Band Averaged All Modes"
    radar_metrics = [
        ("mean_ttns_s",           "TTNS↓",   True),
        ("qdc_pct",               "QDC↑",    False),
        ("iterations_completed",  "Iters↑",  False),
        ("calib_ratio_pct",       "CalibR↑", False),
        ("drift_penalties",       "DriftP↓", True),
    ]
    n_vars = len(radar_metrics)
    angles = np.linspace(0, 2 * np.pi, n_vars, endpoint=False).tolist() + [0]

    fig = plt.figure(figsize=_figsize(ncols=3))
    for col, (band, panel) in enumerate(zip(CATALOG.keys(), ["R", "S", "T"])):
        ax = fig.add_subplot(1, 3, col + 1, projection="polar")
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
        raw: Dict[str, List[float]] = {}
        for mprefix in MODES:
            vals = []
            for metric, _, _ in radar_metrics:
                ms = [float((data[band][l].get(mprefix) or {}).get(metric, 0) or 0)
                      for l in CATALOG[band]]
                vals.append(np.mean(ms) if ms else 0.0)
            raw[mprefix] = vals
        for mi in range(n_vars):
            all_v = [raw[m][mi] for m in MODES]
            vmin, vmax = min(all_v), max(all_v)
            lb = radar_metrics[mi][2]
            for mprefix in MODES:
                v = raw[mprefix][mi]
                norm = (v - vmin) / (vmax - vmin) if vmax > vmin else 0.5
                raw[mprefix][mi] = 1.0 - norm if lb else norm
        for mprefix in MODES:
            vals = raw[mprefix] + raw[mprefix][:1]
            ax.plot(angles, vals, color=MODE_COLORS[mprefix], linewidth=1.6,
                    marker=MODE_MARKERS[mprefix], markersize=5, label=MODE_LABELS[mprefix], zorder=3)
            ax.fill(angles, vals, color=MODE_COLORS[mprefix], alpha=0.10)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([m[1] for m in radar_metrics], fontsize=14)
        ax.set_ylim(0, 1); ax.set_yticks([0.25, 0.5, 0.75])
        ax.set_yticklabels(["0.25", "0.5", "0.75"], fontsize=14)
        ax.set_facecolor("white")
        if col == 0:
            ax.legend(handles=_legend_handles(), fontsize=14, loc="upper right",
                      bbox_to_anchor=(1.45, 1.15), ncol=1)
        _panel_label(ax, panel)
    fig.tight_layout(w_pad=0.5)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F10 Convergence scatter ───────────────────────────────────────────────────

def fig_convergence_scatter(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Convergence Time vs Iterations and EFaaS Speedup"
    band_markers = {"simple": "o", "medium": "s", "complex": "^"}

    fig, axes = plt.subplots(1, 2, figsize=_figsize(ncols=2))
    ax_ct, ax_efaas = axes

    for band in CATALOG:
        for mprefix in MODES:
            ct_vals, iter_vals, qdc_vals = [], [], []
            for lvl in CATALOG[band]:
                s = data[band][lvl].get(mprefix)
                if not s: continue
                ct = s.get("convergence_time_s")
                if ct is not None:
                    ct_vals.append(ct)
                    iter_vals.append(s.get("iterations_completed", 0))
                    qdc_vals.append(s.get("qdc_pct", 10))
            if ct_vals:
                ax_ct.scatter(iter_vals, ct_vals, s=np.array(qdc_vals) * 2.5,
                              color=MODE_COLORS[mprefix], marker=band_markers[band],
                              alpha=0.65, edgecolors="white", linewidths=0.4, zorder=3)

    mode_handles = _legend_handles()
    band_handles = [Line2D([0],[0], marker=band_markers[b], color="#555555",
                           linestyle="None", markersize=6, label=b.capitalize())
                    for b in CATALOG]
    ax_ct.legend(handles=mode_handles + band_handles, fontsize=18, loc="best",
                 ncol=2, title="Mode / Band", title_fontsize=18)
    ax_ct.set_xlabel("Iterations Completed"); ax_ct.set_ylabel("Convergence Time (s)")
    _ylim_margin(ax_ct, bottom=0)
    _panel_label(ax_ct, "U")

    for bm in BASELINES:
        xs, ys = [], []
        for band in CATALOG:
            for lvl in CATALOG[band]:
                s_ef = data[band][lvl].get("efaas"); s_bm = data[band][lvl].get(bm)
                if not s_ef or not s_bm: continue
                b_ct = s_bm.get("convergence_time_s"); e_ct = s_ef.get("convergence_time_s")
                if b_ct and e_ct and b_ct > 0:
                    xs.append(b_ct); ys.append(_pct_change(b_ct, e_ct))
        if xs:
            ax_efaas.scatter(xs, ys, s=35, alpha=0.65, color=MODE_COLORS[bm],
                             marker=MODE_MARKERS[bm], edgecolors="white", linewidths=0.4,
                             label=f"vs {MODE_LABELS[bm]}", zorder=3)
            xs_arr = np.array(xs); sort_i = np.argsort(xs_arr)
            ax_efaas.plot(xs_arr[sort_i], np.array(ys)[sort_i],
                          color=MODE_COLORS[bm], linestyle="--", linewidth=1.0,
                          alpha=0.55, zorder=2)

    ax_efaas.axhline(0, color="#555555", linestyle=":", linewidth=0.9)
    ax_efaas.set_xlabel("Baseline Conv. Time (s)")
    ax_efaas.set_ylabel("EFaaS Conv. Time Reduc. (%)")
    ax_efaas.legend(fontsize=18, loc="best")
    _ylim_margin(ax_efaas)
    _panel_label(ax_efaas, "V")

    fig.tight_layout(w_pad=2.0)
    return _save(fig, output_dir, _title_to_slug(title))


# ── F11 Secondary metrics grid ────────────────────────────────────────────────

def fig_secondary_metrics(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Secondary Performance Metrics All Bands and Circuits"
    metrics = [
        ("mean_queue_wait_s",          "Queue Wait (s)"),
        ("calib_ratio_pct",            "Calib. Ratio (%)"),
        ("classical_util_pct",         "Classical Util. (%)"),
        ("cache_hit_rate_pct",         "Cache Hit Rate (%)"),
        ("reconcile_failure_rate_pct", "Reconcile Fail. (%)"),
    ]
    bands   = list(CATALOG.keys())
    n_modes = len(MODES)
    width   = 0.14
    n_col   = len(metrics)
    n_row   = len(bands)

    fig, axes = plt.subplots(n_row, n_col, figsize=(_W1 * n_col // 2, _H1 * n_row // 2 + 1))
    for row_idx, band in enumerate(bands):
        for col_idx, (metric, mlabel) in enumerate(metrics):
            ax = axes[row_idx][col_idx]
            levels = CATALOG[band]; x = np.arange(len(levels))
            for i, mprefix in enumerate(MODES):
                vals = [float((data[band][l].get(mprefix) or {}).get(metric, 0) or 0)
                        for l in levels]
                offset = (i - (n_modes - 1) / 2) * width
                ax.bar(x + offset, vals, width=width, color=MODE_COLORS[mprefix],
                       alpha=0.85, edgecolor="white", linewidth=0.4, zorder=3)
            ax.set_xticks(x)
            ax.set_xticklabels([_short_label(l).replace("\n", " ") for l in levels],
                               rotation=55, ha="right", fontsize=5.5)
            if col_idx == 0:
                ax.set_ylabel(f"{band.capitalize()}\n{mlabel}", fontsize=14)
            if row_idx == 0:
                ax.text(0.5, 1.02, mlabel, transform=ax.transAxes,
                        ha="center", fontsize=14, fontweight="bold")
            _ylim_margin(ax, bottom=0)
            ax.tick_params(axis="y", labelsize=14)

    fig.legend(handles=_legend_handles(), loc="lower center", ncol=n_modes,
               fontsize=14, bbox_to_anchor=(0.5, -0.02),
               title="Architecture", title_fontsize=14)
    fig.tight_layout(h_pad=1.8, w_pad=1.2)
    return _save(fig, output_dir, _title_to_slug(title))


# ─────────────────────────────────────────────────────────────────────────────
# ═══════════════════════  DRIFT FIGURES  ════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

# ── F12 Drift penalty heatmap ─────────────────────────────────────────────────

def fig_drift_heatmap(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Quantum Drift Penalty Events per Circuit and Mode"
    all_circuits, row_labels, row_dividers, cumulative = [], [], [], 0
    for band in CATALOG:
        for lvl in CATALOG[band]:
            all_circuits.append((band, lvl))
            row_labels.append(_short_label(lvl).replace("\n", " "))
        row_dividers.append(cumulative + len(CATALOG[band]))
        cumulative += len(CATALOG[band])

    n_rows    = len(all_circuits)
    mode_keys = list(MODES.keys())
    n_cols    = len(mode_keys)
    mat       = np.zeros((n_rows, n_cols))
    for r, (band, lvl) in enumerate(all_circuits):
        for c, mp in enumerate(mode_keys):
            s = data[band][lvl].get(mp)
            mat[r, c] = float((s or {}).get("drift_penalties", 0))

    cmap_drift = LinearSegmentedColormap.from_list(
        "drift", ["#2ca02c", "#ffffcc", "#d62728"], N=256)
    efaas_col  = mode_keys.index("efaas")

    fig, ax = plt.subplots(figsize=(_W1, max(_H1, n_rows * 0.38 + 1.0)))
    im = ax.imshow(mat, aspect="auto", cmap=cmap_drift, vmin=0,
                   vmax=max(mat.max(), 1), interpolation="nearest")

    for r in range(n_rows):
        for c in range(n_cols):
            v = int(mat[r, c])
            ax.text(c, r, str(v) if v > 0 else "0", ha="center", va="center",
                    fontsize=7, fontweight="bold" if v > 0 else "normal",
                    color="white" if mat[r, c] > mat.max() * 0.6 else "black")
        ax.add_patch(mpatches.FancyBboxPatch(
            (efaas_col - 0.48, r - 0.48), 0.96, 0.96,
            boxstyle="round,pad=0.0", linewidth=1.4,
            edgecolor="#2ca02c", facecolor="none", zorder=5))

    for div in row_dividers[:-1]:
        ax.axhline(div - 0.5, color="#333333", linewidth=1.2)

    band_starts = [0] + row_dividers[:-1]
    for band, bs, be, bc in zip(CATALOG.keys(), band_starts, row_dividers, BAND_COLORS.values()):
        ax.text(-0.7, (bs + be - 1) / 2, band.capitalize(),
                ha="right", va="center", fontsize=8.5,
                fontweight="bold", color=bc, transform=ax.transData)

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([MODE_LABELS[m] for m in mode_keys], fontsize=14, fontweight="bold")
    ax.set_yticks(range(n_rows)); ax.set_yticklabels(row_labels, fontsize=14)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.03, label="Drift Penalty Count")
    _panel_label(ax, "D1")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F13 Drift per band: bar + pie ─────────────────────────────────────────────

def fig_drift_per_band(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Drift Events per Mode and Complexity Band"
    bands = list(CATALOG.keys())
    drift: Dict[str, Dict[str, int]] = {mp: {b: 0 for b in bands} for mp in MODES}
    for band in bands:
        for lvl in CATALOG[band]:
            for mp in MODES:
                s = data[band][lvl].get(mp)
                if s:
                    drift[mp][band] += int(s.get("drift_penalties", 0))

    fig = plt.figure(figsize=_figsize(ncols=6, nrows=1))
    gs  = gridspec.GridSpec(1, 6, figure=fig, wspace=0.45)
    ax_bar = fig.add_subplot(gs[0, :2])

    x = np.arange(len(MODES))
    bottoms = np.zeros(len(MODES))
    for bi, band in enumerate(bands):
        vals = [drift[mp][band] for mp in MODES]
        ax_bar.bar(x, vals, bottom=bottoms, width=0.55,
                   color=[MODE_COLORS[mp] for mp in MODES],
                   alpha=0.88 - bi * 0.15, edgecolor="white",
                   linewidth=0.6, hatch=["", "///", "xxx"][bi], zorder=3)
        bottoms += np.array(vals, dtype=float)

    for xi, mp in enumerate(MODES):
        total = sum(drift[mp][b] for b in bands)
        ax_bar.text(xi, bottoms[xi] + 0.3, str(int(total)),
                    ha="center", va="bottom", fontsize=8.5,
                    fontweight="bold", color=MODE_COLORS[mp])

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels([MODE_LABELS[mp] for mp in MODES], fontsize=14)
    ax_bar.set_ylabel("Total Drift Penalty Events", labelpad=4)
    band_patches = [mpatches.Patch(facecolor=BAND_COLORS[b], label=b.capitalize())
                    for b in bands]
    ax_bar.legend(handles=band_patches, title="Band", fontsize=14, loc="best")
    _ylim_margin(ax_bar, bottom=0)
    _panel_label(ax_bar, "D2")

    for pi, bm in enumerate(BASELINES):
        ax_pie = fig.add_subplot(gs[0, 2 + pi])
        pie_vals = [drift[bm][b] for b in bands]
        if sum(pie_vals) == 0:
            pie_vals = [1, 1, 1]
        _, _, autotexts = ax_pie.pie(
            pie_vals, labels=None,
            colors=[BAND_COLORS[b] for b in bands],
            autopct="%1.0f%%", pctdistance=0.72, startangle=90,
            wedgeprops=dict(linewidth=0.6, edgecolor="white"),
        )
        for at in autotexts:
            at.set_fontsize(7); at.set_fontweight("bold")
        total_bm = sum(drift[bm][b] for b in bands)
        ax_pie.text(0, -1.35, f"{MODE_LABELS[bm]}\n({total_bm} total)",
                    ha="center", fontsize=8.5, fontweight="bold")

    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F14 Calibration ratio vs drift penalty scatter ───────────────────────────

def fig_calib_drift_scatter(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Calibration Overhead vs Drift Penalty Events"
    band_markers_s = {"simple": "o", "medium": "s", "complex": "^"}

    fig, ax = plt.subplots(figsize=(_W1, _H1))
    for band in CATALOG:
        for mprefix in MODES:
            xs, ys = [], []
            for lvl in CATALOG[band]:
                s = data[band][lvl].get(mprefix)
                if not s: continue
                xs.append(float(s.get("calib_ratio_pct", 0)))
                ys.append(float(s.get("drift_penalties", 0)))
            if xs:
                ax.scatter(xs, ys, s=55, alpha=0.72,
                           color=MODE_COLORS[mprefix], marker=band_markers_s[band],
                           edgecolors="white", linewidths=0.5, zorder=3)

    ax.axvline(0.5, color="#2ca02c", linestyle=":", linewidth=1.0, alpha=0.6)
    ax.axhline(0.5, color="#2ca02c", linestyle=":", linewidth=1.0, alpha=0.6)
    ax.text(0.1, -0.3, "EFaaS\nIdeal Zone",
            fontsize=8, color="#2ca02c", fontweight="bold", alpha=0.8)

    mode_handles = _legend_handles()
    band_handles = [Line2D([0],[0], marker=band_markers_s[b], color="#555555",
                           linestyle="None", markersize=6, label=b.capitalize())
                    for b in CATALOG]
    all_handles = mode_handles + band_handles
    ax.legend(handles=all_handles, fontsize=12, ncol=4,
              loc="lower center", bbox_to_anchor=(0.5, 1.02),
              framealpha=0.92, borderaxespad=0)
    ax.set_xlabel("Calibration Ratio (%)", labelpad=4)
    ax.set_ylabel("Drift Penalty Events", labelpad=4)
    _ylim_margin(ax, bottom=-0.1)
    _panel_label(ax, "D3")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F15 Drift vs qubit count ──────────────────────────────────────────────────

def fig_drift_qubit_scaling(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Drift Penalty Scaling with Circuit Complexity"

    fig, ax = plt.subplots(figsize=(_W1, _H1))
    for mprefix in MODES:
        q_vals, d_vals = [], []
        for band in CATALOG:
            for lvl in CATALOG[band]:
                s = data[band][lvl].get(mprefix)
                if not s: continue
                q_vals.append(_extract_qubits(lvl))
                d_vals.append(float(s.get("drift_penalties", 0)))
        q_arr = np.array(q_vals); sort_i = np.argsort(q_arr)
        ax.plot(q_arr[sort_i], np.array(d_vals)[sort_i],
                color=MODE_COLORS[mprefix],
                linestyle="-" if mprefix == "efaas" else "--",
                marker=MODE_MARKERS[mprefix],
                linewidth=2.5 if mprefix == "efaas" else 1.5,
                markersize=5.5, label=MODE_LABELS[mprefix],
                zorder=5 if mprefix == "efaas" else 3)
        if mprefix == "efaas":
            ax.fill_between(q_arr[sort_i], np.array(d_vals)[sort_i], 0,
                            color="#2ca02c", alpha=0.12, zorder=2)

    for qb in [5.5, 10.5]:
        ax.axvline(qb, color="#888888", linestyle=":", linewidth=0.8, alpha=0.7)

    ax.axhline(0, color="#2ca02c", linestyle="-", linewidth=1.2, alpha=0.5)
    ax.set_xlabel("Number of Qubits", labelpad=4)
    ax.set_ylabel("Drift Penalty Events", labelpad=4)
    ax.legend(fontsize=16, loc="best", ncol=2)
    _ylim_margin(ax, bottom=-0.1)
    _panel_label(ax, "D4")
    fig.tight_layout()
    return _save(fig, output_dir, _title_to_slug(title))


# ── F16 Cumulative drift timeline ─────────────────────────────────────────────

def fig_drift_timeline(data: Dict, output_dir: str, json_dir: str) -> str:
    _set_pub_style()
    title = "Cumulative Drift Timeline per Band"

    fig, axes = plt.subplots(1, 3, figsize=_figsize(ncols=3))
    for ax, (band, panel) in zip(axes, zip(CATALOG.keys(), ["D5", "D6", "D7"])):
        levels = CATALOG[band]
        rep = levels[len(levels) // 2]
        max_drift = -1
        for lvl in levels:
            total = sum(int((data[band][lvl].get(mp) or {}).get("drift_penalties", 0))
                        for mp in BASELINES)
            if total > max_drift:
                max_drift = total; rep = lvl

        for mprefix in MODES:
            records = load_shot_records(json_dir, band, rep, mprefix)
            if not records: continue
            sim_times = [r["sim_time"] for r in records]
            cum_drift = np.cumsum([1 if r.get("drift_penalty") else 0 for r in records])
            ax.step(sim_times, cum_drift,
                    color=MODE_COLORS[mprefix],
                    linestyle="-" if mprefix == "efaas" else "--",
                    linewidth=2.5 if mprefix == "efaas" else 1.4,
                    alpha=1.0 if mprefix == "efaas" else 0.80,
                    label=MODE_LABELS[mprefix], where="post",
                    zorder=5 if mprefix == "efaas" else 3)

        ax.set_xlabel("Simulated Time (s)", labelpad=3)
        ax.set_ylabel("Cum. Drift Events", labelpad=1)
        ax.text(0.02, 0.97, f"{band.capitalize()}\n[{_short_label(rep).replace(chr(10),' ')}]",
                transform=ax.transAxes, fontsize=7.5, va="top", ha="left",
                color=BAND_COLORS[band], fontweight="bold")
        ax.legend(fontsize=16, loc="best", ncol=2)
        _ylim_margin(ax, bottom=-0.1)
        _panel_label(ax, panel)

    fig.tight_layout(w_pad=1.5)
    return _save(fig, output_dir, _title_to_slug(title))


# ─────────────────────────────────────────────────────────────────────────────
# ═══════════════════════  TABLE FIGURES  ════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def _save_csv(output_dir: str, slug: str, headers: List[str],
              rows: List[List[str]]) -> str:
    os.makedirs(output_dir, exist_ok=True)
    p = os.path.join(output_dir, f"{slug}.csv")
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  [circuit_plotter] Saved → {p}")
    return p


def _style_table(table, row_labels: List[str], efaas_rows: List[int],
                 band_row_groups: Optional[List[Tuple[str, int, int]]] = None,
                 row_h: float = 0.055, hdr_h: float = 0.065) -> None:
    """Apply publication styling to a matplotlib table."""
    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(0.4); cell.set_edgecolor("#b0b8c8")
        if r == 0:
            cell.set_facecolor(_HDR_BG); cell.get_text().set_color(_HDR_FG)
            cell.get_text().set_fontweight("bold"); cell.set_height(hdr_h); continue
        ri = r - 1; cell.set_height(row_h)
        # Band stripe
        bg = _ROW_A_BG if ri % 2 == 0 else _ROW_B_BG
        if band_row_groups:
            for band, bs, be in band_row_groups:
                if bs <= ri < be:
                    bg = _BAND_BG[band]; break
        # EFaaS row
        if ri in efaas_rows:
            cell.set_facecolor(_EFAAS_BG); cell.get_text().set_color(_EFAAS_FG)
            cell.get_text().set_fontweight("bold")
        else:
            cell.set_facecolor(bg)
        if c == 0:
            cell.get_text().set_fontweight("bold")


# ── T1  Per-band aggregate statistics ────────────────────────────────────────

def table_band_summary(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Band Aggregate Statistics"
    col_labels = ["Mean TTNS", "Std TTNS", "QDC%", "Conv.Time(s)",
                  "Drift", "CalibR%", "Iters", "CacheHit%"]
    metrics    = ["mean_ttns_s", "std_ttns_s", "qdc_pct", "convergence_time_s",
                  "drift_penalties", "calib_ratio_pct", "iterations_completed",
                  "cache_hit_rate_pct"]
    fmts       = [".2f", ".2f", ".1f", ".1f", ".1f", ".2f", ".0f", ".1f"]

    row_labels, cell_data, band_row_groups = [], [], []
    for band in CATALOG:
        start = len(row_labels)
        for mp in MODES:
            row_labels.append(f"{band.capitalize()} / {MODE_LABELS[mp]}")
            row = []
            for metric, fmt in zip(metrics, fmts):
                vals = [float((data[band][l].get(mp) or {}).get(metric, 0) or 0)
                        for l in CATALOG[band]]
                row.append(f"{np.mean(vals):{fmt}}")
            cell_data.append(row)
        band_row_groups.append((band, start, len(row_labels)))

    efaas_rows = [i for i, rl in enumerate(row_labels) if "EFaaS" in rl]
    n_rows     = len(row_labels)

    fig, ax = plt.subplots(figsize=(_W1 * 2, max(_H1, n_rows * 0.38 + 1.2)))
    ax.axis("off")
    all_col = ["Band / Mode"] + col_labels
    all_rows = [[row_labels[i]] + r for i, r in enumerate(cell_data)]
    table = ax.table(cellText=all_rows, colLabels=all_col, loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(7.5)
    table.auto_set_column_width(list(range(len(all_col))))
    _style_table(table, row_labels, efaas_rows, band_row_groups)

    slug = _title_to_slug(title)
    _save_csv(output_dir, slug, all_col, all_rows)
    fig.tight_layout()
    return _save(fig, output_dir, slug)


# ── T2  EFaaS improvement over every baseline ────────────────────────────────

def table_efaas_improvement(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "EFaaS Improvement Over Baselines"
    metric_defs = [
        ("mean_ttns_s",          "TTNS Reduction (%)",       True),
        ("qdc_pct",              "QDC Gain (%)",             False),
        ("convergence_time_s",   "Conv.Time Reduc.",  True),
        ("drift_penalties",      "Drift Elimin. (%)",    True),
        ("calib_ratio_pct",      "CalibRatio Reduc. (%)", True),
        ("mean_vqe_wait_s",      "VQE Wait Reduc. (%)",   True),
        ("iterations_completed", "Iteration Gain (%)",       False),
    ]
    col_labels = [f"vs {MODE_LABELS[bm]}" for bm in BASELINES]
    row_labels, cell_data, band_row_groups = [], [], []

    for band in CATALOG:
        start = len(row_labels)
        for mname, mlabel, lb in metric_defs:
            row_labels.append(f"{band.capitalize()} — {mlabel}")
            row = []
            for bm in BASELINES:
                ef_v = [float((data[band][l].get("efaas") or {}).get(mname, 0) or 0) for l in CATALOG[band]]
                bm_v = [float((data[band][l].get(bm)      or {}).get(mname, 0) or 0) for l in CATALOG[band]]
                pcts = [_pct_change(b, e, lb) for b, e in zip(bm_v, ef_v) if b != 0]
                row.append(f"{np.mean(pcts):+.1f}%" if pcts else "—")
            cell_data.append(row)
        band_row_groups.append((band, start, len(row_labels)))

    efaas_rows = []  # no EFaaS rows in this table
    n_rows     = len(row_labels)

    fig, ax = plt.subplots(figsize=(_W1 * 2, max(_H1, n_rows * 0.42 + 1.2)))
    ax.axis("off")
    all_col  = ["Metric"] + col_labels
    all_rows = [[row_labels[i]] + r for i, r in enumerate(cell_data)]
    table = ax.table(cellText=all_rows, colLabels=all_col, loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(8)
    table.auto_set_column_width(list(range(len(all_col))))

    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(0.4); cell.set_edgecolor("#b0b8c8")
        if r == 0:
            cell.set_facecolor(_HDR_BG); cell.get_text().set_color(_HDR_FG)
            cell.get_text().set_fontweight("bold"); cell.set_height(0.065); continue
        ri = r - 1; cell.set_height(0.052)
        for band, bs, be in band_row_groups:
            if bs <= ri < be:
                cell.set_facecolor(_BAND_BG[band]); break
        if c == 0:
            cell.get_text().set_fontweight("bold"); continue
        try:
            val = float(cell.get_text().get_text().replace("%", "").strip())
            if val > 10:
                cell.set_facecolor(_BEST_BG); cell.get_text().set_fontweight("bold")
            elif val > 0:
                cell.set_facecolor("#e8f8ec")
            elif val < 0:
                cell.set_facecolor(_WORST_BG)
        except Exception:
            pass

    slug = _title_to_slug(title)
    _save_csv(output_dir, slug, all_col, all_rows)
    fig.tight_layout()
    return _save(fig, output_dir, slug)


# ── T3  Drift analysis table ──────────────────────────────────────────────────

def table_drift_analysis(data: Dict, output_dir: str) -> str:
    _set_pub_style()
    title = "Drift Analysis"
    all_circuits = [(band, lvl) for band in CATALOG for lvl in CATALOG[band]]
    n_total      = len(all_circuits)

    rows_data = []
    for mp in MODES:
        drift_vals = [int((data[band][lvl].get(mp) or {}).get("drift_penalties", 0))
                      for band, lvl in all_circuits]
        total    = sum(drift_vals)
        affected = sum(1 for v in drift_vals if v > 0)
        ef_drift = [int((data[band][lvl].get("efaas") or {}).get("drift_penalties", 0))
                    for band, lvl in all_circuits]
        elim     = sum(1 for bv, ev in zip(drift_vals, ef_drift) if bv > 0 and ev == 0)
        rows_data.append({
            "mode":     MODE_LABELS[mp],
            "total":    total,
            "affected": affected,
            "pct_aff":  affected / n_total * 100.0,
            "max":      max(drift_vals),
            "mean_aff": (total / affected) if affected > 0 else 0.0,
            "elim":     elim,
            "elim_pct": elim / affected * 100.0 if affected > 0 else 100.0,
        })

    col_labels = ["Total Events", "Circuits Affected", "% Affected",
                  "Max per Circuit", "Mean per Affected",
                  "EFaaS Eliminates (#)", "EFaaS Eliminates (%)"]
    row_labels = [r["mode"] for r in rows_data]
    cell_data  = [
        [str(r["total"]), str(r["affected"]), f"{r['pct_aff']:.1f}%",
         str(r["max"]),   f"{r['mean_aff']:.2f}",
         str(r["elim"])   if r["mode"] != "EFaaS" else "N/A",
         f"{r['elim_pct']:.1f}%" if r["mode"] != "EFaaS" else "N/A"]
        for r in rows_data
    ]
    efaas_row_idx = [i for i, m in enumerate(row_labels) if m == "EFaaS"]

    fig, ax = plt.subplots(figsize=(_W1 * 2, _H1))
    ax.axis("off")
    all_col  = ["Mode"] + col_labels
    all_rows = [[row_labels[i]] + r for i, r in enumerate(cell_data)]
    table = ax.table(cellText=all_rows, colLabels=all_col, loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(8.5)
    table.auto_set_column_width(list(range(len(all_col))))
    _style_table(table, row_labels, efaas_row_idx, row_h=0.10, hdr_h=0.12)

    for (r, c), cell in table.get_celld().items():
        if r == 0: continue
        txt = cell.get_text().get_text()
        if "100.0%" in txt or txt == "0":
            ri = r - 1
            if ri not in efaas_row_idx:
                cell.set_facecolor(_BEST_BG); cell.get_text().set_fontweight("bold")

    slug = _title_to_slug(title)
    _save_csv(output_dir, slug, all_col, all_rows)
    fig.tight_layout()
    return _save(fig, output_dir, slug)


# ── T4–T6  Per-circuit detail tables ─────────────────────────────────────────

def table_per_band(data: Dict, output_dir: str, band: str) -> str:
    _set_pub_style()
    title = f"Per-Circuit Detail {band.capitalize()}"
    levels     = CATALOG[band]
    sub_cols   = []
    for mp in MODES:
        lbl = MODE_LABELS[mp]
        sub_cols += [f"{lbl}\nTTNS(s)", f"{lbl}\nQDC%", f"{lbl}\nDrift"]
    col_labels = ["Family", "Qubits", "Reps"] + sub_cols
    row_labels = [_short_label(lvl).replace("\n", " ") for lvl in levels]

    cell_data = []
    for lvl in levels:
        row = [_family(lvl), str(_extract_qubits(lvl)), str(_extract_reps(lvl))]
        for mp in MODES:
            s = data[band][lvl].get(mp)
            if s:
                row += [f"{s['mean_ttns_s']:.2f}", f"{s['qdc_pct']:.1f}",
                        str(int(s.get("drift_penalties", 0)))]
            else:
                row += ["—", "—", "—"]
        cell_data.append(row)

    efaas_idx  = list(MODES.keys()).index("efaas")
    n_rows     = len(row_labels)
    n_cols_all = 1 + len(col_labels)
    fig_w      = min(28, 3.0 + len(col_labels) * 0.85)
    fig_h      = max(_H1, n_rows * 0.50 + 1.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    all_col  = ["Circuit"] + col_labels
    all_rows = [[row_labels[i]] + r for i, r in enumerate(cell_data)]
    table = ax.table(cellText=all_rows, colLabels=all_col, loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(7)
    table.auto_set_column_width(list(range(n_cols_all)))
    _style_table(table, row_labels, [], row_h=0.075, hdr_h=0.09)

    for (r, c), cell in table.get_celld().items():
        if r == 0: continue
        ci = c - 1  # 0-based in col_labels
        if ci >= 3:
            mp_idx = (ci - 3) // 3
            if list(MODES.keys())[mp_idx] == "efaas":
                cell.set_facecolor(_EFAAS_BG)
                cell.get_text().set_color(_EFAAS_FG)
                cell.get_text().set_fontweight("bold")
        txt = cell.get_text().get_text()
        if ci >= 3 and (ci - 3) % 3 == 2:
            if txt == "0":
                cell.set_facecolor(_BEST_BG)
            elif txt not in ("—",):
                try:
                    if float(txt) > 0:
                        cell.set_facecolor(_WORST_BG)
                except Exception:
                    pass

    slug = _title_to_slug(title)
    _save_csv(output_dir, slug, all_col, all_rows)
    fig.tight_layout()
    return _save(fig, output_dir, slug)


# ─────────────────────────────────────────────────────────────────────────────
# Master driver
# ─────────────────────────────────────────────────────────────────────────────

def generate_all(output_dir: str, figures_dir: str) -> List[str]:
    print("\n" + "═" * 68)
    print("  CIRCUIT PLOTTER — IEEE Publication Figures + Tables")
    print("═" * 68)
    print("\n[1/2] Loading JSON results …")
    data = load_all(output_dir)
    loaded = sum(1 for band in data for lvl in data[band]
                 for mp in data[band][lvl] if data[band][lvl][mp] is not None)
    total  = sum(len(v) for v in CATALOG.values()) * len(MODES)
    print(f"      Loaded {loaded}/{total} result files.\n")

    print("[2/2] Rendering …\n")
    paths: List[str] = []

    print("── Main Comparison Figures ─────────────────────────────────")
    for band in CATALOG:
        paths.append(fig_ttns_per_band(data, figures_dir, band))
        paths.append(fig_qdc_per_band(data, figures_dir, band))
    paths.append(fig_band_summary(data, figures_dir))
    paths.append(fig_efaas_improvement(data, figures_dir))
    paths.append(fig_scaling(data, figures_dir))
    paths.append(fig_heatmap(data, figures_dir))
    paths.append(fig_energy_race(data, figures_dir))
    paths.append(fig_ttns_boxplot(data, figures_dir))
    paths.append(fig_radar(data, figures_dir))
    paths.append(fig_convergence_scatter(data, figures_dir))
    paths.append(fig_secondary_metrics(data, figures_dir))

    print("\n── Drift Analysis Figures ──────────────────────────────────")
    paths.append(fig_drift_heatmap(data, figures_dir))
    paths.append(fig_drift_per_band(data, figures_dir))
    paths.append(fig_calib_drift_scatter(data, figures_dir))
    paths.append(fig_drift_qubit_scaling(data, figures_dir))
    paths.append(fig_drift_timeline(data, figures_dir, output_dir))

    print("\n── Table Figures (PDF + PNG + CSV) ─────────────────────────")
    paths.append(table_band_summary(data, figures_dir))
    paths.append(table_efaas_improvement(data, figures_dir))
    paths.append(table_drift_analysis(data, figures_dir))
    for band in CATALOG:
        paths.append(table_per_band(data, figures_dir, band))

    n_figs = sum(1 for p in paths if p.endswith(".png"))
    print("\n" + "═" * 68)
    print(f"  Done. {n_figs} figures saved to: {figures_dir}")
    print("═" * 68 + "\n")
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IEEE circuit benchmark plots + tables for Entangled-FaaS."
    )
    base = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument("--output-dir",  default=os.path.join(base, "output"))
    parser.add_argument("--figures-dir", default=os.path.join(base, "figures", "circuits_ieee"))
    args = parser.parse_args()
    generate_all(args.output_dir, args.figures_dir)