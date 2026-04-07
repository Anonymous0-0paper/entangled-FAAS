#!/usr/bin/env python3
"""
serverless_batch_submit.py — Full Serverless Batch Job Submission
==================================================================
Generates and submits serverless jobs for all mode/circuit combinations.
Can run locally (dry-run) or submit to Qiskit Serverless provider.

Usage:
    python3 serverless_batch_submit.py --mode [all|efaas|sbq|pq|pf|sr] \\
        --circuits [all|simple|medium|complex] \\
        --max-jobs 50 --local --output batch_run_001
"""

import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import subprocess

# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODES = ["EFaaS", "SBQ", "PQ", "PF", "SR"]
DEFAULT_CIRCUITS = ["simple", "medium", "complex"]

MODE_ALIASES = {
    "EFAAS": "Entangled-FaaS",
    "SBQ": "Standard Batch-Queue (SBQ)",
    "PQ": "Pilot-Quantum (PQ)",
    "PF": "Pure FaaS (PF)",
    "SR": "Static Reservation (SR)",
}

CIRCUIT_LEVELS = {
    "simple": ["bv_4q"],
    "medium": ["esu2_6q"],
    "complex": ["esu2_8q", "efficientsu2_10q_r6_full"],
}

# ─────────────────────────────────────────────────────────────────────────────

