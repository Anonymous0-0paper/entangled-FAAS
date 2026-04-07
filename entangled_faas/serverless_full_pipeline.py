#!/usr/bin/env python3
"""
serverless_full_pipeline.py — Full Serverless Workflow Orchestrator
====================================================================
Orchestrates the complete end-to-end serverless pipeline:
  1. Generate batch jobs for all modes/circuits
  2. Execute jobs locally (or submit to provider)
  3. Aggregate results
  4. Analyze and compute improvements
  5. Generate comparison plots
  6. Create summary report

Usage:
    python3 serverless_full_pipeline.py \\
        --modes efaas,sbq,pq --circuits simple,medium \\
        --max-jobs 20 --run-name "full_serverless_demo"
"""

import json
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────

class FullServerlessPipeline:
    """Orchestrate complete serverless workflow."""

    def __init__(self, run_name: str = "serverless_pipeline"):
        self.run_name = run_name
        self.run_dir = Path(f"output/{run_name}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = datetime.now()
        self.log_file = self.run_dir / "pipeline.log"

    def log(self, message: str, level: str = "INFO") -> None:
        """Log message to file and stdout."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        with open(self.log_file, "a") as f:
            f.write(log_msg + "\n")

    def run_step(self, name: str, cmd: list, cwd: Optional[str] = None) -> bool:
        """Run a pipeline step."""
        self.log(f"\n{'='*70}")
        self.log(f"STEP: {name}")
        self.log(f"{'='*70}")
        self.log(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                self.log(f"✓ {name} completed successfully")
                if result.stdout:
                    self.log(result.stdout, level="OUTPUT")
                return True
            else:
                self.log(f"✗ {name} failed with code {result.returncode}", level="ERROR")
                if result.stderr:
                    self.log(result.stderr, level="ERROR")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"✗ {name} timed out", level="ERROR")
            return False
        except Exception as e:
            self.log(f"✗ {name} error: {str(e)}", level="ERROR")
            return False

    def find_latest_batch_results(self) -> Optional[str]:
        """Find the most recent batch results file."""
        batch_results_dir = Path("output/batch_results")
        if not batch_results_dir.exists():
            return None

        result_files = list(batch_results_dir.glob("*.json"))
        if not result_files:
            return None

        # Sort by modification time, get latest
        latest = sorted(result_files, key=lambda p: p.stat().st_mtime)[-1]
        return str(latest)

    def run_full_pipeline(
        self,
        modes: str,
        circuits: str,
        max_jobs: Optional[int] = None,
    ) -> bool:
        """Execute the complete pipeline."""
        self.log(f"Starting Full Serverless Pipeline: {self.run_name}")
        self.log(f"Modes: {modes}")
        self.log(f"Circuits: {circuits}")
        if max_jobs:
            self.log(f"Max jobs: {max_jobs}")

        # Step 1: Generate and run batch jobs
        batch_cmd = [
            "python3",
            "serverless_batch_submit.py",
            "--mode", modes,
            "--circuits", circuits,
            "--output", self.run_name,
        ]
        if max_jobs:
            batch_cmd.extend(["--max-jobs", str(max_jobs)])
        batch_cmd.append("--local")

        if not self.run_step("Generate and Execute Batch Jobs", batch_cmd):
            self.log("Pipeline aborted: batch job execution failed", level="ERROR")
            return False

        # Find batch results file
        batch_file = self.find_latest_batch_results()
        if not batch_file:
            self.log("Could not find batch results file", level="ERROR")
            return False

        self.log(f"Found batch results: {batch_file}")

        # Step 2: Analyze results
        analysis_file = self.run_dir / "analysis_results.json"
        analysis_cmd = [
            "python3",
            "serverless_results_analyzer.py",
            "--batch-results", batch_file,
            "--output", str(analysis_file),
        ]

        if not self.run_step("Analyze Results", analysis_cmd):
            self.log("Pipeline aborted: results analysis failed", level="ERROR")
            return False

        # Step 3: Generate plots
        plots_dir = self.run_dir / "plots"
        plotter_cmd = [
            "python3",
            "serverless_plotter.py",
            "--analysis", str(analysis_file),
            "--output", str(plots_dir),
            "--format", "png",
        ]

        if not self.run_step("Generate Comparison Plots", plotter_cmd):
            self.log("Warning: plot generation failed (matplotlib may not be available)", level="WARN")
            # Don't abort on plot failure

        # Step 4: Generate summary report
        self.generate_summary_report(analysis_file, batch_file)

        self.log(f"\n{'='*70}")
        self.log("PIPELINE COMPLETED SUCCESSFULLY")
        self.log(f"{'='*70}")
        self.log(f"Run directory: {self.run_dir.absolute()}")
        self.log(f"Analysis file: {analysis_file}")
        if plots_dir.exists():
            plot_count = len(list(plots_dir.glob("*.png"))) + len(list(plots_dir.glob("*.pdf")))
            self.log(f"Plots generated: {plot_count} files")
        self.log(f"Total time: {datetime.now() - self.start_time}")

        return True

    def generate_summary_report(self, analysis_file: Path, batch_file: str) -> None:
        """Generate human-readable summary report."""
        try:
            with open(analysis_file, "r") as f:
                analysis = json.load(f)

            report_file = self.run_dir / "SUMMARY.md"
            with open(report_file, "w") as f:
                f.write("# Serverless Batch Execution Summary\n\n")
                f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")

                # Batch info
                with open(batch_file, "r") as bf:
                    batch = json.load(bf)
                f.write(f"## Batch Execution\n\n")
                f.write(f"- **Submitted**: {batch.get('submitted', 0)} jobs\n")
                f.write(f"- **Completed**: {batch.get('completed', 0)} jobs\n")
                f.write(f"- **Failed**: {batch.get('failed', 0)} jobs\n")
                f.write(f"- **Success Rate**: {100*batch.get('completed', 0)/max(1, batch.get('submitted', 1)):.1f}%\n\n")

                # Key findings
                findings = analysis.get("key_findings", {})
                f.write(f"## Key Findings\n\n")
                for baseline, metrics in findings.items():
                    f.write(f"### {baseline}\n\n")
                    if "ttns_reduction_pct" in metrics:
                        ttns = metrics["ttns_reduction_pct"]
                        f.write(f"**TTNS Reduction**: {ttns['min']:.1f}% - {ttns['max']:.1f}% (avg {ttns['mean']:.1f}%)\n\n")
                    if "qdc_improvement_pp" in metrics and metrics["qdc_improvement_pp"]["mean"]:
                        qdc = metrics["qdc_improvement_pp"]
                        f.write(f"**QDC Improvement**: {qdc['min']:.2f} - {qdc['max']:.2f} pp (avg {qdc['mean']:.2f} pp)\n\n")
                    if "convergence_speedup_pct" in metrics and metrics["convergence_speedup_pct"]["mean"]:
                        conv = metrics["convergence_speedup_pct"]
                        f.write(f"**Convergence Speedup**: {conv['min']:.1f}% - {conv['max']:.1f}% (avg {conv['mean']:.1f}%)\n\n")

                # Metrics by mode
                summary = analysis.get("metrics_by_mode_circuit", {})
                f.write(f"## Detailed Metrics\n\n")
                for mode, circuits in summary.items():
                    f.write(f"### {mode}\n\n")
                    for level, metrics in circuits.items():
                        f.write(f"**{level}**\n")
                        f.write(f"- Mean TTNS: {metrics.get('mean_ttns_s', 'N/A'):.2f}s\n")
                        f.write(f"- QDC: {metrics.get('qdc_pct', 'N/A'):.2f}%\n")
                        f.write(f"- Convergence: {metrics.get('convergence_time_s', 'N/A'):.2f}s\n")
                        f.write(f"- Samples: {metrics.get('samples', 0)}\n\n")

            self.log(f"Summary report: {report_file}")

        except Exception as e:
            self.log(f"Error generating summary report: {str(e)}", level="WARN")


def main():
    parser = argparse.ArgumentParser(
        description="Run full serverless end-to-end pipeline"
    )
    parser.add_argument(
        "--modes",
        default="efaas,sbq,pq",
        help="Modes to test (default: efaas,sbq,pq)",
    )
    parser.add_argument(
        "--circuits",
        default="simple,medium",
        help="Circuit types (default: simple,medium)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Limit total jobs (default: unlimited)",
    )
    parser.add_argument(
        "--run-name",
        default="full_serverless_demo",
        help="Name of this run (default: full_serverless_demo)",
    )

    args = parser.parse_args()

    pipeline = FullServerlessPipeline(run_name=args.run_name)
    success = pipeline.run_full_pipeline(
        modes=args.modes,
        circuits=args.circuits,
        max_jobs=args.max_jobs,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
