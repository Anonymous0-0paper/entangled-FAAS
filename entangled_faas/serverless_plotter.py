#!/usr/bin/env python3
"""
serverless_plotter.py — Visualize Batch Results & Improvements
==============================================================
Creates comparison plots of EFaaS vs baselines showing TTNS, QDC, and convergence metrics.

Usage:
    python3 serverless_plotter.py \\
        --analysis analysis_results.json \\
        --output figs_batch_improvements \\
        --format png
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import statistics

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available. Plots will not be generated.")

# ─────────────────────────────────────────────────────────────────────────────

class BatchPlotter:
    """Generate comparison plots from analysis results."""

    def __init__(self, output_dir: str = "figs_batch_improvements", fmt: str = "png"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.fmt = fmt
        self.dpi = 300

    def create_improvement_bar_chart(
        self,
        improvements: Dict,
        metric: str = "ttns_reduction_pct",
        title: str = "EFaaS TTNS Reduction vs Baselines",
    ) -> str:
        """Bar chart comparing metric across baselines."""
        if not HAS_MATPLOTLIB:
            return ""

        fig, ax = plt.subplots(figsize=(12, 6))

        baselines = []
        values = []
        colors = ["#2ca02c", "#d62728", "#ff7f0e", "#1f77b4", "#9467bd"]

        for baseline, level_data in improvements.items():
            metric_values = []
            for level, metrics in level_data.items():
                if metric in metrics and metrics[metric] is not None:
                    metric_values.append(metrics[metric])

            if metric_values:
                baselines.append(baseline)
                values.append(statistics.mean(metric_values))

        if not values:
            print("Warning: No data for bar chart")
            return ""

        x = np.arange(len(baselines))
        bars = ax.bar(x, values, color=colors[:len(baselines)], edgecolor="black", linewidth=1.5)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%' if metric.endswith("pct") else f'{height:.2f}',
                ha='center', va='bottom', fontsize=11, fontweight='bold'
            )

        ax.set_xlabel("Baseline Mode", fontsize=12, fontweight='bold')
        ax.set_ylabel(self._metric_label(metric), fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(baselines, fontsize=11)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        plt.tight_layout()
        output_file = self.output_dir / f"improvement_{metric}.{self.fmt}"
        plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
        plt.close()

        return str(output_file)

    def create_metric_heatmap(
        self,
        summary: Dict,
        metric: str = "mean_ttns_s",
        title: str = "TTNS by Mode and Circuit",
    ) -> str:
        """Heatmap of metric values across modes and circuits."""
        if not HAS_MATPLOTLIB:
            return ""

        # Collect all circuit levels
        all_levels = set()
        for mode, circuits in summary.items():
            all_levels.update(circuits.keys())
        all_levels = sorted(list(all_levels))

        modes = sorted(list(summary.keys()))
        data = np.zeros((len(modes), len(all_levels)))

        for i, mode in enumerate(modes):
            for j, level in enumerate(all_levels):
                if level in summary[mode]:
                    value = summary[mode][level].get(metric)
                    data[i, j] = value if value else np.nan

        fig, ax = plt.subplots(figsize=(14, 6))
        im = ax.imshow(data, cmap='RdYlGn_r', aspect='auto')

        # Labels
        ax.set_xticks(np.arange(len(all_levels)))
        ax.set_yticks(np.arange(len(modes)))
        ax.set_xticklabels(all_levels, fontsize=9)
        ax.set_yticklabels(modes, fontsize=10)

        # Rotate x labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(self._metric_label(metric), rotation=270, labelpad=20)

        # Add text annotations
        for i in range(len(modes)):
            for j in range(len(all_levels)):
                value = data[i, j]
                if not np.isnan(value):
                    text = ax.text(j, i, f'{value:.1f}',
                                  ha="center", va="center", color="black", fontsize=9)

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()

        output_file = self.output_dir / f"heatmap_{metric}.{self.fmt}"
        plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
        plt.close()

        return str(output_file)

    def create_improvement_summary_plot(
        self,
        improvements: Dict,
    ) -> str:
        """Multi-panel plot showing all three key metrics."""
        if not HAS_MATPLOTLIB:
            return ""

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        metrics = [
            ("ttns_reduction_pct", "TTNS Reduction (%)", 0),
            ("qdc_improvement_pp", "QDC Improvement (pp)", 1),
            ("convergence_speedup_pct", "Convergence Speedup (%)", 2),
        ]

        baselines = list(improvements.keys())
        x = np.arange(len(baselines))
        width = 0.6
        colors = ["#2ca02c", "#d62728", "#ff7f0e", "#1f77b4", "#9467bd"]

        for metric, ylabel, ax_idx in metrics:
            ax = axes[ax_idx]
            values = []

            for baseline in baselines:
                metric_values = []
                for level, metrics_dict in improvements[baseline].items():
                    if metric in metrics_dict and metrics_dict[metric] is not None:
                        metric_values.append(metrics_dict[metric])

                if metric_values:
                    values.append(statistics.mean(metric_values))
                else:
                    values.append(0)

            bars = ax.bar(x, values, width, color=colors[:len(baselines)], 
                         edgecolor="black", linewidth=1.5)

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}' if metric.endswith("pct") else f'{height:.2f}',
                           ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax.set_xlabel("Baseline Mode", fontsize=11, fontweight='bold')
            ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
            ax.set_title(ylabel, fontsize=12, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(baselines, fontsize=10)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)

        plt.suptitle("EFaaS Improvements Over Baselines", fontsize=14, fontweight='bold', y=1.00)
        plt.tight_layout()

        output_file = self.output_dir / f"improvements_summary.{self.fmt}"
        plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
        plt.close()

        return str(output_file)

    def create_circuit_comparison_plot(
        self,
        summary: Dict,
    ) -> str:
        """Compare performance across circuit levels by mode."""
        if not HAS_MATPLOTLIB:
            return ""

        # Collect all circuit levels
        all_levels = set()
        for mode, circuits in summary.items():
            all_levels.update(circuits.keys())
        all_levels = sorted(list(all_levels))

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()
        metrics = [
            ("mean_ttns_s", "TTNS (seconds)", 0),
            ("qdc_pct", "QDC (%)", 1),
            ("convergence_time_s", "Convergence Time (seconds)", 2),
            ("iterations_completed", "Iterations Completed", 3),
        ]

        for metric, ylabel, ax_idx in metrics:
            ax = axes[ax_idx]
            x = np.arange(len(all_levels))
            width = 0.15
            modes = sorted(list(summary.keys()))

            for mode_idx, mode in enumerate(modes):
                values = []
                for level in all_levels:
                    if level in summary[mode]:
                        value = summary[mode][level].get(metric)
                        values.append(value if value else 0)
                    else:
                        values.append(0)

                offset = (mode_idx - len(modes)/2) * width
                ax.bar(x + offset, values, width, label=mode, alpha=0.8)

            ax.set_xlabel("Circuit Level", fontsize=10, fontweight='bold')
            ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
            ax.set_title(ylabel, fontsize=11, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(all_levels, fontsize=9, rotation=45, ha='right')
            ax.legend(fontsize=9)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)

        plt.suptitle("Performance Metrics by Circuit Level", fontsize=14, fontweight='bold')
        plt.tight_layout()

        output_file = self.output_dir / f"circuit_comparison.{self.fmt}"
        plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
        plt.close()

        return str(output_file)

    @staticmethod
    def _metric_label(metric: str) -> str:
        """Get human-readable metric label."""
        labels = {
            "ttns_reduction_pct": "TTNS Reduction (%)",
            "qdc_improvement_pp": "QDC Improvement (pp)",
            "convergence_speedup_pct": "Convergence Speedup (%)",
            "mean_ttns_s": "Mean TTNS (s)",
            "qdc_pct": "QDC (%)",
            "convergence_time_s": "Convergence Time (s)",
        }
        return labels.get(metric, metric)

# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Plot batch analysis results"
    )
    parser.add_argument(
        "--analysis",
        required=True,
        help="Path to analysis JSON file",
    )
    parser.add_argument(
        "--output",
        default="figs_batch_improvements",
        help="Output directory for plots (default: figs_batch_improvements)",
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=["png", "pdf", "svg"],
        help="Output format (default: png)",
    )

    args = parser.parse_args()

    # Load analysis
    print(f"\nLoading analysis from: {args.analysis}")
    with open(args.analysis, "r") as f:
        analysis = json.load(f)

    summary = analysis.get("metrics_by_mode_circuit", {})
    improvements = analysis.get("improvements_efaas_vs_baselines", {})

    if not HAS_MATPLOTLIB:
        print("Error: matplotlib not available. Cannot generate plots.")
        return

    # Create plots
    print(f"\nGenerating plots in: {args.output}/")
    plotter = BatchPlotter(output_dir=args.output, fmt=args.format)

    files_created = []

    # Bar charts
    print("  Creating TTNS reduction chart...", end=" ")
    f = plotter.create_improvement_bar_chart(improvements, "ttns_reduction_pct")
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    print("  Creating QDC improvement chart...", end=" ")
    f = plotter.create_improvement_bar_chart(improvements, "qdc_improvement_pp", "EFaaS QDC Improvement vs Baselines")
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    print("  Creating convergence speedup chart...", end=" ")
    f = plotter.create_improvement_bar_chart(improvements, "convergence_speedup_pct", "EFaaS Convergence Speedup vs Baselines")
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    # Summary plot
    print("  Creating summary comparison plot...", end=" ")
    f = plotter.create_improvement_summary_plot(improvements)
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    # Heatmap
    print("  Creating TTNS heatmap...", end=" ")
    f = plotter.create_metric_heatmap(summary, "mean_ttns_s")
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    # Circuit comparison
    print("  Creating circuit comparison plot...", end=" ")
    f = plotter.create_circuit_comparison_plot(summary)
    if f:
        files_created.append(f)
        print("✓")
    else:
        print("✗")

    # Summary
    print(f"\n{'='*70}")
    print(f"PLOTS GENERATED")
    print(f"{'='*70}")
    print(f"Total files created: {len(files_created)}")
    for f in files_created:
        print(f"  {Path(f).name}")
    print()


if __name__ == "__main__":
    main()
