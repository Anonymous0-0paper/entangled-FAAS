"""
plot_motivation.py — generates two introductory motivational figures:
  1. vqe_cumulative_wallclock_motivation — cumulative wall-clock time vs iterations
  2. vqe_iteration_time_breakdown       — per-iteration time component breakdown
Saves to figures/results/ as PDF + PNG.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures", "results")
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — Cumulative wall-clock time (PQ removed)
# ─────────────────────────────────────────────────────────────────────────────
MODES_CUM = {
    "SBQ":   {"ttns": 48.4,  "color": "#d62728", "ls": "--",  "lw": 2.0},
    "PF":    {"ttns": 54.5,  "color": "#ff7f0e", "ls": ":",   "lw": 2.0},
    "SR":    {"ttns": 4.3,   "color": "#1f77b4", "ls": "-.",  "lw": 1.8},
    "EFaaS": {"ttns": 3.6,   "color": "#2ca02c", "ls": "-",   "lw": 2.8},
}

MAX_ITER = 1000
iters = np.arange(0, MAX_ITER + 1)

fig1, ax1 = plt.subplots(figsize=(8, 5))
fig1.patch.set_facecolor("white")
ax1.set_facecolor("white")

for name, cfg in MODES_CUM.items():
    ax1.plot(iters, iters * cfg["ttns"] / 3600,
             color=cfg["color"], linestyle=cfg["ls"],
             linewidth=cfg["lw"], label=name, zorder=3)

y_sbq   = MAX_ITER * MODES_CUM["SBQ"]["ttns"]  / 3600
y_efaas = MAX_ITER * MODES_CUM["EFaaS"]["ttns"] / 3600
y_pf    = MAX_ITER * MODES_CUM["PF"]["ttns"]    / 3600

ax1.annotate("",
    xy=(MAX_ITER, y_efaas + 0.15), xytext=(MAX_ITER, y_sbq - 0.15),
    arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.5), zorder=5)
ax1.text(MAX_ITER - 38, (y_sbq + y_efaas) / 2, "13×\nfaster",
         ha="right", va="center", fontsize=13, color="#555555", fontweight="bold")

ax1.fill_between(iters,
                 iters * MODES_CUM["EFaaS"]["ttns"] / 3600,
                 iters * MODES_CUM["SBQ"]["ttns"]   / 3600,
                 alpha=0.08, color=MODES_CUM["SBQ"]["color"])

for h, lbl in [(1, "1 h"), (4, "4 h"), (8, "8 h"), (13.4, "13.4 h (SBQ)")]:
    ax1.axhline(h, color="#cccccc", lw=0.8, ls="--", zorder=1)
    ax1.text(2, h + 0.12, lbl, fontsize=11, color="#888888", va="bottom")

ax1.set_xlabel("VQE Iteration", fontsize=15)
ax1.set_ylabel("Cumulative Wall-Clock Time (hours)", fontsize=15)
ax1.tick_params(labelsize=13)
ax1.set_xlim(0, MAX_ITER)
ax1.set_ylim(0, y_pf * 1.10)
ax1.legend(fontsize=14, loc="upper left", framealpha=0.9)
ax1.spines[["top", "right"]].set_visible(False)

for ext in ("pdf", "png"):
    fig1.savefig(os.path.join(OUT, f"vqe_cumulative_wallclock_motivation.{ext}"),
                 dpi=300, bbox_inches="tight", facecolor="white")
    print(f"saved: vqe_cumulative_wallclock_motivation.{ext}")
plt.close(fig1)

# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — Per-iteration time breakdown (stacked horizontal bar)
# t_queue dominates SBQ/PF; EFaaS has near-zero queue + overlapped CPU
# ─────────────────────────────────────────────────────────────────────────────
# Component breakdown derived from TTNS and simulation parameters
#   t_qpu = 2.0s, t_net = 0.5s, t_calib = calib_ratio * 30s averaged per iter
#   t_cpu = 1.5s (fully overlapped in EFaaS via Quantum Future → 0 effective)
#   t_queue = TTNS - t_qpu - t_net - t_calib - t_cpu (clamped to 0)
T_QPU  = 2.0
T_NET  = 0.5
T_CPU  = 1.5   # shown as "Classical CPU"
# calib overhead per iteration (calib_ratio * t_calib penalty)
CALIB = {"SBQ": 0.1269 * 30, "PF": 0.1203 * 30, "SR": 0.0579 * 30, "EFaaS": 0.0}
TTNS  = {"SBQ": 48.4,        "PF": 54.5,         "SR": 4.3,          "EFaaS": 3.6}

modes_bar = ["SBQ", "PF", "SR", "EFaaS"]
colors_bar = {
    "SBQ":   "#d62728",
    "PF":    "#ff7f0e",
    "SR":    "#1f77b4",
    "EFaaS": "#2ca02c",
}

component_colors = {
    "Queue wait":      "#e88e8e",
    "Re-calibration":  "#f5c06e",
    "Network":         "#aec7e8",
    "Classical CPU":   "#c5b0d5",
    "QPU execution":   "#98df8a",
    "CPU (overlapped)": "#d9f0d3",
}

rows = []
for m in modes_bar:
    t_calib = CALIB[m]
    t_queue = max(0.0, TTNS[m] - T_QPU - T_NET - t_calib - T_CPU)
    if m == "EFaaS":
        # Quantum Future overlaps CPU with QPU; net CPU contribution = 0
        rows.append({
            "mode": m,
            "Queue wait":      0.0,
            "Re-calibration":  0.0,
            "Network":         T_NET,
            "Classical CPU":   0.0,
            "QPU execution":   T_QPU,
            "CPU (overlapped)": T_CPU,
        })
    else:
        rows.append({
            "mode": m,
            "Queue wait":      t_queue,
            "Re-calibration":  t_calib,
            "Network":         T_NET,
            "Classical CPU":   T_CPU,
            "QPU execution":   T_QPU,
            "CPU (overlapped)": 0.0,
        })

components = ["Queue wait", "Re-calibration", "Classical CPU",
              "CPU (overlapped)", "Network", "QPU execution"]

fig2, ax2 = plt.subplots(figsize=(8, 5))
fig2.patch.set_facecolor("white")
ax2.set_facecolor("white")

y_pos = np.arange(len(modes_bar))
bar_h = 0.52
lefts = np.zeros(len(modes_bar))

for comp in components:
    vals = np.array([r[comp] for r in rows])
    bars = ax2.barh(y_pos, vals, left=lefts, height=bar_h,
                    color=component_colors[comp],
                    edgecolor="white", linewidth=0.6,
                    label=comp if any(v > 0 for v in vals) else "_nolegend_")
    # label each segment if wide enough
    for i, (v, l) in enumerate(zip(vals, lefts)):
        if v > 1.0:
            ax2.text(l + v / 2, y_pos[i], f"{v:.1f}s",
                     ha="center", va="center", fontsize=11,
                     color="white" if comp in ("Queue wait", "QPU execution") else "#333333",
                     fontweight="bold")
    lefts += vals

# total TTNS label at end of each bar
for i, m in enumerate(modes_bar):
    ax2.text(lefts[i] + 0.4, y_pos[i], f"{TTNS[m]:.1f} s",
             va="center", fontsize=13, color="#333333", fontweight="bold")

ax2.set_yticks(y_pos)
ax2.set_yticklabels(modes_bar, fontsize=15)
ax2.set_xlabel("Per-Iteration Time (seconds)", fontsize=15)
ax2.tick_params(axis="x", labelsize=13)
ax2.set_xlim(0, max(TTNS.values()) * 1.18)
ax2.spines[["top", "right"]].set_visible(False)

# legend — only entries with data
handles, labels = ax2.get_legend_handles_labels()
ax2.legend(handles, labels, fontsize=12, loc="lower right",
           framealpha=0.9, ncol=2)

# "wasted" brace annotation for SBQ
wasted = TTNS["SBQ"] - T_QPU - T_NET
ax2.annotate("", xy=(T_QPU + T_NET, y_pos[0] + bar_h / 2 + 0.08),
             xytext=(TTNS["SBQ"], y_pos[0] + bar_h / 2 + 0.08),
             arrowprops=dict(arrowstyle="<->", color="#999999", lw=1.2))
ax2.text((T_QPU + T_NET + TTNS["SBQ"]) / 2, y_pos[0] + bar_h / 2 + 0.22,
         f"{wasted:.0f} s wasted", ha="center", fontsize=11,
         color="#999999", style="italic")

fig2.tight_layout()
for ext in ("pdf", "png"):
    fig2.savefig(os.path.join(OUT, f"vqe_iteration_time_breakdown.{ext}"),
                 dpi=300, bbox_inches="tight", facecolor="white")
    print(f"saved: vqe_iteration_time_breakdown.{ext}")
plt.close(fig2)
