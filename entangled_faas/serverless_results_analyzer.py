#!/usr/bin/env python3
"""
serverless_results_analyzer.py — Aggregate Batch Results & Calculate Improvements
==================================================================================
Reads batch job outputs, aggregates by mode/circuit, and calculates key improvement metrics.

Usage:
    python3 serverless_results_analyzer.py \\
        --batch-results output/batch_results/batch_run_001_*.json \\
        --output analysis_results.json --plot
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import statistics

# ─────────────────────────────────────────────────────────────────────────────

# Mode label mappings 
MODE_LABEL_MAP = {
    "Entangled-FaaS": "EFaaS",
    "Standard Batch-Queue (SBQ)": "SBQ",
    "Pure FaaS (PF)": "PF",
    "Static Reservation (SR)": "SR",
    "Pilot-Quantum (PQ)": "PQ",
}

class ResultsAggregator:
    """Aggregate batch job results by mode and circuit."""

    def __init__(self):
        self.raw_results: Dict = {}
        self.aggregated: Dict = {}

    def load_batch_results(self, result_file: str) -> Dict:
        """Load batch execution results JSON."""
        with open(result_file, "r") as f:
            return json.load(f)

    def extract_metrics(self, output: Dict) -> Dict:
        """Extract key metrics from serverless job output."""
        mode = output.get("mode")
        # Convert full mode name to label if needed
        if mode in MODE_LABEL_MAP:
            mode = MODE_LABEL_MAP[mode]
        
        return {
            "mode": mode,
            "level": output.get("level"),
            "mean_ttns_s": output.get("mean_ttns_s"),
            "std_ttns_s": output.get("std_ttns_s"),
            "qdc_pct": output.get("qdc_pct"),
            "convergence_time_s": output.get("convergence_time_s"),
            "mean_energy_ha": output.get("mean_energy_ha"),
            "drift_penalties": output.get("drift_penalties"),
            "iterations_completed": output.get("iterations_completed"),
        }

    def aggregate_by_mode_circuit(self, batch_results: Dict) -> Dict:
        """Group results by mode and circuit level."""
        aggregated = defaultdict(lambda: defaultdict(list))

        for result in batch_results.get("results", []):
            if result.get("status") != "completed":
                continue

            output = result.get("output", {})
            metrics = self.extract_metrics(output)

            mode = metrics.get("mode")
            # Convert full mode name to label
            if mode in MODE_LABEL_MAP:
                mode = MODE_LABEL_MAP[mode]
            
            level = metrics.get("level")

            aggregated[mode][level].append(metrics)

        return dict(aggregated)

    def calculate_aggregates(self, aggregated: Dict) -> Dict:
        """Calculate mean/std for each mode-circuit combination."""
        summary = {}

        for mode, circuits in aggregated.items():
            summary[mode] = {}
            for level, metrics_list in circuits.items():
                if not metrics_list:
                    continue

                # Aggregate across runs (seeds)
                ttns_values = [m["mean_ttns_s"] for m in metrics_list if m["mean_ttns_s"]]
                qdc_values = [m["qdc_pct"] for m in metrics_list if m["qdc_pct"]]
                conv_values = [m["convergence_time_s"] for m in metrics_list if m["convergence_time_s"]]
                iter_values = [m["iterations_completed"] for m in metrics_list if m.get("iterations_completed") is not None]

                def _stats(values: List[float]) -> Dict:
                    if not values:
                        return {"min": None, "max": None, "mean": None, "samples": 0}
                    return {
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "samples": len(values),
                    }

                summary[mode][level] = {
                    "mean_ttns_s": statistics.mean(ttns_values) if ttns_values else None,
                    "qdc_pct": statistics.mean(qdc_values) if qdc_values else None,
                    "convergence_time_s": statistics.mean(conv_values) if conv_values else None,
                    "iterations_completed": statistics.mean(iter_values) if iter_values else None,
                    "ttns_stats": _stats(ttns_values),
                    "qdc_stats": _stats(qdc_values),
                    "convergence_time_stats": _stats(conv_values),
                    "iterations_stats": _stats(iter_values),
                    "samples": len(metrics_list),
                }

        return summary

    def calculate_improvements(self, summary: Dict, baseline_mode: str = "SBQ") -> Dict:
        """Calculate improvements of EFaaS vs all baselines."""
        improvements = {}

        if "EFaaS" not in summary:
            print(f"Warning: EFaaS not found in results")
            return improvements

        efaas_metrics = summary["EFaaS"]

        for mode in summary:
            if mode == "EFaaS":
                continue

            improvements[mode] = {}
            baseline_metrics = summary[mode]

            # Calculate improvements for each circuit level
            for level in efaas_metrics:
                if level not in baseline_metrics:
                    continue

                efaas = efaas_metrics[level]
                baseline = baseline_metrics[level]

                # TTNS reduction (% improvement)
                ttns_reduction = None
                if baseline["mean_ttns_s"] and efaas["mean_ttns_s"]:
                    ttns_reduction = 100 * (1 - efaas["mean_ttns_s"] / baseline["mean_ttns_s"])

                # QDC improvement (percentage points)
                qdc_improvement = None
                if baseline["qdc_pct"] and efaas["qdc_pct"]:
                    qdc_improvement = efaas["qdc_pct"] - baseline["qdc_pct"]

                # Convergence speedup (% faster)
                conv_speedup = None
                if baseline["convergence_time_s"] and efaas["convergence_time_s"]:
                    conv_speedup = 100 * (1 - efaas["convergence_time_s"] / baseline["convergence_time_s"])

                improvements[mode][level] = {
                    "ttns_reduction_pct": ttns_reduction,
                    "qdc_improvement_pp": qdc_improvement,
                    "convergence_speedup_pct": conv_speedup,
                }

        return improvements

    def generate_report(
        self,
        summary: Dict,
        improvements: Dict,
        num_completed: int,
    ) -> Dict:
        """Generate comprehensive analysis report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "jobs_analyzed": num_completed,
                "modes": list(summary.keys()),
            },
            "metrics_by_mode_circuit": summary,
            "improvements_efaas_vs_baselines": improvements,
            "key_findings": self._extract_key_findings(improvements),
        }
        return report

    def _extract_key_findings(self, improvements: Dict) -> Dict:
        """Extract headline metrics across all comparisons."""
        findings = {}

        for baseline_mode, level_improvements in improvements.items():
            ttns_reductions = []
            qdc_improvements = []
            conv_speedups = []

            for level, metrics in level_improvements.items():
                if metrics.get("ttns_reduction_pct"):
                    ttns_reductions.append(metrics["ttns_reduction_pct"])
                if metrics.get("qdc_improvement_pp"):
                    qdc_improvements.append(metrics["qdc_improvement_pp"])
                if metrics.get("convergence_speedup_pct"):
                    conv_speedups.append(metrics["convergence_speedup_pct"])

            if ttns_reductions:
                findings[f"vs_{baseline_mode}"] = {
                    "ttns_reduction_pct": {
                        "min": min(ttns_reductions),
                        "max": max(ttns_reductions),
                        "mean": statistics.mean(ttns_reductions),
                    },
                    "qdc_improvement_pp": {
                        "min": min(qdc_improvements) if qdc_improvements else None,
                        "max": max(qdc_improvements) if qdc_improvements else None,
                        "mean": statistics.mean(qdc_improvements) if qdc_improvements else None,
                    },
                    "convergence_speedup_pct": {
                        "min": min(conv_speedups) if conv_speedups else None,
                        "max": max(conv_speedups) if conv_speedups else None,
                        "mean": statistics.mean(conv_speedups) if conv_speedups else None,
                    },
                }

        return findings

# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyze serverless batch results"
    )
    parser.add_argument(
        "--batch-results",
        required=True,
        help="Path to batch results JSON file",
    )
    parser.add_argument(
        "--output",
        default="analysis_results.json",
        help="Output analysis file (default: analysis_results.json)",
    )

    args = parser.parse_args()

    # Load and analyze
    print(f"\nLoading batch results from: {args.batch_results}")
    aggregator = ResultsAggregator()
    batch_results = aggregator.load_batch_results(args.batch_results)

    print(f"  Submitted: {batch_results.get('submitted', 0)}")
    print(f"  Completed: {batch_results.get('completed', 0)}")

    # Aggregate results
    print("\nAggregating by mode and circuit...")
    aggregated = aggregator.aggregate_by_mode_circuit(batch_results)
    summary = aggregator.calculate_aggregates(aggregated)

    # Calculate improvements
    print("Calculating improvements...")
    improvements = aggregator.calculate_improvements(summary)

    # Generate report
    report = aggregator.generate_report(
        summary,
        improvements,
        batch_results.get("completed", 0),
    )

    # Save report
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nAnalysis report saved to: {args.output}")

    # Print summary
    print("\n" + "="*70)
    print("KEY FINDINGS")
    print("="*70)
    for baseline, findings in report.get("key_findings", {}).items():
        print(f"\n{baseline}:")
        if "ttns_reduction_pct" in findings:
            ttns = findings["ttns_reduction_pct"]
            print(f"  TTNS Reduction:   {ttns['min']:.1f}% - {ttns['max']:.1f}% (avg {ttns['mean']:.1f}%)")
        if "qdc_improvement_pp" in findings:
            qdc = findings["qdc_improvement_pp"]
            if qdc["mean"]:
                print(f"  QDC Improvement:  {qdc['min']:.2f} - {qdc['max']:.2f} pp (avg {qdc['mean']:.2f} pp)")
        if "convergence_speedup_pct" in findings:
            conv = findings["convergence_speedup_pct"]
            if conv["mean"]:
                print(f"  Convergence:      {conv['min']:.1f}% - {conv['max']:.1f}% (avg {conv['mean']:.1f}%)")

    print()


if __name__ == "__main__":
    main()
