"""
tracker.py — Experiment Metrics Tracker (Extended: JSON output)
================================================================
Tracks all four metrics from Section V of the paper:
  1. TTNS (per-iteration latency array)
  2. End-to-end convergence time
  3. Quantum Duty Cycle (QDC)
  4. Hardware drift penalty (count + variance spike detection)

Now includes to_json() for full metric export.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

from tabulate import tabulate
import config


# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShotRecord:
    """One VQE iteration data point."""
    iteration:     int
    sim_time:      float
    ttns:          float
    energy:        float
    variance:      float
    drift_penalty: bool
    qpu_id:        int


# ─────────────────────────────────────────────────────────────────────────────

class MetricsTracker:

    def __init__(self, mode: str, n_qpus: int) -> None:
        self.mode    = mode
        self.n_qpus  = n_qpus
        self.shots:  List[ShotRecord] = []
        self.qpu_active_time: Dict[int, float] = {}
        self.convergence_time:      Optional[float] = None
        self.convergence_iteration: Optional[int]   = None
        self.bg_jobs_submitted  = 0
        self.bg_jobs_completed  = 0

    # ── Record helpers ────────────────────────────────────────────────────────

    def record_shot(
        self, iteration: int, sim_time: float, ttns: float,
        energy: float, variance: float, drift_penalty: bool, qpu_id: int,
    ) -> None:
        self.shots.append(ShotRecord(
            iteration=iteration, sim_time=sim_time, ttns=ttns,
            energy=energy, variance=variance,
            drift_penalty=drift_penalty, qpu_id=qpu_id,
        ))

    def record_qpu_active(self, qpu_id: int, duration: float) -> None:
        self.qpu_active_time[qpu_id] = self.qpu_active_time.get(qpu_id, 0.0) + duration

    def record_convergence(self, sim_time: float, iteration: int) -> None:
        if self.convergence_time is None:
            self.convergence_time      = sim_time
            self.convergence_iteration = iteration

    # ── Derived metrics ───────────────────────────────────────────────────────

    def ttns_list(self) -> List[float]:
        return [s.ttns for s in self.shots]

    def energy_list(self) -> List[float]:
        return [s.energy for s in self.shots]

    def variance_list(self) -> List[float]:
        return [s.variance for s in self.shots]

    def mean_ttns(self) -> float:
        lst = self.ttns_list()
        return sum(lst) / len(lst) if lst else 0.0

    def std_ttns(self) -> float:
        lst = self.ttns_list()
        if len(lst) < 2:
            return 0.0
        mu = self.mean_ttns()
        return math.sqrt(sum((x - mu) ** 2 for x in lst) / (len(lst) - 1))

    def qdc(self, total_sim_time: float) -> float:
        if total_sim_time <= 0.0:
            return 0.0
        return sum(self.qpu_active_time.values()) / (self.n_qpus * total_sim_time)

    def drift_penalty_count(self) -> int:
        return sum(1 for s in self.shots if s.drift_penalty)

    def mean_energy(self) -> float:
        lst = self.energy_list()
        return sum(lst) / len(lst) if lst else float("nan")

    def mean_variance(self) -> float:
        lst = self.variance_list()
        return sum(lst) / len(lst) if lst else float("nan")

    # ── Summary dict ─────────────────────────────────────────────────────────

    def summary(self, total_sim_time: float) -> Dict:
        return {
            "mode":                 self.mode,
            "label":                config.MODE_LABELS.get(self.mode, self.mode),
            "iterations_completed": len(self.shots),
            "mean_ttns_s":          round(self.mean_ttns(), 4),
            "std_ttns_s":           round(self.std_ttns(), 4),
            "ttns_list":            [round(v, 4) for v in self.ttns_list()],
            "energy_list":          [round(v, 6) for v in self.energy_list()],
            "variance_list":        [round(v, 6) for v in self.variance_list()],
            "sim_times":            [round(s.sim_time, 3) for s in self.shots],
            "qdc_pct":              round(self.qdc(total_sim_time) * 100, 3),
            "convergence_time_s":   self.convergence_time,
            "convergence_iter":     self.convergence_iteration,
            "drift_penalties":      self.drift_penalty_count(),
            "mean_energy_ha":       round(self.mean_energy(), 6),
            "mean_variance":        round(self.mean_variance(), 6),
            "bg_jobs_completed":    self.bg_jobs_completed,
            "total_sim_time_s":     round(total_sim_time, 2),
        }

    # ── JSON export ───────────────────────────────────────────────────────────

    def to_json(self, filepath: str, total_sim_time: float) -> None:
        """
        Save the full summary + per-shot records to a JSON file.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            "summary":    self.summary(total_sim_time),
            "shot_records": [asdict(s) for s in self.shots],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  [tracker] Saved metrics → {filepath}")

    # ── Pretty comparison table ───────────────────────────────────────────────

    @staticmethod
    def print_comparison(summaries: List[Dict]) -> None:
        metrics = [
            ("Iterations Completed",  "iterations_completed",  ""),
            ("Mean TTNS",             "mean_ttns_s",           "s"),
            ("Std TTNS",              "std_ttns_s",            "s"),
            ("Quantum Duty Cycle",    "qdc_pct",               "%"),
            ("Convergence Time",      "convergence_time_s",    "s"),
            ("Convergence Iteration", "convergence_iter",      ""),
            ("Drift Penalty Events",  "drift_penalties",       ""),
            ("Mean Energy ⟨H⟩",      "mean_energy_ha",        "Hₐ"),
            ("Mean Energy Variance",  "mean_variance",         ""),
            ("BG Jobs Completed",     "bg_jobs_completed",     ""),
        ]

        headers = ["Metric"] + [s.get("label", s.get("mode", "?")) for s in summaries]
        rows    = []
        for label, key, unit in metrics:
            row = [label]
            for s in summaries:
                v = s.get(key)
                row.append(f"{v} {unit}".strip() if v is not None else "N/A")
            rows.append(row)

        print("\n" + "=" * 90)
        print("  ENTANGLED-FaaS: COMPARATIVE RESULTS — ALL ARCHITECTURES")
        print("=" * 90)
        print(tabulate(rows, headers=headers, tablefmt="github"))
        print("=" * 90 + "\n")