class BatchJobGenerator:
    """Generate serverless payloads for all combinations."""

    def __init__(self, output_dir: str = "batch_payloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.payloads: List[Dict] = []

    def generate_payload(
        self,
        mode: str,
        level: str,
        seed_offset: int = 0,
        sim_time: float = 1200.0,
        max_iter: int = 500,
        backend: str = "aer",
    ) -> Dict:
        """Create a serverless job payload."""
        payload = {
            "mode": mode,
            "level": level,
            "seed_offset": seed_offset,
            "alpha": 100.0,
            "beta": 5.0,
            "gamma": 1.0,
            "tau_drift": 300.0,
            "verbose": False,
            "config_overrides": {
                "SIM_TIME": sim_time,
                "max_iter": max_iter,
                "QUANTUM_BACKEND": backend,
            },
            "output_filename": f"serverless_batch_{mode}_{level}_{seed_offset}",
        }
        return payload

    def create_batch(
        self,
        modes: List[str],
        circuits: List[str],
        seeds: int = 1,
        max_jobs: Optional[int] = None,
    ) -> List[Dict]:
        """Generate all payload combinations."""
        payloads = []
        job_count = 0

        for mode in modes:
            for circuit_type in circuits:
                for level in CIRCUIT_LEVELS.get(circuit_type, []):
                    for seed in range(seeds):
                        if max_jobs and job_count >= max_jobs:
                            break

                        payload = self.generate_payload(
                            mode=mode,
                            level=f"{circuit_type}_{level}",
                            seed_offset=seed,
                            sim_time=1200.0 if circuit_type == "complex" else 800.0,
                            max_iter=300 if circuit_type == "complex" else 200,
                            backend="aer",
                        )
                        payloads.append(payload)
                        job_count += 1

        self.payloads = payloads
        return payloads

    def save_payloads(self) -> List[str]:
        """Save all payloads to JSON files."""
        saved_files = []
        for i, payload in enumerate(self.payloads):
            filename = self.output_dir / f"payload_{i:04d}.json"
            with open(filename, "w") as f:
                json.dump(payload, f, indent=2)
            saved_files.append(str(filename))
        return saved_files

    def print_summary(self) -> None:
        """Print batch job summary."""
        print(f"\n{'='*70}")
        print(f"BATCH JOB SUMMARY")
        print(f"{'='*70}")
        print(f"Total jobs:       {len(self.payloads)}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"\nPayloads saved:   {len(self.payloads)} files")

        # Count by mode and circuit
        by_mode = {}
        by_circuit = {}
        for p in self.payloads:
            mode = p["mode"]
            level = p["level"]
            by_mode[mode] = by_mode.get(mode, 0) + 1
            by_circuit[level] = by_circuit.get(level, 0) + 1

        print("\nBy Mode:")
        for mode, count in sorted(by_mode.items()):
            print(f"  {mode:20s}: {count:3d} jobs")

        print("\nBy Circuit Level:")
        for level, count in sorted(by_circuit.items()):
            print(f"  {level:30s}: {count:3d} jobs")
        print()

# ─────────────────────────────────────────────────────────────────────────────

class BatchJobSubmitter:
    """Submit batch jobs locally or to Qiskit Serverless."""

    def __init__(self, payload_dir: str = "batch_payloads"):
        self.payload_dir = Path(payload_dir)
        self.results_dir = Path("output/batch_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_locally(self, max_jobs: Optional[int] = None) -> Dict:
        """Execute all payloads locally using serverless_job.py."""
        payload_files = sorted(self.payload_dir.glob("payload_*.json"))
        if max_jobs:
            payload_files = payload_files[:max_jobs]

        results = {
            "submitted": len(payload_files),
            "completed": 0,
            "failed": 0,
            "start_time": datetime.now().isoformat(),
            "results": [],
        }

        for i, payload_file in enumerate(payload_files):
            try:
                job_id = f"job_{i:04d}"
                print(f"\n[{i+1}/{len(payload_files)}] Running {job_id}...", end=" ", flush=True)

                cmd = [
                    "python3",
                    "serverless_job.py",
                    "--payload-file",
                    str(payload_file),
                ]

                result = subprocess.run(
                    cmd,
                    cwd=Path(__file__).parent,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    # Parse output JSON - look for JSON object in stdout
                    try:
                        # Find JSON object in output (skip status messages)
                        output_text = result.stdout
                        json_start = output_text.find('{')
                        if json_start >= 0:
                            output_json = json.loads(output_text[json_start:])
                            summary = output_json.get("summary", {})
                            results["results"].append({
                                "job_id": job_id,
                                "payload_file": str(payload_file),
                                "status": "completed",
                                "output": summary,
                            })
                            results["completed"] += 1
                            mean_ttns = summary.get('mean_ttns_s', 0)
                            print(f"✓ (mean_ttns={mean_ttns:.2f}s)")
                        else:
                            raise ValueError("No JSON object found")
                    except (json.JSONDecodeError, ValueError) as e:
                        results["results"].append({
                            "job_id": job_id,
                            "payload_file": str(payload_file),
                            "status": "failed",
                            "error": f"JSON parse error: {str(e)[:100]}",
                        })
                        results["failed"] += 1
                        print("✗ (JSON parse error)")
                else:
                    results["results"].append({
                        "job_id": job_id,
                        "payload_file": str(payload_file),
                        "status": "failed",
                        "error": result.stderr[:200],
                    })
                    results["failed"] += 1
                    print(f"✗ ({result.returncode})")

            except subprocess.TimeoutExpired:
                results["results"].append({
                    "job_id": f"job_{i:04d}",
                    "payload_file": str(payload_file),
                    "status": "timeout",
                })
                results["failed"] += 1
                print("✗ (timeout)")
            except Exception as e:
                results["results"].append({
                    "job_id": f"job_{i:04d}",
                    "payload_file": str(payload_file),
                    "status": "error",
                    "error": str(e)[:200],
                })
                results["failed"] += 1
                print(f"✗ ({str(e)[:30]})")

        results["end_time"] = datetime.now().isoformat()
        return results

    def submit_to_provider(self, max_jobs: Optional[int] = None) -> Dict:
        """Submit payloads to Qiskit Serverless provider."""
        payload_files = sorted(self.payload_dir.glob("payload_*.json"))
        if max_jobs:
            payload_files = payload_files[:max_jobs]

        print(f"\nSubmitting {len(payload_files)} jobs to Qiskit Serverless...")
        print("(Not yet implemented - requires provider credentials)")
        return {"status": "not_yet_implemented", "jobs": len(payload_files)}

    def save_results(self, results: Dict, name: str = "batch_results") -> str:
        """Save batch results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.results_dir / f"{name}_{timestamp}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        return str(output_file)

    def print_results(self, results: Dict) -> None:
        """Print batch execution summary."""
        print(f"\n{'='*70}")
        print(f"BATCH EXECUTION RESULTS")
        print(f"{'='*70}")
        print(f"Submitted: {results['submitted']}")
        print(f"Completed: {results['completed']}")
        print(f"Failed:    {results['failed']}")
        print(f"Success:   {100*results['completed']/max(1,results['submitted']):.1f}%")
        print(f"\nStart: {results.get('start_time', 'N/A')}")
        print(f"End:   {results.get('end_time', 'N/A')}")
        print()

# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate and submit serverless batch jobs"
    )
    parser.add_argument(
        "--mode",
        default="all",
        help="Modes: all, efaas, sbq, pq, pf, sr (default: all)",
    )
    parser.add_argument(
        "--circuits",
        default="all",
        help="Circuit types: all, simple, medium, complex (default: all)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=1,
        help="Number of random seeds per job (default: 1)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Limit total jobs (default: unlimited)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally instead of submitting to provider",
    )
    parser.add_argument(
        "--output",
        default="batch_run",
        help="Output subdirectory name (default: batch_run)",
    )

    args = parser.parse_args()

    # Resolve mode and circuit selection
    modes = (
        DEFAULT_MODES
        if args.mode.lower() == "all"
        else [m.upper() for m in args.mode.split(",")]
    )
    circuits = (
        DEFAULT_CIRCUITS
        if args.circuits.lower() == "all"
        else args.circuits.lower().split(",")
    )

    # Generate batch
    print("\n" + "="*70)
    print("GENERATING BATCH JOBS")
    print("="*70)
    gen = BatchJobGenerator(output_dir=f"batch_payloads/{args.output}")
    gen.create_batch(modes=modes, circuits=circuits, seeds=args.seeds, max_jobs=args.max_jobs)
    gen.save_payloads()
    gen.print_summary()

    # Submit/run batch
    print("\n" + "="*70)
    print("EXECUTING BATCH JOBS (LOCAL)")
    print("="*70)
    submitter = BatchJobSubmitter(payload_dir=f"batch_payloads/{args.output}")
    results = submitter.run_locally(max_jobs=args.max_jobs)
    submitter.print_results(results)

    # Save results
    results_file = submitter.save_results(results, name=args.output)
    print(f"Results saved to: {results_file}\n")


if __name__ == "__main__":
    main()
